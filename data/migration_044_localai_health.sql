-- Log de health checks do LocalAI (localai_health.py).
-- Tabela de histórico para monitoramento da saúde da infraestrutura de inferência.
CREATE TABLE IF NOT EXISTS localai_health_log (
    id SERIAL PRIMARY KEY,
    checked_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT NOT NULL,
    base_url TEXT,
    models_available INTEGER,
    models_loaded TEXT[],
    models_tracked TEXT[],
    latency_ms NUMERIC(10,2),
    circuit_state TEXT,
    circuit_failures INTEGER,
    vram_total_mib INTEGER,
    vram_free_mib INTEGER,
    vram_used_mib INTEGER,
    vram_estimated_used_mib INTEGER,
    monitor_failures INTEGER,
    details JSONB
);

CREATE INDEX IF NOT EXISTS idx_localai_health_checked
    ON localai_health_log (checked_at DESC);
