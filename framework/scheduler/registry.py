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
  2. Adicione um JobConfig em _build_job_list().
     - trigger=None        → job exclusivamente via API (POST /jobs/{id}/run)
     - in_catalog=False    → oculto no GET /jobs/catalog (mas registrado)
     - job_kwargs={...}    → passado como **kwargs à função em cada execução

Como adicionar um novo job containerizado:
  1. Crie o entrypoint da task (como tasks/containerized_example.py).
  2. Construa e publique a imagem Docker.
  3. Adicione um ContainerJobConfig em _build_container_job_list().
     - job_kwargs={...}   → injetado como JOB_KWARGS env var (JSON); leia via ch.kwargs

Nota sobre intervalos: valores atuais usam SEGUNDOS para demo.
Os valores de PRODUÇÃO estão comentados ao lado de cada job.
"""

from dataclasses import dataclass, field
from typing import Any, Callable

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from container_runner.config import ContainerJobConfig, make_container_callable, register_container_jobs
from listeners.execution_logger import make_logged_callable
from tasks.analytics import AnalyticsTask
from tasks.devops import DevOpsTask
from tasks.ecommerce import EcommerceTask


# ── Instâncias singleton de tarefas ───────────────────────────────────────────
# Criadas uma única vez no nível do módulo e compartilhadas entre o registry
# e o TASK_CATALOG usado pela API REST.
_ecom      = EcommerceTask()
_analytics = AnalyticsTask()
_devops    = DevOpsTask()


@dataclass
class JobConfig:
    """Definição de um job para registro no scheduler."""

    id: str                                      # identificador único — PK no job store
    name: str                                    # nome legível — logs e banco
    func: Callable                               # callable a executar
    trigger: Any = None                          # None → acionamento exclusivo via API REST
    max_instances: int = 1                       # instâncias paralelas permitidas
    coalesce: bool = True                        # sobrescreve o default do scheduler
    misfire_grace_time: int = 60
    in_catalog: bool = True                      # False → oculto no GET /jobs/catalog
    job_kwargs: dict[str, Any] = field(default_factory=dict)  # parâmetros passados à função


def _build_job_list() -> list[JobConfig]:
    """
    Retorna a lista completa de jobs do sistema.
    Adicione novos JobConfig aqui para registrar novas tarefas.
    """
    return [
        # ── E-commerce ────────────────────────────────────────────────────
        JobConfig(
            id="ecom_processar_pedidos",
            name="E-commerce: Processar Pedidos Pendentes",
            func=_ecom.processar_pedidos,
            trigger=IntervalTrigger(seconds=10),     # prod: minutes=5
        ),
        JobConfig(
            id="ecom_verificar_estoque",
            name="E-commerce: Verificar Estoque Crítico",
            func=_ecom.verificar_estoque,
            trigger=IntervalTrigger(seconds=15),     # prod: minutes=15
        ),
        JobConfig(
            id="ecom_relatorio_vendas",
            name="E-commerce: Exportar Relatório de Vendas",
            func=_ecom.exportar_relatorio_vendas,
            trigger=CronTrigger(second="*/20"),      # prod: hour=8, minute=0
        ),

        # ── Analytics / ETL ───────────────────────────────────────────────
        JobConfig(
            id="analytics_etl",
            name="Analytics: Executar ETL Incremental",
            func=_analytics.executar_etl,
            trigger=IntervalTrigger(seconds=12),     # prod: minutes=30
        ),
        JobConfig(
            id="analytics_dashboard",
            name="Analytics: Atualizar Dashboard",
            func=_analytics.atualizar_dashboard,
            trigger=IntervalTrigger(seconds=8),      # prod: minutes=10
        ),
        JobConfig(
            id="analytics_relatorio_exec",
            name="Analytics: Relatório Executivo Diário",
            func=_analytics.gerar_relatorio_executivo,
            trigger=CronTrigger(second="*/25"),      # prod: hour=6, minute=30
        ),

        # ── DevOps / Infraestrutura ───────────────────────────────────────
        JobConfig(
            id="devops_health_check",
            name="DevOps: Health Check de Serviços",
            func=_devops.health_check,
            trigger=IntervalTrigger(seconds=6),      # prod: seconds=30
        ),
        JobConfig(
            id="devops_limpar_tmp",
            name="DevOps: Limpar Arquivos Temporários",
            func=_devops.limpar_temporarios,
            trigger=CronTrigger(second="*/18"),      # prod: hour="*/4"
        ),
        JobConfig(
            id="devops_ssl",
            name="DevOps: Verificar Certificados SSL",
            func=_devops.verificar_certificados_ssl,
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
        # ── Exemplo 1: ETL containerizado — agendamento automático (padrão) ───────
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
        #     max_instances=1,
        #     coalesce=True,
        #     misfire_grace_time=120,
        #     in_catalog=True,      # aparece em GET /jobs/catalog com api_only=false
        # ),

        # ── Exemplo 2: Job API-only — trigger=None (sem agendamento automático) ───
        # Idêntico ao trigger=None de JobConfig: registrado paused (next_run_time=null).
        # Dispara somente via POST /jobs/{id}/run.
        # Após cada execução, o listener EVENT_JOB_EXECUTED re-pausa automaticamente.
        # ContainerJobConfig(
        #     id="etl_reprocessar_lote",
        #     name="ETL: Reprocessar Lote Específico (API-only)",
        #     image="myorg/etl-task:latest",
        #     trigger=None,         # ← sem disparo automático
        #     env_vars={"MODE": "reprocess"},
        #     timeout=600,
        #     in_catalog=True,      # aparece em GET /jobs/catalog com api_only=true
        # ),

        # ── Exemplo 3: Job oculto do catálogo — in_catalog=False ──────────────────
        # Registrado e agendado normalmente, mas não aparece em GET /jobs/catalog.
        # Útil para jobs internos de manutenção que não devem ser expostos na API.
        # ContainerJobConfig(
        #     id="manutencao_interna",
        #     name="Manutenção: Limpeza Interna de Artifacts",
        #     image="myorg/maintenance:latest",
        #     trigger=CronTrigger(hour=3, minute=0),  # prod: todo dia 03:00
        #     timeout=120,
        #     in_catalog=False,     # ← oculto em GET /jobs/catalog
        # ),

        # ── Exemplo 4: Relatório em R/Julia com dependências específicas ──────────
        # ContainerJobConfig(
        #     id="relatorio_r",
        #     name="Analytics: Relatório Estatístico (R)",
        #     image="myorg/r-reports:latest",
        #     trigger=CronTrigger(hour=7, minute=0),  # prod: todo dia 07:00
        #     command=["Rscript", "/app/report.R"],
        #     timeout=600,
        #     in_catalog=True,
        # ),

        # ── Exemplo 5: Task de ML com GPU ─────────────────────────────────────────
        # ContainerJobConfig(
        #     id="treinamento_modelo",
        #     name="ML: Re-treino Incremental",
        #     image="myorg/ml-trainer:latest",
        #     trigger=CronTrigger(day_of_week="sun", hour=2),
        #     env_vars={"MODEL_VERSION": "v3", "EPOCHS": "10"},
        #     timeout=3600,
        #     in_catalog=True,
        # ),
    ]


# ── Listas avaliadas no nível do módulo ──────────────────────────────────────
# Avaliadas uma única vez no import; usadas por TASK_CATALOG e register_jobs().
_JOBS: list[JobConfig]                    = _build_job_list()
_CONTAINER_JOBS: list[ContainerJobConfig] = _build_container_job_list()

# ── Catálogo público — gerado automaticamente ─────────────────────────────────
# Mapeia `id` do job → callable para uso em POST /jobs.
# Inclui apenas jobs com in_catalog=True.
TASK_CATALOG: dict[str, Callable] = {
    jc.id: jc.func
    for jc in _JOBS
    if jc.in_catalog
} | {
    cfg.id: make_container_callable(cfg)
    for cfg in _CONTAINER_JOBS
    if cfg.in_catalog
}

# Metadados do catálogo: nome legível e flag api_only por job_id.
CATALOG_METADATA: dict[str, dict] = {
    jc.id: {"name": jc.name, "api_only": jc.trigger is None}
    for jc in _JOBS
    if jc.in_catalog
} | {
    cfg.id: {"name": cfg.name, "api_only": cfg.trigger is None}
    for cfg in _CONTAINER_JOBS
    if cfg.in_catalog
}

# IDs de jobs sem trigger automático — acionados somente via API REST.
# Populado a partir da definição estática; atualizado em runtime pela API
# quando novos jobs API-only são criados via POST /jobs.
API_ONLY_JOB_IDS: set[str] = (
    {jc.id  for jc in _JOBS           if jc.trigger is None}
    | {cfg.id for cfg in _CONTAINER_JOBS if cfg.trigger is None}
)

# Trigger sentinela para jobs API-only (~100 anos).
# Garante que o job fique no job store mas nunca dispare automaticamente.
# Após execução manual, o listener EVENT_JOB_EXECUTED re-pausa o job
# (next_run_time → None), fazendo GET /jobs/{id} voltar a mostrar null.
_API_ONLY_TRIGGER = IntervalTrigger(days=36500)


def register_jobs(scheduler) -> int:
    """
    Registra todos os jobs in-process e containerizados no scheduler.

    Comportamento por tipo de trigger:
      jc.trigger is not None  → job com agendamento automático normal.
      jc.trigger is None      → job registrado paused (next_run_time=None);
                                 dispara apenas via POST /jobs/{id}/run.
                                 O ID é adicionado a API_ONLY_JOB_IDS para que
                                 o listener EVENT_JOB_EXECUTED o re-pause
                                 automaticamente após cada execução manual.

    Retorna o total de jobs registrados (in-process + containerizados).
    """
    # ── In-process ─────────────────────────────────────────────────────────
    for jc in _JOBS:
        logged_func = make_logged_callable(jc.func, jc.id, jc.name)
        add_kwargs: dict = dict(
            trigger=jc.trigger if jc.trigger is not None else _API_ONLY_TRIGGER,
            id=jc.id,
            name=jc.name,
            max_instances=jc.max_instances,
            coalesce=jc.coalesce,
            misfire_grace_time=jc.misfire_grace_time,
            replace_existing=True,
            kwargs=jc.job_kwargs,  # passados à função em cada execução
        )
        if jc.trigger is None:
            add_kwargs["next_run_time"] = None  # começa pausado
        scheduler.add_job(logged_func, **add_kwargs)

    # ── Containerizados ────────────────────────────────────────────────────
    register_container_jobs(scheduler, _CONTAINER_JOBS)
    return len(_JOBS) + len(_CONTAINER_JOBS)
