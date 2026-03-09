"""
Exemplo 5: Casos de Uso do Mundo Real
======================================
Cenários realistas de múltiplos domínios de negócio, cada um com
seus próprios jobs usando diferentes triggers e estratégias.

Domínios simulados:
  1. E-commerce    — Processamento de pedidos, estoque, frete
  2. Analytics/ETL — Pipeline de dados, dashboards, relatórios
  3. DevOps        — Health check, limpeza, rotação de credenciais
  4. Financeiro    — Conciliação bancária, cobranças recorrentes
  5. Conteúdo      — Publicação agendada em redes sociais (DateTrigger)
"""

import time
import random
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# DOMÍNIO 1 — E-commerce
# ══════════════════════════════════════════════════════════════════════════════

class EcommerceService:
    """Jobs típicos de uma plataforma de e-commerce."""

    # Produção: IntervalTrigger(minutes=5)
    def processar_pedidos_pendentes(self) -> None:
        qtd = random.randint(0, 30)
        valor = qtd * random.uniform(50, 500)
        msg = f"{qtd} pedido(s) processados (R$ {valor:,.2f})" if qtd else "Nenhum pedido pendente"
        logger.info(f"🛍️  [E-commerce] {msg}")

    # Produção: IntervalTrigger(minutes=15)
    def verificar_estoque_critico(self) -> None:
        abaixo_minimo = random.randint(0, 6)
        if abaixo_minimo:
            logger.warning(f"⚠️  [Estoque] {abaixo_minimo} SKU(s) abaixo do mínimo — reposição necessária!")
        else:
            logger.info("📦 [Estoque] Todos os produtos com nível adequado")

    # Produção: IntervalTrigger(hours=1)
    def renovar_cotacoes_frete(self) -> None:
        cotacoes = random.randint(20, 200)
        logger.info(f"🚚 [Frete] {cotacoes} cotações renovadas (FedEx, Correios, Jadlog)")

    # Produção: CronTrigger(hour=7, minute=0)  → todo dia às 07:00
    def importar_catalogo_fornecedor(self) -> None:
        novos = random.randint(0, 150)
        atualizados = random.randint(10, 500)
        logger.info(f"🗂️  [Catálogo] {novos} novos + {atualizados} atualizados (fornecedor)")


# ══════════════════════════════════════════════════════════════════════════════
# DOMÍNIO 2 — Analytics / ETL
# ══════════════════════════════════════════════════════════════════════════════

class AnalyticsService:
    """Pipeline de dados e geração de relatórios."""

    # Produção: IntervalTrigger(minutes=30)
    def executar_etl_incremental(self) -> None:
        extraidos = random.randint(500, 50_000)
        rejeitados = int(extraidos * random.uniform(0, 0.03))
        carregados = extraidos - rejeitados
        logger.info(
            f"📊 [ETL] {extraidos:,} extraídos → {carregados:,} carregados "
            f"| {rejeitados} rejeitados"
        )

    # Produção: IntervalTrigger(minutes=10)
    def atualizar_dashboards(self) -> None:
        metricas = ["Vendas", "CAC", "LTV", "Churn", "NPS"]
        logger.info(f"📈 [Dashboard] KPIs atualizados: {', '.join(metricas)}")

    # Produção: CronTrigger(hour=6, minute=30)  → todo dia às 06:30
    def gerar_relatorio_executivo(self) -> None:
        periodo = datetime.now().strftime("%d/%m/%Y")
        logger.info(f"📋 [Relatório] Relatório executivo de {periodo} enviado à diretoria")

    # Produção: CronTrigger(day_of_week='mon', hour=8)  → toda segunda às 08:00
    def gerar_relatorio_semanal(self) -> None:
        logger.info(f"📑 [Relatório Semanal] Análise de performance da semana gerada")


# ══════════════════════════════════════════════════════════════════════════════
# DOMÍNIO 3 — DevOps / Infraestrutura
# ══════════════════════════════════════════════════════════════════════════════

_alertas_disparados = 0


