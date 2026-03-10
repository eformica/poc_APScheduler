# Framework APScheduler — Documentação Técnica

Framework production-ready para agendamento de tarefas com Docker, PostgreSQL, suporte a jobs in-process e jobs em containers Docker isolados.

---

## Início rápido

```bash
cp .env.example .env        # opcional — o .env padrão já funciona para dev
docker-compose up --build
```

O scheduler inicia automaticamente após o PostgreSQL estar saudável.

---

## Estrutura de diretórios

```
framework/
│
├── Dockerfile                   # Imagem do scheduler (python:3.13-slim + docker.io CLI)
├── docker-compose.yml           # Postgres 16 + Scheduler (porta 8000 exposta)
├── requirements.txt             # apscheduler, sqlalchemy, fastapi, uvicorn, jose, passlib...
├── .env                         # Variáveis de ambiente (não commitar)
├── .env.example                 # Template de variáveis
│
├── api/                         # API REST (FastAPI)
│   ├── main.py                  # App FastAPI com lifespan (inicia/encerra scheduler)
│   ├── auth.py                  # JWT: hash_password, create_access_token, decode_token
│   ├── dependencies.py          # get_db, get_scheduler, get_current_user, require_admin...
│   ├── schemas/
│   │   ├── auth.py              # TokenResponse, RefreshRequest, AccessTokenResponse
│   │   ├── jobs.py              # TriggerConfig, JobCreate, JobReschedule, JobResponse
│   │   └── users.py             # UserCreate, UserUpdate, UserResponse
│   └── routers/
│       ├── auth.py              # POST /auth/login, POST /auth/refresh
│       ├── jobs.py              # CRUD /jobs + /run, /pause, /resume
│       └── users.py             # CRUD /users + /users/me
│
├── scheduler/                   # Núcleo do agendador
│   ├── app.py                   # wait_for_db, ensure_tables, _create_admin_user, main (uvicorn)
│   ├── config.py                # Settings (pydantic-settings) + leitura de .env
│   ├── engine.py                # Fábrica do BackgroundScheduler com SQLAlchemyJobStore
│   └── registry.py              # TASK_CATALOG + registro central de jobs
│
├── db/
│   ├── models.py                # ORM: JobExecutionLog, ContainerTaskLog, User
│   ├── session.py               # engine + SessionLocal (thread-safe, pool_pre_ping)
│   └── init.sql                 # DDL manual com índices e views analíticas
│
├── listeners/
│   └── execution_logger.py      # Wrapper de log + listener de misfire
│
├── container_runner/
│   ├── channel.py               # TaskChannel — API de comunicação DENTRO do container
│   ├── runner.py                # ContainerRunner — lança e monitora containers
│   └── config.py                # ContainerJobConfig + make_container_callable
│
└── tasks/
    ├── base.py                  # BaseTask (ABC com logger pré-configurado)
    ├── ecommerce.py             # EcommerceTask (pedidos, estoque, relatório)
    ├── analytics.py             # AnalyticsTask (ETL, dashboard, relatório executivo)
    ├── devops.py                # DevOpsTask (health check, limpeza, SSL)
    └── containerized_example.py # Entrypoint de exemplo para task containerizada
```

---

