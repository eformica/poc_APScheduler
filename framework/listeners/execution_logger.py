"""
Logging de execução de jobs para PostgreSQL.

Dois mecanismos complementares:

  1. make_logged_callable(func, job_id, job_name)
     ─ Wrapper de função aplicado no registro do job (registry.py).
     ─ Captura: tempo de início/fim, duração, tipo de erro, traceback.
     ─ Persiste um registro em job_execution_logs para CADA execução.
     ─ Re-lança exceções para que o APScheduler também as registre.

  2. register_listeners(scheduler)
     ─ Event listener para EVENT_JOB_MISSED.
     ─ Registra no banco quando um job perde a janela de execução
       (misfire_grace_time ultrapassado).

Princípio de resiliência:
  Falhas no próprio mecanismo de logging nunca derrubam o scheduler.
  Erros são capturados silenciosamente e emitidos como log de nível ERROR.
"""

import functools
import logging
import traceback as tb
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from apscheduler.events import EVENT_JOB_MISSED, JobExecutionEvent

logger = logging.getLogger(__name__)


# ── Persistência ───────────────────────────────────────────────────────────────

def _persist_log(
    job_id: str,
    job_name: Optional[str],
    started_at: datetime,
    finished_at: Optional[datetime],
    status: str,                      # 'success' | 'error' | 'missed'
    *,
    scheduled_at: Optional[datetime] = None,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
    traceback_text: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> None:
    """
    Persiste um registro de execução no PostgreSQL.
    Falhas nesta função são silenciadas para não impactar o scheduler.
    """
    try:
        from db.models import JobExecutionLog
        from db.session import SessionLocal

        with SessionLocal() as session:
            session.add(
                JobExecutionLog(
                    job_id=job_id,
                    job_name=job_name,
                    scheduled_at=scheduled_at,
                    started_at=started_at,
                    finished_at=finished_at,
                    status=status,
                    error_type=error_type,
                    error_message=error_message,
                    traceback=traceback_text,
                    duration_ms=duration_ms,
                )
            )
            session.commit()

    except Exception as exc:
        # Nunca deixa o log de persistência derrubar o scheduler
        logger.error(
            f"[execution_logger] falha ao persistir log de '{job_id}': {exc}"
        )


# ── Wrapper de job ─────────────────────────────────────────────────────────────

def make_logged_callable(func: Callable, job_id: str, job_name: str) -> Callable:
    """
    Envolve um callable com logging automático de execução para o PostgreSQL.

    Em caso de SUCESSO persiste:
      started_at, finished_at, status='success', duration_ms

    Em caso de ERRO persiste:
      started_at, finished_at, status='error',
      error_type, error_message, traceback, duration_ms

    O erro é sempre re-lançado para que o APScheduler registre
    internamente o EVENT_JOB_ERROR.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        started_at = datetime.now(timezone.utc)
        try:
            result = func(*args, **kwargs)
            finished_at = datetime.now(timezone.utc)
            duration_ms = int(
                (finished_at - started_at).total_seconds() * 1000
            )
            _persist_log(
                job_id, job_name,
                started_at, finished_at,
                "success",
                duration_ms=duration_ms,
            )
            logger.debug(f"[{job_id}] concluído em {duration_ms}ms")
            return result

        except Exception as exc:
            finished_at = datetime.now(timezone.utc)
            duration_ms = int(
                (finished_at - started_at).total_seconds() * 1000
            )
            _persist_log(
                job_id, job_name,
                started_at, finished_at,
                "error",
                duration_ms=duration_ms,
                error_type=type(exc).__name__,
                error_message=str(exc),
                traceback_text=tb.format_exc(),
            )
            # Re-lança para o APScheduler registrar EVENT_JOB_ERROR
            raise

    return wrapper


# ── Event listener: execuções perdidas ────────────────────────────────────────

def _on_job_missed(event: JobExecutionEvent) -> None:
    """
    Chamado pelo APScheduler quando um job perde sua janela de execução
    (misfire_grace_time ultrapassado).
    Persiste um registro com status='missed' no banco.
    """
    now = datetime.now(timezone.utc)
    scheduled_at = getattr(event, "scheduled_run_time", None) or now

    logger.warning(
        f"[{event.job_id}] execução PERDIDA — "
        f"agendada para {scheduled_at.isoformat()}"
    )

    _persist_log(
        event.job_id,
        None,           # job_name não disponível no evento de misfire
        now,            # started_at = momento em que detectamos o miss
        None,           # finished_at = não aplicável
        "missed",
        scheduled_at=scheduled_at,
    )


def register_listeners(scheduler: Any) -> None:
    """Registra os event listeners no scheduler."""
    from apscheduler.events import EVENT_JOB_EXECUTED

    def _on_job_executed_api_only(event: JobExecutionEvent) -> None:
        """
        Re-pausa jobs API-only após cada execução manual.

        Fluxo:
          1. POST /jobs/{id}/run → modify_job(next_run_time=now)
          2. Job executa
          3. APScheduler recalcula next_run_time via _API_ONLY_TRIGGER (~100 anos)
          4. Este listener detecta o job em API_ONLY_JOB_IDS e re-pausa
             → next_run_time volta a None (aparece como null na API)
        """
        from scheduler.registry import API_ONLY_JOB_IDS
        if event.job_id in API_ONLY_JOB_IDS:
            try:
                scheduler.pause_job(event.job_id)
            except Exception as exc:
                logger.debug(
                    "[execution_logger] falha ao re-pausar job api-only '%s': %s",
                    event.job_id, exc,
                )

    scheduler.add_listener(_on_job_missed, EVENT_JOB_MISSED)
    scheduler.add_listener(_on_job_executed_api_only, EVENT_JOB_EXECUTED)
    logger.info("✅ Event listeners registrados (misfire + api-only re-pause → PostgreSQL)")
