-- Telemetria de Quality Check dos analistas RAG v7.
-- Controlada por RAG_PERSIST_QC (config/settings.py, default off).
CREATE TABLE IF NOT EXISTS dossie_analyst_qc (
    id SERIAL PRIMARY KEY,
    politico_id INTEGER NOT NULL,
    tipo_politico TEXT NOT NULL DEFAULT 'deputado',
    analyst_id TEXT NOT NULL,
    section_title TEXT,
    quality_ok BOOLEAN NOT NULL,
    quality_score NUMERIC(5,2) NOT NULL,
    duration_sec NUMERIC(8,2),
    chunks_count INTEGER,
    briefing_chars INTEGER,
    llm_model TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dossie_qc_politico
    ON dossie_analyst_qc (politico_id, tipo_politico, created_at);
CREATE INDEX IF NOT EXISTS idx_dossie_qc_analyst
    ON dossie_analyst_qc (analyst_id, created_at);