class DevOpsService:
    """Monitoramento e operações de infraestrutura."""

    SERVICOS = ["API Gateway", "Auth Service", "Payment API", "DB Primary", "Cache Redis"]

    # Produção: IntervalTrigger(seconds=30)
    def health_check(self) -> None:
        global _alertas_disparados
        falhou = random.random() < 0.12  # 12% de chance de detectar problema
        if falhou:
            _alertas_disparados += 1
            servico = random.choice(self.SERVICOS)
            logger.error(
                f"🚨 [DevOps] ALERTA #{_alertas_disparados}: "
                f"{servico} não responde! Acionando on-call..."
            )
        else:
            logger.info(f"✅ [DevOps] {len(self.SERVICOS)} serviços OK")

    # Produção: CronTrigger(hour='*/4')  → a cada 4 horas
    def limpar_arquivos_temporarios(self) -> None:
        mb = random.randint(50, 2000)
        logger.info(f"🗑️  [DevOps] {mb} MB de arquivos temporários removidos")

    # Produção: CronTrigger(day_of_week='wed', hour=3)  → quarta às 03:00
    def rotacionar_credenciais(self) -> None:
        servicos = random.randint(3, 12)
        logger.info(f"🔐 [DevOps] Credenciais rotacionadas em {servicos} serviços")

    # Produção: IntervalTrigger(minutes=5)
    def verificar_certificados_ssl(self) -> None:
        a_expirar = random.randint(0, 2)
        if a_expirar:
            logger.warning(f"🔑 [SSL] {a_expirar} certificado(s) expira(m) em menos de 30 dias!")
        else:
            logger.info("🔑 [SSL] Todos os certificados SSL válidos")


# ══════════════════════════════════════════════════════════════════════════════
# DOMÍNIO 4 — Financeiro
# ══════════════════════════════════════════════════════════════════════════════

class FinanceiroService:
    """Processos financeiros automatizados."""

    # Produção: CronTrigger(hour='*/2')  → a cada 2 horas
    def conciliar_transacoes(self) -> None:
        total = random.randint(100, 2000)
        diverg = random.randint(0, 4)
        if diverg:
            logger.warning(
                f"💰 [Financeiro] Conciliação: {total} transações — "
                f"⚠️ {diverg} divergência(s) para revisão"
            )
        else:
            logger.info(f"💰 [Financeiro] Conciliação OK — {total} transações sem divergências")

    # Produção: CronTrigger(hour='*/3')  → a cada 3 horas
    def processar_cobrancas_recorrentes(self) -> None:
        cobradas = random.randint(20, 500)
        falhas = random.randint(0, 8)
        valor_total = cobradas * random.uniform(29, 299)
        logger.info(
            f"💳 [Cobranças] {cobradas} processadas (R$ {valor_total:,.2f}) | "
            f"{falhas} falha(s) enfileiradas para retry"
        )

    # Produção: CronTrigger(day=1, hour=6)  → dia 1 de cada mês às 06:00
    def fechar_periodo_contabil(self) -> None:
        mes = datetime.now().strftime("%B/%Y")
        logger.info(f"📒 [Contábil] Período {mes} fechado e exportado para ERP")


# ══════════════════════════════════════════════════════════════════════════════
# DOMÍNIO 5 — Conteúdo (DateTrigger)
# ══════════════════════════════════════════════════════════════════════════════

def publicar_conteudo_agendado(titulo: str, plataforma: str) -> None:
    logger.info(f"📣 [Conteúdo] Publicado em {plataforma}: \"{titulo}\"")


POSTS_AGENDADOS = [
    {"titulo": "5 tendências de tech para 2026",       "plataforma": "LinkedIn",   "delay": 6},
    {"titulo": "Lançamento: versão 3.0 disponível!",   "plataforma": "Twitter/X",  "delay": 11},
    {"titulo": "Bastidores do nosso produto",           "plataforma": "Instagram",  "delay": 16},
    {"titulo": "Webinar ao vivo — inscrições abertas", "plataforma": "YouTube",    "delay": 21},
]


# ══════════════════════════════════════════════════════════════════════════════
# Execução do exemplo
# ══════════════════════════════════════════════════════════════════════════════

