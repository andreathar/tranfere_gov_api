-- ============================================================================
-- TransfereGov — Migration: Novas Fontes de Dados
-- ============================================================================
-- Banco: transferegov_db
-- Data: 2026-07-24
-- Descrição: Tabelas de compras públicas, saúde, educação e violência municipal
--            plus materialized views para consultas cruzadas e tendências.
-- Pré-requisitos: migration_003_enrichment.sql (municipios_ibge),
--                 migration_005_unificacao.sql (v_emendas_unificadas),
--                 migration_008_enriched_views.sql (beneficiario_ibge_map)
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. TABELA — Compras Públicas (PNCP, Contratos.gov, Dados Abertos)
-- ============================================================================
-- Licitações, contratos e dispensas por município vinculados a fontes abertas

CREATE TABLE IF NOT EXISTS compras_municipios (
    id                  SERIAL PRIMARY KEY,
    municipio_id        INTEGER REFERENCES municipios_ibge(municipio_id),
    fonte               TEXT NOT NULL,           -- 'PNCP', 'CONTRATOS_GOV', 'DADOS_ABERTOS'
    tipo_documento      TEXT NOT NULL,           -- 'LICITACAO', 'CONTRATO', 'DISPENSA'
    numero              TEXT,
    descricao           TEXT,
    valor_estimado      NUMERIC(15,2),
    valor_homologado    NUMERIC(15,2),
    data_publicacao     DATE,
    data_vigencia       DATE,
    modalidade          TEXT,
    cnpj_orgao          TEXT,
    nome_orgao          TEXT,
    cnpj_fornecedor     TEXT,
    nome_fornecedor     TEXT,
    status              TEXT,
    uf                  CHAR(2),
    extracted_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (fonte, tipo_documento, numero, municipio_id)
);

-- ============================================================================
-- 2. TABELA — Saúde Municipal (CNES/DataSUS)
-- ============================================================================
-- Indicadores consolidados de estabelecimentos, leitos e profissionais por município

