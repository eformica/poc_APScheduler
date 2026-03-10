"""
Router de jobs — gerenciamento completo de agendamentos.

Permissões:
  GET    /jobs              — viewer, operator, admin
  GET    /jobs/catalog      — viewer, operator, admin
  GET    /jobs/{id}         — viewer, operator, admin
  POST   /jobs              — operator, admin
  PATCH  /jobs/{id}/reschedule — operator, admin
  POST   /jobs/{id}/pause   — operator, admin
  POST   /jobs/{id}/resume  — operator, admin
  POST   /jobs/{id}/run     — operator, admin  (execução imediata fora do agendamento)
  DELETE /jobs/{id}         — admin
"""

from datetime import datetime, timezone
from typing import List

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_current_user, get_scheduler, require_admin, require_operator
from api.schemas.jobs import CatalogItem, JobCreate, JobReschedule, JobResponse, TriggerType
from db.models import User
from listeners.execution_logger import make_logged_callable
from scheduler.registry import API_ONLY_JOB_IDS, CATALOG_METADATA, TASK_CATALOG

router = APIRouter(prefix="/jobs", tags=["Jobs"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_trigger(cfg):
    """Constrói uma instância de trigger APScheduler a partir de TriggerConfig."""
    if cfg.type == TriggerType.interval:
        return IntervalTrigger(
            weeks=cfg.weeks,
            days=cfg.days,
            hours=cfg.hours,
            minutes=cfg.minutes,
            seconds=cfg.seconds,
            jitter=cfg.jitter,
        )
    if cfg.type == TriggerType.cron:
        params = {
            k: v
            for k, v in {
                "year": cfg.year,
                "month": cfg.month,
                "day": cfg.day,
                "week": cfg.week,
                "day_of_week": cfg.day_of_week,
                "hour": cfg.hour,
                "minute": cfg.minute,
                "second": cfg.second,
            }.items()
            if v is not None
        }
        return CronTrigger(**params)
    if cfg.type == TriggerType.date:
        return DateTrigger(run_date=cfg.run_date or datetime.now(timezone.utc))
    raise ValueError(f"Trigger desconhecido: {cfg.type}")


def _job_to_response(job) -> JobResponse:
    return JobResponse(
        id=job.id,
        name=job.name or job.id,
        func=str(getattr(job, "func_ref", None) or job.func),
        trigger=str(job.trigger),
        next_run_time=job.next_run_time,
        pending=getattr(job, "pending", False),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/catalog",
    response_model=List[CatalogItem],
    summary="Lista funções disponíveis para agendamento",
)
def list_catalog(_: User = Depends(get_current_user)):
    """
    Retorna todas as funções de tarefa registradas no `TASK_CATALOG`.
    Use o campo `key` como `func_key` ao criar um job via `POST /jobs`.
    """
    return [
        CatalogItem(
            key=k,
            name=CATALOG_METADATA.get(k, {}).get("name", k),
            module=k.split("_")[0] if "_" in k else k,
            api_only=CATALOG_METADATA.get(k, {}).get("api_only", False),
        )
        for k in sorted(TASK_CATALOG)
    ]


@router.get(
    "",
    response_model=List[JobResponse],
    summary="Lista todos os jobs agendados",
)
def list_jobs(
    scheduler=Depends(get_scheduler),
    _: User = Depends(get_current_user),
):
    return [_job_to_response(j) for j in scheduler.get_jobs()]


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Detalhes de um job específico",
)
def get_job(
    job_id: str,
    scheduler=Depends(get_scheduler),
    _: User = Depends(get_current_user),
):
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    return _job_to_response(job)


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Adiciona um novo agendamento",
)
def create_job(
    body: JobCreate,
    scheduler=Depends(get_scheduler),
    _: User = Depends(require_operator),
):
    """
    Cria um novo job a partir de uma função do catálogo.

    - `func_key`: chave obtida em `GET /jobs/catalog`
    - `trigger`: configuração do trigger; **`null` cria um job API-only**
      (sem agendamento automático — acionado somente via `POST /jobs/{id}/run`)
    - `id`: opcional — gerado automaticamente a partir do `func_key` se omitido

    O job é envolvido automaticamente com o logger de execução
    (registra sucesso, erro e misfires em `job_execution_logs`).
    """
    if body.func_key not in TASK_CATALOG:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Função '{body.func_key}' não encontrada no catálogo. "
                f"Consulte GET /jobs/catalog para as opções disponíveis."
            ),
        )

    trigger = None
    if body.trigger is not None:
        try:
            trigger = _build_trigger(body.trigger)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Trigger inválido: {exc}")

    func = TASK_CATALOG[body.func_key]
    job_id = body.id or body.func_key
    job_name = body.name or CATALOG_METADATA.get(body.func_key, {}).get("name", body.func_key)

    # Jobs containerizados já persistem via ContainerRunner — não envolver com
    # make_logged_callable() para evitar dupla gravação em job_execution_logs.
    is_container = getattr(func, "_is_container_callable", False)
    logged_func = func if is_container else make_logged_callable(func, job_id, job_name)

    add_kwargs: dict = dict(
        trigger=trigger if trigger is not None else IntervalTrigger(days=36500),
        id=job_id,
        name=job_name,
        max_instances=body.max_instances,
        coalesce=body.coalesce,
        misfire_grace_time=body.misfire_grace_time,
        replace_existing=True,
        kwargs=body.job_kwargs,  # passados à função (in-process) ou como JOB_KWARGS env var (container)
    )
    if trigger is None:
        add_kwargs["next_run_time"] = None  # começa pausado
        API_ONLY_JOB_IDS.add(job_id)

    job = scheduler.add_job(logged_func, **add_kwargs)
    return _job_to_response(job)


