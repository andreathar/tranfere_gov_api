-- ============================================================================
-- TransfereGov — Migration: Tabelas de Enriquecimento
-- ============================================================================
-- Banco: transferegov_db
-- Data: 2026-07-23
-- ============================================================================

-- ============================================================================
-- 1. Validação de CNPJs (BrasilAPI)
-- ============================================================================

CREATE TABLE IF NOT EXISTS validacao_cnpj (
    id                  SERIAL PRIMARY KEY,
    cnpj                TEXT UNIQUE NOT NULL,
    razao_social        TEXT,
    nome_fantasia       TEXT,
    situacao_cadastral  TEXT,
    data_situacao       TEXT,
    porte               TEXT,
    natureza_juridica   TEXT,
    cep                 TEXT,
    telefone            TEXT,
    email               TEXT,
    valido              BOOLEAN,
    erro                TEXT,
    checked_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 2. Dados IBGE dos Municípios
-- ============================================================================

CREATE TABLE IF NOT EXISTS municipios_ibge (
    id                  SERIAL PRIMARY KEY,
    municipio_id        INTEGER UNIQUE NOT NULL,   -- código IBGE
    nome                TEXT NOT NULL,
    uf                  CHAR(2),
    regiao              TEXT,
    mesorregiao         TEXT,
    microrregiao        TEXT,
    populacao           INTEGER,
    pib_per_capita      NUMERIC(15,2),
    area_km2            NUMERIC(12,2),
    densidade_demografica NUMERIC(10,2),
    idhm                NUMERIC(5,3),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 3. Dados Câmara dos Deputados
-- ============================================================================

CREATE TABLE IF NOT EXISTS parlamentares_dados (
    id                  SERIAL PRIMARY KEY,
    deputado_id         INTEGER UNIQUE NOT NULL,
    nome                TEXT NOT NULL,
    nome_urna           TEXT,
    sigla_partido       TEXT,
    uf                  CHAR(2),
    situacao            TEXT,
    gabinete_numero     INTEGER,
    gabinete_predio     TEXT,
    gabinete_telefone   TEXT,
    gabinete_email      TEXT,
    url_foto            TEXT,
    ultimo_status       TEXT,
    data_nascimento     DATE,
    municipio_nascimento TEXT,
    uf_nascimento       CHAR(2),
    escolaridade        TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 4. Vinculação parlamentar → beneficiário
-- ============================================================================

CREATE TABLE IF NOT EXISTS parlamentar_beneficiario (
    id                  SERIAL PRIMARY KEY,
    parlamentar_nome    TEXT NOT NULL,
    beneficiario_id     INTEGER REFERENCES beneficiarios(beneficiario_id),
    emenda_codigo       TEXT,
    valor_total         NUMERIC(15,2),
    plano_acao_situacao TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(parlamentar_nome, beneficiario_id, emenda_codigo)
);

-- ============================================================================
-- 5. ÍNDICES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_vc_cnpj ON validacao_cnpj(cnpj);
CREATE INDEX IF NOT EXISTS idx_vc_valido ON validacao_cnpj(valido);
CREATE INDEX IF NOT EXISTS idx_mi_uf ON municipios_ibge(uf);
CREATE INDEX IF NOT EXISTS idx_mi_nome ON municipios_ibge(nome);
CREATE INDEX IF NOT EXISTS idx_pd_nome ON parlamentares_dados(nome);
CREATE INDEX IF NOT EXISTS idx_pd_partido ON parlamentares_dados(sigla_partido);
CREATE INDEX IF NOT EXISTS idx_pb_parlamentar ON parlamentar_beneficiario(parlamentar_nome);
CREATE INDEX IF NOT EXISTS idx_pb_beneficiario ON parlamentar_beneficiario(beneficiario_id);

-- ============================================================================
-- 6. GRANTS
-- ============================================================================

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO cognee;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO cognee;
