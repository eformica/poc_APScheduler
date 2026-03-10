"""
Aplicação FastAPI — ponto de entrada da API REST.

Lifespan (startup → shutdown):
  1. Aguarda PostgreSQL (wait_for_db)
  2. Cria tabelas ORM (ensure_tables)
  3. Cria usuário admin padrão se inexistente (_create_admin_user)
  4. Inicia BackgroundScheduler com todos os jobs registrados
  5. No shutdown: scheduler.shutdown(wait=True)

Routers:
  /auth   — login (OAuth2 Password Flow) e refresh de token
  /jobs   — CRUD de agendamentos + execução manual + catálogo
  /users  — gerenciamento de usuários (admin)
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from scheduler.config import settings

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)-28s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("api.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida do scheduler junto com a aplicação FastAPI."""
    from scheduler.app import _create_admin_user, ensure_tables, wait_for_db
    from scheduler.engine import create_scheduler
    from scheduler.registry import register_jobs
    from listeners.execution_logger import register_listeners

    wait_for_db()
    ensure_tables()
    _create_admin_user()

    scheduler = create_scheduler()
    register_listeners(scheduler)
    count = register_jobs(scheduler)
    scheduler.start()

    logger.info("🚀 Scheduler iniciado com %d jobs | API disponível em :8000", count)
    app.state.scheduler = scheduler

    yield  # ← aplicação fica em execução aqui

    scheduler.shutdown(wait=True)
    logger.info("👋 Scheduler encerrado com sucesso")


app = FastAPI(
    title="APScheduler REST API",
    description=(
        "API para gerenciamento de agendamentos de tarefas.\n\n"
        "**Roles de acesso:**\n"
        "- `admin` — acesso total (jobs + usuários)\n"
        "- `operator` — criar/modificar/executar jobs; alterar própria senha\n"
        "- `viewer` — somente leitura de jobs\n\n"
        "**Como autenticar:** `POST /auth/login` → use o `access_token` no header "
        "`Authorization: Bearer <token>`.\n\n"
        "**Renovar token:** `POST /auth/refresh` com o `refresh_token`."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from api.routers import auth, jobs, users  # noqa: E402

app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(users.router)


@app.get("/health", tags=["Sistema"], summary="Health check da API e do scheduler")
def health(request: Request):
    scheduler = request.app.state.scheduler
    return {
        "status": "ok",
        "scheduler": "running" if scheduler.running else "stopped",
        "jobs": len(scheduler.get_jobs()),
    }
