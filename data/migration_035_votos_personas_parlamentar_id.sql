-- ============================================================================
-- TransfereGov — Migration 035: parlamentar_id em votos_camara + parlamentares_personas
-- ============================================================================
-- Banco: transferegov_db
-- Data: 2026-07-30
-- ============================================================================
--
-- Contexto:
--   As tabelas votos_camara e parlamentares_personas usavam apenas deputado_id
--   como identificador do parlamentar. Para consistência com o resto do esquema
--   (planos_acao usa parlamentar_id), adicionamos parlamentar_id como coluna
--   extra sem remover deputado_id (chave natural das APIs da Câmara) e sem FK
--   (parlamentares_dados.parlamentar_id nao tem UNIQUE constraint).
--
-- Mudanças:
--   1. Adiciona parlamentar_id INTEGER em votos_camara
--   2. Backfill via JOIN com parlamentares_dados ON deputado_id
--   3. Índice btree em parlamentar_id para JOINs diretos
--   4. Mesmo para parlamentares_personas
-- ============================================================================

BEGIN;

-- ============================================================================
-- PARTE 1: votos_camara
-- ============================================================================

-- 1a. Adicionar coluna parlamentar_id (sem FK)
ALTER TABLE votos_camara
    ADD COLUMN IF NOT EXISTS parlamentar_id INTEGER;

-- 1b. Backfill — popular parlamentar_id via JOIN com parlamentares_dados
UPDATE votos_camara vc
SET parlamentar_id = pad.parlamentar_id
FROM parlamentares_dados pad
WHERE vc.deputado_id = pad.deputado_id
  AND pad.parlamentar_id IS NOT NULL
  AND vc.parlamentar_id IS NULL;

-- 1c. Índice para JOINs por parlamentar_id
CREATE INDEX IF NOT EXISTS idx_votos_parlamentar_id
    ON votos_camara(parlamentar_id);

-- ============================================================================
-- PARTE 2: parlamentares_personas
-- ============================================================================

-- 2a. Adicionar coluna parlamentar_id (sem FK)
ALTER TABLE parlamentares_personas
    ADD COLUMN IF NOT EXISTS parlamentar_id INTEGER;

-- 2b. Backfill — popular parlamentar_id via JOIN com parlamentares_dados
UPDATE parlamentares_personas pp
SET parlamentar_id = pad.parlamentar_id
FROM parlamentares_dados pad
WHERE pp.deputado_id = pad.deputado_id
  AND pad.parlamentar_id IS NOT NULL
  AND pp.parlamentar_id IS NULL;

-- 2c. Índice para JOINs por parlamentar_id
CREATE INDEX IF NOT EXISTS idx_personas_parlamentar_id
    ON parlamentares_personas(parlamentar_id);

-- ============================================================================
-- 3. Grants
-- ============================================================================

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO cognee;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO cognee;

COMMIT;
