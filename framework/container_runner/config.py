"""
ContainerJobConfig — configuração de jobs containerizados.
==========================================================
Análogo ao JobConfig do scheduler/registry.py, mas para tasks
que rodam em containers Docker isolados.

Como registrar um job containerizado:

    from container_runner.config import ContainerJobConfig, make_container_callable
    from apscheduler.triggers.cron import CronTrigger

    cfg = ContainerJobConfig(
        id="etl_pipeline",
        name="ETL: Pipeline de Dados",
        image="myorg/etl-task:latest",
        trigger=CronTrigger(hour=6, minute=0),
        env_vars={"DATABASE_URL": "postgresql://...", "BATCH_SIZE": "500"},
        timeout=600,
    )
    scheduler.add_job(
        make_container_callable(cfg),
        trigger=cfg.trigger,
        id=cfg.id,
        name=cfg.name,
        max_instances=cfg.max_instances,
        coalesce=cfg.coalesce,
        misfire_grace_time=cfg.misfire_grace_time,
        replace_existing=True,
    )

Nota: NÃO envolva o callable com make_logged_callable().
O ContainerRunner já persiste em job_execution_logs E container_task_logs.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class ContainerJobConfig:
    """
    Definição completa de um job que roda em container Docker isolado.

    Campos Docker-específicos:
        image          → imagem Docker a executar (ex: 'myorg/etl:latest')
        command        → substitui o CMD padrão da imagem (opcional)
        env_vars       → variáveis de ambiente injetadas no container
        timeout        → tempo máximo de execução em segundos
        network        → rede Docker ('host' | 'bridge' | nome customizado)

    Campos de scheduling (mesmo contrato de JobConfig):
        id, name, trigger, max_instances, coalesce, misfire_grace_time, job_kwargs

    job_kwargs é serializado como JSON e injetado como variável de ambiente JOB_KWARGS
    no container. Leia dentro do container com: TaskChannel.from_env().kwargs
    """

    id: str
    name: str
    image: str
    trigger: Optional[Any]             = None   # None → acionamento exclusivo via API REST
    command: Optional[list[str]]       = None
    env_vars: dict[str, str]           = field(default_factory=dict)
    timeout: int                       = 300
    network: str                       = "host"
    max_instances: int                 = 1
    coalesce: bool                     = True
    misfire_grace_time: int            = 60
    in_catalog: bool                   = True   # False → oculto no GET /jobs/catalog
    job_kwargs: dict[str, Any]         = field(default_factory=dict)  # injetado como JOB_KWARGS env var (JSON)


def make_container_callable(cfg: ContainerJobConfig) -> Callable[[], None]:
    """
    Cria o callable que o APScheduler invocará para executar o job.

    Ao ser chamado, instancia um ContainerRunner, lança o container,
    faz streaming dos logs e persiste o resultado no PostgreSQL.

    Levanta RuntimeError se o container falhar (exit code != 0),
    o que faz o APScheduler disparar EVENT_JOB_ERROR normalmente.

    NÃO use make_logged_callable() em cima deste callable —
    o ContainerRunner já cuida de toda a persistência.
    """
    from container_runner.runner import ContainerRunner

    def _run_in_container(**job_kwargs: Any) -> None:
        # cfg.job_kwargs = valores PADRÃO definidos em ContainerJobConfig (estáticos).
        # job_kwargs     = parâmetros DINÂMICOS passados pelo APScheduler em cada
        #                  execução (vem de add_job(kwargs=...) — definidos via
        #                  POST /jobs ou modificados via modify_job).
        # Dinâmicos sobrescrevem padrões: {**padrões, **overrides}.
        env = dict(cfg.env_vars)
        merged_kwargs = {**cfg.job_kwargs, **job_kwargs}  # dinâmicos têm precedência
        if merged_kwargs:
            env["JOB_KWARGS"] = json.dumps(merged_kwargs, default=str)
        runner = ContainerRunner(
            job_id=cfg.id,
            job_name=cfg.name,
            image=cfg.image,
            command=cfg.command,
            env_vars=env,
            timeout=cfg.timeout,
            network=cfg.network,
        )
        result = runner.run()
        if not result.success:
            raise RuntimeError(
                result.error_message
                or f"Container '{cfg.image}' falhou (exit={result.exit_code})"
            )

    # Preserva identidade para logs do APScheduler
    _run_in_container.__name__     = cfg.id
    _run_in_container.__qualname__ = f"container_job.{cfg.id}"
    # Sentinel: permite que chamadores (ex: create_job na API) detectem que este
    # callable já cuida da própria persistência via ContainerRunner —
    # NÃO deve ser envolvido com make_logged_callable().
    _run_in_container._is_container_callable = True  # type: ignore[attr-defined]
    return _run_in_container


def register_container_jobs(
    scheduler: Any,
    configs: list[ContainerJobConfig],
) -> int:
    """
    Registra uma lista de ContainerJobConfig no scheduler.

    cfg.trigger is not None  → job com agendamento automático.
    cfg.trigger is None      → job pausado (next_run_time=None),
                               acionado somente via POST /jobs/{id}/run.

    Retorna o total de jobs registrados.
    """
    from apscheduler.triggers.interval import IntervalTrigger
    _sentinel = IntervalTrigger(days=36500)

    for cfg in configs:
        add_kwargs: dict = dict(
            id=cfg.id,
            name=cfg.name,
            max_instances=cfg.max_instances,
            coalesce=cfg.coalesce,
            misfire_grace_time=cfg.misfire_grace_time,
            replace_existing=True,
            kwargs=cfg.job_kwargs,  # APScheduler passa como **kwargs ao callable
        )
        if cfg.trigger is None:
            add_kwargs["trigger"] = _sentinel
            add_kwargs["next_run_time"] = None  # começa pausado
        else:
            add_kwargs["trigger"] = cfg.trigger
        scheduler.add_job(make_container_callable(cfg), **add_kwargs)
    return len(configs)
