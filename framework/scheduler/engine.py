"""
Fábrica do BlockingScheduler com PostgreSQL como job store.

Decisões de design:
  - BlockingScheduler: o container Docker É o processo do scheduler,
    por isso bloqueamos a thread principal em vez de usar Background.
  - SQLAlchemyJobStore (PostgreSQL): jobs persistidos sobrevivem a restarts.
  - ThreadPoolExecutor: ideal para tarefas I/O-bound (HTTP, DB, filesystem).
  - coalesce=True: se o scheduler ficou offline e voltou, executa cada job
    atrasado somente UMA vez (não todas as execuções perdidas).
  - misfire_grace_time=60s: janela de tolerância para execuções atrasadas.
"""

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.blocking import BlockingScheduler

from scheduler.config import settings


def create_scheduler() -> BlockingScheduler:
    """Cria e retorna o BlockingScheduler configurado para produção."""

    jobstores = {
        # Todos os jobs persistidos no PostgreSQL.
        # APScheduler gerencia automaticamente a tabela 'apscheduler_jobs'.
        "default": SQLAlchemyJobStore(
            url=settings.database_url,
            tablename="apscheduler_jobs",
        ),
    }

    executors = {
        # ThreadPool para tarefas I/O-bound concorrentes.
        # Aumente SCHEDULER_THREAD_POOL_SIZE para workloads maiores.
        "default": ThreadPoolExecutor(
            max_workers=settings.SCHEDULER_THREAD_POOL_SIZE
        ),
    }

    job_defaults = {
        "coalesce": True,           # não acumula execuções perdidas
        "max_instances": 1,         # evita sobreposição de instâncias
        "misfire_grace_time": 60,   # tolera até 60s de atraso
    }

    return BlockingScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
        timezone=settings.SCHEDULER_TIMEZONE,
    )
