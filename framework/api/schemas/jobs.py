"""Schemas de jobs — criação, reagendamento e resposta de agendamentos."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

# Importado apenas para type-hint abaixo
_ = Optional  # noqa: F401  (já importado acima)


class TriggerType(str, Enum):
    interval = "interval"
    cron = "cron"
    date = "date"


class TriggerConfig(BaseModel):
    type: TriggerType

    # ── IntervalTrigger ───────────────────────────────────────────────────────
    weeks: int = 0
    days: int = 0
    hours: int = 0
    minutes: int = 0
    seconds: int = 0
    jitter: Optional[int] = None

    # ── CronTrigger ───────────────────────────────────────────────────────────
    year: Optional[str] = None
    month: Optional[str] = None
    day: Optional[str] = None
    week: Optional[str] = None
    day_of_week: Optional[str] = None
    hour: Optional[str] = None
    minute: Optional[str] = None
    second: Optional[str] = None

    # ── DateTrigger ───────────────────────────────────────────────────────────
    run_date: Optional[datetime] = None

    @model_validator(mode="after")
    def check_interval_fields(self) -> "TriggerConfig":
        if self.type == TriggerType.interval:
            total = self.weeks + self.days + self.hours + self.minutes + self.seconds
            if total == 0:
                raise ValueError(
                    "IntervalTrigger requer pelo menos um campo "
                    "(weeks, days, hours, minutes, seconds) > 0"
                )
        return self


class JobCreate(BaseModel):
    func_key: str                                   # chave do catálogo — use GET /jobs/catalog
    trigger: Optional[TriggerConfig] = None         # None → job API-only (sem agendamento automático)
    id: Optional[str] = None
    name: Optional[str] = None
    max_instances: int = 1
    coalesce: bool = True
    misfire_grace_time: int = 60
    job_kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Parâmetros passados à função em cada execução. "
            "Para jobs in-process: repassados como **kwargs à função. "
            "Para jobs containerizados: injetados como JOB_KWARGS env var (JSON); "
            "leia dentro do container via TaskChannel.kwargs."
        ),
    )


class JobReschedule(BaseModel):
    trigger: TriggerConfig


class JobResponse(BaseModel):
    id: str
    name: str
    func: str
    trigger: str
    next_run_time: Optional[datetime]
    pending: bool


class CatalogItem(BaseModel):
    key: str
    name: str
    module: str
    api_only: bool = False  # True → sem agendamento automático; acione via POST /jobs/{id}/run
