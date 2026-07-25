-- Migration 003: Tabela para cache local do DataJud (CNJ)

CREATE TABLE IF NOT EXISTS beneficiario_processos (
    cnpj TEXT PRIMARY KEY,
    total_processos INTEGER DEFAULT 0,
    processos_detalhes JSONB DEFAULT '{}'::jsonb,
    erro TEXT,
    checked_at TIMESTAMPTZ DEFAULT NOW()
);
