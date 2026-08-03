-- ============================================================================
-- TransfereGov — Migration 014: Tabela e View de Vereadores (Dados TSE)
-- ============================================================================
-- Banco: transferegov_db
-- Data: 2026-07-26
-- Fonte: TSE — Portal de Dados Abertos (consulta_cand + votacao)
-- ============================================================================

BEGIN;

-- 1. Tabela de Vereadores (Dados TSE / Eleições Municipais)
-- Cada linha = 1 candidato a vereador em 1 município
CREATE TABLE IF NOT EXISTS vereadores_dados (
    sq_candidato BIGINT PRIMARY KEY,          -- ID único do candidato no TSE
    municipio_id INTEGER NOT NULL REFERENCES municipios_ibge(municipio_id),
    municipio_nome TEXT,
    uf CHAR(2),
    nome_completo TEXT NOT NULL,
    nome_urna TEXT,
    sigla_partido TEXT,
    numero_candidato TEXT,
    ano_eleicao INTEGER DEFAULT 2024,
    votos INTEGER DEFAULT 0,
    percentual_votos NUMERIC(5,2) DEFAULT 0.00,
    situacao_candidatura TEXT,                 -- ELEITO POR QP, ELEITO POR QL, NÃO ELEITO, etc.
    coligacao TEXT,
    cargo TEXT DEFAULT 'VEREADOR',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Indexação
CREATE INDEX IF NOT EXISTS idx_vereadors_municipio ON vereadores_dados (municipio_id);
CREATE INDEX IF NOT EXISTS idx_vereadors_partido ON vereadores_dados (sigla_partido);
CREATE INDEX IF NOT EXISTS idx_vereadors_uf ON vereadores_dados (uf);
CREATE INDEX IF NOT EXISTS idx_vereadors_nome ON vereadores_dados (nome_completo);
CREATE INDEX IF NOT EXISTS idx_vereadors_situacao ON vereadores_dados (situacao_candidatura);
CREATE INDEX IF NOT EXISTS idx_vereadors_ano ON vereadores_dados (ano_eleicao);

-- 3. View Canônica: Vereadores Eleitos por Município
DROP VIEW IF EXISTS v_vereadores_eleitos CASCADE;
CREATE VIEW v_vereadores_eleitos AS
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
    ROUND(v.votos::NUMERIC / NULLIF(m.populacao, 0) * 100, 4) AS votos_por_1000_hab,
    v.updated_at
FROM vereadores_dados v
LEFT JOIN municipios_ibge m ON v.municipio_id = m.municipio_id
WHERE UPPER(v.situacao_candidatura) LIKE '%ELEITO%';

-- 4. View Resumo: Quantidade de Vereadores Eleitos por Município
DROP VIEW IF EXISTS v_resumo_vereadores_municipio CASCADE;
CREATE VIEW v_resumo_vereadores_municipio AS
SELECT
    v.municipio_id,
    v.municipio_nome,
    v.uf,
    v.ano_eleicao,
    COUNT(*) AS total_vereadores_eleitos,
    COUNT(DISTINCT v.sigla_partido) AS total_partidos,
    ROUND(AVG(v.votos), 0) AS media_votos,
    SUM(v.votos) AS total_votos,
    m.populacao AS ibge_populacao
FROM vereadores_dados v
LEFT JOIN municipios_ibge m ON v.municipio_id = m.municipio_id
WHERE UPPER(v.situacao_candidatura) LIKE '%ELEITO%'
GROUP BY v.municipio_id, v.municipio_nome, v.uf, v.ano_eleicao, m.populacao;

-- 5. View Resumo: Vereadores por Partido (UF)
DROP VIEW IF EXISTS v_vereadores_por_partido CASCADE;
CREATE VIEW v_vereadores_por_partido AS
SELECT
    uf,
    sigla_partido AS partido,
    ano_eleicao,
    COUNT(*) AS total_eleitos,
    SUM(votos) AS total_votos,
    ROUND(AVG(votos), 0) AS media_votos
FROM vereadores_dados
WHERE UPPER(situacao_candidatura) LIKE '%ELEITO%'
GROUP BY uf, sigla_partido, ano_eleicao
ORDER BY total_eleitos DESC;

-- 6. Grants
GRANT ALL PRIVILEGES ON TABLE vereadores_dados TO cognee;
GRANT ALL PRIVILEGES ON v_vereadores_eleitos TO cognee;
GRANT ALL PRIVILEGES ON v_resumo_vereadores_municipio TO cognee;
GRANT ALL PRIVILEGES ON v_vereadores_por_partido TO cognee;

COMMIT;
