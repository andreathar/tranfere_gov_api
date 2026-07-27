-- ============================================================================
-- TransfereGov — Migration 018: View Vereadores em Exercício (Frontend)
-- ============================================================================
-- Banco: transferegov_db
-- Data: 2026-07-27
-- Objetivo: View simplificada para listagem no frontend com filtros por
--           partido, UF e município, incluindo dados IBGE agregados.
-- ============================================================================

BEGIN;

-- 1. View Canônica: Vereadores em Exercício (somente eleitos)
-- Usada pela API REST e pelo frontend para listagem, busca e filtros.
DROP VIEW IF EXISTS v_vereadores_em_exercicio CASCADE;
CREATE VIEW v_vereadores_em_exercicio AS
SELECT
    v.sq_candidato,
    v.municipio_id,
    v.municipio_nome,
    v.uf,
    v.nome_completo,
    v.nome_urna,
    v.sigla_partido AS partido,
    v.numero_candidato,
    v.ano_eleicao,
    v.votos,
    v.percentual_votos,
    v.situacao_candidatura,
    v.coligacao,
    -- Dados IBGE
    m.regiao AS ibge_regiao,
    m.populacao AS ibge_populacao,
    m.idhm AS ibge_idhm,
    m.pib_per_capita AS ibge_pib_per_capita,
    -- Indicadores derivados
    ROUND(v.votos::NUMERIC / NULLIF(m.populacao, 0) * 1000, 2) AS votos_por_1000_hab,
    v.updated_at
FROM vereadores_dados v
LEFT JOIN municipios_ibge m ON v.municipio_id = m.municipio_id
WHERE UPPER(v.situacao_candidatura) LIKE '%ELEITO%';

-- 2. View Resumo: Vereadores Eleitos por Partido (para gráfico de barras)
DROP VIEW IF EXISTS v_vereadores_por_partido_resumo CASCADE;
CREATE VIEW v_vereadores_por_partido_resumo AS
SELECT
    partido,
    uf,
    ano_eleicao,
    COUNT(*) AS total_eleitos,
    SUM(votos) AS total_votos,
    ROUND(AVG(votos), 0) AS media_votos
FROM v_vereadores_em_exercicio
GROUP BY partido, uf, ano_eleicao
ORDER BY total_eleitos DESC;

-- 3. View Resumo: Top Municípios por Nº de Vereadores Eleitos
DROP VIEW IF EXISTS v_vereadores_por_municipio CASCADE;
CREATE VIEW v_vereadores_por_municipio AS
SELECT
    municipio_id,
    municipio_nome,
    uf,
    ano_eleicao,
    COUNT(*) AS total_vereadores,
    COUNT(DISTINCT partido) AS total_partidos,
    ROUND(AVG(votos), 0) AS media_votos,
    SUM(votos) AS total_votos,
    ibge_populacao,
    ROUND(ibge_idhm::NUMERIC, 3) AS ibge_idhm
FROM v_vereadores_em_exercicio
GROUP BY municipio_id, municipio_nome, uf, ano_eleicao, ibge_populacao, ibge_idhm
ORDER BY total_vereadores DESC;

COMMIT;
