-- ============================================================================
-- TransfereGov — Migration 023: parlamentar_id em parlamentar_discursos
-- ============================================================================
-- Banco: transferegov_db
-- Data: 2026-07-30
-- ============================================================================
--
-- Contexto:
--   A tabela parlamentar_discursos usava apenas deputado_id (ID da Câmara)
--   como identificador. Para consistência com o resto do esquema, adicionamos
--   parlamentar_id como coluna extra (sem remover deputado_id, que é a chave
--   natural da API da Câmara, e sem FK — parlamentares_dados.parlamentar_id
--   nao tem UNIQUE constraint).
--
-- Mudanças:
--   1. Adiciona parlamentar_id INTEGER
--   2. Backfill via JOIN com parlamentares_dados ON deputado_id
--   3. Índice btree em parlamentar_id para JOINs diretos
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. Adicionar coluna parlamentar_id (sem FK — mesma abordagem de
--    emendas_discricionarias na migration_018)
-- ============================================================================

ALTER TABLE parlamentar_discursos
    ADD COLUMN IF NOT EXISTS parlamentar_id INTEGER;

-- ============================================================================
-- 2. Backfill — popular parlamentar_id via JOIN com parlamentares_dados
-- ============================================================================

UPDATE parlamentar_discursos pd
SET parlamentar_id = pad.parlamentar_id
FROM parlamentares_dados pad
WHERE pd.deputado_id = pad.deputado_id
  AND pad.parlamentar_id IS NOT NULL
  AND pd.parlamentar_id IS NULL;

-- ============================================================================
-- 3. Índice para JOINs por parlamentar_id
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_discursos_parlamentar_id
    ON parlamentar_discursos(parlamentar_id);

-- ============================================================================
-- 4. Grants
-- ============================================================================

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO cognee;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO cognee;

COMMIT;