CREATE TABLE IF NOT EXISTS saude_municipios (
    municipio_id                INTEGER PRIMARY KEY REFERENCES municipios_ibge(municipio_id),
    total_estabelecimentos      INTEGER DEFAULT 0,
    estabelecimentos_ativos     INTEGER DEFAULT 0,
    total_leitos                INTEGER DEFAULT 0,
    leitos_sus                  INTEGER DEFAULT 0,
    total_profissionais         INTEGER DEFAULT 0,
    hospitais                   INTEGER DEFAULT 0,
    ubs                         INTEGER DEFAULT 0,
    caps                        INTEGER DEFAULT 0,
    extracted_at                TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 3. TABELA — Educação Municipal (INEP/IDEB)
-- ============================================================================
-- Indicadores educacionais consolidados por município (IDEB, aprovação, matrículas)

CREATE TABLE IF NOT EXISTS educacao_municipios (
    municipio_id        INTEGER PRIMARY KEY REFERENCES municipios_ibge(municipio_id),
    ideb_initial_years  REAL,                   -- IDEB anos iniciais (1º ao 5º ano)
    ideb_final_years    REAL,                   -- IDEB anos finais (6º ao 9º ano)
    taxa_aprovacao      REAL,
    taxa_abandono       REAL,
    media_tap           REAL,
    escolas_totais      INTEGER DEFAULT 0,
    matriculas_totais   INTEGER DEFAULT 0,
    extracted_at        TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 4. TABELA — Violência Municipal (Atlas da Violência / ISP/DEMATRAN)
-- ============================================================================
-- Estatísticas criminais por município e ano de referência

CREATE TABLE IF NOT EXISTS violencia_municipios (
    id                  SERIAL PRIMARY KEY,
    municipio_id        INTEGER REFERENCES municipios_ibge(municipio_id),
    ano_referencia      INTEGER NOT NULL,
    homicidios          INTEGER DEFAULT 0,
    taxa_homicidios     REAL,                   -- por 100 mil habitantes
    mortes_transito     INTEGER DEFAULT 0,
    roubos              INTEGER DEFAULT 0,
    furto               INTEGER DEFAULT 0,
    violencia_genero    INTEGER DEFAULT 0,
    extracted_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (municipio_id, ano_referencia)
);

-- ============================================================================
-- 5. ÍNDICES — Compras Públicas
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_cm_municipio ON compras_municipios(municipio_id);
CREATE INDEX IF NOT EXISTS idx_cm_fonte ON compras_municipios(fonte);
CREATE INDEX IF NOT EXISTS idx_cm_tipo ON compras_municipios(tipo_documento);
CREATE INDEX IF NOT EXISTS idx_cm_uf ON compras_municipios(uf);
CREATE INDEX IF NOT EXISTS idx_cm_data ON compras_municipios(data_publicacao);
CREATE INDEX IF NOT EXISTS idx_cm_orgao_cnpj ON compras_municipios(cnpj_orgao);
CREATE INDEX IF NOT EXISTS idx_cm_fornecedor_cnpj ON compras_municipios(cnpj_fornecedor);

-- ============================================================================
-- 6. ÍNDICES — Saúde Municipal
-- ============================================================================

-- saude_municipios já tem PK em municipio_id (índice implícito)

-- ============================================================================
-- 7. ÍNDICES — Educação Municipal
-- ============================================================================

-- educacao_municipios já tem PK em municipio_id (índice implícito)

-- ============================================================================
-- 8. ÍNDICES — Violência Municipal
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_vm_municipio ON violencia_municipios(municipio_id);
CREATE INDEX IF NOT EXISTS idx_vm_ano ON violencia_municipios(ano_referencia);

-- ============================================================================
-- 9. MATERIALIZED VIEW — Cruzamento Multi-Fontes por Município
-- ============================================================================
-- Cruza dados de emendas, compras, saúde e educação em uma única tabela
-- para consultas nos dashboards. Requer REFRESH MATERIALIZED VIEW após
-- atualização de qualquer tabela fonte.

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_cruzamento_multi_fontes AS
SELECT
    m.municipio_id,
    m.nome AS municipio,
    m.uf,
    m.regiao,
    m.populacao,
    m.idhm,
    -- Emendas
    COALESCE(SUM(DISTINCT ve.valor_total), 0) AS total_emendas,
    COUNT(DISTINCT ve.codigo_emenda) AS qtd_emendas,
    -- Compras
    COALESCE(cm.total_licitacoes, 0) AS total_licitacoes,
    COALESCE(cm.total_contratos, 0) AS total_contratos,
    COALESCE(cm.valor_total_compras, 0) AS valor_total_compras,
    -- Saúde
    COALESCE(sm.total_estabelecimentos, 0) AS total_estabelecimentos,
    COALESCE(sm.total_leitos, 0) AS total_leitos,
    COALESCE(sm.leitos_sus, 0) AS leitos_sus,
    COALESCE(sm.hospitais, 0) AS hospitais,
    -- Educação
    em.ideb_initial_years,
    em.ideb_final_years,
    COALESCE(em.matriculas_totais, 0) AS matriculas_totais,
    -- Índices derivados
    CASE WHEN m.populacao > 0
         THEN ROUND(SUM(DISTINCT ve.valor_total)::NUMERIC / m.populacao, 2)
         ELSE 0
    END AS emendas_per_capita,
    CASE WHEN m.populacao > 0
         THEN ROUND(sm.total_leitos::NUMERIC / m.populacao * 10000, 2)
         ELSE 0
    END AS leitos_por_10k
FROM municipios_ibge m
LEFT JOIN beneficiario_ibge_map bm ON m.municipio_id = bm.municipio_id
LEFT JOIN beneficiarios b ON bm.beneficiario_id = b.beneficiario_id
LEFT JOIN v_emendas_unificadas ve ON b.nome = ve.beneficiario_nome
LEFT JOIN (
    SELECT municipio_id,
           COUNT(*) FILTER (WHERE tipo_documento = 'LICITACAO') AS total_licitacoes,
           COUNT(*) FILTER (WHERE tipo_documento = 'CONTRATO') AS total_contratos,
           SUM(COALESCE(valor_homologado, valor_estimado, 0)) AS valor_total_compras
    FROM compras_municipios
    GROUP BY municipio_id
) cm ON m.municipio_id = cm.municipio_id
LEFT JOIN saude_municipios sm ON m.municipio_id = sm.municipio_id
LEFT JOIN educacao_municipios em ON m.municipio_id = em.municipio_id
GROUP BY
    m.municipio_id, m.nome, m.uf, m.regiao, m.populacao, m.idhm,
    cm.total_licitacoes, cm.total_contratos, cm.valor_total_compras,
    sm.total_estabelecimentos, sm.total_leitos, sm.leitos_sus, sm.hospitais,
    em.ideb_initial_years, em.ideb_final_years, em.matriculas_totais
WITH DATA;

-- ============================================================================
-- 10. MATERIALIZED VIEW — Tendência Temporal de Planos de Ação
-- ============================================================================
-- Agrega planos de ação por mês de extração e situação para gráficos de
-- série temporal. Atualizado com REFRESH MATERIALIZED VIEW.

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_tendencia_temporal AS
SELECT
    DATE_TRUNC('month', extracted_at) AS mes,
    COUNT(*) AS total_planos,
    SUM(valor_total) AS valor_total,
    COUNT(DISTINCT parlamentar_nome) AS parlamentares,
    COUNT(DISTINCT beneficiario_id) AS municipios,
    plano_acao_situacao AS situacao
FROM planos_acao
WHERE extracted_at IS NOT NULL
GROUP BY DATE_TRUNC('month', extracted_at), plano_acao_situacao
ORDER BY mes DESC
WITH DATA;

-- ============================================================================
-- 11. ÍNDICES EM MATERIALIZED VIEWS
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_mvcf_municipio ON mv_cruzamento_multi_fontes(municipio_id);
CREATE INDEX IF NOT EXISTS idx_mvcf_uf ON mv_cruzamento_multi_fontes(uf);
CREATE INDEX IF NOT EXISTS idx_mvcf_regiao ON mv_cruzamento_multi_fontes(regiao);

CREATE INDEX IF NOT EXISTS idx_mvt_mes ON mv_tendencia_temporal(mes);
CREATE INDEX IF NOT EXISTS idx_mvt_situacao ON mv_tendencia_temporal(situacao);

-- ============================================================================
-- 12. GRANTS
-- ============================================================================

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO cognee;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO cognee;

COMMIT;