## Variáveis de ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `POSTGRES_HOST` | `postgres` | Host do PostgreSQL |
| `POSTGRES_PORT` | `5432` | Porta do PostgreSQL |
| `POSTGRES_DB` | `scheduler_db` | Nome do banco |
| `POSTGRES_USER` | `scheduler` | Usuário do banco |
| `POSTGRES_PASSWORD` | `scheduler_pass` | Senha do banco |
| `SCHEDULER_TIMEZONE` | `America/Sao_Paulo` | Fuso horário dos triggers |
| `SCHEDULER_THREAD_POOL_SIZE` | `10` | Workers do ThreadPoolExecutor |
| `LOG_LEVEL` | `INFO` | Nível de log (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `JWT_SECRET_KEY` | *(veja .env.example)* | Chave para assinar JWTs — **alterar em produção** |
| `ADMIN_DEFAULT_PASSWORD` | `admin123` | Senha do admin criado no primeiro start |

---

## Arquitetura

```
┌──────────────────────────────────────────────────────┐
│                  scheduler/app.py                    │
│  boot → wait_for_db → ensure_tables → start          │
└────────────────────────┬─────────────────────────────┘
                         │
            ┌────────────▼─────────────┐
            │   scheduler/engine.py    │
            │  BackgroundScheduler     │
            │  SQLAlchemyJobStore (PG) │
            │  ThreadPoolExecutor      │
            └────────────┬─────────────┘
                         │
            ┌────────────▼─────────────┐
            │   scheduler/registry.py  │
            │  ┌───────────────────┐   │
            │  │  JobConfig        │──►│──► make_logged_callable()
            │  │  (in-process)     │   │    └─► tasks/*.py (threads)
            │  └───────────────────┘   │
            │  ┌───────────────────┐   │
            │  │ ContainerJobConfig│──►│──► make_container_callable()
            │  │  (containerizado) │   │    └─► ContainerRunner.run()
            │  └───────────────────┘   │         └─► docker run <image>
            └──────────────────────────┘               │
                                                        │ stdout (JSON Lines)
                                              ┌─────────▼──────────┐
                                              │   TaskChannel       │
                                              │  (dentro do         │
                                              │   container)        │
                                              └─────────────────────┘

     Persistência:
     ┌───────────────────────────────┐
     │         PostgreSQL            │
     │  apscheduler_jobs             │  ← estado dos triggers
     │  job_execution_logs           │  ← sucesso/erro/missed (todos os jobs)
     │  container_task_logs          │  ← linhas JSON do stdout dos containers
     │  users                        │  ← usuários da API REST (criados pelo ORM)
     └───────────────────────────────┘
```

---

## API REST

A API sobe junto com o scheduler no mesmo processo uvicorn. Porta `8000`.

### Autenticação

```http
# 1. Login (form data)
POST /auth/login
Content-Type: application/x-www-form-urlencoded

username=admin&password=admin123

# Resposta:
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}

# 2. Usar o token
GET /jobs
Authorization: Bearer eyJ...

# 3. Renovar access_token (sem novo login)
POST /auth/refresh
{"refresh_token": "eyJ..."}
```

### Endpoints de jobs

| Método | Endpoint | Permissão | Descrição |
|---|---|---|---|
| `GET` | `/jobs/catalog` | viewer+ | Lista funções disponíveis para agendar |
| `GET` | `/jobs` | viewer+ | Lista todos os jobs agendados |
| `GET` | `/jobs/{id}` | viewer+ | Detalhes de um job |
| `POST` | `/jobs` | operator+ | Cria novo agendamento |
| `PATCH` | `/jobs/{id}/reschedule` | operator+ | Altera o trigger de um job |
| `POST` | `/jobs/{id}/pause` | operator+ | Pausa um job |
| `POST` | `/jobs/{id}/resume` | operator+ | Retoma um job pausado |
| `POST` | `/jobs/{id}/run` | operator+ | Executa imediatamente |
| `DELETE` | `/jobs/{id}` | admin | Remove permanentemente |

#### Resposta de `GET /jobs/catalog`

```json
[
  {
    "key": "ecom_processar_pedidos",
    "name": "E-commerce: Processar Pedidos Pendentes",
    "module": "tasks.ecommerce",
    "api_only": false
  },
  {
    "key": "ecom_reprocessar_pedido",
    "name": "E-commerce: Reprocessar Pedido Específico",
    "module": "tasks.ecommerce",
    "api_only": true
  }
]
```

`api_only: true` indica que o job não possui trigger automático — só pode ser acionado via `POST /jobs/{id}/run`.

#### Criar um novo agendamento

```http
POST /jobs
Authorization: Bearer eyJ...
Content-Type: application/json

{
  "func_key": "ecom_processar_pedidos",
  "trigger": {
    "type": "interval",
    "minutes": 30,
    "jitter": 60
  },
  "id": "processar_pedidos_extra",
  "name": "Processar Pedidos (intervalo extra)",
  "max_instances": 1,
  "coalesce": true,
  "job_kwargs": {
    "loja_id": "BR-SP-01",
    "limite": 200
  }
}
```

#### Criar um job API-only (sem agendamento automático)

```http
POST /jobs
Authorization: Bearer eyJ...
Content-Type: application/json

{
  "func_key": "ecom_processar_pedidos",
  "trigger": null,
  "id": "processar_pedido_spot",
  "name": "Processar Pedido Spot (disparo manual)",
  "job_kwargs": {
    "order_id": 98765,
    "retry": true
  }
}
```

Com `trigger: null`, o job é registrado com `next_run_time: null`. Ele aparece em `GET /jobs` mas nunca dispara sozinho. Após cada `POST /jobs/{id}/run`, o listener `EVENT_JOB_EXECUTED` re-pausa o job automaticamente.

#### Reagendar com CronTrigger

```http
PATCH /jobs/ecom_processar_pedidos/reschedule
Authorization: Bearer eyJ...
Content-Type: application/json

{
  "trigger": {
    "type": "cron",
    "hour": "6",
    "minute": "0",
    "day_of_week": "mon-fri"
  }
}
```

#### Executar manualmente

```http
POST /jobs/ecom_processar_pedidos/run
Authorization: Bearer eyJ...

# Resposta 202 Accepted:
{"detail": "Job 'ecom_processar_pedidos' agendado para execução imediata"}
```

### Endpoints de usuários

| Método | Endpoint | Permissão | Descrição |
|---|---|---|---|
| `GET` | `/users/me` | viewer+ | Perfil próprio |
| `GET` | `/users` | admin | Lista todos |
| `POST` | `/users` | admin | Cria usuário |
| `PUT` | `/users/{id}` | admin / próprio | Atualiza usuário |
| `DELETE` | `/users/{id}` | admin | Remove usuário |

#### Criar usuário (admin)

```http
POST /users
Authorization: Bearer eyJ...
Content-Type: application/json

{
  "username": "operador1",
  "email": "operador1@empresa.com",
  "password": "senha-segura",
  "role": "operator"
}
```

### Roles e permissões

| Role | Jobs (leitura) | Jobs (escrita) | Jobs (deletar) | Usuários |
|---|---|---|---|---|
| `viewer` | ✔ | ✗ | ✗ | Próprio perfil |
| `operator` | ✔ | ✔ | ✗ | Própria senha/email |
| `admin` | ✔ | ✔ | ✔ | Acesso total |

### Swagger UI

Acesse `http://localhost:8000/docs` após `docker-compose up --build`.
Use **Authorize** no canto superior direito para inserir o `access_token`.

---

## Jobs API-only (`trigger=None`) e catálogo (`in_catalog`)

### `trigger=None` — sem agendamento automático

Qualquer `JobConfig` ou `ContainerJobConfig` pode ser registrado sem trigger automático:

```python
# scheduler/registry.py — em _build_job_list()
JobConfig(
    id="ecom_reprocessar_pedido",
    name="E-commerce: Reprocessar Pedido Específico",
    func=_ecom.processar_pedidos,
    trigger=None,       # ← sem disparo automático
    in_catalog=True,    # aparece em GET /jobs/catalog com api_only=true
)
```

**Ciclo de vida em runtime:**

| Etapa | O que acontece |
|---|---|
| Startup | Registrado com `next_run_time=null` (paused) |
| `GET /jobs/{id}` | `next_run_time: null` — nunca dispara sozinho |
| `POST /jobs/{id}/run` | `next_run_time → now()` — execução imediata |
| Pós-execução | Listener `EVENT_JOB_EXECUTED` detecta o ID em `API_ONLY_JOB_IDS` e chama `pause_job()` — `next_run_time` volta a `null` |

### `in_catalog=False` — ocultar do catálogo

Por padrão todos os jobs aparecem em `GET /jobs/catalog`. Para omitir um job:

```python
JobConfig(
    id="limpeza_interna",
    name="Limpeza Interna de Cache",
    func=_devops.limpar_temporarios,
    trigger=IntervalTrigger(hours=1),
    in_catalog=False,   # ← oculto em GET /jobs/catalog
)
```

### `TASK_CATALOG` gerado automaticamente

Os três dicionários exportados por `registry.py` são derivados diretamente das listas `_JOBS` / `_CONTAINER_JOBS`:

```python
# Gerado uma única vez no import — sem manutenção manual:
TASK_CATALOG     = {jc.id: jc.func          for jc in _JOBS if jc.in_catalog} | {...containers}
CATALOG_METADATA = {jc.id: {"name": jc.name, "api_only": jc.trigger is None} ...}
API_ONLY_JOB_IDS = {jc.id                   for jc in _JOBS if jc.trigger is None} | {...containers}
```

`API_ONLY_JOB_IDS` também é atualizado em runtime quando novos jobs API-only são criados via `POST /jobs`.

---

## Parâmetros dinâmicos por job (`job_kwargs`)

`job_kwargs` é um dicionário de parâmetros passados à função do job em **cada execução**. Funciona de forma idêntica para jobs in-process e containerizados.

### Jobs in-process

Os parâmetros são repassados como `**kwargs` à função:

```python
# Em registry.py — definição estática:
JobConfig(
    id="ecom_processar_pedidos",
    func=_ecom.processar_pedidos,
    trigger=IntervalTrigger(minutes=5),
    job_kwargs={"loja_id": "BR-SP-01", "limite": 100},
)

# A função precisa aceitar os parâmetros:
class EcommerceTask(BaseTask):
    def processar_pedidos(self, loja_id: str = "default", limite: int = 50) -> None:
        self.logger.info(f"Processando pedidos da loja {loja_id} (limite: {limite})")
        ...
```

### Jobs containerizados

Os parâmetros são serializados como JSON e injetados na variável de ambiente `JOB_KWARGS`. Leia dentro do container com `ch.kwargs`:

```python
# Em registry.py — definição estática:
ContainerJobConfig(
    id="etl_pipeline",
    image="myorg/etl:latest",
    trigger=IntervalTrigger(hours=1),
    job_kwargs={"batch_size": 500, "source": "orders_db"},
)

# main.py DENTRO do container:
from container_runner.channel import TaskChannel

ch = TaskChannel.from_env()
params = ch.kwargs                        # {"batch_size": 500, "source": "orders_db"}
batch  = params.get("batch_size", 100)
source = params.get("source", "default")

ch.info("Iniciando ETL", batch_size=batch, source=source)
```

### Via API — `POST /jobs`

O campo `job_kwargs` pode ser passado no body ao criar um job:

```http
POST /jobs
Authorization: Bearer eyJ...

{
  "func_key": "ecom_processar_pedidos",
  "trigger": {"type": "interval", "hours": 1},
  "job_kwargs": {"loja_id": "BR-RJ-02", "limite": 300}
}
```

Os kwargs são **persistidos no job store** (PostgreSQL) junto com o trigger, portanto sobrevivem a restarts do container.

### Precedência de kwargs em jobs containerizados

Quando um `ContainerJobConfig` define `job_kwargs` estaticamente **e** a API cria uma instância com `job_kwargs` dinâmicos, os kwargs do APScheduler têm precedência:

```python
# Resultado final passado ao container:
# merged = {**cfg.job_kwargs, **kwargs_do_apscheduler}
```

---

## Adicionando um job in-process

### 1. Crie a tarefa em `tasks/`

```python
# tasks/minha_tarefa.py
from tasks.base import BaseTask

class MinhaTarefa(BaseTask):
    def executar(self) -> None:
        self.logger.info("Tarefa executada com sucesso")
        # ... lógica aqui
```

### 2. Registre em `scheduler/registry.py`

```python
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from tasks.minha_tarefa import MinhaTarefa

_task = MinhaTarefa()

def _build_job_list() -> list[JobConfig]:
    return [
        # ... jobs existentes ...

        # Job com agendamento automático (padrão):
        JobConfig(
            id="minha_tarefa_diaria",
            name="Minha Tarefa Diária",
            func=_task.executar,
            trigger=CronTrigger(hour=6, minute=0),
        ),

        # Job com parâmetros dinâmicos (job_kwargs):
        JobConfig(
            id="minha_tarefa_parametrizada",
            name="Minha Tarefa Parametrizada",
            func=_task.executar,
            trigger=IntervalTrigger(hours=1),
            job_kwargs={"modo": "incremental", "limite": 500},
        ),

        # Job exclusivamente via API (trigger=None):
        JobConfig(
            id="minha_tarefa_manual",
            name="Minha Tarefa Manual",
            func=_task.executar,
            trigger=None,          # dispara somente via POST /jobs/{id}/run
            in_catalog=True,       # aparece em GET /jobs/catalog com api_only=true
            job_kwargs={"modo": "completo"},
        ),

        # Job registrado mas oculto do catálogo:
        JobConfig(
            id="minha_tarefa_interna",
            name="Minha Tarefa Interna",
            func=_task.executar,
            trigger=IntervalTrigger(hours=1),
            in_catalog=False,      # não aparece em GET /jobs/catalog
        ),
    ]
```

O `make_logged_callable()` é aplicado automaticamente pelo `register_jobs()` — todo sucesso, erro e misfire é salvo em `job_execution_logs`.

> A função da tarefa deve aceitar os parâmetros declarados em `job_kwargs`:
> ```python
> def executar(self, modo: str = "incremental", limite: int = 100) -> None:
>     self.logger.info(f"Executando modo={modo}, limite={limite}")
> ```

---

## Adicionando um job containerizado

### 1. Crie o Dockerfile da tarefa

```dockerfile
# Imagem da sua tarefa — qualquer linguagem, qualquer dependência
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

### 2. Crie o entrypoint usando `TaskChannel`

```python
# main.py (DENTRO do container da tarefa)
import sys
from container_runner.channel import TaskChannel

def main():
    ch = TaskChannel.from_env()     # lê JOB_ID e JOB_KWARGS do ambiente

    # Lê parâmetros injetados pelo orquestrador via job_kwargs:
    params     = ch.kwargs                        # dict — vazio se não definido
    batch_size = params.get("batch_size", 100)
    source     = params.get("source", "default")

    try:
        ch.info("Iniciando processamento", batch_size=batch_size, source=source)
        resultado = processar(batch_size=batch_size, source=source)
        ch.metric("registros_processados", len(resultado))
        ch.info("Concluído", registros=len(resultado))
        ch.emit_result("success", total=len(resultado))
    except Exception as exc:
        ch.error(f"Falha: {exc}")
        ch.emit_result("error", reason=str(exc))
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### 3. Registre em `scheduler/registry.py`

```python
from apscheduler.triggers.interval import IntervalTrigger
from container_runner.config import ContainerJobConfig

def _build_container_job_list() -> list[ContainerJobConfig]:
    return [
        ContainerJobConfig(
            id="etl_containerizado",
            name="ETL Containerizado",
            image="minha-org/etl-task:latest",
            trigger=IntervalTrigger(hours=1),
            command=None,           # usa o CMD do Dockerfile
            env_vars={"DATABASE_URL": "postgresql://..."},  # variáveis estáticas
            timeout=600,            # segundos
            job_kwargs={            # parâmetros lidos dentro do container via ch.kwargs
                "batch_size": 500,
                "source": "orders_db",
            },
        ),
    ]
```

`make_container_callable()` constrói o callable que o APScheduler invoca. O `ContainerRunner` serializa `job_kwargs` como JSON e injeta na variável de ambiente `JOB_KWARGS` antes de lançar o container. O resultado e os logs são persistidos automaticamente.

> **`env_vars` vs `job_kwargs`**
> - `env_vars` → variáveis de ambiente estáticas (credenciais, URLs, flags de infra)
> - `job_kwargs` → parâmetros de negócio do job, persistidos no job store e acessíveis via `ch.kwargs`

---

## Protocolo de comunicação de containers

Toda comunicação entre o container da tarefa e o orquestrador é feita via **JSON Lines no stdout**.

### `TaskChannel` — API dentro do container

```python
from container_runner.channel import TaskChannel

ch = TaskChannel.from_env()          # ou TaskChannel(job_id="meu_job")

ch.debug("Mensagem de depuração")
ch.info("Operação concluída", registros=100, arquivo="output.csv")
ch.warning("Dado fora do range esperado", valor=999)
ch.error("Falha na conexão", host="db.exemplo.com", tentativas=3)
ch.metric("tempo_processamento_ms", 432.5, modulo="etl")
ch.emit_result("success", total=500, rejeitados=3)   # apenas uma vez
```

### Formato do protocolo (JSON Lines)

```jsonc
// Cada linha emitida no stdout:
{"level": "INFO",    "message": "Operação concluída", "job_id": "etl_01", "ts": "2026-01-15T10:30:00", "registros": 100}
{"level": "METRIC",  "message": "tempo_processamento_ms=432.5", "job_id": "etl_01", "ts": "...", "name": "tempo_processamento_ms", "value": 432.5}
{"level": "RESULT",  "message": "success", "job_id": "etl_01", "ts": "...", "total": 500, "rejeitados": 3}
```

Linhas que não são JSON válido são armazenadas com `level = "RAW"`.

### Níveis disponíveis

| Nível | Método | Salvo em `container_task_logs` | Descrição |
|---|---|---|---|
| `DEBUG` | `ch.debug()` | ✔ | Informações de depuração |
| `INFO` | `ch.info()` | ✔ | Progresso normal |
| `WARNING` | `ch.warning()` | ✔ | Situações inesperadas, não fatais |
| `ERROR` | `ch.error()` | ✔ | Erros recuperáveis ou fatais |
| `METRIC` | `ch.metric()` | ✔ | Métricas numéricas |
| `RESULT` | `ch.emit_result()` | ✔ | Resultado final (emitido uma vez) |
| `RAW` | — | ✔ | Stdout não-JSON (capturado automaticamente) |

---

## Banco de dados

### Tabelas

#### `apscheduler_jobs`
Gerenciada automaticamente pelo APScheduler. Armazena o estado serializado de cada trigger.

#### `job_execution_logs`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | SERIAL PK | — |
| `job_id` | TEXT | ID do job no APScheduler |
| `job_name` | TEXT | Nome descritivo |
| `scheduled_at` | TIMESTAMPTZ | Horário previsto de execução |
| `started_at` | TIMESTAMPTZ | Início efetivo |
| `finished_at` | TIMESTAMPTZ | Término |
| `status` | TEXT | `success`, `error`, `missed` |
| `error_type` | TEXT | Classe da exceção (se houver) |
| `error_message` | TEXT | Mensagem da exceção |
| `traceback` | TEXT | Traceback completo |
| `duration_ms` | FLOAT | Duração em milissegundos |
| `created_at` | TIMESTAMPTZ | Momento do registro no banco |

#### `container_task_logs`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | SERIAL PK | — |
| `job_id` | TEXT | ID do job que lançou o container |
| `job_name` | TEXT | Nome descritivo |
| `level` | TEXT | `INFO`, `WARNING`, `ERROR`, `METRIC`, `RESULT`, `RAW` |
| `message` | TEXT | Mensagem principal |
| `extra` | JSONB | Campos adicionais (indexado via GIN) |
| `emitted_at` | TIMESTAMPTZ | Timestamp emitido pelo container |
| `created_at` | TIMESTAMPTZ | Momento da inserção |

### Views analíticas

| View | Fonte | O que mostra |
|---|---|---|
| `v_last_job_executions` | `job_execution_logs` | Última execução de cada job |
| `v_job_error_summary` | `job_execution_logs` | Contagem de erros por job (últimas 24 h) |
| `v_job_success_rate_24h` | `job_execution_logs` | Taxa de sucesso por job (últimas 24 h) |
| `v_recent_errors` | `job_execution_logs` | Erros recentes ordenados por horário |
| `v_container_executions` | `container_task_logs` | Execuções agrupadas por janela de 1 min |
| `v_container_metrics` | `container_task_logs` | Linhas de métrica (METRIC level) |
| `v_container_recent_errors` | `container_task_logs` | Erros das últimas 1 h |

```sql
-- Exemplos de consultas rápidas
SELECT * FROM v_job_success_rate_24h ORDER BY success_rate;
SELECT * FROM v_recent_errors LIMIT 20;
SELECT * FROM v_container_metrics WHERE job_id = 'etl_containerizado';
```

---

## Docker-outside-of-Docker (DooD)

O scheduler precisa lançar containers de tarefas a partir de dentro de um container. Isso é feito montando o socket do Docker Host:

```yaml
# docker-compose.yml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```

E instalando o CLI do Docker na imagem do scheduler:

```dockerfile
RUN apt-get update && apt-get install -y docker.io && rm -rf /var/lib/apt/lists/*
```

> **Segurança**: O acesso ao socket Docker equivale a acesso root no host. Em produção, prefira **Docker-in-Docker (DinD)** com TLS ou uma solução como [Sysbox](https://github.com/nestybox/sysbox).

---

## Ciclo de vida do scheduler

```
docker-compose up
│
├─ postgres (healthcheck: pg_isready)
│
└─ scheduler (uvicorn api.main:app → porta 8000)
   ├─ wait_for_db()           # tenta SELECT 1 até 15x com intervalo de 3 s
   ├─ ensure_tables()         # cria tabelas ORM se não existirem (incl. users)
   ├─ _create_admin_user()    # cria admin padrão se não houver nenhum admin
   ├─ create_scheduler()      # BackgroundScheduler + SQLAlchemyJobStore
   ├─ register_listeners()    # misfire + executed → job_execution_logs; re-pausa API-only
   ├─ register_jobs()         # carrega JobConfig + ContainerJobConfig (trigger=None → paused)
   └─ scheduler.start()       # thread em background
      │
      └─ uvicorn serve        # ← bloqueia aqui; API disponível em :8000
         │
         ├─ SIGTERM / SIGINT → uvicorn shutdown → scheduler.shutdown(wait=True)
         └─ cada execução → make_logged_callable() → persiste resultado
```

---

## Adicionando um novo domínio de tarefas (passo a passo)

1. **Criar `tasks/meu_dominio.py`** estendendo `BaseTask`
2. **Registrar os jobs** em `_build_job_list()` (in-process) ou `_build_container_job_list()` (container)
   - `trigger=None` → job acionado somente via API
   - `in_catalog=False` → job oculto em `GET /jobs/catalog`
   - `job_kwargs={...}` → parâmetros passados à função (in-process: `**kwargs`; container: `ch.kwargs`)
3. **Reconstruir a imagem**: `docker-compose up --build`
4. **Verificar o catálogo**: `GET /jobs/catalog` já reflete os novos jobs automaticamente
5. **Monitorar** via logs do scheduler ou consultando as views no PostgreSQL

Não é necessário alterar `app.py`, `engine.py`, `listeners/` ou `TASK_CATALOG` manualmente — o framework cuida do resto.
