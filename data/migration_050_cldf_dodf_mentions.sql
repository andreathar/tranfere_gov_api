-- ============================================================================
-- TransfereGov — Migration 050: CLDF × DODF Mentions
-- ============================================================================
-- Banco: transferegov_db
-- Data: 2026-08-18
-- Fonte: Querido Diário API (api.queridodiario.ok.org.br)
--        DODF — Diário Oficial do Distrito Federal (território 5300108)
-- ============================================================================
-- O DODF publica todos os atos do Poder Legislativo do DF (CLDF) na Seção I.
-- Esta migração cria a tabela de menções rastreadas pelo scanner DODF,
-- indexadas por deputado e tipo de ato.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. MENÇÕES DE DEPUTADOS DISTRITAIS NO DODF
-- ============================================================================

CREATE TABLE IF NOT EXISTS cldf_dodf_mentions (
    id              SERIAL PRIMARY KEY,
    territory_id    TEXT NOT NULL DEFAULT '5300108',   -- IBGE DF
    date_pub        DATE NOT NULL,                     -- Data da edição
    edition         TEXT,                              -- Número da edição
    is_extra        BOOLEAN DEFAULT FALSE,             -- Edição extra?
    query_term      TEXT NOT NULL,                     -- Termo buscado (nome ou tipo de ato)
    query_type      TEXT NOT NULL DEFAULT 'deputado',  -- 'deputado' | 'ato_type' | 'cldf_general'
    deputado_nome   TEXT,                              -- Nome do deputado (se query_type='deputado')
    sq_candidato    BIGINT,                            -- Vínculo com df_deputados_distritais_cldf
    excerpt         TEXT,                              -- Trecho do DODF com a menção
    gazette_url     TEXT,                              -- URL do PDF da edição
    txt_url         TEXT,                              -- URL do TXT para full-text
    scraped_at      TIMESTAMPTZ,                       -- Quando o QD indexou
    fetched_at      TIMESTAMPTZ DEFAULT NOW(),         -- Quando nós coletamos
    hash_key        TEXT UNIQUE,                       -- Dedup: MD5(territory+date+edition+query)
    CONSTRAINT cldf_dodf_mentions_hash_unique UNIQUE (hash_key)
);

COMMENT ON TABLE cldf_dodf_mentions IS
    'Menções de deputados distritais e atos CLDF no DODF, via Querido Diário API';
COMMENT ON COLUMN cldf_dodf_mentions.query_type IS
    '''deputado'' = busca por nome do deputado; '
    '''ato_type'' = busca por tipo de ato (Decreto Legislativo, Resolução, etc.); '
    '''cldf_general'' = busca geral por CLDF / Câmara Legislativa';
COMMENT ON COLUMN cldf_dodf_mentions.hash_key IS
    'MD5(territory_id || date_pub || edition || query_term) — evita duplicatas';

CREATE INDEX IF NOT EXISTS idx_cldf_dodf_date   ON cldf_dodf_mentions (date_pub DESC);
CREATE INDEX IF NOT EXISTS idx_cldf_dodf_dep    ON cldf_dodf_mentions (deputado_nome);
CREATE INDEX IF NOT EXISTS idx_cldf_dodf_sqcand ON cldf_dodf_mentions (sq_candidato);
CREATE INDEX IF NOT EXISTS idx_cldf_dodf_type   ON cldf_dodf_mentions (query_type);

-- ============================================================================
-- 2. RESUMO DE ATIVIDADE LEGISLATIVA POR DEPUTADO (view analítica)
-- ============================================================================

DROP VIEW IF EXISTS v_cldf_atividade_dodf CASCADE;
CREATE VIEW v_cldf_atividade_dodf AS
SELECT
    m.deputado_nome,
    d.sigla_partido,
    d.votos_total,
    COUNT(*)                                          AS total_mencoes,
    MIN(m.date_pub)                                   AS primeira_mencao,
    MAX(m.date_pub)                                   AS ultima_mencao,
    COUNT(DISTINCT m.date_pub)                        AS edicoes_distintas,
    COUNT(*) FILTER (WHERE m.is_extra)                AS mencoes_extra,
    ARRAY_AGG(DISTINCT m.edition ORDER BY m.edition)
        FILTER (WHERE m.edition IS NOT NULL)          AS edicoes
FROM cldf_dodf_mentions m
LEFT JOIN df_deputados_distritais_cldf d
    ON d.sq_candidato = m.sq_candidato
WHERE m.query_type = 'deputado'
GROUP BY m.deputado_nome, d.sigla_partido, d.votos_total
ORDER BY total_mencoes DESC;

COMMENT ON VIEW v_cldf_atividade_dodf IS
    'Ranking de atividade dos deputados distritais no DODF — quantas vezes cada um foi mencionado';

-- ============================================================================
-- 3. ATOS CLDF MAIS RECENTES (view de radar)
-- ============================================================================

DROP VIEW IF EXISTS v_cldf_atos_recentes CASCADE;
CREATE VIEW v_cldf_atos_recentes AS
SELECT
    date_pub,
    edition,
    is_extra,
    query_term      AS tipo_ato,
    excerpt,
    gazette_url,
    txt_url
FROM cldf_dodf_mentions
WHERE query_type = 'ato_type'
ORDER BY date_pub DESC, edition DESC
LIMIT 200;

COMMENT ON VIEW v_cldf_atos_recentes IS
    'Últimos atos da CLDF (Decreto Legislativo, Resolução, etc.) publicados no DODF';

-- ============================================================================
-- 4. GRANTS
-- ============================================================================

GRANT ALL PRIVILEGES ON TABLE cldf_dodf_mentions TO cognee;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO cognee;
GRANT SELECT ON v_cldf_atividade_dodf TO cognee;
GRANT SELECT ON v_cldf_atos_recentes TO cognee;

COMMIT;
