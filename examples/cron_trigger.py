"""
Exemplo 2: CronTrigger — Agendamento Estilo Cron
=================================================
Executa tarefas em horários/dias específicos, como o cron do Unix.

Campos do CronTrigger (todos opcionais, padrão = '*'):
  year, month, day, week, day_of_week, hour, minute, second

Sintaxe de expressão:
  *        → qualquer valor
  */N      → a cada N unidades
  a-b      → intervalo de a até b
  a,b,c    → múltiplos valores
  mon-fri  → segunda a sexta

Casos de uso:
  ✔ Relatório diário às 08:00
  ✔ Backup noturno à meia-noite
  ✔ Limpeza de logs toda segunda-feira às 02:00
  ✔ Folha de pagamento no dia 5 de cada mês
  ✔ Digest de e-mail em horário comercial (seg-sex, hora em hora)
"""

import time
import random
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─── Funções de trabalho ────────────────────────────────────────────────────────

def gerar_relatorio_diario() -> None:
    """Produção: CronTrigger(hour=8, minute=0)  → todo dia às 08:00"""
    linhas = random.randint(200, 5000)
    arquivo = f"reports/daily_{datetime.now().strftime('%Y%m%d')}.csv"
    logger.info(f"📄 [Relatório Diário] {linhas} registros exportados → {arquivo}")


def backup_banco_dados() -> None:
    """Produção: CronTrigger(hour=0, minute=0)  → meia-noite diária"""
    tamanho_mb = random.randint(80, 1200)
    arquivo = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql.gz"
    logger.info(f"💾 [Backup DB] {arquivo} ({tamanho_mb} MB)")


def limpeza_logs_antigos() -> None:
    """Produção: CronTrigger(day_of_week='mon', hour=2)  → segunda às 02:00"""
    arquivos = random.randint(30, 300)
    mb = random.randint(50, 800)
    logger.info(f"🗑️  [Limpeza] {arquivos} arquivos removidos ({mb} MB liberados)")


def processar_folha_pagamento() -> None:
    """Produção: CronTrigger(day=5, hour=6, minute=0)  → dia 5 do mês às 06:00"""
    funcionarios = random.randint(50, 2000)
    logger.info(f"💰 [Folha] Processado para {funcionarios} funcionários")


def enviar_digest_email() -> None:
    """Produção: CronTrigger(day_of_week='mon-fri', hour='9-17', minute=0)
       → seg-sex, hora em hora, das 09:00 às 17:00"""
    destinatarios = random.randint(10, 5000)
    logger.info(f"📧 [E-mail Digest] Enviado para {destinatarios} destinatários")


def verificar_expiracoes() -> None:
    """Produção: CronTrigger(hour='*/6')  → a cada 6 horas"""
    expirados = random.randint(0, 15)
    logger.info(
        f"🔑 [Expirações] {expirados} token(s)/certificado(s) a expirar detectados"
    )


# ─── Referência de configurações de produção ──────────────────────────────────

PRODUCAO_REF = [
    ("Relatório Diário",      "CronTrigger(hour=8, minute=0)"),
    ("Backup Noturno",        "CronTrigger(hour=0, minute=0)"),
    ("Limpeza Semanal",       "CronTrigger(day_of_week='mon', hour=2)"),
    ("Folha de Pagamento",    "CronTrigger(day=5, hour=6)"),
    ("Digest de E-mail",      "CronTrigger(day_of_week='mon-fri', hour='9-17', minute=0)"),
    ("Verificar Expirações",  "CronTrigger(hour='*/6')"),
]


# ─── Execução do exemplo ────────────────────────────────────────────────────────

def run() -> None:
    print("\n" + "═" * 64)
    print("  Exemplo 2: CronTrigger — Agendamento Estilo Cron")
    print("═" * 64)

    print("\n  Configurações de produção (referência):")
    for nome, trigger_str in PRODUCAO_REF:
        print(f"    • {nome:<25} → {trigger_str}")

    print("\n  DEMO: usando second='*/N' para visualização imediata\n")

    scheduler = BackgroundScheduler()

    # DEMO: a cada 6 s  |  Produção: hour=8, minute=0
    scheduler.add_job(
        gerar_relatorio_diario,
        trigger=CronTrigger(second="*/6"),
        id="relatorio_diario",
        name="Relatório Diário        [demo: */6s | prod: hour=8]",
        max_instances=1,
    )

    # DEMO: a cada 9 s  |  Produção: hour=0, minute=0
    scheduler.add_job(
        backup_banco_dados,
        trigger=CronTrigger(second="*/9"),
        id="backup_noturno",
        name="Backup Noturno          [demo: */9s | prod: hour=0]",
        max_instances=1,
    )

    # DEMO: a cada 11 s  |  Produção: day_of_week='mon', hour=2
    scheduler.add_job(
        limpeza_logs_antigos,
        trigger=CronTrigger(second="*/11"),
        id="limpeza_logs",
        name="Limpeza Semanal         [demo: */11s | prod: day_of_week='mon']",
    )

    # DEMO: a cada 14 s  |  Produção: day=5, hour=6
    scheduler.add_job(
        processar_folha_pagamento,
        trigger=CronTrigger(second="*/14"),
        id="folha_pagamento",
        name="Folha de Pagamento      [demo: */14s | prod: day=5, hour=6]",
    )

    # DEMO: a cada 7 s  |  Produção: day_of_week='mon-fri', hour='9-17', minute=0
    scheduler.add_job(
        enviar_digest_email,
        trigger=CronTrigger(second="*/7"),
        id="email_digest",
        name="E-mail Digest           [demo: */7s | prod: mon-fri 09-17]",
    )

    # DEMO: a cada 12 s  |  Produção: hour='*/6'
    scheduler.add_job(
        verificar_expiracoes,
        trigger=CronTrigger(second="*/12"),
        id="check_expiracoes",
        name="Verificar Expirações    [demo: */12s | prod: hour='*/6']",
    )

    scheduler.start()

    print("  Jobs agendados:")
    for job in scheduler.get_jobs():
        print(f"    • {job.name}")
        print(f"      Próxima execução: {job.next_run_time}")

    print("\n  Executando por 28 segundos... (Ctrl+C para parar)\n")

    try:
        time.sleep(28)
    except KeyboardInterrupt:
        pass
    finally:
        scheduler.shutdown(wait=False)
        print("\n  Scheduler encerrado.")
