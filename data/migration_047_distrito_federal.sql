-- ============================================================================
-- TransfereGov — Migration 047: Tabelas Específicas do Distrito Federal
-- ============================================================================
-- Banco: transferegov_db
-- Data: 2026-08-17
-- Fontes: CLDF (Câmara Legislativa do DF), TSE 2022, Wikipedia, mcp-brasil
-- ============================================================================
-- O DF é único no Brasil: não tem prefeito nem vereadores.
-- Possui: Governador, 2 Senadores, 8 Deputados Federais, 24 Deputados
--         Distritais (CLDF), e 33 Regiões Administrativas (em vez de municípios).
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. REGIÕES ADMINISTRATIVAS DO DF (33)
-- ============================================================================

CREATE TABLE IF NOT EXISTS df_regioes_administrativas (
    ra_codigo       INTEGER PRIMARY KEY,       -- Código da região administrativa (IBGE)
    nome_ra         TEXT NOT NULL,
    populacao_est   INTEGER,                   -- População estimada
    area_km2        NUMERIC(10,2),             -- Área em km²
    densidade       NUMERIC(10,2),             -- Hab/km²
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE df_regioes_administrativas IS
    '33 Regiões Administrativas do Distrito Federal (substituem municípios)';
COMMENT ON COLUMN df_regioes_administrativas.ra_codigo IS
    'Código IBGE da região administrativa (5300108=Plano Piloto, etc.)';

-- ============================================================================
-- 2. DEPUTADOS DISTRITAIS — CLDF 9ª Legislatura (2023–2027)
-- ============================================================================

CREATE TABLE IF NOT EXISTS df_deputados_distritais_cldf (
    id                  SERIAL PRIMARY KEY,
    nome_candidato      TEXT NOT NULL,
    nome_civil          TEXT,
    sigla_partido       TEXT NOT NULL,
    votos_total         INTEGER DEFAULT 0,
    pct_votos           NUMERIC(5,2) DEFAULT 0.0,
    nr_candidato        INTEGER,               -- Número nournico no TSE
    sq_candidato        BIGINT,                -- Sequencial do candidato TSE
    ocupacao            TEXT,
    idade               INTEGER,
    municipio_nascimento TEXT,
    uf_nascimento       CHAR(2),
    situacao            TEXT DEFAULT 'ELEITO', -- ELEITO, SUPLENTE, AFASTADO
    legislatura         INTEGER DEFAULT 9,     -- 9ª legislatura (2023-2027)
    mandato_inicio      DATE DEFAULT '2023-01-01',
    mandato_fim         DATE DEFAULT '2027-01-01',
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(sq_candidato)
);

COMMENT ON TABLE df_deputados_distritais_cldf IS
    '24 Deputados Distritais eleitos — CLDF 9ª legislatura (2022/2023-2027)';
COMMENT ON COLUMN df_deputados_distritais_cldf.sq_candidato IS
    'Sequencial do candidato TSE (divulgacandcontas.tse.jus.br)';

CREATE INDEX IF NOT EXISTS idx_cldf_partido ON df_deputados_distritais_cldf (sigla_partido);
CREATE INDEX IF NOT EXISTS idx_cldf_votos ON df_deputados_distritais_cldf (votos_total DESC);

-- ============================================================================
-- 3. ELEIÇÕES DF — Resumo por Cargo (2022)
-- ============================================================================

CREATE TABLE IF NOT EXISTS df_eleicoes_resumo (
    id              SERIAL PRIMARY KEY,
    ano_eleicao     INTEGER NOT NULL DEFAULT 2022,
    cargo           TEXT NOT NULL,             -- GOVERNADOR, SENADOR, DEPUTADO_FEDERAL, DEPUTADO_DISTRITAL
    turno           INTEGER DEFAULT 1,
    nome_candidato  TEXT NOT NULL,
    sigla_partido   TEXT NOT NULL,
    votos_total     INTEGER DEFAULT 0,
    pct_votos       NUMERIC(5,2) DEFAULT 0.0,
    coligacao       TEXT,
    situacao        TEXT DEFAULT 'ELEITO',     -- ELEITO, NAO_ELEITO, AFASTADO
    sq_candidato    BIGINT,
    nr_candidato    INTEGER,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE df_eleicoes_resumo IS
    'Resultados das eleições no DF (2022): Governador, Senador, Dep. Federal, Dep. Distrital';
COMMENT ON COLUMN df_eleicoes_resumo.cargo IS
    'GOVERNADOR, SENADOR, DEPUTADO_FEDERAL, DEPUTADO_DISTRITAL, PRESIDENTE_DF';

CREATE INDEX IF NOT EXISTS idx_eleicoes_df_cargo ON df_eleicoes_resumo (cargo, ano_eleicao);
CREATE INDEX IF NOT EXISTS idx_eleicoes_df_partido ON df_eleicoes_resumo (sigla_partido);

-- ============================================================================
-- 4. VOTO DO DF NAS ELEIÇÕES PRESIDENCIAIS (2022)
-- ============================================================================

CREATE TABLE IF NOT EXISTS df_votacao_presidencia (
    id              SERIAL PRIMARY KEY,
    ano_eleicao     INTEGER NOT NULL DEFAULT 2022,
    turno           INTEGER DEFAULT 2,
    nome_candidato  TEXT NOT NULL,
    sigla_partido   TEXT NOT NULL,
    votos_df        INTEGER DEFAULT 0,
    pct_df          NUMERIC(5,2) DEFAULT 0.0,
    situacao        TEXT DEFAULT 'ELEITO',
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE df_votacao_presidencia IS
    'Votação do DF em eleições presidenciais (2022 T1/T2)';

-- ============================================================================
-- 5. DADOS ATUAIS: DEPUTADOS FEDERAIS DO DF (Câmara, 57ª Leg)
-- ============================================================================

CREATE TABLE IF NOT EXISTS df_deputados_federais_atuais (
    id                  SERIAL PRIMARY KEY,
    deputado_id_camara  INTEGER,               -- ID na API da Câmara
    nome                TEXT NOT NULL,
    sigla_partido       TEXT NOT NULL,
    uf                  CHAR(2) DEFAULT 'DF',
    mandato_inicio      DATE,
    mandato_fim         DATE,
    legislatura         INTEGER DEFAULT 57,    -- 57ª legislatura (2023-2027)
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE df_deputados_federais_atuais IS
    'Deputados Federais do DF em exercício (Câmara, 57ª legislatura 2023-2027)';

CREATE INDEX IF NOT EXISTS idx_depfed_df_partido ON df_deputados_federais_atuais (sigla_partido);

-- ============================================================================
-- 6. VIEWS CONSOLIDADAS
-- ============================================================================

-- View: Resumo de todas as eleições no DF (2022)
DROP VIEW IF EXISTS v_df_eleicoes_resumo CASCADE;
CREATE VIEW v_df_eleicoes_resumo AS
SELECT
    cargo,
    turno,
    nome_candidato,
    sigla_partido,
    votos_total,
    pct_votos,
    coligacao,
    situacao,
    ano_eleicao
FROM df_eleicoes_resumo
WHERE ano_eleicao = 2022
ORDER BY cargo, votos_total DESC;

COMMENT ON VIEW v_df_eleicoes_resumo IS
    'Resultados consolidados das eleições no DF — 2022, todos os cargos';

-- View: Triângulo Político DF (Governador × Senadores × Dep. Fed. × Dep. Distrital)
DROP VIEW IF EXISTS v_df_triangulo_politico CASCADE;
CREATE VIEW v_df_triangulo_politico AS
SELECT
    -- Governador (já existe em governadores_dados)
    g.nome_governador,
    g.sigla_partido AS partido_governador,
    -- Senadores
    s.nome_completo AS senador_nome,
    s.sigla_partido AS partido_senador,
    -- Dep. Federais atuais
    df.nome AS dep_federal_nome,
    df.sigla_partido AS partido_dep_federal,
    -- Dep. Distritais CLDF
    cd.nome_candidato AS dep_distrital_nome,
    cd.sigla_partido AS partido_dep_distrital,
    cd.votos_total AS votos_dep_distrital
FROM governadores_dados g
CROSS JOIN senadores_dados s
LEFT JOIN df_deputados_federais_atuais df ON TRUE
LEFT JOIN df_deputados_distritais_cldf cd ON TRUE
WHERE g.uf = 'DF'
  AND s.uf = 'DF'
  AND s.situacao = 'EM EXERCÍCIO';

COMMENT ON VIEW v_df_triangulo_politico IS
    'Triângulo político do DF: Governador × Senadores × Dep. Federais × Dep. Distritais';

-- View: Bancada por partido no DF (todos os níveis)
DROP VIEW IF EXISTS v_df_bancada_por_partido CASCADE;
CREATE VIEW v_df_bancada_por_partido AS
WITH gov AS (
    SELECT sigla_partido, COUNT(*) AS total, 'GOVERNADOR' AS cargo
    FROM governadores_dados WHERE uf = 'DF'
    GROUP BY sigla_partido
),
sen AS (
    SELECT sigla_partido, COUNT(*) AS total, 'SENADOR' AS cargo
    FROM senadores_dados WHERE uf = 'DF' AND situacao = 'EM EXERCÍCIO'
    GROUP BY sigla_partido
),
dfed AS (
    SELECT sigla_partido, COUNT(*) AS total, 'DEP_FEDERAL' AS cargo
    FROM df_deputados_federais_atuais WHERE uf = 'DF'
    GROUP BY sigla_partido
),
dcl AS (
    SELECT sigla_partido, COUNT(*) AS total, 'DEP_DISTRITAL' AS cargo
    FROM df_deputados_distritais_cldf WHERE situacao = 'ELEITO'
    GROUP BY sigla_partido
)
SELECT sigla_partido, cargo, total FROM gov
UNION ALL
SELECT sigla_partido, cargo, total FROM sen
UNION ALL
SELECT sigla_partido, cargo, total FROM dfed
UNION ALL
SELECT sigla_partido, cargo, total FROM dcl
ORDER BY sigla_partido, cargo;

COMMENT ON VIEW v_df_bancada_por_partido IS
    'Bancada do DF por partido em todos os níveis: Governador, Senado, Câmara Federal, CLDF';

-- View: Resumo completo DF (quantitativo por nível)
DROP VIEW IF EXISTS v_df_resumo_quantitativo CASCADE;
CREATE VIEW v_df_resumo_quantitativo AS
SELECT
    'GOVERNADOR' AS nivel,
    COUNT(*) AS total_parlamentares,
    COUNT(DISTINCT g.sigla_partido) AS total_partidos,
    ARRAY_AGG(DISTINCT g.sigla_partido ORDER BY g.sigla_partido) AS partidos
FROM governadores_dados g WHERE g.uf = 'DF'
UNION ALL
SELECT
    'SENADOR' AS nivel,
    COUNT(*) AS total_parlamentares,
    COUNT(DISTINCT s.sigla_partido) AS total_partidos,
    ARRAY_AGG(DISTINCT s.sigla_partido ORDER BY s.sigla_partido) AS partidos
FROM senadores_dados s WHERE s.uf = 'DF' AND s.situacao = 'EM EXERCÍCIO'
UNION ALL
SELECT
    'DEP_FEDERAL' AS nivel,
    COUNT(*) AS total_parlamentares,
    COUNT(DISTINCT df.sigla_partido) AS total_partidos,
    ARRAY_AGG(DISTINCT df.sigla_partido ORDER BY df.sigla_partido) AS partidos
FROM df_deputados_federais_atuais df WHERE df.uf = 'DF'
UNION ALL
SELECT
    'DEP_DISTRITAL_CLDF' AS nivel,
    COUNT(*) AS total_parlamentares,
    COUNT(DISTINCT cd.sigla_partido) AS total_partidos,
    ARRAY_AGG(DISTINCT cd.sigla_partido ORDER BY cd.sigla_partido) AS partidos
FROM df_deputados_distritais_cldf cd WHERE cd.situacao = 'ELEITO';

COMMENT ON VIEW v_df_resumo_quantitativo IS
    'Resumo quantitativo de parlamentares do DF por nível (Governador a Dep. Distrital)';

-- View: Emendas no DF por nível político
DROP VIEW IF EXISTS v_df_emendas_por_nivel CASCADE;
CREATE VIEW v_df_emendas_por_nivel AS
SELECT
    'DEP_FEDERAL' AS nivel,
    p.nome AS parlamentar_nome,
    COUNT(pa.id) AS total_planos,
    SUM(pa.valor_total) AS valor_total
FROM planos_acao pa
JOIN parlamentares p ON pa.parlamentar_id = p.parlamentar_id
WHERE p.UF = 'DF'
GROUP BY p.nome
UNION ALL
SELECT
    'DEP_DISTRITAL' AS nivel,
    cd.nome_candidato AS parlamentar_nome,
    0 AS total_planos,
    0::NUMERIC AS valor_total
FROM df_deputados_distritais_cldf cd
WHERE cd.situacao = 'ELEITO'
ORDER BY nivel, valor_total DESC NULLS LAST;

COMMENT ON VIEW v_df_emendas_por_nivel IS
    'Emendas PIX do DF, separadas por nível parlamentar (Fed. vs Distrital)';

-- ============================================================================
-- 7. GRANTS
-- ============================================================================

GRANT ALL PRIVILEGES ON TABLE df_regioes_administrativas TO cognee;
GRANT ALL PRIVILEGES ON TABLE df_deputados_distritais_cldf TO cognee;
GRANT ALL PRIVILEGES ON TABLE df_eleicoes_resumo TO cognee;
GRANT ALL PRIVILEGES ON TABLE df_votacao_presidencia TO cognee;
GRANT ALL PRIVILEGES ON TABLE df_deputados_federais_atuais TO cognee;
GRANT ALL PRIVILEGES ON v_df_eleicoes_resumo TO cognee;
GRANT ALL PRIVILEGES ON v_df_triangulo_politico TO cognee;
GRANT ALL PRIVILEGES ON v_df_bancada_por_partido TO cognee;
GRANT ALL PRIVILEGES ON v_df_resumo_quantitativo TO cognee;
GRANT ALL PRIVILEGES ON v_df_emendas_por_nivel TO cognee;

-- Grants nas sequences
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO cognee;

COMMIT;
