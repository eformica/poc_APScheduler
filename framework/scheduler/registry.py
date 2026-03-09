"""
Registro central de jobs — ÚNICO lugar onde novos jobs são definidos.

Dois tipos de jobs suportados:

  1. JobConfig (in-process)
     ─ Task executada na thread pool do próprio scheduler.
     ─ Envolva a função com make_logged_callable() para persistência automática.
     ─ Ideal para tarefas leves, rápidas e que não precisam de isolamento.

  2. ContainerJobConfig (containerizado)
     ─ Task executada em um container Docker isolado.
     ─ Use make_container_callable() ou register_container_jobs().
     ─ NÃO use make_logged_callable() — o ContainerRunner já persiste tudo.
     ─ Ideal para tarefas pesadas, com dependências próprias ou que exigem
       isolamento de processo, memória e sistema de arquivos.

Como adicionar um novo job in-process:
  1. Implemente o método em tasks/<dominio>.py herdando de BaseTask.
  2. Instancie a classe em _build_job_list() e adicione um JobConfig.

Como adicionar um novo job containerizado:
  1. Crie o entrypoint da task (como tasks/containerized_example.py).
  2. Construa e publique a imagem Docker.
  3. Adicione um ContainerJobConfig em _build_container_job_list().

Nota sobre intervalos: valores atuais usam SEGUNDOS para demo.
Os valores de PRODUÇÃO estão comentados ao lado de cada job.
"""

from dataclasses import dataclass
from typing import Any, Callable

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from container_runner.config import ContainerJobConfig, register_container_jobs
from listeners.execution_logger import make_logged_callable
from tasks.analytics import AnalyticsTask
from tasks.devops import DevOpsTask
from tasks.ecommerce import EcommerceTask


@dataclass
class JobConfig:
    """Definição de um job para registro no scheduler."""

    id: str                   # identificador único — usado como PK no job store
    name: str                 # nome legível — aparece nos logs e no banco
    func: Callable            # callable que será executado
    trigger: Any              # instância de IntervalTrigger, CronTrigger etc.
    max_instances: int = 1    # instâncias paralelas permitidas deste job
    coalesce: bool = True     # sobrescreve o default do scheduler se necessário
    misfire_grace_time: int = 60


def _build_job_list() -> list[JobConfig]:
    """
    Retorna a lista completa de jobs do sistema.
    Adicione novos JobConfig aqui para registrar novas tarefas.
    """
    ecom      = EcommerceTask()
    analytics = AnalyticsTask()
    devops    = DevOpsTask()

    return [
        # ── E-commerce ────────────────────────────────────────────────────
        JobConfig(
            id="ecom_processar_pedidos",
            name="E-commerce: Processar Pedidos Pendentes",
            func=ecom.processar_pedidos,
            trigger=IntervalTrigger(seconds=10),     # prod: minutes=5
        ),
        JobConfig(
            id="ecom_verificar_estoque",
            name="E-commerce: Verificar Estoque Crítico",
            func=ecom.verificar_estoque,
            trigger=IntervalTrigger(seconds=15),     # prod: minutes=15
        ),
        JobConfig(
            id="ecom_relatorio_vendas",
            name="E-commerce: Exportar Relatório de Vendas",
            func=ecom.exportar_relatorio_vendas,
            trigger=CronTrigger(second="*/20"),      # prod: hour=8, minute=0
        ),

        # ── Analytics / ETL ───────────────────────────────────────────────
        JobConfig(
            id="analytics_etl",
            name="Analytics: Executar ETL Incremental",
            func=analytics.executar_etl,
            trigger=IntervalTrigger(seconds=12),     # prod: minutes=30
        ),
        JobConfig(
            id="analytics_dashboard",
            name="Analytics: Atualizar Dashboard",
            func=analytics.atualizar_dashboard,
            trigger=IntervalTrigger(seconds=8),      # prod: minutes=10
        ),
        JobConfig(
            id="analytics_relatorio_exec",
            name="Analytics: Relatório Executivo Diário",
            func=analytics.gerar_relatorio_executivo,
            trigger=CronTrigger(second="*/25"),      # prod: hour=6, minute=30
        ),

        # ── DevOps / Infraestrutura ───────────────────────────────────────
        JobConfig(
            id="devops_health_check",
            name="DevOps: Health Check de Serviços",
            func=devops.health_check,
            trigger=IntervalTrigger(seconds=6),      # prod: seconds=30
        ),
        JobConfig(
            id="devops_limpar_tmp",
            name="DevOps: Limpar Arquivos Temporários",
            func=devops.limpar_temporarios,
            trigger=CronTrigger(second="*/18"),      # prod: hour="*/4"
        ),
        JobConfig(
            id="devops_ssl",
            name="DevOps: Verificar Certificados SSL",
            func=devops.verificar_certificados_ssl,
            trigger=IntervalTrigger(seconds=20),     # prod: hours=6
        ),
    ]


