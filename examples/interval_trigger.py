"""
Exemplo 1: IntervalTrigger — Agendamento por Intervalo
=======================================================
Executa tarefas repetidamente em intervalos regulares de tempo.

Parâmetros principais:
  weeks, days, hours, minutes, seconds  — define o intervalo
  start_date   — quando o job deve começar a ser agendado
  end_date     — quando o job deve parar de ser executado
  jitter       — variação aleatória (segundos) para evitar pico simultâneo
  max_instances — número máximo de instâncias paralelas do job

Casos de uso:
  ✔ Monitoramento de APIs e serviços (health check)
  ✔ Coleta periódica de métricas de sistema
  ✔ Sincronização incremental de dados entre sistemas
  ✔ Heartbeat / watchdog de serviços
  ✔ Refresh de cache em memória
"""

import time
import random
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─── Funções de trabalho (jobs) ────────────────────────────────────────────────

def monitorar_api() -> None:
    """Caso de uso: Health check de uma API REST externa."""
    status = random.choices(["OK", "LENTO", "ERRO"], weights=[80, 15, 5])[0]
    latency_ms = random.randint(40, 450)
    icons = {"OK": "✅", "LENTO": "⚠️ ", "ERRO": "❌"}
    logger.info(
        f"{icons[status]} [API Monitor] status={status} | latência={latency_ms}ms"
    )


_metrics_count = 0


def coletar_metricas() -> None:
    """Caso de uso: Coleta de métricas de sistema (CPU, RAM, disco)."""
    global _metrics_count
    _metrics_count += 1
    cpu = random.uniform(15.0, 90.0)
    mem = random.uniform(35.0, 80.0)
    disk = random.uniform(20.0, 60.0)
    logger.info(
        f"📊 [Métricas #{_metrics_count}] "
        f"CPU={cpu:.1f}% | RAM={mem:.1f}% | Disco={disk:.1f}%"
    )


def sincronizar_dados() -> None:
    """Caso de uso: Sincronização incremental com servidor remoto."""
    registros = random.randint(0, 200)
    if registros:
        logger.info(f"🔄 [Sync] {registros} registros sincronizados com o servidor")
    else:
        logger.info("🔄 [Sync] Nenhum registro novo — já sincronizado")


def enviar_heartbeat() -> None:
    """Caso de uso: Sinal de vida para sistema de monitoramento externo."""
    logger.info(f"💓 [Heartbeat] serviço-principal alive @ {datetime.now().isoformat()}")


def atualizar_cache() -> None:
    """Caso de uso: Invalidação e recarregamento de cache em memória."""
    itens = random.randint(50, 600)
    logger.info(f"🗄️  [Cache] {itens} entradas atualizadas no cache")


# ─── Execução do exemplo ────────────────────────────────────────────────────────

def run() -> None:
    print("\n" + "═" * 64)
    print("  Exemplo 1: IntervalTrigger — Agendamento por Intervalo")
    print("═" * 64)

    scheduler = BackgroundScheduler()

    # Job 1 — Health check a cada 3 s
    #   max_instances=1  → nunca roda duas instâncias ao mesmo tempo
    #   misfire_grace_time → tolera até 5 s de atraso antes de pular
    scheduler.add_job(
        monitorar_api,
        trigger=IntervalTrigger(seconds=3),
        id="api_monitor",
        name="Monitoramento de API",
        max_instances=1,
        misfire_grace_time=5,
    )

    # Job 2 — Métricas a cada 5 s com jitter ±1 s
    #   jitter → adiciona atraso aleatório para evitar pico de carga
    scheduler.add_job(
        coletar_metricas,
        trigger=IntervalTrigger(seconds=5, jitter=1),
        id="metrics_collector",
        name="Coleta de Métricas",
    )

    # Job 3 — Sync a cada 10 s, começa após 2 s
    #   start_date → adia o início do job
    scheduler.add_job(
        sincronizar_dados,
        trigger=IntervalTrigger(
            seconds=10,
            start_date=datetime.now() + timedelta(seconds=2),
        ),
        id="data_sync",
        name="Sincronização de Dados",
    )

    # Job 4 — Heartbeat a cada 4 s
    scheduler.add_job(
        enviar_heartbeat,
        trigger=IntervalTrigger(seconds=4),
        id="heartbeat",
        name="Heartbeat",
    )

    # Job 5 — Cache refresh a cada 8 s, para automaticamente em 22 s
    #   end_date → o job é removido depois dessa data
    scheduler.add_job(
        atualizar_cache,
        trigger=IntervalTrigger(
            seconds=8,
            end_date=datetime.now() + timedelta(seconds=22),
        ),
        id="cache_refresh",
        name="Cache Refresh (para em 22s)",
    )

    scheduler.start()

    print("\n  Jobs agendados:")
    for job in scheduler.get_jobs():
        print(f"    • [{job.id}] {job.name}")
        print(f"      Próxima execução: {job.next_run_time}")

    print("\n  Executando por 25 segundos... (Ctrl+C para parar)\n")

    try:
        time.sleep(25)
    except KeyboardInterrupt:
        pass
    finally:
        scheduler.shutdown(wait=False)
        print("\n  Scheduler encerrado.")
