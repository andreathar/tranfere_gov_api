CREATE TABLE IF NOT EXISTS rag_efficiency_runs (
    id SERIAL PRIMARY KEY,
    run_date TIMESTAMPTZ DEFAULT NOW(),
    model_name TEXT NOT NULL,
    golden_set_version TEXT NOT NULL,
    total_questions INTEGER,
    global_efficiency_score NUMERIC(5,2),
    avg_retrieval_hit_rate NUMERIC(5,2),
    avg_generation_faithfulness NUMERIC(5,2),
    avg_emergence_layer NUMERIC(5,2)
);

CREATE TABLE IF NOT EXISTS rag_efficiency_metrics (
    id SERIAL PRIMARY KEY,
    run_id INTEGER REFERENCES rag_efficiency_runs(id) ON DELETE CASCADE,
    politico_id INTEGER NOT NULL,
    tipo_politico TEXT NOT NULL,
    question TEXT NOT NULL,
    expected_answer TEXT NOT NULL,
    
    -- Retrieval metrics
    retrieved_chunks_count INTEGER,
    hit_rate_at_k NUMERIC(5,2),
    mrr_at_k NUMERIC(5,2),
    
    -- Generation metrics
    actual_answer TEXT,
    faithfulness_score NUMERIC(5,2),
    context_utilization_score NUMERIC(5,2),
    
    -- Mechanistic metrics (Phase 2, offline)
    emergence_layer INTEGER,
    total_layers INTEGER,
    target_token_prob NUMERIC(5,4),
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rag_eff_run ON rag_efficiency_metrics(run_id);
