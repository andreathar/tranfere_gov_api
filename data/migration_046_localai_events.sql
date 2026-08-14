-- Migration 046: Observabilidade LocalAI — cadeia de eventos persistida.
-- Grava a "cadeia de eventos" (traces de request, backend traces, logs,
-- monitor) para permitir follow-up pós-falha (500 / connection refused / OOM)
-- sem depender de varredura manual de logs.

CREATE TABLE IF NOT EXISTS localai_event_log (
    id            BIGSERIAL PRIMARY KEY,
    event_at      TIMESTAMPTZ          NOT NULL DEFAULT now(),
    event_type    TEXT                 NOT NULL,          -- request | backend | monitor | system | log
    level         TEXT                 NOT NULL DEFAULT 'info',  -- info | warning | error
    model         TEXT,
    backend       TEXT,
    method        TEXT,
    path          TEXT,
    status_code   INTEGER,
    duration_ms   NUMERIC(12,2),
    summary       TEXT,
    payload       JSONB
);

CREATE INDEX IF NOT EXISTS idx_localai_event_at      ON localai_event_log (event_at DESC);
CREATE INDEX IF NOT EXISTS idx_localai_event_model   ON localai_event_log (model);
CREATE INDEX IF NOT EXISTS idx_localai_event_type    ON localai_event_log (event_type);

-- Snapshot da cadeia por execução do CLI de diagnóstico (para comparar execuções)
CREATE TABLE IF NOT EXISTS localai_chain_snapshot (
    id            BIGSERIAL PRIMARY KEY,
    taken_at      TIMESTAMPTZ          NOT NULL DEFAULT now(),
    model         TEXT,
    status        TEXT                 NOT NULL,          -- ok | degraded | error
    duration_hint NUMERIC(12,2),
    events_count  INTEGER              NOT NULL DEFAULT 0,
    anomalies     JSONB                NOT NULL DEFAULT '[]'::jsonb,
    chain         JSONB                NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_localai_chain_taken     ON localai_chain_snapshot (taken_at DESC);
CREATE INDEX IF NOT EXISTS idx_localai_chain_model     ON localai_chain_snapshot (model);