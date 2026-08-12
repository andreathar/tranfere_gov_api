-- ============================================================
-- migration_020_tipo_politico.sql
-- Fase 3 (2026-08-10): dossiês multi-cargo (deputado/senador/
-- governador/prefeito/vereador) + checkpoint de retomada.
--
-- 1. parlamentares_personas: colunas tipo_politico + politico_id
--    (backward-compat: deputados mantêm deputado_id; politico_id
--     espelha deputado_id para cargos novos).
-- 2. dossie_checkpoint: retomada segura do backfill v8.
-- ============================================================

-- --- 1. parlamentares_personas ---
ALTER TABLE parlamentares_personas
    ADD COLUMN IF NOT EXISTS tipo_politico VARCHAR(20) NOT NULL DEFAULT 'deputado';
ALTER TABLE parlamentares_personas
    ADD COLUMN IF NOT EXISTS politico_id INTEGER;

-- Espelhar deputado_id -> politico_id (uma única vez, idempotente)
UPDATE parlamentares_personas
SET politico_id = deputado_id
WHERE politico_id IS NULL AND deputado_id IS NOT NULL;

-- Índice de consulta por tipo (dashboards de cobertura)
CREATE INDEX IF NOT EXISTS idx_personas_tipo
    ON parlamentares_personas (tipo_politico, versao_prompt);

-- Chave natural por cargo: (tipo_politico, politico_id, versao_prompt).
-- Espelha uniq_dep_versao para deputados (politico_id = deputado_id); para
-- os demais cargos (deputado_id NULL) garante ON CONFLICT correto.
-- NOTA: índice NÃO-parcial — o ON CONFLICT (cols) do _save_persona não
-- infere índices parciais (erro "no unique or exclusion constraint matching").
DROP INDEX IF EXISTS uniq_politico_versao;
CREATE UNIQUE INDEX IF NOT EXISTS uniq_politico_versao
    ON parlamentares_personas (tipo_politico, politico_id, versao_prompt);

-- --- 2. dossie_checkpoint ---
CREATE TABLE IF NOT EXISTS dossie_checkpoint (
    tipo        VARCHAR(20)   NOT NULL,
    politico_id INTEGER       NOT NULL,
    versao      INTEGER       NOT NULL DEFAULT 8,
    status      VARCHAR(10)   NOT NULL DEFAULT 'pendente'
                CHECK (status IN ('ok', 'fail', 'pendente')),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tipo, politico_id, versao)
);

CREATE INDEX IF NOT EXISTS idx_dossie_checkpoint_fila
    ON dossie_checkpoint (tipo, versao, status, politico_id);
