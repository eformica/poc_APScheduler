"""
Modelos SQLAlchemy — mapeados para as tabelas do PostgreSQL.

Tabelas gerenciadas pelo ORM:
  job_execution_logs  → registros de cada execução de job

Tabelas gerenciadas pelo APScheduler:
  apscheduler_jobs    → estado persistido dos jobs (criada automaticamente)
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class JobExecutionLog(Base):
    """
    Registro de uma execução de job agendado.

    Campos:
      job_id         → ID único do job no APScheduler
      job_name       → nome legível (para dashboards e alertas)
      scheduled_at   → quando o job estava agendado para rodar
      started_at     → quando a execução de fato começou
      finished_at    → quando a execução terminou (None se misfire)
      status         → 'success' | 'error' | 'missed'
      error_type     → nome da classe da exceção (ex: ConnectionError)
      error_message  → str(exception)
      traceback      → traceback completo formatado
      duration_ms    → duração em milissegundos (None se misfire)
    """

    __tablename__ = "job_execution_logs"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    job_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    job_name: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
        # CHECK constraint definido no init.sql
    )
    error_type: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    traceback: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<JobExecutionLog id={self.id} job_id={self.job_id!r} "
            f"status={self.status!r} duration={self.duration_ms}ms>"
        )
