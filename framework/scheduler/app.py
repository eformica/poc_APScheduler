"""
Ponto de entrada do scheduler.

Fluxo de inicialização:
  1. Configura logging estruturado para stdout (capturado pelo Docker)
  2. Aguarda o PostgreSQL ficar disponível (retry com backoff)
  3. Garante que as tabelas de log existem (create_all idempotente)
  4. Cria o BlockingScheduler com PostgreSQL job store
  5. Registra os event listeners (execuções perdidas → DB)
  6. Registra todos os jobs definidos em registry.py
  7. Configura handlers de SIGTERM/SIGINT para graceful shutdown
  8. Inicia o scheduler (bloqueia até shutdown)

Execução:
  docker-compose up --build
  python -m scheduler.app
"""

import logging
import signal
import sys
import time

from scheduler.config import settings

# ── Logging ─────────────────────────────────────────────────────────────────
# Configurado antes de qualquer importação para capturar todos os logs
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)-28s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("scheduler.app")


# ── Utilitários de inicialização ─────────────────────────────────────────────

def wait_for_db(max_retries: int = 15, delay: int = 3) -> None:
    """
    Aguarda o PostgreSQL responder antes de iniciar o scheduler.
    Evita falha de startup por race condition com o container do banco.
    """
    from sqlalchemy import text
    from db.session import engine

    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✅ Conexão com PostgreSQL estabelecida")
            return
        except Exception as exc:
            logger.warning(
                f"⏳ PostgreSQL indisponível "
                f"(tentativa {attempt}/{max_retries}): {exc}"
            )
            if attempt < max_retries:
                time.sleep(delay)

    logger.critical("❌ Não foi possível conectar ao PostgreSQL. Encerrando.")
    sys.exit(1)


def ensure_tables() -> None:
    """
    Garante que as tabelas do ORM existem no banco.
    Complementa o init.sql — idempotente, seguro de rodar múltiplas vezes.
    """
    from db.session import engine
    from db.models import Base

    Base.metadata.create_all(bind=engine)
    logger.info("✅ Tabelas de log verificadas/criadas")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    logger.info("=" * 60)
    logger.info("  APScheduler Framework — iniciando")
    logger.info(f"  PostgreSQL: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
    logger.info(f"  Timezone  : {settings.SCHEDULER_TIMEZONE}")
    logger.info(f"  Workers   : {settings.SCHEDULER_THREAD_POOL_SIZE}")
    logger.info("=" * 60)

    # 1. Aguarda o banco
    wait_for_db()

    # 2. Garante as tabelas de log
    ensure_tables()

    # 3. Cria o scheduler
    from scheduler.engine import create_scheduler
    scheduler = create_scheduler()

    # 4. Registra event listeners (execuções perdidas → DB)
    from listeners.execution_logger import register_listeners
    register_listeners(scheduler)

    # 5. Registra todos os jobs
    from scheduler.registry import register_jobs
    total = register_jobs(scheduler)

    # 6. Graceful shutdown — Docker envia SIGTERM antes de SIGKILL
    def handle_shutdown(signum: int, frame: object) -> None:
        sig_name = signal.Signals(signum).name
        logger.info(f"🛑 Sinal {sig_name} recebido — aguardando jobs em execução...")
        scheduler.shutdown(wait=True)
        logger.info("👋 Scheduler encerrado com sucesso.")
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    # 7. Log dos jobs registrados
    logger.info(f"🚀 {total} jobs registrados:")
    for job in scheduler.get_jobs():
        logger.info(f"   • [{job.id}]  próxima: {job.next_run_time}")
    logger.info("=" * 60)

    # 8. Inicia — bloqueia até shutdown()
    scheduler.start()


if __name__ == "__main__":
    main()
