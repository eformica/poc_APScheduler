"""
TaskChannel — protocolo de comunicação entre container de tarefa e orquestrador.
================================================================================
Usado DENTRO do container de tarefa para emitir eventos estruturados
para o orquestrador via stdout (protocolo JSON Lines).

Protocolo (JSON Lines):
  Uma linha JSON por evento. O orquestrador lê, parseia e persiste
  cada linha em tempo real na tabela 'container_task_logs'.

  Campos obrigatórios em todo evento:
    ts      → ISO 8601 UTC timestamp
    level   → INFO | WARNING | ERROR | DEBUG | METRIC | RESULT | RAW
    job_id  → ID do job (injetado via variável de ambiente JOB_ID)
    msg     → mensagem legível por humanos

  Campos opcionais (passados via **kwargs):
    Qualquer par chave-valor serializado junto ao evento.

  Evento RESULT (deve ser emitido EXATAMENTE UMA VEZ ao final):
    {"ts":"...","level":"RESULT","job_id":"...","msg":"status=success",
     "status":"success","records_processed":1000}

Uso típico dentro de um container:
─────────────────────────────────────────────
  #!/usr/bin/env python
  import sys
  from container_runner.channel import TaskChannel

  def main():
      ch = TaskChannel.from_env()          # lê JOB_ID do ambiente
      ch.info("Iniciando processamento")
      try:
          records = process_data()
          ch.info("Concluído", records=records)
          ch.metric("records_processed", records)
          ch.emit_result("success", records_processed=records)
      except Exception as exc:
          ch.error(str(exc))
          ch.emit_result("error", error=str(exc))
          sys.exit(1)

  if __name__ == "__main__":
      main()
─────────────────────────────────────────────
Dependências: apenas stdlib (json, os, sys, datetime).
Pode ser copiado/instalado em qualquer imagem Docker.
"""

import json
import os
import sys
from datetime import datetime, timezone
from typing import IO, Any, Optional


class TaskChannel:
    """
    Emite eventos JSON estruturados para stdout, capturado em tempo real
    pelo ContainerRunner no orquestrador.

    Thread-safe: print() em CPython é GIL-protected, garantindo
    que linhas JSON não sejam intercaladas entre threads.
    """

    def __init__(self, job_id: str, *, out: Optional[IO[str]] = None) -> None:
        """
        Args:
            job_id : Identificador único do job — mesmo ID usado no APScheduler.
            out    : Stream de saída (padrão: sys.stdout). Útil para testes unitários.
        """
        self.job_id = job_id
        self._out = out or sys.stdout
        self._result_emitted = False

    @classmethod
    def from_env(cls) -> "TaskChannel":
        """
        Cria um TaskChannel lendo job_id da variável de ambiente JOB_ID.

        O ContainerRunner injeta JOB_ID automaticamente ao lançar o container.
        Lança EnvironmentError se JOB_ID não estiver definida.
        """
        job_id = os.environ.get("JOB_ID", "").strip()
        if not job_id:
            raise EnvironmentError(
                "Variável de ambiente 'JOB_ID' não encontrada.\n"
                "Defina via:  docker run -e JOB_ID=<id> <image>\n"
                "ou use ContainerRunner, que injeta automaticamente."
            )
        return cls(job_id=job_id)

    # ── Emissão interna ────────────────────────────────────────────────────────

    def _emit(self, level: str, msg: str, **extra: Any) -> None:
        """Serializa e escreve um evento JSON em uma única linha para stdout."""
        event: dict[str, Any] = {
            "ts":     datetime.now(timezone.utc).isoformat(),
            "level":  level,
            "job_id": self.job_id,
            "msg":    msg,
        }
        event.update(extra)
        try:
            print(json.dumps(event, default=str), flush=True, file=self._out)
        except Exception as write_err:
            # Falha no canal NUNCA interrompe a execução da task
            print(
                f"[TaskChannel:write_error] {write_err}",
                file=sys.stderr,
                flush=True,
            )

    # ── API pública de log ─────────────────────────────────────────────────────

    def debug(self, msg: str, **extra: Any) -> None:
        """Mensagem de depuração (filtrada por padrão no orquestrador)."""
        self._emit("DEBUG", msg, **extra)

    def info(self, msg: str, **extra: Any) -> None:
        """Progresso e informações sobre a execução."""
        self._emit("INFO", msg, **extra)

    def warning(self, msg: str, **extra: Any) -> None:
        """Situação de atenção que não interrompe a execução."""
        self._emit("WARNING", msg, **extra)

    def error(self, msg: str, **extra: Any) -> None:
        """
        Erro que impactou a execução.
        Deve ser seguido de emit_result('error') e sys.exit(1).
        """
        self._emit("ERROR", msg, **extra)

    def metric(self, name: str, value: float, **labels: Any) -> None:
        """
        Emite uma métrica nomeada para coleta pelo orquestrador.

        Exemplo:
            ch.metric("records_processed", 1000, source="orders_db")
            ch.metric("latency_ms", 342.5, endpoint="/api/v1/users")
        """
        self._emit("METRIC", f"{name}={value}", metric_name=name, value=value, **labels)

    # ── Resultado final ────────────────────────────────────────────────────────

    def emit_result(self, status: str, **metadata: Any) -> None:
        """
        Emite o resultado final da execução.
        DEVE ser chamado exatamente UMA VEZ, ao final da função main().

        Args:
            status   : 'success' ou 'error'
            metadata : Pares chave-valor arbitrários persistidos no banco
                       (ex: records_processed=1000, duration_ms=342).

        Comportamento:
            - Chamadas repetidas geram um WARNING e são ignoradas.
            - Status inválido gera um WARNING mas é persistido mesmo assim.
        """
        if self._result_emitted:
            self.warning("emit_result chamado mais de uma vez — ignorando chamada extra")
            return

        if status not in ("success", "error"):
            self.warning(
                f"status inválido '{status}' em emit_result "
                "— use 'success' ou 'error'"
            )

        self._result_emitted = True
        self._emit("RESULT", f"status={status}", status=status, **metadata)