# ── Jobs containerizados ───────────────────────────────────────────────────────

def _build_container_job_list() -> list[ContainerJobConfig]:
    """
    Retorna a lista de jobs que rodam em containers Docker isolados.

    Cada job lança um container separado via ContainerRunner.
    O container deve emitir eventos JSON via TaskChannel (channel.py).

    Descomente e adapte os exemplos abaixo para ativar jobs containerizados.
    Substitua 'myorg/...:latest' pelas imagens reais do seu registry.
    """
    return [
        # ── Exemplo: ETL containerizado ───────────────────────────────────
        # Container com ambiente Python + dependências próprias (pandas, etc.)
        # ContainerJobConfig(
        #     id="etl_containerizado",
        #     name="ETL: Pipeline Containerizado",
        #     image="myorg/etl-task:latest",
        #     trigger=IntervalTrigger(minutes=30),    # prod: minutes=30
        #     env_vars={
        #         "BATCH_SIZE": "500",
        #         "SOURCE_DB": "postgresql://user:pass@db-source/analytics",
        #     },
        #     timeout=300,
        # ),

        # ── Exemplo: Relatório em R/Julia com dependências específicas ─────
        # ContainerJobConfig(
        #     id="relatorio_r",
        #     name="Analytics: Relatório Estatístico (R)",
        #     image="myorg/r-reports:latest",
        #     trigger=CronTrigger(hour=7, minute=0),  # prod: todo dia 07:00
        #     command=["Rscript", "/app/report.R"],
        #     timeout=600,
        # ),

        # ── Exemplo: Task de ML com GPU ────────────────────────────────────
        # ContainerJobConfig(
        #     id="treinamento_modelo",
        #     name="ML: Re-treino Incremental",
        #     image="myorg/ml-trainer:latest",
        #     trigger=CronTrigger(day_of_week="sun", hour=2),
        #     env_vars={"MODEL_VERSION": "v3", "EPOCHS": "10"},
        #     timeout=3600,
        # ),
    ]


def register_jobs(scheduler: BlockingScheduler) -> int:
    """
    Registra todos os jobs in-process e containerizados no scheduler.

    Jobs in-process:
      Envolvidos com make_logged_callable() → persistência automática.

    Jobs containerizados:
      Usam make_container_callable() via register_container_jobs()
      → ContainerRunner gerencia persistência (container_task_logs + job_execution_logs).

    Retorna o total de jobs registrados (in-process + containerizados).
    """
    # ── In-process ─────────────────────────────────────────────────────────
    in_process_list = _build_job_list()

    for jc in in_process_list:
        scheduler.add_job(
            make_logged_callable(jc.func, jc.id, jc.name),
            trigger=jc.trigger,
            id=jc.id,
            name=jc.name,
            max_instances=jc.max_instances,
            coalesce=jc.coalesce,
            misfire_grace_time=jc.misfire_grace_time,
            replace_existing=True,
        )

    # ── Containerizados ────────────────────────────────────────────────────
    container_list = _build_container_job_list()
    register_container_jobs(scheduler, container_list)

    return len(in_process_list) + len(container_list)
