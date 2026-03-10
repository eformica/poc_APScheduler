# POC APScheduler — Agendador de Tarefas

Prova de conceito do [APScheduler 3.x](https://apscheduler.readthedocs.io/) em dois níveis:

- **`examples/`** — exemplos didáticos e interativos dos triggers e APIs do APScheduler
- **`framework/`** — implementação production-ready com Docker, PostgreSQL, tarefas in-process e tarefas containerizadas

---

## Estrutura do projeto

```
poc_APScheduler/
│
├── main.py                            # Menu interativo (ponto de entrada dos exemplos)
├── pyproject.toml
│
├── examples/                          # Exemplos didáticos autocontidos
│   ├── interval_trigger.py            # 1 — IntervalTrigger
│   ├── cron_trigger.py                # 2 — CronTrigger
│   ├── date_trigger.py                # 3 — DateTrigger (execução única)
│   ├── job_management.py              # 4 — Gerenciamento dinâmico de jobs
│   ├── real_world_cases.py            # 5 — Casos reais: 5 domínios, 19 jobs
│   └── persistent_jobs.py             # 6 — Persistência SQLite + event listeners
│
└── framework/                         # Framework production-ready
    ├── Dockerfile
    ├── docker-compose.yml
    ├── requirements.txt
    ├── .env / .env.example
    │
    ├── scheduler/                     # Núcleo do agendador
    │   ├── app.py                     # Entrypoint: boot, retry DB, uvicorn
    │   ├── config.py                  # Settings via pydantic-settings + .env
    │   ├── engine.py                  # Fábrica do BackgroundScheduler
    │   └── registry.py                # TASK_CATALOG + registro central de todos os jobs
    │
    ├── api/                           # API REST (FastAPI + JWT)
    │   ├── main.py                    # App FastAPI com lifespan
    │   ├── auth.py                    # JWT: hash, create_token, decode
    │   ├── dependencies.py            # get_db, get_scheduler, get_current_user
    │   ├── schemas/                   # Pydantic models (auth, jobs, users)
    │   └── routers/                   # Endpoints: /auth, /jobs, /users
    │
    ├── db/                            # Camada de dados
    │   ├── models.py                  # ORM: JobExecutionLog, ContainerTaskLog, User
    │   ├── session.py                 # Engine + SessionLocal (thread-safe)
    │   └── init.sql                   # Esquema, índices e views analíticas
    │
    ├── listeners/
    │   └── execution_logger.py        # make_logged_callable() + misfire + executed listener
    │
    ├── container_runner/              # Módulo de tasks containerizadas
    │   ├── channel.py                 # TaskChannel — usado DENTRO do container
    │   ├── runner.py                  # ContainerRunner — usado pelo orquestrador
    │   └── config.py                  # ContainerJobConfig + make_container_callable
    │
    └── tasks/                         # Implementações de tarefas
        ├── base.py                    # BaseTask (ABC com logger pré-configurado)
        ├── ecommerce.py               # EcommerceTask
        ├── analytics.py               # AnalyticsTask
        ├── devops.py                  # DevOpsTask
        └── containerized_example.py   # Exemplo de task containerizada
```

---

## Exemplos didáticos (`examples/`)

### Instalação

```bash
uv sync
```

### Execução

```bash
uv run python main.py
```

### Exemplos disponíveis

| # | Trigger / Tópico | O que demonstra |
|---|---|---|
| 1 | `IntervalTrigger` | Repetição a cada N seg/min/h; `jitter`, `start_date`, `end_date`, `max_instances` |
| 2 | `CronTrigger` | Horários fixos com expressão cron; `day_of_week`, `hour`, `minute` |
| 3 | `DateTrigger` | Execução única em datetime exato; notificações, publicações, manutenções |
| 4 | Gerenciamento | `pause_job`, `resume_job`, `reschedule_job`, `modify_job`, `remove_job` |
| 5 | Casos reais | E-commerce, Analytics/ETL, DevOps, Financeiro, Conteúdo |
| 6 | Persistência | `SQLAlchemyJobStore` + SQLite, restart recovery, event listeners |

---

## Framework production-ready (`framework/`)

> Ver [framework/README.md](framework/README.md) para documentação completa.

### Início rápido

```bash
cd framework
cp .env.example .env       # ajuste credenciais se necessário
docker-compose up --build
```

### API REST

O framework expõe uma API REST na porta `8000` com autenticação JWT. Ver [framework/README.md](framework/README.md#api-rest) para referência completa.

```bash
curl -s -X POST http://localhost:8000/auth/login \
  -d 'username=admin&password=admin123' | jq .access_token
```

### Dois tipos de jobs

| Tipo | Onde roda | Persistência | Quando usar |
|---|---|---|---|
| **In-process** (`JobConfig`) | Thread pool do scheduler | `job_execution_logs` | Tarefas leves, rápidas, sem dependências extras |
| **Containerizado** (`ContainerJobConfig`) | Container Docker isolado | `job_execution_logs` + `container_task_logs` | Tarefas pesadas, dependências próprias, isolamento total |

> **Parâmetros disponíveis em ambos os tipos:**
> - `trigger=None` → job sem agendamento automático; dispara somente via `POST /jobs/{id}/run`
> - `in_catalog=False` → job oculto no `GET /jobs/catalog` (registrado, mas não listado)
> - `job_kwargs={...}` → parâmetros passados à função em cada execução (in-process: `**kwargs`; container: `JOB_KWARGS` env var JSON)

---

## Referência rápida de APScheduler

### Triggers

| Trigger | Uso | Exemplo |
|---|---|---|
| `IntervalTrigger` | Repetir a cada N unidades | `IntervalTrigger(minutes=30, jitter=60)` |
| `CronTrigger` | Horário fixo estilo cron | `CronTrigger(day_of_week='mon-fri', hour=8)` |
| `DateTrigger` | Execução única | `DateTrigger(run_date=datetime(2026, 12, 31, 23, 59))` |

### `add_job` — parâmetros essenciais

```python
scheduler.add_job(
    func,
    trigger=IntervalTrigger(seconds=30, jitter=5),
    id="meu_job",
    name="Descrição do Job",
    max_instances=1,         # evita execuções sobrepostas
    misfire_grace_time=30,   # tolera até 30 s de atraso
    coalesce=True,           # se atrasou, executa só uma vez
    replace_existing=True,   # substitui se o ID já existir
)
```

### Gerenciamento dinâmico

```python
scheduler.pause_job("meu_job")
scheduler.resume_job("meu_job")
scheduler.reschedule_job("meu_job", trigger=IntervalTrigger(minutes=1))
scheduler.modify_job("meu_job", kwargs={"param": "novo_valor"})
scheduler.remove_job("meu_job")
scheduler.remove_all_jobs()
```

### Event Listeners

```python
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED

def meu_listener(event):
    if event.exception:
        print(f"Job {event.job_id} falhou: {event.exception}")
    else:
        print(f"Job {event.job_id} concluído")

scheduler.add_listener(meu_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED)
```

### Schedulers

| Classe | Comportamento | Uso típico |
|---|---|---|
| `BackgroundScheduler` | Thread separada, não bloqueia | Aplicações web, scripts com outras tarefas |
| `BlockingScheduler` | Bloqueia a thread principal | Container/processo dedicado ao agendador |

### Job Stores

| Store | Persistência | Uso |
|---|---|---|
| `MemoryJobStore` | ✗ Perde no restart | Desenvolvimento, testes |
| `SQLAlchemyJobStore` | ✔ SQLite / PostgreSQL / MySQL | Produção |
| `MongoDBJobStore` | ✔ MongoDB | Ambientes com Mongo |
| `RedisJobStore` | ✔ Redis | Alta performance |

### Executors

| Executor | Ideal para |
|---|---|
| `ThreadPoolExecutor` | Tarefas I/O-bound (HTTP, DB, arquivos) |
| `ProcessPoolExecutor` | Tarefas CPU-intensive (compressão, ML, criptografia) |
| `AsyncIOExecutor` | Coroutines `async def` |
