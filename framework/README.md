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
├── docker-compose.yml           # Postgres 16 + Scheduler com socket Docker montado
├── requirements.txt             # apscheduler, sqlalchemy, psycopg2-binary, pydantic-settings
├── .env                         # Variáveis de ambiente (não commitar)
├── .env.example                 # Template de variáveis
│
├── scheduler/
│   ├── app.py                   # Entrypoint: boot, retry DB, handlers SIGTERM/SIGINT
│   ├── config.py                # Settings (pydantic-settings) + leitura de .env
│   ├── engine.py                # Fábrica do BlockingScheduler com SQLAlchemyJobStore
│   └── registry.py              # Registro central de jobs in-process e containerizados
│
├── db/
│   ├── models.py                # ORM: JobExecutionLog e ContainerTaskLog
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
            │  BlockingScheduler       │
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
     └───────────────────────────────┘
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
from tasks.minha_tarefa import MinhaTarefa

_task = MinhaTarefa()

def _build_job_list() -> list[JobConfig]:
    return [
        # ... jobs existentes ...
        JobConfig(
            id="minha_tarefa_diaria",
            name="Minha Tarefa Diária",
            func=_task.executar,
            trigger=CronTrigger(hour=6, minute=0, timezone=settings.SCHEDULER_TIMEZONE),
        ),
    ]
```

O `make_logged_callable()` é aplicado automaticamente pelo `register_jobs()` — todo sucesso, erro e misfire é salvo em `job_execution_logs`.

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
    ch = TaskChannel.from_env()     # lê JOB_ID do ambiente
    try:
        ch.info("Iniciando processamento")
        resultado = processar()
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
            env_vars={"BATCH_SIZE": "1000"},
            timeout=600,            # segundos
        ),
    ]
```

`make_container_callable()` constrói o callable que o APScheduler invoca. O `ContainerRunner` lança o container, lê o stdout linha a linha, persiste os logs e registra o resultado final.

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
└─ scheduler
   ├─ wait_for_db()        # tenta SELECT 1 até 15x com intervalo de 3 s
   ├─ ensure_tables()      # cria tabelas ORM se não existirem
   ├─ create_scheduler()   # BlockingScheduler + SQLAlchemyJobStore
   ├─ register_listeners() # misfire → job_execution_logs
   ├─ register_jobs()      # carrega JobConfig + ContainerJobConfig
   └─ scheduler.start()    # ← bloqueia aqui (BlockingScheduler)
      │
      ├─ SIGTERM / SIGINT → scheduler.shutdown(wait=True)  # graceful
      └─ cada execução → make_logged_callable() → persiste resultado
```

---

## Adicionando um novo domínio de tarefas (passo a passo)

1. **Criar `tasks/meu_dominio.py`** estendendo `BaseTask`
2. **Registrar os jobs** em `_build_job_list()` (in-process) ou `_build_container_job_list()` (container)
3. **Reconstruir a imagem**: `docker-compose up --build`
4. **Monitorar** via logs do scheduler ou consultando as views no PostgreSQL

Não é necessário alterar `app.py`, `engine.py` ou `listeners/` — o framework cuida do rest.