def run() -> None:
    agora = datetime.now()

    print("\n" + "═" * 64)
    print("  Exemplo 5: Casos de Uso do Mundo Real")
    print("═" * 64)
    print("\n  Inicializando 5 domínios de negócio...\n")

    scheduler = BackgroundScheduler()

    ecommerce  = EcommerceService()
    analytics  = AnalyticsService()
    devops     = DevOpsService()
    financeiro = FinanceiroService()

    # ── E-commerce ────────────────────────────────────────────────────────────
    scheduler.add_job(ecommerce.processar_pedidos_pendentes, IntervalTrigger(seconds=5),  id="ecom_pedidos",   name="E-com: Processar Pedidos")
    scheduler.add_job(ecommerce.verificar_estoque_critico,   IntervalTrigger(seconds=8),  id="ecom_estoque",   name="E-com: Verificar Estoque")
    scheduler.add_job(ecommerce.renovar_cotacoes_frete,      IntervalTrigger(seconds=13), id="ecom_frete",     name="E-com: Renovar Frete")
    scheduler.add_job(ecommerce.importar_catalogo_fornecedor, CronTrigger(second="*/18"), id="ecom_catalogo",  name="E-com: Importar Catálogo")

    # ── Analytics / ETL ────────────────────────────────────────────────────────
    scheduler.add_job(analytics.executar_etl_incremental, IntervalTrigger(seconds=7),  id="etl",          name="Analytics: ETL Incremental")
    scheduler.add_job(analytics.atualizar_dashboards,     IntervalTrigger(seconds=10), id="dashboard",    name="Analytics: Dashboards")
    scheduler.add_job(analytics.gerar_relatorio_executivo, CronTrigger(second="*/15"), id="relat_exec",   name="Analytics: Relatório Executivo")
    scheduler.add_job(analytics.gerar_relatorio_semanal,   CronTrigger(second="*/22"), id="relat_semanal",name="Analytics: Relatório Semanal")

    # ── DevOps ────────────────────────────────────────────────────────────────
    scheduler.add_job(devops.health_check,                  IntervalTrigger(seconds=4),  id="health_check",   name="DevOps: Health Check")
    scheduler.add_job(devops.limpar_arquivos_temporarios,   CronTrigger(second="*/19"),  id="limpar_tmp",     name="DevOps: Limpar Temporários")
    scheduler.add_job(devops.rotacionar_credenciais,        CronTrigger(second="*/25"),  id="rotate_creds",   name="DevOps: Rotacionar Credenciais")
    scheduler.add_job(devops.verificar_certificados_ssl,    IntervalTrigger(seconds=12), id="check_ssl",      name="DevOps: Verificar SSL")

    # ── Financeiro ────────────────────────────────────────────────────────────
    scheduler.add_job(financeiro.conciliar_transacoes,            IntervalTrigger(seconds=9),  id="conciliacao",  name="Fin: Conciliação Bancária")
    scheduler.add_job(financeiro.processar_cobrancas_recorrentes, CronTrigger(second="*/14"),  id="cobrancas",    name="Fin: Cobranças Recorrentes")
    scheduler.add_job(financeiro.fechar_periodo_contabil,         CronTrigger(second="*/28"),  id="fech_contabil",name="Fin: Fechar Período Contábil")

    # ── Conteúdo (DateTrigger — publicações pontuais) ─────────────────────────
    for post in POSTS_AGENDADOS:
        scheduler.add_job(
            publicar_conteudo_agendado,
            trigger=DateTrigger(run_date=agora + timedelta(seconds=post["delay"])),
            kwargs={"titulo": post["titulo"], "plataforma": post["plataforma"]},
            id=f"post_{post['plataforma'].lower().split('/')[0]}",
            name=f"Conteúdo: {post['plataforma']}",
        )

    scheduler.start()

    total = len(scheduler.get_jobs())
    dominios_resumo = [
        ("E-commerce",    4, "pedidos, estoque, frete, catálogo"),
        ("Analytics/ETL", 4, "ETL, dashboard, 2× relatórios"),
        ("DevOps",        4, "health check, limpeza, SSL, credenciais"),
        ("Financeiro",    3, "conciliação, cobranças, contábil"),
        ("Conteúdo",      4, "publicações agendadas (DateTrigger)"),
    ]

    print(f"  {total} jobs ativos em 5 domínios:\n")
    for nome, qtd, descricao in dominios_resumo:
        print(f"    • {nome:<16} {qtd} jobs  —  {descricao}")

    print(f"\n  Executando por 32 segundos... (Ctrl+C para parar)\n")

    try:
        time.sleep(32)
    except KeyboardInterrupt:
        pass
    finally:
        scheduler.shutdown(wait=False)
        print(f"\n  {_alertas_disparados} alerta(s) de infraestrutura disparado(s) durante a execução.")
        print("  Scheduler encerrado.")
