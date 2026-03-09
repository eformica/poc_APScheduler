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
        id, name, trigger, max_instances, coalesce, misfire_grace_time
    """

    id: str
    name: str
    image: str
    trigger: Any

    command: Optional[list[str]]       = None
    env_vars: dict[str, str]           = field(default_factory=dict)
    timeout: int                       = 300
    network: str                       = "host"
    max_instances: int                 = 1
    coalesce: bool                     = True
    misfire_grace_time: int            = 60


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

    def _run_in_container() -> None:
        runner = ContainerRunner(
            job_id=cfg.id,
            job_name=cfg.name,
            image=cfg.image,
            command=cfg.command,
            env_vars=cfg.env_vars,
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
    return _run_in_container


def register_container_jobs(
    scheduler: Any,
    configs: list[ContainerJobConfig],
) -> int:
    """
    Registra uma lista de ContainerJobConfig no scheduler.

    Equivalente a register_jobs() do scheduler/registry.py,
    mas para jobs containerizados.

    Retorna o total de jobs registrados.
    """
    for cfg in configs:
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
    return len(configs)
