"""
Exemplo 6: Persistência de Jobs com SQLite + Event Listeners
=============================================================
Jobs armazenados em banco de dados sobrevivem a reinicializações
do processo. Ao subir novamente, o scheduler recupera o estado
dos jobs automaticamente.

Job Stores disponíveis:
  MemoryJobStore       (padrão — não persiste, perde no restart)
  SQLAlchemyJobStore   (SQLite, PostgreSQL, MySQL, Oracle…)
  MongoDBJobStore      (MongoDB)
  RedisJobStore        (Redis)

Executors disponíveis:
  ThreadPoolExecutor   (padrão — ideal para tarefas I/O-bound)
  ProcessPoolExecutor  (tarefas CPU-intensive — requer funções picklable)
  AsyncIOExecutor      (coroutines asyncio)

Configurações globais (job_defaults):
  coalesce             → se atrasou, executa só UMA vez (não todas as perdidas)
  max_instances        → limite de instâncias paralelas
  misfire_grace_time   → janela de tolerância para execuções atrasadas

Event Listeners:
  EVENT_JOB_EXECUTED   → job terminou com sucesso
  EVENT_JOB_ERROR      → job lançou exceção
  EVENT_JOB_MISSED     → job perdeu a janela (misfire)
  EVENT_JOB_ADDED      → novo job adicionado
  EVENT_JOB_REMOVED    → job removido
  EVENT_SCHEDULER_STARTED / SHUTDOWN

Casos de uso:
  ✔ Tarefas críticas que não podem ser perdidas em restart
  ✔ Ambientes com múltiplos workers (shared job store)
  ✔ Auditoria completa de execuções (via listeners)
  ✔ Recuperação automática após falha de processo
"""

import os
import time
import random
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import (
    EVENT_JOB_EXECUTED,
    EVENT_JOB_ERROR,
    EVENT_JOB_MISSED,
    EVENT_JOB_ADDED,
    EVENT_JOB_REMOVED,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Banco de dados SQLite criado na raiz do projeto
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(_BASE_DIR, "apscheduler_jobs.db")
DB_URL = f"sqlite:///{DB_PATH}"

# Estatísticas coletadas pelos event listeners
_stats: dict[str, int] = {"executados": 0, "erros": 0, "perdidos": 0}


# ─── Event Listeners ────────────────────────────────────────────────────────────

def on_job_executed(event) -> None:
    _stats["executados"] += 1
    logger.debug(f"   ✅ '{event.job_id}' OK — total executados: {_stats['executados']}")


def on_job_error(event) -> None:
    _stats["erros"] += 1
    logger.error(
        f"   ❌ '{event.job_id}' FALHOU: {event.exception} "
        f"— total erros: {_stats['erros']}"
    )


def on_job_missed(event) -> None:
    _stats["perdidos"] += 1
    logger.warning(
        f"   ⏭️  '{event.job_id}' perdeu janela de execução "
        f"— total perdidos: {_stats['perdidos']}"
    )


def on_job_added(event) -> None:
    logger.info(f"   ➕ Job adicionado ao store: '{event.job_id}'")


def on_job_removed(event) -> None:
    logger.info(f"   ➖ Job removido do store: '{event.job_id}'")


# ─── Funções de trabalho ────────────────────────────────────────────────────────

def tarefa_critica() -> None:
    """Tarefa que NÃO pode ser perdida — deve sobreviver a restarts."""
    logger.info("🔒 [Crítico] Processamento crítico executado com sucesso")


def tarefa_com_falha_aleatoria() -> None:
    """Demonstra o event listener de erro (30% chance de falha)."""
    if random.random() < 0.30:
        raise RuntimeError("Simulação: falha no processamento de dados")
    logger.info("⚙️  [Processamento] Executado com sucesso")


def backup_incremental() -> None:
    """Backup que deve sobreviver a reinicializações do sistema."""
    tamanho = random.randint(5, 120)
    logger.info(f"💾 [Backup] Backup incremental: {tamanho} MB arquivados")


def sincronizar_cache() -> None:
    """Tarefa I/O-bound executada pelo ThreadPoolExecutor."""
    itens = random.randint(100, 1000)
    logger.info(f"🗄️  [Cache] {itens} entradas sincronizadas (ThreadPool)")


# ─── Fábrica do scheduler ───────────────────────────────────────────────────────

def criar_scheduler() -> BackgroundScheduler:
    """
    Cria um BackgroundScheduler com:
      - SQLite como job store (persistência)
      - ThreadPoolExecutor (10 workers para I/O)
      - Configurações globais de coalesce e grace time
    """
    jobstores = {
        # Todos os jobs vão para o SQLite por padrão
        "default": SQLAlchemyJobStore(url=DB_URL),
    }
    executors = {
        # ThreadPool para tarefas I/O-bound (HTTP, DB, filesystem)
        "default": ThreadPoolExecutor(max_workers=10),
    }
    job_defaults = {
        "coalesce": True,          # se atrasou, roda só uma vez
        "max_instances": 2,        # máximo 2 instâncias simultâneas
        "misfire_grace_time": 30,  # tolera até 30 s de atraso
    }
    return BackgroundScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
    )


