-- ============================================================================
-- TransfereGov — Migration 041: Add sq_candidato to prefeitos_dados
-- ============================================================================

BEGIN;

-- Adiciona a coluna sq_candidato para integração direta com mcp-brasil tse_bens
ALTER TABLE prefeitos_dados
ADD COLUMN IF NOT EXISTS sq_candidato BIGINT;

-- Adiciona índice para facilitar cruzamento com bens e receitas de campanha
CREATE INDEX IF NOT EXISTS idx_prefeitos_sq_candidato ON prefeitos_dados (sq_candidato);

-- E também para vereadores_dados (se houver, vou tentar adicionar lá tb para o mesmo fim)
ALTER TABLE vereadores_dados
ADD COLUMN IF NOT EXISTS sq_candidato BIGINT;

CREATE INDEX IF NOT EXISTS idx_vereadores_sq_candidato ON vereadores_dados (sq_candidato);

COMMIT;
