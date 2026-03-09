"""
Exemplo 3: DateTrigger — Execução Única em Data/Hora Específica
===============================================================
Executa uma tarefa UMA ÚNICA VEZ em um momento determinado.
Após a execução, o job é automaticamente removido do scheduler.

Parâmetros:
  run_date  → datetime, date ou string ISO 8601
  timezone  → fuso horário (ex: 'America/Sao_Paulo')

Casos de uso:
  ✔ Notificações push agendadas pelo usuário
  ✔ Publicação de conteúdo em redes sociais
  ✔ Janelas de manutenção programadas
  ✔ Lembretes de carrinho abandonado
  ✔ E-mail de boas-vindas com delay (melhora UX)
  ✔ Processamento pós-pagamento
  ✔ Campanhas de marketing em horário programado
"""

import time
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─── Funções de trabalho ────────────────────────────────────────────────────────

def enviar_notificacao(usuario: str, mensagem: str) -> None:
    """Notificação push para o usuário no momento agendado."""
    logger.info(f"🔔 [Notificação] → {usuario}: \"{mensagem}\"")


def publicar_post(titulo: str, plataforma: str) -> None:
    """Publica conteúdo agendado em uma plataforma social."""
    logger.info(f"📢 [Publicação] \"{titulo}\" publicado no {plataforma}")


def iniciar_manutencao(servico: str) -> None:
    """Abre janela de manutenção de um serviço."""
    logger.info(f"🔧 [Manutenção] Janela iniciada — {servico} em modo de manutenção")


def encerrar_manutencao(servico: str) -> None:
    """Encerra a janela de manutenção e sobe o serviço."""
    logger.info(f"✅ [Manutenção] {servico} de volta ao ar")


def processar_cobranca(pedido_id: str, valor: float) -> None:
    """Processa a cobrança de um pedido após confirmação."""
    logger.info(f"💳 [Cobrança] Pedido #{pedido_id}: R$ {valor:.2f} processado")


def enviar_email_boas_vindas(nome: str, email: str) -> None:
    """E-mail de boas-vindas enviado alguns segundos após o cadastro."""
    logger.info(f"📧 [Boas-vindas] Enviado para {nome} <{email}>")


def lembrete_carrinho_abandonado(usuario_id: str, itens: int) -> None:
    """Lembrete enviado N horas após o abandono do carrinho."""
    logger.info(
        f"🛒 [Carrinho] Lembrete enviado para USR-{usuario_id} "
        f"({itens} item(ns) no carrinho)"
    )


def iniciar_campanha(campanha: str, canal: str) -> None:
    """Dispara campanha de marketing no horário agendado."""
    logger.info(f"🚀 [Campanha] \"{campanha}\" iniciada no canal: {canal}")


# ─── Execução do exemplo ────────────────────────────────────────────────────────

def run() -> None:
    agora = datetime.now()

    print("\n" + "═" * 64)
    print("  Exemplo 3: DateTrigger — Execução Única")
    print("═" * 64)
    print(f"\n  Hora atual: {agora.strftime('%H:%M:%S')}\n")

    scheduler = BackgroundScheduler()

    # Cada job é agendado para um momento específico no futuro
    jobs_demo = [
        {
            "func": enviar_notificacao,
            "kwargs": {"usuario": "Ana Lima", "mensagem": "Seu pedido #1042 foi confirmado!"},
            "delay": 3,
            "id": "notif_pedido",
            "name": "Notificação de Pedido",
        },
        {
            "func": enviar_email_boas_vindas,
            "kwargs": {"nome": "Carlos Souza", "email": "carlos@example.com"},
            "delay": 5,
            "id": "email_bvindas",
            "name": "E-mail de Boas-vindas",
        },
        {
            "func": publicar_post,
            "kwargs": {"titulo": "Promoção Imperdível — 50% OFF", "plataforma": "Instagram"},
            "delay": 7,
            "id": "post_instagram",
            "name": "Publicação Instagram",
        },
        {
            "func": publicar_post,
            "kwargs": {"titulo": "Novo artigo no blog: APScheduler na prática", "plataforma": "LinkedIn"},
            "delay": 9,
            "id": "post_linkedin",
            "name": "Publicação LinkedIn",
        },
        {
            "func": processar_cobranca,
            "kwargs": {"pedido_id": "ORD-20260309-7834", "valor": 349.90},
            "delay": 11,
            "id": "cobranca_pedido",
            "name": "Cobrança de Pedido",
        },
        {
            "func": iniciar_manutencao,
            "kwargs": {"servico": "API de Pagamentos v2"},
            "delay": 13,
            "id": "manut_inicio",
            "name": "Início de Manutenção",
        },
        {
            "func": lembrete_carrinho_abandonado,
            "kwargs": {"usuario_id": "58291", "itens": 3},
            "delay": 15,
            "id": "carrinho_lembrete",
            "name": "Lembrete Carrinho Abandonado",
        },
        {
            "func": iniciar_campanha,
            "kwargs": {"campanha": "Black Friday 2026", "canal": "E-mail + SMS"},
            "delay": 17,
            "id": "campanha_bf",
            "name": "Campanha Black Friday",
        },
        {
            "func": encerrar_manutencao,
            "kwargs": {"servico": "API de Pagamentos v2"},
            "delay": 20,
            "id": "manut_fim",
            "name": "Encerramento de Manutenção",
        },
    ]

    for job_def in jobs_demo:
        scheduler.add_job(
            job_def["func"],
            trigger=DateTrigger(run_date=agora + timedelta(seconds=job_def["delay"])),
            kwargs=job_def["kwargs"],
            id=job_def["id"],
            name=job_def["name"],
        )

    scheduler.start()

    print("  Jobs agendados (cada um executa UMA única vez):")
    for job in scheduler.get_jobs():
        run_at = job.next_run_time.strftime("%H:%M:%S") if job.next_run_time else "—"
        print(f"    • {job.name:<35} executa às {run_at}")

    print("\n  Aguardando execução de todos os jobs...\n")

    try:
        time.sleep(23)
    except KeyboardInterrupt:
        pass
    finally:
        scheduler.shutdown(wait=False)
        print("\n  Todos os jobs foram executados. Scheduler encerrado.")
