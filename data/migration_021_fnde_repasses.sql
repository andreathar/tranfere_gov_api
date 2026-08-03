-- ============================================================================
-- TransfereGov — Migration: FNDE Repasses
-- ============================================================================
-- Banco: transferegov_db
-- Data: 2026-07-27
-- Descrição: Tabela de repasses do FNDE (FUNDEB, PNAE, PNLD, PNATE) por município
-- Pré-requisitos: migration_003_enrichment.sql (municipios_ibge)
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. TABELA — Repasses FNDE por Município
-- ============================================================================
-- Dados de programas educacionais do FNDE: FUNDEB, PNAE, PNLD, PNATE

CREATE TABLE IF NOT EXISTS fnde_repasses (
    id                      SERIAL PRIMARY KEY,
    municipio_id            INTEGER REFERENCES municipios_ibge(municipio_id),
    programa                TEXT NOT NULL,           -- 'FUNDEB', 'PNAE', 'PNLD', 'PNATE'
    ano                     INTEGER,
    descricao_programa      TEXT,
    etapa_ensino            TEXT,                   -- Ex: Ensino Fundamental, Educação Infantil
    tipo_rede               TEXT,                   -- Ex: Municipal, Estadual, Federal
    localizacao             TEXT,                   -- Ex: Urbana, Rural
    quantidade_matriculas   INTEGER,
    quantidade_alunos       INTEGER,
    valor_total             NUMERIC(15,2),
    valor_por_aluno         NUMERIC(10,2),
    extracted_at            TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (municipio_id, programa, ano, etapa_ensino, tipo_rede)
);

-- ============================================================================
-- 2. ÍNDICES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_fnde_municipio ON fnde_repasses(municipio_id);
CREATE INDEX IF NOT EXISTS idx_fnde_programa ON fnde_repasses(programa);
CREATE INDEX IF NOT EXISTS idx_fnde_ano ON fnde_repasses(ano);
CREATE INDEX IF NOT EXISTS idx_fnde_uf ON fnde_repasses(municipio_id);

-- ============================================================================
-- 3. VIEW — Resumo FNDE por Município
-- ============================================================================

CREATE OR REPLACE VIEW v_fnde_resumo_municipio AS
SELECT
    m.municipio_id,
    m.nome AS municipio,
    m.uf,
    m.populacao,
    -- FUNDEB
    COALESCE(SUM(CASE WHEN f.programa = 'FUNDEB' THEN f.quantidade_matriculas END), 0) AS fundeb_matriculas,
    -- PNAE
    COALESCE(SUM(CASE WHEN f.programa = 'PNAE' THEN f.quantidade_alunos END), 0) AS pnae_alunos,
    -- PNLD
    COALESCE(SUM(CASE WHEN f.programa = 'PNLD' THEN f.quantidade_alunos END), 0) AS pnld_alunos,
    -- PNATE
    COALESCE(SUM(CASE WHEN f.programa = 'PNATE' THEN f.quantidade_alunos END), 0) AS pnate_alunos,
    -- Total geral
    COALESCE(SUM(f.quantidade_matriculas), 0) + COALESCE(SUM(f.quantidade_alunos), 0) AS total_beneficiados,
    MAX(f.extracted_at) AS ultima_atualizacao
FROM municipios_ibge m
LEFT JOIN fnde_repasses f ON m.municipio_id = f.municipio_id
GROUP BY m.municipio_id, m.nome, m.uf, m.populacao;

-- ============================================================================
-- 4. VIEW — Resumo FNDE por Estado
-- ============================================================================

CREATE OR REPLACE VIEW v_fnde_resumo_estado AS
SELECT
    m.uf,
    COUNT(DISTINCT m.municipio_id) AS total_municipios,
    SUM(COALESCE(f.quantidade_matriculas, 0)) AS total_matriculas,
    SUM(COALESCE(f.quantidade_alunos, 0)) AS total_alunos,
    MAX(f.extracted_at) AS ultima_atualizacao
FROM municipios_ibge m
LEFT JOIN fnde_repasses f ON m.municipio_id = f.municipio_id
GROUP BY m.uf
ORDER BY total_alunos DESC;

-- ============================================================================
-- 5. VIEW — Programas por Município (pivot)
-- ============================================================================

CREATE OR REPLACE VIEW v_fnde_programas_municipio AS
SELECT
    m.municipio_id,
    m.nome AS municipio,
    m.uf,
    f.programa,
    f.ano,
    f.etapa_ensino,
    f.quantidade_matriculas,
    f.quantidade_alunos,
    f.valor_total,
    f.valor_por_aluno
FROM municipios_ibge m
JOIN fnde_repasses f ON m.municipio_id = f.municipio_id
ORDER BY m.uf, m.nome, f.programa, f.ano;

COMMIT;
