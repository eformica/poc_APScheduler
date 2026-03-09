"""
ContainerRunner — lança tarefas em containers Docker isolados.
==============================================================
Usado pelo ORQUESTRADOR (scheduler) para executar tasks containerizadas.

Fluxo de execução:
  1. Constrói o comando 'docker run' com variáveis de ambiente injetadas
  2. Lança o container como subprocesso
  3. Lê stdout linha a linha em tempo real (thread dedicada)
  4. Parseia JSON Lines emitidas pelo TaskChannel dentro do container
  5. Persiste cada linha individualmente em 'container_task_logs'
  6. Ao encerrar, persiste o resumo em 'job_execution_logs'
  7. Retorna um TaskResult com status, duração e linhas capturadas

Requisitos Docker (Docker-outside-of-Docker):
  O container do orquestrador precisa acessar o socket do Docker host:
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
  Ver docker-compose.yml para a configuração completa.

Resiliência:
  - Falhas de persistência NUNCA derrubam o scheduler.
  - Timeout → container é encerrado via SIGKILL.
  - Docker CLI ausente → erro reportado imediatamente com mensagem clara.
  - Linhas não-JSON (plain text) são capturadas com level='RAW'.
"""

import json
import logging
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

_RESULT_LEVEL = "RESULT"


# ── Resultado da execução ──────────────────────────────────────────────────────

@dataclass
class TaskResult:
    """Resultado completo de uma execução de container."""

    job_id: str
    job_name: str
    status: str                                  # 'success' | 'error'
    exit_code: int
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    log_lines: list[dict] = field(default_factory=list)
    error_message: Optional[str] = None
    result_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status == "success"


# ── Utilitário de timestamp ────────────────────────────────────────────────────

def _parse_ts(ts_str: Optional[str]) -> datetime:
    """Converte string ISO 8601 para datetime com timezone. Fallback para UTC now."""
    if not ts_str:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(ts_str)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


# ── Runner principal ───────────────────────────────────────────────────────────

