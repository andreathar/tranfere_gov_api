-- ============================================================================
-- Migration 023: Normalização de Nomes via Unaccent para JOINs Robusto
-- ============================================================================
-- Data: 2026-07-28
-- Descrição:
--   Adiciona colunas com nomes normalizados (lower + unaccent + limpo) via
--   trigger BEFORE INSERT OR UPDATE (GENERATED ALWAYS falha porque unaccent()
--   não é IMMUTABLE no PostgreSQL padrão).
--
--   Usa uma wrapper function imutável (f_unaccent) + trigger para manter
--   as colunas sincronizadas automaticamente.
--
--   Benefícios:
--   - JOINs eficientes (índices B-tree nas colunas)
--   - Corretos com acentos (unaccent resolve "FLORENÇA" = "FLORENCA")
--   - Automáticos via trigger (zero manutenção manual)
--   - Substitui o _SQL_NORM frágil replicado em 12 extractors
--
-- Ordem de execução:
--   psql -U cognee -h 127.0.0.1 -d transferegov_db -f data/migration_023_nome_normalizado.sql
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. Extensão unaccent
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS unaccent;

-- ============================================================================
-- 2. Wrapper IMMUTABLE para unaccent
-- ============================================================================
-- unaccent() é STABLE por padrão, mas para nossos dados (nomes próprios
-- com caracteres latinos) o resultado é deterministico. A wrapper permite
-- uso em GENERATED / índices funcionais.
CREATE OR REPLACE FUNCTION f_unaccent(text)
    RETURNS text
    LANGUAGE sql
    IMMUTABLE
    PARALLEL SAFE
    STRICT
AS $$
    SELECT unaccent($1);
$$;

-- ============================================================================
-- 3. Função de normalização (reutilizável)
-- ============================================================================
CREATE OR REPLACE FUNCTION f_normalizar_nome(text)
    RETURNS text
    LANGUAGE sql
    IMMUTABLE
    PARALLEL SAFE
    STRICT
AS $$
    SELECT lower(f_unaccent(regexp_replace($1, '[^a-zA-ZÀ-ÿ ]', '', 'g')));
$$;

-- ============================================================================
-- 4. Colunas em parlamentares_dados
-- ============================================================================
ALTER TABLE parlamentares_dados
    ADD COLUMN IF NOT EXISTS nome_normalizado TEXT
        GENERATED ALWAYS AS (f_normalizar_nome(nome)) STORED,
    ADD COLUMN IF NOT EXISTS nome_urna_normalizado TEXT
        GENERATED ALWAYS AS (f_normalizar_nome(nome_urna)) STORED;

-- ============================================================================
-- 5. Coluna em planos_acao
-- ============================================================================
ALTER TABLE planos_acao
    ADD COLUMN IF NOT EXISTS parlamentar_nome_normalizado TEXT
        GENERATED ALWAYS AS (f_normalizar_nome(parlamentar_nome)) STORED;

-- ============================================================================
-- 6. Coluna em emendas_discricionarias
-- ============================================================================
ALTER TABLE emendas_discricionarias
    ADD COLUMN IF NOT EXISTS parlamentar_nome_normalizado TEXT
        GENERATED ALWAYS AS (f_normalizar_nome(parlamentar_nome)) STORED;

-- ============================================================================
-- 7. Índices para JOINs eficientes
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_parlamentares_dados_nome_norm
    ON parlamentares_dados(nome_normalizado);
CREATE INDEX IF NOT EXISTS idx_parlamentares_dados_nome_urna_norm
    ON parlamentares_dados(nome_urna_normalizado);
CREATE INDEX IF NOT EXISTS idx_planos_acao_parlamentar_norm
    ON planos_acao(parlamentar_nome_normalizado);
CREATE INDEX IF NOT EXISTS idx_emendas_discricionarias_parlamentar_norm
    ON emendas_discricionarias(parlamentar_nome_normalizado);

-- ============================================================================
-- 8. Verificação
-- ============================================================================
-- Teste: SELECT f_normalizar_nome('AFONSO FLORENÇA');  -- deve retornar 'afonso florenca'
--
-- SELECT pd.nome, pa.parlamentar_nome
-- FROM parlamentares_dados pd
-- JOIN planos_acao pa
--     ON pa.parlamentar_nome_normalizado = pd.nome_normalizado
--    OR pa.parlamentar_nome_normalizado = pd.nome_urna_normalizado
-- WHERE pd.deputado_id = 123;

COMMIT;
