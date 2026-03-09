"""
Exemplo de task containerizada — entrypoint do container de tarefa.
====================================================================
Este arquivo é o __main__ de uma imagem Docker SEPARADA do orquestrador.
Ele demonstra como escrever uma task que usa TaskChannel para se comunicar
com o ContainerRunner no orquestrador.

Dockerfile de exemplo para esta task:
──────────────────────────────────────
  FROM python:3.13-slim
  ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY . .
  CMD ["python", "-m", "tasks.containerized_example"]
──────────────────────────────────────

Registro no orquestrador (scheduler/registry.py):
──────────────────────────────────────────────────
  from container_runner.config import ContainerJobConfig, register_container_jobs
  from apscheduler.triggers.interval import IntervalTrigger

  container_jobs = [
      ContainerJobConfig(
          id="etl_containerizado",
          name="ETL: Pipeline Containerizado",
          image="myorg/etl-task:latest",
          trigger=IntervalTrigger(minutes=30),
          env_vars={"BATCH_SIZE": "500", "SOURCE_DB": "postgresql://..."},
          timeout=300,
      ),
  ]
  register_container_jobs(scheduler, container_jobs)
──────────────────────────────────────────────────

O orquestrador:
  1. Injeta JOB_ID e JOB_NAME como env vars
  2. Inicia o container e lê seu stdout linha a linha
  3. Parseia os JSON Lines emitidos por TaskChannel
  4. Persiste cada linha em 'container_task_logs'
  5. Persiste o resumo em 'job_execution_logs'
"""

import random
import sys
import time

from container_runner.channel import TaskChannel


# ── Simulação de lógica de negócio ────────────────────────────────────────────

def extract_data(ch: TaskChannel, batch_size: int) -> list[dict]:
    """Simula extração de dados de uma fonte (DB, API, S3...)."""
    ch.info("Conectando à fonte de dados...", source="orders_db")
    time.sleep(0.1)

    # Simula falha de conexão (8% de chance)
    if random.random() < 0.08:
        raise ConnectionError(
            "orders_db: connection refused (host=db-primary, port=5432)"
        )

    records = [{"id": i, "value": round(random.uniform(10, 999), 2)} for i in range(batch_size)]
    ch.info(f"{len(records)} registros extraídos", source="orders_db", count=len(records))
    return records


def transform_data(ch: TaskChannel, records: list[dict]) -> tuple[list[dict], int]:
    """Simula transformação e validação dos registros."""
    ch.info("Aplicando transformações...")
    rejected = 0
    valid = []
    for r in records:
        if r["value"] < 15.0:    # regra de negócio: rejeita valores muito baixos
            rejected += 1
        else:
            r["value_brl"] = round(r["value"] * 5.70, 2)   # simulação de câmbio
            valid.append(r)

    if rejected:
        ch.warning(f"{rejected} registro(s) rejeitados por valor abaixo do mínimo")
    ch.metric("records_rejected", rejected)
    ch.metric("records_valid", len(valid))
    return valid, rejected


def load_data(ch: TaskChannel, records: list[dict]) -> int:
    """Simula carregamento no Data Warehouse."""
    ch.info(f"Carregando {len(records)} registros no DW...")
    time.sleep(0.05)

    # Simula erro de schema (5% de chance)
    if random.random() < 0.05:
        raise ValueError(
            "Schema mismatch: coluna 'value_brl' não encontrada na tabela destino"
        )

    ch.info("Carga concluída com sucesso", destination="dw.orders_fact")
    return len(records)


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main() -> None:
    """
    Entrypoint da task containerizada.

    Padrão recomendado:
      1. Criar o canal via from_env() (lê JOB_ID automaticamente)
      2. Emitir info/warning/metric durante a execução
      3. Sempre encerrar com emit_result('success'|'error')
      4. sys.exit(1) em caso de erro (sinaliza falha para o orquestrador)
    """
    ch = TaskChannel.from_env()

    ch.info("╔══════════════════════════════════════╗")
    ch.info("║  ETL Containerizado — iniciando      ║")
    ch.info("╚══════════════════════════════════════╝")

    batch_size = 200

    try:
        # ── Extração ──────────────────────────────────────────────────────
        records = extract_data(ch, batch_size)

        # ── Transformação ─────────────────────────────────────────────────
        valid_records, rejected = transform_data(ch, records)

        # ── Carga ─────────────────────────────────────────────────────────
        loaded = load_data(ch, valid_records)

        # ── Métricas finais ────────────────────────────────────────────────
        ch.metric("records_extracted", len(records))
        ch.metric("records_loaded", loaded)
        ch.info(
            "Pipeline concluído",
            extracted=len(records),
            loaded=loaded,
            rejected=rejected,
        )

        # ── Resultado: sucesso ─────────────────────────────────────────────
        ch.emit_result(
            "success",
            records_extracted=len(records),
            records_loaded=loaded,
            records_rejected=rejected,
        )

    except ConnectionError as exc:
        ch.error(f"Falha de conexão: {exc}", error_type="ConnectionError")
        ch.emit_result("error", error=str(exc), stage="extract")
        sys.exit(1)

    except ValueError as exc:
        ch.error(f"Erro de schema: {exc}", error_type="ValueError")
        ch.emit_result("error", error=str(exc), stage="load")
        sys.exit(1)

    except Exception as exc:
        ch.error(f"Erro inesperado: {exc}", error_type=type(exc).__name__)
        ch.emit_result("error", error=str(exc), stage="unknown")
        sys.exit(1)


if __name__ == "__main__":
    main()
