-- =============================================================
-- APScheduler Framework — Esquema PostgreSQL
-- =============================================================
-- Este script é executado automaticamente pelo container do
-- PostgreSQL na PRIMEIRA inicialização (via entrypoint-initdb.d).
--
-- Tabelas criadas aqui:
--   job_execution_logs  → log de cada execução de job
--
-- Tabelas criadas automaticamente pelo APScheduler:
--   apscheduler_jobs    → estado persistido dos jobs
-- =============================================================


-- ── Tabela principal de logs ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS job_execution_logs (
    id               BIGSERIAL     PRIMARY KEY,
    job_id           VARCHAR(255)  NOT NULL,
    job_name         VARCHAR(500),
    scheduled_at     TIMESTAMPTZ,
    started_at       TIMESTAMPTZ   NOT NULL,
    finished_at      TIMESTAMPTZ,
    status           VARCHAR(20)   NOT NULL
                         CHECK (status IN ('success', 'error', 'missed')),
    error_type       VARCHAR(255),
    error_message    TEXT,
    traceback        TEXT,
    duration_ms      INTEGER,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  job_execution_logs              IS 'Histórico de execuções dos jobs agendados';
COMMENT ON COLUMN job_execution_logs.job_id       IS 'ID do job no APScheduler';
COMMENT ON COLUMN job_execution_logs.status       IS 'success | error | missed';
COMMENT ON COLUMN job_execution_logs.duration_ms  IS 'Duração da execução em milissegundos';
COMMENT ON COLUMN job_execution_logs.traceback    IS 'Traceback completo em caso de erro';


-- ── Índices ───────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_jel_job_id
    ON job_execution_logs (job_id);

CREATE INDEX IF NOT EXISTS idx_jel_status
    ON job_execution_logs (status);

CREATE INDEX IF NOT EXISTS idx_jel_started_at
    ON job_execution_logs (started_at DESC);

CREATE INDEX IF NOT EXISTS idx_jel_job_status
    ON job_execution_logs (job_id, status);


-- ── View: última execução por job ─────────────────────────────────────────────

CREATE OR REPLACE VIEW v_last_job_executions AS
SELECT DISTINCT ON (job_id)
    job_id,
    job_name,
    scheduled_at,
    started_at,
    finished_at,
    status,
    error_type,
    error_message,
    duration_ms
FROM job_execution_logs
ORDER BY job_id, started_at DESC;

COMMENT ON VIEW v_last_job_executions IS
    'Última execução registrada para cada job';


-- ── View: resumo de erros por job ─────────────────────────────────────────────

CREATE OR REPLACE VIEW v_job_error_summary AS
SELECT
    job_id,
    job_name,
    error_type,
    COUNT(*)         AS error_count,
    MAX(started_at)  AS last_error_at,
    MIN(started_at)  AS first_error_at,
    ROUND(
        AVG(duration_ms)
    )                AS avg_duration_ms
FROM job_execution_logs
WHERE status = 'error'
GROUP BY job_id, job_name, error_type
ORDER BY error_count DESC;

COMMENT ON VIEW v_job_error_summary IS
    'Contagem e detalhes de erros agrupados por job e tipo de exceção';


-- ── View: taxa de sucesso nas últimas 24 horas ────────────────────────────────

CREATE OR REPLACE VIEW v_job_success_rate_24h AS
SELECT
    job_id,
    job_name,
    COUNT(*)                                                         AS total,
    COUNT(*) FILTER (WHERE status = 'success')                      AS successes,
    COUNT(*) FILTER (WHERE status = 'error')                        AS errors,
    COUNT(*) FILTER (WHERE status = 'missed')                       AS missed,
    ROUND(
        100.0
        * COUNT(*) FILTER (WHERE status = 'success')
        / NULLIF(COUNT(*), 0),
        2
    )                                                                AS success_rate_pct,
    ROUND(
        AVG(duration_ms) FILTER (WHERE status = 'success')
    )                                                                AS avg_success_ms
FROM job_execution_logs
WHERE started_at >= NOW() - INTERVAL '24 hours'
GROUP BY job_id, job_name
ORDER BY success_rate_pct ASC;

COMMENT ON VIEW v_job_success_rate_24h IS
    'Taxa de sucesso por job nas últimas 24 horas — útil para alertas e SLAs';


-- ── View: jobs com erro nas últimas 1 hora (alerta rápido) ───────────────────

CREATE OR REPLACE VIEW v_recent_errors AS
SELECT
    id,
    job_id,
    job_name,
    started_at,
    error_type,
    error_message,
    duration_ms
FROM job_execution_logs
WHERE status = 'error'
  AND started_at >= NOW() - INTERVAL '1 hour'
ORDER BY started_at DESC;

COMMENT ON VIEW v_recent_errors IS
    'Erros ocorridos na última hora — base para alertas de monitoramento';