@router.patch(
    "/{job_id}/reschedule",
    response_model=JobResponse,
    summary="Reagenda um job (altera o trigger)",
)
def reschedule_job(
    job_id: str,
    body: JobReschedule,
    scheduler=Depends(get_scheduler),
    _: User = Depends(require_operator),
):
    """Altera somente o trigger do job, preservando a função e as configurações."""
    if not scheduler.get_job(job_id):
        raise HTTPException(status_code=404, detail="Job não encontrado")
    try:
        trigger = _build_trigger(body.trigger)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Trigger inválido: {exc}")

    job = scheduler.reschedule_job(job_id, trigger=trigger)
    return _job_to_response(job)


@router.post(
    "/{job_id}/pause",
    response_model=JobResponse,
    summary="Pausa um job (mantém o agendamento)",
)
def pause_job(
    job_id: str,
    scheduler=Depends(get_scheduler),
    _: User = Depends(require_operator),
):
    if not scheduler.get_job(job_id):
        raise HTTPException(status_code=404, detail="Job não encontrado")
    scheduler.pause_job(job_id)
    return _job_to_response(scheduler.get_job(job_id))


@router.post(
    "/{job_id}/resume",
    response_model=JobResponse,
    summary="Retoma um job pausado",
)
def resume_job(
    job_id: str,
    scheduler=Depends(get_scheduler),
    _: User = Depends(require_operator),
):
    if not scheduler.get_job(job_id):
        raise HTTPException(status_code=404, detail="Job não encontrado")
    scheduler.resume_job(job_id)
    return _job_to_response(scheduler.get_job(job_id))


@router.post(
    "/{job_id}/run",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Executa um job imediatamente (fora do agendamento)",
)
def run_job_now(
    job_id: str,
    scheduler=Depends(get_scheduler),
    _: User = Depends(require_operator),
):
    """
    Agenda a execução imediata do job modificando `next_run_time` para agora.
    O trigger original é **preservado** — a próxima execução regular continua normalmente.

    Retorna HTTP 202 Accepted (a execução ocorre em background).
    """
    if not scheduler.get_job(job_id):
        raise HTTPException(status_code=404, detail="Job não encontrado")
    scheduler.modify_job(job_id, next_run_time=datetime.now(timezone.utc))
    return {"detail": f"Job '{job_id}' agendado para execução imediata"}


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove um job permanentemente (admin)",
)
def delete_job(
    job_id: str,
    scheduler=Depends(get_scheduler),
    _: User = Depends(require_admin),
):
    """Remove o job do scheduler e do job store (PostgreSQL). Ação irreversível."""
    if not scheduler.get_job(job_id):
        raise HTTPException(status_code=404, detail="Job não encontrado")
    scheduler.remove_job(job_id)
