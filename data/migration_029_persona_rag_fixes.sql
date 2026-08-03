-- ============================================================================
-- Migration 029: Correções para Parlamentares Personas (RAG v3)
-- ============================================================================
-- Data: 2026-07-28
-- Descrição: Corrige schema da tabela parlamentares_personas para suportar
--            geração de personas corretamente:
--            1. fontes_usadas: TEXT → TEXT[] (array PostgreSQL)
--            2. Adiciona coluna qualidade_ok (BOOLEAN)
--            3. Adiciona índice em data_analise DESC
--            4. Migra dados existentes (texto → array)
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. Corrigir fontes_usadas: TEXT → TEXT[]
-- ============================================================================
-- psycopg2 converte listas Python para texto literal '{a,b,c}' quando a coluna
-- é TEXT. Precisamos de TEXT[] para operações corretas.

-- Criar coluna temporária com tipo correto
ALTER TABLE parlamentares_personas
    ADD COLUMN fontes_usadas_tmp TEXT[];

-- Migrar dados: converter '{voto,emenda}' (texto) → ARRAY['voto','emenda']
UPDATE parlamentares_personas
SET fontes_usadas_tmp = CASE
    WHEN fontes_usadas IS NULL THEN NULL
    WHEN fontes_usadas = '' THEN NULL
    ELSE string_to_array(
        -- Remove { e } das extremidades
        trim(both '{}' from fontes_usadas),
        ','
    )
END
WHERE fontes_usadas IS NOT NULL;

-- Remover coluna antiga
ALTER TABLE parlamentares_personas DROP COLUMN fontes_usadas;

-- Renomear temporária
ALTER TABLE parlamentares_personas RENAME COLUMN fontes_usadas_tmp TO fontes_usadas;

-- NOT NULL com default vazio
ALTER TABLE parlamentares_personas
    ALTER COLUMN fontes_usadas SET DEFAULT '{}';

-- ============================================================================
-- 2. Adicionar coluna qualidade_ok
-- ============================================================================
-- Salva resultado do quality check (True/False/NULL)
-- NULL = ainda não verificado, True = aprovado, False = reprovado

ALTER TABLE parlamentares_personas
    ADD COLUMN IF NOT EXISTS qualidade_ok BOOLEAN DEFAULT NULL;

COMMENT ON COLUMN parlamentares_personas.qualidade_ok IS
    'Resultado do quality check: True=APROVADO, False=REPROVADO, NULL=pendente';

-- ============================================================================
-- 3. Índices para performance
-- ============================================================================

-- Índice para ordenação por data (dashboard: "últimas personas geradas")
CREATE INDEX IF NOT EXISTS idx_personas_data_desc
    ON parlamentares_personas(data_analise DESC);

-- Índice para filtrar por qualidade (dashboard: "personas aprovadas")
CREATE INDEX IF NOT EXISTS idx_personas_qualidade
    ON parlamentares_personas(qualidade_ok)
    WHERE qualidade_ok IS NOT NULL;

-- ============================================================================
-- 4. View de auditoria para personas
-- ============================================================================

CREATE OR REPLACE VIEW v_personas_audit AS
SELECT
    pp.deputado_id,
    pd.nome AS deputado_nome,
    pd.sigla_partido,
    pd.uf,
    pp.versao_prompt,
    pp.qualidade_ok,
    CASE
        WHEN pp.qualidade_ok IS TRUE THEN 'APROVADO'
        WHEN pp.qualidade_ok IS FALSE THEN 'REPROVADO'
        ELSE 'PENDENTE'
    END AS status_qualidade,
    pp.fontes_usadas,
    array_length(pp.fontes_usadas, 1) AS n_fontes,
    LEFT(pp.analise_gerada, 200) AS analise_preview,
    pp.duracao_segundos,
    pp.data_analise
FROM parlamentares_personas pp
JOIN parlamentares_dados pd ON pp.deputado_id = pd.deputado_id
ORDER BY pp.data_analise DESC;

COMMIT;
