# POC APScheduler — Agendador de Tarefas

Prova de conceito do [APScheduler 3.x](https://apscheduler.readthedocs.io/) com exemplos práticos e comentados de múltiplos casos de uso.

## Estrutura do projeto

```
poc_APScheduler/
├── main.py                      # Menu interativo (ponto de entrada)
├── pyproject.toml
├── examples/
│   ├── interval_trigger.py      # Exemplo 1 — Intervalos regulares
│   ├── cron_trigger.py          # Exemplo 2 — Horários fixos (cron)
│   ├── date_trigger.py          # Exemplo 3 — Execução única
│   ├── job_management.py        # Exemplo 4 — Gerenciar jobs dinamicamente
│   ├── real_world_cases.py      # Exemplo 5 — Casos reais (5 domínios)
│   └── persistent_jobs.py       # Exemplo 6 — Persistência SQLite
```

## Instalação

```bash
uv sync
# ou
pip install apscheduler sqlalchemy
```

## Execução

```bash
uv run python main.py
# ou
python main.py
```

## Exemplos disponíveis

| # | Trigger / Tópico | O que demonstra |
|---|---|---|
| 1 | `IntervalTrigger` | Repetição a cada N seg/min/h; `jitter`, `start_date`, `end_date`, `max_instances` |
| 2 | `CronTrigger` | Horários fixos com expressão cron; `day_of_week`, `hour`, `minute` |
| 3 | `DateTrigger` | Execução única em datetime exato; notificações, publicações, manutenções |
| 4 | Gerenciamento | `pause_job`, `resume_job`, `reschedule_job`, `modify_job`, `remove_job` |
| 5 | Casos reais | E-commerce, Analytics/ETL, DevOps, Financeiro, Conteúdo |
| 6 | Persistência | `SQLAlchemyJobStore` + SQLite, restart recovery, event listeners |

## Conceitos cobertos

### Triggers

| Trigger | Uso | Exemplo |
|---|---|---|
| `IntervalTrigger` | Repetir a cada N unidades de tempo | Monitor de API a cada 30 s |
| `CronTrigger` | Horário fixo estilo cron Unix | Backup toda meia-noite |
| `DateTrigger` | Uma única execução em datetime específico | Publicação agendada |

### Schedulers

- **`BackgroundScheduler`** — roda em thread separada, não bloqueia o processo principal
- **`BlockingScheduler`** — bloqueia o processo (ideal para scripts dedicados ao agendador)

### Job Stores

- **`MemoryJobStore`** — padrão, não persiste (perde tudo no restart)
- **`SQLAlchemyJobStore`** — persiste em SQLite / PostgreSQL / MySQL / Oracle

### Executors

- **`ThreadPoolExecutor`** — tarefas I/O-bound (chamadas HTTP, banco de dados, arquivos)
- **`ProcessPoolExecutor`** — tarefas CPU-intensive (processamento, compressão, criptografia)

### Parâmetros úteis

```python
scheduler.add_job(
    func,
    trigger=IntervalTrigger(seconds=30, jitter=5),
    id="meu_job",
    name="Descrição do Job",
    max_instances=1,        # evita execuções sobrepostas
    misfire_grace_time=10,  # tolera até 10 s de atraso
    coalesce=True,          # se atrasou, executa só uma vez (não todas)
    replace_existing=True,  # substitui job se o mesmo ID já existir
)
```

### Gerenciamento dinâmico

```python
scheduler.pause_job("meu_job")              # pausa (não perde schedule)
scheduler.resume_job("meu_job")             # retoma
scheduler.reschedule_job("meu_job", trigger=IntervalTrigger(minutes=1))
scheduler.modify_job("meu_job", kwargs={"param": "novo_valor"})
scheduler.remove_job("meu_job")
scheduler.remove_all_jobs()
```

### Event Listeners

```python
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

def meu_listener(event):
    if event.exception:
        print(f"Job {event.job_id} falhou: {event.exception}")
    else:
        print(f"Job {event.job_id} concluído")

scheduler.add_listener(meu_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
```
