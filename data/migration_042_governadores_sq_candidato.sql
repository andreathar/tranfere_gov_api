-- ============================================================================
-- TransfereGov — Migration 042: Add sq_candidato to governadores_dados
-- ============================================================================

BEGIN;

ALTER TABLE governadores_dados
ADD COLUMN IF NOT EXISTS sq_candidato BIGINT;

CREATE INDEX IF NOT EXISTS idx_governadores_sq_candidato ON governadores_dados (sq_candidato);

COMMIT;