class ContainerRunner:
    """
    Lança um container Docker para executar uma task isolada,
    faz streaming dos logs em tempo real e persiste os resultados
    no PostgreSQL.

    Args:
        job_id      : ID do job no APScheduler (injetado como JOB_ID no container)
        job_name    : Nome legível do job (injetado como JOB_NAME no container)
        image       : Imagem Docker (ex: 'myorg/etl-task:latest')
        command     : Override do CMD da imagem (lista de strings)
        env_vars    : Variáveis de ambiente adicionais para o container
        timeout     : Tempo máximo de execução em segundos (padrão: 300)
        network     : Rede Docker para o container (padrão: 'host')
        docker_cmd  : Executável do Docker CLI (padrão: 'docker')
    """

    def __init__(
        self,
        job_id: str,
        job_name: str,
        image: str,
        *,
        command: Optional[list[str]] = None,
        env_vars: Optional[dict[str, str]] = None,
        timeout: int = 300,
        network: str = "host",
        docker_cmd: str = "docker",
    ) -> None:
        self.job_id     = job_id
        self.job_name   = job_name
        self.image      = image
        self.command    = command or []
        self.env_vars   = env_vars or {}
        self.timeout    = timeout
        self.network    = network
        self.docker_cmd = docker_cmd

    # ── Construção do comando ──────────────────────────────────────────────────

    def _build_docker_args(self) -> list[str]:
        """Constrói a lista completa de argumentos para 'docker run'."""
        args = [
            self.docker_cmd, "run",
            "--rm",                         # remove o container após encerrar
            "--init",                        # tini como PID 1 (graceful SIGTERM)
            f"--network={self.network}",
            # Variáveis padrão injetadas automaticamente
            "-e", f"JOB_ID={self.job_id}",
            "-e", f"JOB_NAME={self.job_name}",
        ]
        for key, value in self.env_vars.items():
            args += ["-e", f"{key}={value}"]
        args.append(self.image)
        args.extend(self.command)
        return args

    # ── Parsing de linha ───────────────────────────────────────────────────────

    def _parse_line(self, raw: str) -> Optional[dict]:
        """
        Parseia uma linha de stdout do container como JSON.
        Retorna None para linhas vazias.
        Linhas não-JSON são embrulhadas como evento RAW (não descartadas).
        """
        raw = raw.strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {
                "ts":     datetime.now(timezone.utc).isoformat(),
                "level":  "RAW",
                "job_id": self.job_id,
                "msg":    raw,
            }

    # ── Relay de log para o logger do orquestrador ─────────────────────────────

    def _relay(self, parsed: dict) -> None:
        """Retransmite o evento para o logger do orquestrador (stdout do scheduler)."""
        level = parsed.get("level", "RAW")
        msg   = parsed.get("msg", "")
        prefix = f"  ↳ [{self.job_id}]"
        if level == "ERROR":
            logger.error(f"{prefix} {msg}")
        elif level == "WARNING":
            logger.warning(f"{prefix} {msg}")
        elif level == _RESULT_LEVEL:
            logger.info(f"{prefix} 📋 resultado: {msg}")
        elif level != "DEBUG":
            logger.info(f"{prefix} {msg}")

    # ── Persistência ───────────────────────────────────────────────────────────

    def _persist_log_lines(self, log_lines: list[dict]) -> None:
        """Persiste as linhas individuais em 'container_task_logs'."""
        if not log_lines:
            return
        try:
            from db.models import ContainerTaskLog
            from db.session import SessionLocal

            with SessionLocal() as session:
                for line in log_lines:
                    extra = {
                        k: v for k, v in line.items()
                        if k not in ("ts", "level", "job_id", "msg")
                    }
                    session.add(
                        ContainerTaskLog(
                            job_id=line.get("job_id", self.job_id),
                            job_name=self.job_name,
                            level=line.get("level", "RAW"),
                            message=line.get("msg", ""),
                            extra=extra if extra else None,
                            emitted_at=_parse_ts(line.get("ts")),
                        )
                    )
                session.commit()
        except Exception as exc:
            logger.error(
                f"[ContainerRunner] falha ao persistir logs de '{self.job_id}': {exc}"
            )

    def _persist_summary(self, result: TaskResult) -> None:
        """Persiste o resumo da execução em 'job_execution_logs'."""
        try:
            from db.models import JobExecutionLog
            from db.session import SessionLocal

            full_output = "\n".join(
                f"[{ln.get('level','RAW')}] {ln.get('msg','')}"
                for ln in result.log_lines
            )
            with SessionLocal() as session:
                session.add(
                    JobExecutionLog(
                        job_id=result.job_id,
                        job_name=result.job_name,
                        started_at=result.started_at,
                        finished_at=result.finished_at,
                        status=result.status,
                        error_type="ContainerError" if result.status == "error" else None,
                        error_message=result.error_message,
                        traceback=full_output or None,
                        duration_ms=result.duration_ms,
                    )
                )
                session.commit()
        except Exception as exc:
            logger.error(
                f"[ContainerRunner] falha ao persistir summary de '{self.job_id}': {exc}"
            )

    # ── Execução principal ─────────────────────────────────────────────────────

    def run(self) -> TaskResult:
        """
        Lança o container, faz streaming dos logs e aguarda a conclusão.

        O stdout do container é lido em uma thread dedicada para permitir
        o timeout via proc.wait(timeout=N) na thread principal.

        Retorna um TaskResult com status, duração e linhas coletadas.
        Nunca levanta exceção — erros são capturados e retornados no result.
        """
        docker_args = self._build_docker_args()
        started_at  = datetime.now(timezone.utc)
        log_lines: list[dict] = []
        error_message: Optional[str] = None
        result_metadata: dict[str, Any] = {}
        exit_code: int = -1

        logger.info(
            f"[{self.job_id}] 🐳 Lançando container: {self.image}"
        )
        logger.debug(f"[{self.job_id}] cmd: {' '.join(docker_args)}")

        try:
            proc = subprocess.Popen(
                docker_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,   # stderr → stdout (captura tudo)
                text=True,
                bufsize=1,                  # line-buffered
            )

            # ── Thread de leitura: não bloqueia o timeout ──────────────────
            def _read_stdout() -> None:
                for raw_line in proc.stdout:  # type: ignore[union-attr]
                    parsed = self._parse_line(raw_line)
                    if parsed is None:
                        continue
                    log_lines.append(parsed)
                    self._relay(parsed)
                    # Captura metadados do evento RESULT
                    if parsed.get("level") == _RESULT_LEVEL:
                        result_metadata.update({
                            k: v for k, v in parsed.items()
                            if k not in ("ts", "level", "job_id", "msg")
                        })
                    # Registra última mensagem de erro para o summary
                    if parsed.get("level") == "ERROR":
                        nonlocal error_message
                        error_message = parsed.get("msg")

            reader = threading.Thread(target=_read_stdout, daemon=True)
            reader.start()

            # ── Timeout: aguarda na thread principal ───────────────────────
            try:
                exit_code = proc.wait(timeout=self.timeout)
                reader.join(timeout=5)       # aguarda flush final dos logs
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                exit_code = -1
                error_message = (
                    f"Container encerrado por timeout ({self.timeout}s)"
                )
                logger.error(f"[{self.job_id}] ⏰ {error_message}")

        except FileNotFoundError:
            error_message = (
                f"Docker CLI não encontrado ('{self.docker_cmd}'). "
                "Verifique se o Docker está instalado e no PATH."
            )
            logger.error(f"[{self.job_id}] ❌ {error_message}")

        except Exception as exc:
            error_message = f"Erro inesperado ao lançar container: {exc}"
            logger.error(f"[{self.job_id}] ❌ {error_message}")

        # ── Monta resultado ────────────────────────────────────────────────
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        status = "success" if exit_code == 0 else "error"

        if exit_code != 0 and not error_message:
            error_message = f"Container encerrou com exit code {exit_code}"

        result = TaskResult(
            job_id=self.job_id,
            job_name=self.job_name,
            status=status,
            exit_code=exit_code,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            log_lines=log_lines,
            error_message=error_message,
            result_metadata=result_metadata,
        )

        # ── Persiste tudo no PostgreSQL ────────────────────────────────────
        self._persist_log_lines(log_lines)
        self._persist_summary(result)

        icon = "✅" if result.success else "❌"
        (logger.info if result.success else logger.error)(
            f"[{self.job_id}] {icon} container finalizado | "
            f"status={status} | exit={exit_code} | {duration_ms}ms"
        )

        return result
