"""
Registro central de jobs — ÚNICO lugar onde novos jobs são definidos.

Como adicionar um novo job:
  1. Implemente a tarefa em tasks/<dominio>.py herdando de BaseTask.
  2. Instancie a classe de tarefa em _build_job_list().
  3. Adicione um JobConfig à lista com o trigger desejado.

Triggers disponíveis:
  IntervalTrigger(seconds=N, minutes=N, hours=N)  → repetição periódica
  CronTrigger(hour=H, minute=M, day_of_week='mon-fri')  → horário fixo
  DateTrigger(run_date=datetime(...))  → execução única

Nota sobre os intervalos neste arquivo:
  Os valores atuais usam SEGUNDOS para facilitar a visualização durante
  desenvolvimento. Os valores de PRODUÇÃO estão comentados ao lado de cada job.
"""

from dataclasses import dataclass
from typing import Any, Callable

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

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


def register_jobs(scheduler: BlockingScheduler) -> int:
    """
    Envolve cada job com o logger de execução e o registra no scheduler.

    O wrapper make_logged_callable() garante que início, fim, duração
    e traceback de cada execução sejam persistidos no PostgreSQL.

    Retorna o total de jobs registrados.
    """
    job_list = _build_job_list()

    for jc in job_list:
        scheduler.add_job(
            # Envolve o callable com logging automático para o banco
            make_logged_callable(jc.func, jc.id, jc.name),
            trigger=jc.trigger,
            id=jc.id,
            name=jc.name,
            max_instances=jc.max_instances,
            coalesce=jc.coalesce,
            misfire_grace_time=jc.misfire_grace_time,
            replace_existing=True,   # idempotente: sem DuplicateJobError no restart
        )

    return len(job_list)
