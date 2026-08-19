-- ============================================================================
-- TransfereGov — Migration 049: Enriquecimento CLDF (Proposições, Emendas, etc.)
-- ============================================================================
-- Banco: transferegov_db
-- Data: 2026-08-18
-- Fontes: PLE API CLDF (proposições), CKAN dados.cl.df.gov.br (CSVs)
-- ============================================================================
-- Adiciona tabelas de enriquecimento para deputados distritais do DF:
--   1. cldf_proposicoes        (PLE API — proposições legislativas)
--   2. cldf_emendas             (CKAN — emendas orçamentárias)
--   3. cldf_despesas            (CKAN — despesas por unidade orçamentária)
--   4. cldf_empenhos            (CKAN — notas de empenho)
--   5. cldf_verbas_indenizatorias (CKAN — verbas de gabinete)
--   6. Views consolidadas para o dashboard
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. PROPOSIÇÕES LEGISLATIVAS (PLE API — Câmara Distrital do DF)
-- ============================================================================

CREATE TABLE IF NOT EXISTS cldf_proposicoes (
    id                  SERIAL PRIMARY KEY,
    proposicao_id       TEXT NOT NULL UNIQUE,       -- ID original da API PLE
    tipo                TEXT NOT NULL,               -- PL, PLP, PDC, etc.
    numero              INTEGER,
    ano                 INTEGER NOT NULL,
    ementa              TEXT,
    regiao_admin        TEXT,                        -- Região administrativa (quando aplicável)
    tema                TEXT,                        -- Tema legislativo (66 temas disponíveis)
    autor_nome          TEXT,                        -- Nome do autor
    autor_cpf           TEXT,                        -- CPF do autor (quando disponível)
    data_apresentacao   DATE,
    situacao_atual      TEXT,                        -- Situação da proposição
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE cldf_proposicoes IS
    'Proposições legislativas da CLDF (PLE API) — PLs, PLPs, etc.';
COMMENT ON COLUMN cldf_proposicoes.proposicao_id IS
    'ID único da proposição na API PLE (ex: "PL 1234/2024")';
COMMENT ON COLUMN cldf_proposicoes.tema IS
    'Tema legislativo (66 temas disponíveis na API PLE)';

CREATE INDEX IF NOT EXISTS idx_cldf_prop_ano ON cldf_proposicoes (ano);
CREATE INDEX IF NOT EXISTS idx_cldf_prop_tipo ON cldf_proposicoes (tipo);
CREATE INDEX IF NOT EXISTS idx_cldf_prop_tema ON cldf_proposicoes (tema);
CREATE INDEX IF NOT EXISTS idx_cldf_prop_autor ON cldf_proposicoes (autor_nome);

-- ============================================================================
-- 2. EMENDAS ORÇAMENTÁRIAS (CKAN — dados.cl.df.gov.br)
-- Fonte: CSV com delimitador ";", 18 colunas
-- ============================================================================

CREATE TABLE IF NOT EXISTS cldf_emendas (
    id                      SERIAL PRIMARY KEY,
    ano_emenda              INTEGER NOT NULL,
    data_emenda             TIMESTAMP,
    id_emenda               INTEGER NOT NULL UNIQUE,    -- ID original
    lei_emenda              TEXT,                        -- Ex: "7650/2024(PL1294-2024)"
    nr_emenda               TEXT,                        -- Número da emenda
    pt                      TEXT,                        -- Código PT
    pt_compartilhado        INTEGER DEFAULT 0,
    status_emenda           TEXT DEFAULT 'ATIVO',        -- ATIVO, CANCELADO, etc.
    cod_uo                  TEXT,                        -- Código Unidade Orçamentária
    nome_uo                 TEXT,                        -- Nome da UO
    vl_lei_alteracao        NUMERIC(15,2) DEFAULT 0,    -- Valor da lei de alteração
    vl_bloqueado_siggo      NUMERIC(15,2) DEFAULT 0,    -- Valor bloqueado SIGGO
    vl_disponivel           NUMERIC(15,2) DEFAULT 0,    -- Valor disponível
    vl_empenhado            NUMERIC(15,2) DEFAULT 0,    -- Valor empenhado
    vl_emenda               NUMERIC(15,2) DEFAULT 0,    -- Valor total da emenda
    vl_desbloqueado         NUMERIC(15,2) DEFAULT 0,    -- Valor desbloqueado
    vl_saldo_a_solicitar    NUMERIC(15,2) DEFAULT 0,    -- Saldo a solicitar
    vl_liquidado            NUMERIC(15,2) DEFAULT 0,    -- Valor liquidado
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE cldf_emendas IS
    'Emendas orçamentárias da CLDF (CKAN dados.cl.df.gov.br)';
COMMENT ON COLUMN cldf_emendas.id_emenda IS
    'ID único da emenda no portal CLDF';
COMMENT ON COLUMN cldf_emendas.cod_uo IS
    'Código da Unidade Orçamentária (ex: 160101 = Secretaria de Educação)';

CREATE INDEX IF NOT EXISTS idx_cldf_emendas_ano ON cldf_emendas (ano_emenda);
CREATE INDEX IF NOT EXISTS idx_cldf_emendas_uo ON cldf_emendas (cod_uo);
CREATE INDEX IF NOT EXISTS idx_cldf_emendas_status ON cldf_emendas (status_emenda);
CREATE INDEX IF NOT EXISTS idx_cldf_emendas_vl ON cldf_emendas (vl_empenhado DESC);

-- ============================================================================
-- 3. DESPESAS POR UNIDADE ORÇAMENTÁRIA (CKAN)
-- Fonte: CSV com delimitador ";", 6 colunas (UO, Ano, Mês, Empenhado, Liquidado, Pago)
-- ============================================================================

CREATE TABLE IF NOT EXISTS cldf_despesas (
    id                  SERIAL PRIMARY KEY,
    ano                 INTEGER NOT NULL,
    mes                 TEXT NOT NULL,                    -- "Janeiro", "Fevereiro", etc.
    uo_codigo           TEXT NOT NULL,                    -- Código da Unidade Orçamentária
    empenhado           NUMERIC(15,2) DEFAULT 0,
    liquidado           NUMERIC(15,2) DEFAULT 0,
    pago                NUMERIC(15,2) DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(ano, mes, uo_codigo)
);

COMMENT ON TABLE cldf_despesas IS
    'Despesas por Unidade Orçamentária do DF (CKAN dados.cl.df.gov.br)';

CREATE INDEX IF NOT EXISTS idx_cldf_despesas_ano ON cldf_despesas (ano);
CREATE INDEX IF NOT EXISTS idx_cldf_despesas_uo ON cldf_despesas (uo_codigo);

-- ============================================================================
-- 4. EMPENHOS (CKAN — Notas de Empenho)
-- Fonte: CSV com delimitador ";", 10 colunas
-- ============================================================================

CREATE TABLE IF NOT EXISTS cldf_empenhos (
    id                      SERIAL PRIMARY KEY,
    ano                     INTEGER NOT NULL,
    mes                     TEXT NOT NULL,                    -- "janeiro", "fevereiro", etc.
    numero_ne               TEXT NOT NULL UNIQUE,             -- Número da NE
    credor                  TEXT,                             -- Nome do credor
    especificacao           TEXT,                             -- Descrição do empenho
    quantidade              INTEGER,
    valor_unitario          NUMERIC(12,2),
    valor_total             NUMERIC(12,2) DEFAULT 0,
    modalidade              TEXT,                             -- "Pregão", "Inexigível", etc.
    identificacao           TEXT,                             -- Código de identificação
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE cldf_empenhos IS
    'Notas de empenho do DF (CKAN dados.cl.df.gov.br)';
COMMENT ON COLUMN cldf_empenhos.numero_ne IS
    'Número único da Nota de Empenho (ex: "2022NE00001")';
COMMENT ON COLUMN cldf_empenhos.modalidade IS
    'Modalidade de licitação: Pregão, Inexigível, Dispensa, etc.';

CREATE INDEX IF NOT EXISTS idx_cldf_empenhos_ano ON cldf_empenhos (ano);
CREATE INDEX IF NOT EXISTS idx_cldf_empenhos_credor ON cldf_empenhos (credor);
CREATE INDEX IF NOT EXISTS idx_cldf_empenhos_modalidade ON cldf_empenhos (modalidade);
CREATE INDEX IF NOT EXISTS idx_cldf_empenhos_valor ON cldf_empenhos (valor_total DESC);

-- ============================================================================
-- 5. VERBAS INDENIZATÓRIAS (CKAN — Despesas de Gabinete)
-- Fonte: CSV com delimitador ";", 10 colunas
-- ============================================================================

CREATE TABLE IF NOT EXISTS cldf_verbas_indenizatorias (
    id                  SERIAL PRIMARY KEY,
    nome_parlamentar    TEXT NOT NULL,
    cpf_parlamentar     TEXT,
    nome_prestador      TEXT,
    cnpj_prestador      TEXT,
    cpf_prestador       TEXT,
    nr_comprovante      TEXT,
    data_comprovante    DATE,
    valor_despesa       NUMERIC(12,2) DEFAULT 0,
    classificacao       TEXT,                             -- "Combustíveis", "Alimentação", etc.
    observacoes         TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE cldf_verbas_indenizatorias IS
    'Verbas indenizatórias/de gabinete dos deputados distritais (CKAN)';
COMMENT ON COLUMN cldf_verbas_indenizatorias.classificacao IS
    'Classificação da despesa: Combustíveis, Alimentação, Material, etc.';

CREATE INDEX IF NOT EXISTS idx_cldf_verbas_parl ON cldf_verbas_indenizatorias (nome_parlamentar);
CREATE INDEX IF NOT EXISTS idx_cldf_verbas_class ON cldf_verbas_indenizatorias (classificacao);
CREATE INDEX IF NOT EXISTS idx_cldf_verbas_data ON cldf_verbas_indenizatorias (data_comprovante);
CREATE INDEX IF NOT EXISTS idx_cldf_verbas_valor ON cldf_verbas_indenizatorias (valor_despesa DESC);

-- ============================================================================
-- 6. VIEWS CONSOLIDADAS
-- ============================================================================

-- 6a. Resumo de emendas por deputado (via join com tabela de deputados)
CREATE OR REPLACE VIEW v_cldf_emendas_por_deputado AS
SELECT
    d.id AS deputado_id,
    d.nome_candidato,
    d.sigla_partido,
    e.ano_emenda,
    COUNT(*) AS total_emendas,
    SUM(e.vl_empenhado) AS total_empenhado,
    SUM(e.vl_liquidado) AS total_liquidado,
    SUM(e.vl_emenda) AS total_valor_emenda
FROM df_deputados_distritais_cldf d
LEFT JOIN cldf_emendas e ON e.nome_uo ILIKE '%' || d.nome_candidato || '%'
GROUP BY d.id, d.nome_candidato, d.sigla_partido, e.ano_emenda
ORDER BY total_empenhado DESC;

COMMENT ON VIEW v_cldf_emendas_por_deputado IS
    'Resumo de emendas por deputado distrital (join com tabela de deputados)';

-- 6b. Resumo de verbas por deputado
CREATE OR REPLACE VIEW v_cldf_verbas_por_deputado AS
SELECT
    d.id AS deputado_id,
    d.nome_candidato,
    d.sigla_partido,
    v.classificacao,
    COUNT(*) AS total_despesas,
    SUM(v.valor_despesa) AS total_valor,
    AVG(v.valor_despesa) AS media_valor,
    MIN(v.data_comprovante) AS primeira_despesa,
    MAX(v.data_comprovante) AS ultima_despesa
FROM df_deputados_distritais_cldf d
LEFT JOIN cldf_verbas_indenizatorias v
    ON v.nome_parlamentar ILIKE '%' || d.nome_candidato || '%'
GROUP BY d.id, d.nome_candidato, d.sigla_partido, v.classificacao
ORDER BY total_valor DESC;

COMMENT ON VIEW v_cldf_verbas_por_deputado IS
    'Verbas indenizatórias por deputado distrital e classificação';

-- 6c. Resumo de proposições por tema
CREATE OR REPLACE VIEW v_cldf_proposicoes_por_tema AS
SELECT
    tema,
    COUNT(*) AS total_proposicoes,
    MIN(ano) AS primeira_proposicao,
    MAX(ano) AS ultima_proposicao
FROM cldf_proposicoes
WHERE tema IS NOT NULL
GROUP BY tema
ORDER BY total_proposicoes DESC;

COMMENT ON VIEW v_cldf_proposicoes_por_tema IS
    'Distribuição de proposições por tema legislativo';

-- 6d. Resumo de empenhos por modalidade
CREATE OR REPLACE VIEW v_cldf_empenhos_por_modalidade AS
SELECT
    ano,
    modalidade,
    COUNT(*) AS total_empenhos,
    SUM(valor_total) AS valor_total,
    AVG(valor_total) AS valor_medio,
    MAX(valor_total) AS maior_empenho
FROM cldf_empenhos
WHERE modalidade IS NOT NULL
GROUP BY ano, modalidade
ORDER BY ano DESC, valor_total DESC;

COMMENT ON VIEW v_cldf_empenhos_por_modalidade IS
    'Empenhos do DF por modalidade de licitação e ano';

-- ============================================================================
-- FIM
-- ============================================================================
COMMIT;
