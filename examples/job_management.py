"""
Exemplo 4: Gerenciamento de Jobs
=================================
Demonstra operações dinâmicas sobre jobs em tempo real.

API de gerenciamento:
  scheduler.add_job()          → adiciona um novo job
  scheduler.get_job(id)        → obtém job pelo ID
  scheduler.get_jobs()         → lista todos os jobs
  scheduler.pause_job(id)      → pausa (não perde o schedule)
  scheduler.resume_job(id)     → retoma job pausado
  scheduler.reschedule_job()   → substitui o trigger do job
  scheduler.modify_job()       → altera propriedades (kwargs, max_instances…)
  scheduler.remove_job(id)     → remove definitivamente
  scheduler.remove_all_jobs()  → remove todos os jobs
  scheduler.pause() / resume() → pausa/retoma o scheduler inteiro

Casos de uso:
  ✔ Painel de controle de agendamentos via API REST
  ✔ Feature flags para ativar/desativar tarefas em produção
  ✔ Manutenção dinâmica de schedules sem restart
  ✔ Reconfiguração de frequência com base em carga
"""

import time
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─── Funções de trabalho ────────────────────────────────────────────────────────

def processar_pedidos(versao: str = "v1") -> None:
    logger.info(f"🛍️  [Pedidos {versao}] Processando pedidos pendentes...")


def gerar_relatorio() -> None:
    logger.info(f"📊 [Relatório] Gerando relatório de vendas...")


def enviar_notificacoes() -> None:
    logger.info(f"📬 [Notificações] Enviando notificações pendentes...")


def sincronizar_estoque() -> None:
    logger.info(f"📦 [Estoque] Sincronizando estoque com ERP...")


# ─── Utilitário de visualização ────────────────────────────────────────────────

def tabela_jobs(scheduler: BackgroundScheduler, titulo: str = "Jobs ativos") -> None:
    """Imprime uma tabela com o estado atual de todos os jobs."""
    jobs = scheduler.get_jobs()
    print(f"\n  ── {titulo} {'─' * max(0, 42 - len(titulo))}")
    if not jobs:
        print("    (nenhum job registrado)")
    else:
        for job in jobs:
            if job.next_run_time is None:
                status = "⏸  PAUSADO"
            else:
                status = f"▶  próx: {job.next_run_time.strftime('%H:%M:%S')}"
            print(f"    [{job.id:<20}] {job.name:<30} {status}")
    print()


# ─── Execução do exemplo ────────────────────────────────────────────────────────

def run() -> None:
    print("\n" + "═" * 64)
    print("  Exemplo 4: Gerenciamento de Jobs")
    print("═" * 64)

    scheduler = BackgroundScheduler()
    scheduler.start()

    # ── Passo 1: add_job — adicionar jobs ───────────────────────────────────────
    print("\n  [1/8] add_job — adicionando 3 jobs...")

    scheduler.add_job(
        processar_pedidos,
        trigger=IntervalTrigger(seconds=3),
        kwargs={"versao": "v1"},
        id="pedidos",
        name="Processar Pedidos",
    )
    scheduler.add_job(
        gerar_relatorio,
        trigger=IntervalTrigger(seconds=4),
        id="relatorio",
        name="Gerar Relatório",
    )
    scheduler.add_job(
        enviar_notificacoes,
        trigger=IntervalTrigger(seconds=5),
        id="notificacoes",
        name="Enviar Notificações",
    )

    tabela_jobs(scheduler, "Após add_job (3 jobs)")
    time.sleep(7)

    # ── Passo 2: pause_job — pausar um job ─────────────────────────────────────
    print("  [2/8] pause_job — pausando 'relatorio'...")
    scheduler.pause_job("relatorio")
    tabela_jobs(scheduler, "Após pause_job('relatorio')")
    time.sleep(6)

    # ── Passo 3: resume_job — retomar job pausado ──────────────────────────────
    print("  [3/8] resume_job — retomando 'relatorio'...")
    scheduler.resume_job("relatorio")
    tabela_jobs(scheduler, "Após resume_job('relatorio')")
    time.sleep(5)

    # ── Passo 4: reschedule_job — alterar trigger ──────────────────────────────
    print("  [4/8] reschedule_job — 'notificacoes' de 5s → 2s...")
    scheduler.reschedule_job("notificacoes", trigger=IntervalTrigger(seconds=2))
    tabela_jobs(scheduler, "Após reschedule_job('notificacoes', seconds=2)")
    time.sleep(6)

    # ── Passo 5: modify_job — alterar propriedades ─────────────────────────────
    print("  [5/8] modify_job — atualizando kwargs de 'pedidos' para v2...")
    scheduler.modify_job("pedidos", kwargs={"versao": "v2"}, max_instances=3)
    logger.info("  🔧 job 'pedidos' modificado: versao=v2, max_instances=3")
    time.sleep(5)

    # ── Passo 6: add_job dinâmico (em runtime) ─────────────────────────────────
    print("  [6/8] add_job dinâmico — adicionando 'estoque' em runtime...")
    scheduler.add_job(
        sincronizar_estoque,
        trigger=CronTrigger(second="*/3"),
        id="estoque",
        name="Sincronizar Estoque",
    )
    tabela_jobs(scheduler, "Após add_job dinâmico (4 jobs)")
    time.sleep(6)

    # ── Passo 7: remove_job — remover job específico ───────────────────────────
    print("  [7/8] remove_job — removendo 'estoque'...")
    scheduler.remove_job("estoque")
    tabela_jobs(scheduler, "Após remove_job('estoque')")
    time.sleep(4)

    # ── Passo 8: remove_all_jobs — limpar tudo ─────────────────────────────────
    print("  [8/8] remove_all_jobs — removendo todos os jobs...")
    scheduler.remove_all_jobs()
    tabela_jobs(scheduler, "Após remove_all_jobs")

    # ── Bônus: pause/resume do scheduler inteiro ──────────────────────────────
    print("  [Bônus] Pausando o scheduler inteiro por 2s e retomando...")
    scheduler.pause()
    logger.info("  ⏸  Scheduler pausado")
    time.sleep(2)
    scheduler.resume()
    logger.info("  ▶  Scheduler retomado (sem jobs, nada executa)")

    time.sleep(1)
    scheduler.shutdown(wait=False)
    print("\n  Scheduler encerrado.")