def registrar_listeners(scheduler: BackgroundScheduler) -> None:
    scheduler.add_listener(on_job_executed, EVENT_JOB_EXECUTED)
    scheduler.add_listener(on_job_error,    EVENT_JOB_ERROR)
    scheduler.add_listener(on_job_missed,   EVENT_JOB_MISSED)
    scheduler.add_listener(on_job_added,    EVENT_JOB_ADDED)
    scheduler.add_listener(on_job_removed,  EVENT_JOB_REMOVED)


# ─── Execução do exemplo ────────────────────────────────────────────────────────

def run() -> None:
    print("\n" + "═" * 64)
    print("  Exemplo 6: Persistência de Jobs com SQLite")
    print("═" * 64)
    print(f"\n  Banco de dados: {DB_PATH}\n")

    # ── Fase 1: Primeira instância — adiciona jobs ao SQLite ──────────────────
    print("  ── Fase 1: Iniciando scheduler e registrando jobs no SQLite...")

    s1 = criar_scheduler()
    registrar_listeners(s1)
    s1.start()

    # replace_existing=True → evita DuplicateJobError ao rodar mais de uma vez
    s1.add_job(
        tarefa_critica,
        trigger=IntervalTrigger(seconds=4),
        id="tarefa_critica",
        name="Tarefa Crítica",
        replace_existing=True,
    )
    s1.add_job(
        tarefa_com_falha_aleatoria,
        trigger=IntervalTrigger(seconds=3),
        id="tarefa_falha",
        name="Tarefa com Falha Aleatória",
        replace_existing=True,
    )
    s1.add_job(
        backup_incremental,
        trigger=CronTrigger(second="*/6"),
        id="backup",
        name="Backup Incremental",
        replace_existing=True,
    )
    s1.add_job(
        sincronizar_cache,
        trigger=IntervalTrigger(seconds=5),
        id="sync_cache",
        name="Sincronizar Cache",
        replace_existing=True,
    )

    print(f"\n  Jobs persistidos no SQLite ({DB_PATH}):")
    for job in s1.get_jobs():
        print(f"    • [{job.id}] {job.name}")

    print("\n  Executando fase 1 por 14s...")
    time.sleep(14)

    # ── Fase 2: Simulação de restart ─────────────────────────────────────────
    print("\n  ── Fase 2: Simulando restart — encerrando scheduler...")
    s1.shutdown(wait=False)
    time.sleep(1)

    # ── Fase 3: Segunda instância — recupera jobs do SQLite ──────────────────
    print("\n  ── Fase 3: Reiniciando scheduler — jobs recuperados do banco...")

    s2 = criar_scheduler()
    registrar_listeners(s2)
    s2.start()  # APScheduler lê os jobs persistidos automaticamente

    jobs_recuperados = s2.get_jobs()
    print(f"\n  {len(jobs_recuperados)} job(s) recuperados do SQLite após restart:")
    for job in jobs_recuperados:
        prox = job.next_run_time.strftime("%H:%M:%S") if job.next_run_time else "—"
        print(f"    • [{job.id}] {job.name}  (próxima: {prox})")

    print("\n  Executando fase 3 por 12s (jobs continuam de onde pararam)...\n")

    try:
        time.sleep(12)
    except KeyboardInterrupt:
        pass
    finally:
        s2.shutdown(wait=False)

    # ── Sumário ───────────────────────────────────────────────────────────────
    print("\n  ── Sumário de execuções (ambas as fases):")
    print(f"     ✅ Executados com sucesso : {_stats['executados']}")
    print(f"     ❌ Com erro               : {_stats['erros']}")
    print(f"     ⏭️  Perdidos (misfire)     : {_stats['perdidos']}")

    # Limpa o banco de demo
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"\n  Banco de dados de demo removido: {DB_PATH}")

    print("  Scheduler encerrado.")
