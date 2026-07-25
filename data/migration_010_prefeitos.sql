-- ============================================================================
-- TransfereGov — Migration 010: Tabela e View Canônica de Prefeitos
-- ============================================================================
-- Banco: transferegov_db
-- Data: 2026-07-25
-- ============================================================================

BEGIN;

-- 1. Tabela de Perfil dos Prefeitos (Dados TSE / Eleições)
CREATE TABLE IF NOT EXISTS prefeitos_dados (
    municipio_id INTEGER PRIMARY KEY REFERENCES municipios_ibge(municipio_id),
    municipio_nome TEXT,
    uf CHAR(2),
    prefeito_nome TEXT NOT NULL,
    prefeito_cpf_parcial TEXT,
    sigla_partido TEXT,
    ano_eleicao INTEGER DEFAULT 2024,
    situacao_candidatura TEXT DEFAULT 'ELEITO',
    patrimonio_total NUMERIC(15,2) DEFAULT 0.00,
    votos_totais INTEGER DEFAULT 0,
    percentual_votos NUMERIC(5,2) DEFAULT 0.00,
    vice_prefeito_nome TEXT,
    coligacao TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Indexação para busca por nome e partido
CREATE INDEX IF NOT EXISTS idx_prefeitos_nome ON prefeitos_dados (prefeito_nome);
CREATE INDEX IF NOT EXISTS idx_prefeitos_partido ON prefeitos_dados (sigla_partido);
CREATE INDEX IF NOT EXISTS idx_prefeitos_uf ON prefeitos_dados (uf);

-- 3. View Canônica Enriquecida de Prefeitos e Gestão Municipal
DROP VIEW IF EXISTS v_prefeitos_completo CASCADE;
CREATE VIEW v_prefeitos_completo AS
SELECT 
    p.municipio_id,
    p.municipio_nome,
    p.uf,
    p.prefeito_nome,
    p.sigla_partido AS prefeito_partido,
    p.ano_eleicao,
    p.situacao_candidatura,
    p.patrimonio_total,
    p.votos_totais,
    p.percentual_votos,
    p.vice_prefeito_nome,
    p.coligacao,
    -- Dados IBGE
    m.regiao AS ibge_regiao,
    m.populacao AS ibge_populacao,
    m.idhm AS ibge_idhm,
    -- Dados SICONFI (Finanças Municipais)
    mf.receitas_correntes AS siconfi_receitas_correntes,
    mf.despesas_correntes AS siconfi_despesas_correntes,
    mf.despesas_capital AS siconfi_despesas_capital,
    ROUND((COALESCE(mf.receitas_correntes, 0) - COALESCE(mf.receitas_transferencias, 0)) / NULLIF(mf.receitas_correntes, 0) * 100, 2) AS siconfi_autonomia_fiscal_pct,
    -- Resumo de Emendas Pix & Convênios Recebidos pela Prefeitura
    COALESCE(em.total_emendas, 0) AS total_emendas_recebidas,
    COALESCE(em.valor_total_emendas, 0.00) AS valor_total_emendas,
    COALESCE(em.valor_aprovado, 0.00) AS valor_emendas_aprovadas,
    COALESCE(em.valor_impedido, 0.00) AS valor_emendas_impedidas,
    -- Indicadores Derivados
    ROUND(COALESCE(em.valor_total_emendas, 0) / NULLIF(m.populacao, 0), 2) AS emendas_per_capita,
    p.updated_at
FROM prefeitos_dados p
LEFT JOIN municipios_ibge m ON p.municipio_id = m.municipio_id
LEFT JOIN (
    SELECT DISTINCT ON (municipio_id) *
    FROM municipios_financeiro
    ORDER BY municipio_id, exercicio DESC
) mf ON p.municipio_id = mf.municipio_id
LEFT JOIN (
    SELECT 
        bm.municipio_id,
        COUNT(pa.id) AS total_emendas,
        SUM(pa.valor_total) AS valor_total_emendas,
        SUM(CASE WHEN pa.plano_acao_situacao IN ('CIENTE', 'APROVADO', 'CONCLUIDO', 'EM_EXECUCAO') THEN pa.valor_total ELSE 0 END) AS valor_aprovado,
        SUM(CASE WHEN pa.plano_acao_situacao IN ('IMPEDIDO', 'REPROVADO', 'CANCELADO', 'IMPEDIDO_REJEICAO_PLANO_TRABALHO') THEN pa.valor_total ELSE 0 END) AS valor_impedido
    FROM planos_acao pa
    JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
    JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
    GROUP BY bm.municipio_id
) em ON p.municipio_id = em.municipio_id;

-- 4. Grants
GRANT ALL PRIVILEGES ON TABLE prefeitos_dados TO cognee;
GRANT ALL PRIVILEGES ON v_prefeitos_completo TO cognee;

COMMIT;
