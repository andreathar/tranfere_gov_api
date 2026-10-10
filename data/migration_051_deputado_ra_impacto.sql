-- ============================================================================
-- TransfereGov — Migration 051: Impacto Deputado × Região Administrativa (DF)
-- ============================================================================
-- Banco: transferegov_db
-- Data: 2026-08-21
-- Objetivo: dar suporte aos mapas CARTO que comparam o trabalho legislativo dos
-- deputados distritais com o impacto orçamentário por Região Administrativa.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. TRABALHO DO DEPUTADO POR RA (proposições cldf_proposicoes agregadas)
-- ============================================================================

CREATE TABLE IF NOT EXISTS cldf_deputado_ra_impacto (
    id                   SERIAL PRIMARY KEY,
    deputado_id          INTEGER REFERENCES df_deputados_distritais_cldf(id),
    nome_candidato       TEXT NOT NULL,
    sigla_partido        TEXT,
    ra_codigo            INTEGER REFERENCES df_regioes_administrativas(ra_codigo),
    nome_ra              TEXT NOT NULL,
    total_proposicoes    INTEGER NOT NULL DEFAULT 0,
    primeira_proposicao  INTEGER,                     -- ano
    ultima_proposicao    INTEGER,                     -- ano
    temas_principais      TEXT,                        -- top 3 temas, separados por "; "
    updated_at           TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (deputado_id, ra_codigo)
);

COMMENT ON TABLE cldf_deputado_ra_impacto IS
    'Agregado deputado × RA a partir de cldf_proposicoes.autor_nome/regiao_admin '
    '(campos multivalorados da PLE API). Um deputado pode aparecer em várias RAs '
    'quando propôs ou co-assinou proposições que citam mais de uma região.';
COMMENT ON COLUMN cldf_deputado_ra_impacto.total_proposicoes IS
    'Contagem de proposições onde o deputado é autor/co-autor E a RA é citada '
    '(não é valor orçamentário — é volume de atuação legislativa territorial).';

CREATE INDEX IF NOT EXISTS idx_dep_ra_deputado ON cldf_deputado_ra_impacto (deputado_id);
CREATE INDEX IF NOT EXISTS idx_dep_ra_ra ON cldf_deputado_ra_impacto (ra_codigo);
CREATE INDEX IF NOT EXISTS idx_dep_ra_total ON cldf_deputado_ra_impacto (total_proposicoes DESC);

-- ============================================================================
-- 2. IMPACTO ORÇAMENTÁRIO POR RA (cldf_emendas agregadas via nome_uo)
-- ============================================================================

CREATE TABLE IF NOT EXISTS cldf_ra_emendas_resumo (
    id                  SERIAL PRIMARY KEY,
    ra_codigo           INTEGER NOT NULL REFERENCES df_regioes_administrativas(ra_codigo),
    nome_ra             TEXT NOT NULL,
    total_emendas       INTEGER NOT NULL DEFAULT 0,
    vl_emenda           NUMERIC(18,2) DEFAULT 0,
    vl_empenhado        NUMERIC(18,2) DEFAULT 0,
    vl_liquidado        NUMERIC(18,2) DEFAULT 0,
    ano_min             INTEGER,
    ano_max             INTEGER,
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ra_codigo)
);

COMMENT ON TABLE cldf_ra_emendas_resumo IS
    'Agregado de emendas orçamentárias (cldf_emendas) por RA, via casamento do '
    'nome_uo (ex: "ADM. REG. DE TAGUATINGA") com a Administração Regional. '
    'Camada de impacto orçamentário independente da atribuição por deputado '
    '(cldf_emendas não referencia o parlamentar proponente, só a UO beneficiária).';

CREATE INDEX IF NOT EXISTS idx_ra_emendas_ra ON cldf_ra_emendas_resumo (ra_codigo);
CREATE INDEX IF NOT EXISTS idx_ra_emendas_valor ON cldf_ra_emendas_resumo (vl_emenda DESC);

-- ============================================================================
-- 3. VIEW consolidada para o dashboard (join com geo)
-- ============================================================================

CREATE OR REPLACE VIEW v_deputado_ra_impacto AS
SELECT
    dr.deputado_id,
    dr.nome_candidato,
    dr.sigla_partido,
    dr.ra_codigo,
    dr.nome_ra,
    dr.total_proposicoes,
    dr.primeira_proposicao,
    dr.ultima_proposicao,
    dr.temas_principais,
    ra.populacao_est,
    ra.area_km2,
    ra.densidade,
    ra.latitude,
    ra.longitude,
    er.total_emendas,
    er.vl_emenda,
    er.vl_empenhado,
    er.vl_liquidado
FROM cldf_deputado_ra_impacto dr
JOIN df_regioes_administrativas ra ON ra.ra_codigo = dr.ra_codigo
LEFT JOIN cldf_ra_emendas_resumo er ON er.ra_codigo = dr.ra_codigo
ORDER BY dr.nome_candidato, dr.total_proposicoes DESC;

COMMENT ON VIEW v_deputado_ra_impacto IS
    'Visão consolidada deputado × RA: volume legislativo (proposições) + '
    'demografia/geo (df_regioes_administrativas) + orçamento (cldf_ra_emendas_resumo).';

COMMIT;
