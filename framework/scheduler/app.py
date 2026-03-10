"""
Ponto de entrada do scheduler (invocado por `python -m scheduler.app`).

Fluxo de inicialização:
  1. Configura logging estruturado para stdout (capturado pelo Docker)
  2. Inicia uvicorn apontando para api.main:app

O lifespan do FastAPI (api/main.py) executa na ordem:
  1. Aguarda o PostgreSQL ficar disponível (retry com backoff)
  2. Garante que as tabelas de log existem (create_all idempotente)
  3. Cria o usuário admin padrão se não existir
  4. Cria o BackgroundScheduler com PostgreSQL job store
  5. Registra os event listeners (execuções perdidas → DB)
  6. Registra todos os jobs definidos em registry.py
  7. Inicia o scheduler em background (não bloqueia o uvicorn)
  8. No shutdown: scheduler.shutdown(wait=True)

Execução:
  docker-compose up --build
  python -m scheduler.app
"""

import logging
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


# ── Criação do usuário admin padrão ─────────────────────────────────────────

def _create_admin_user() -> None:
    """
    Cria o usuário 'admin' padrão se não existir nenhum usuário com role admin.
    Chamado pelo lifespan da API antes de iniciar o scheduler.
    """
    from db.models import User
    from db.session import SessionLocal
    from api.auth import hash_password

    db = SessionLocal()
    try:
        if not db.query(User).filter(User.role == "admin").first():
            admin = User(
                username="admin",
                email="admin@scheduler.local",
                hashed_password=hash_password(settings.ADMIN_DEFAULT_PASSWORD),
                role="admin",
            )
            db.add(admin)
            db.commit()
            if settings.ADMIN_DEFAULT_PASSWORD == "admin123":
                logger.warning(
                    "⚠️  Usuário admin criado com senha padrão 'admin123'. "
                    "Altere via PUT /users/{id} antes de ir para produção!"
                )
            else:
                logger.info("✅ Usuário admin criado")
    except Exception as exc:
        logger.error("❌ Erro ao criar usuário admin: %s", exc)
        db.rollback()
    finally:
        db.close()


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    """Inicia o servidor FastAPI+uvicorn (API REST + BackgroundScheduler integrado)."""
    import uvicorn

    logger.info("=" * 60)
    logger.info("  APScheduler Framework — API REST")
    logger.info("  PostgreSQL : %s:%s/%s", settings.POSTGRES_HOST, settings.POSTGRES_PORT, settings.POSTGRES_DB)
    logger.info("  Timezone   : %s", settings.SCHEDULER_TIMEZONE)
    logger.info("  Workers    : %s", settings.SCHEDULER_THREAD_POOL_SIZE)
    logger.info("  API        : http://0.0.0.0:8000")
    logger.info("  Docs       : http://0.0.0.0:8000/docs")
    logger.info("=" * 60)

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
