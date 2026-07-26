-- ============================================================================
-- TransfereGov — Migration: Arrecadação de Impostos (SICONFI/RREO Anexo 03)
-- ============================================================================
-- Banco: transferegov_db
-- Data: 2026-07-25
-- Fonte: API SICONFI — RREO Anexo 03 (Receita Corrente Líquida)
-- API: https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo
-- ============================================================================

-- ============================================================================
-- 1. NOVAS COLUNAS — Arrecadação de impostos por município/ano
-- ============================================================================
-- Adiciona colunas de impostos à tabela municipios_financeiro existente.
-- Valores são a SOMA dos 6 bimestres do RREO Anexo 03 para o exercício.

ALTER TABLE municipios_financeiro
    ADD COLUMN IF NOT EXISTS arrec_iptu           NUMERIC(15,2),
    ADD COLUMN IF NOT EXISTS arrec_iss             NUMERIC(15,2),
    ADD COLUMN IF NOT EXISTS arrec_itbi            NUMERIC(15,2),
    ADD COLUMN IF NOT EXISTS arrec_irrf            NUMERIC(15,2),
    ADD COLUMN IF NOT EXISTS arrec_cota_icms       NUMERIC(15,2),
    ADD COLUMN IF NOT EXISTS arrec_cota_ipva       NUMERIC(15,2),
    ADD COLUMN IF NOT EXISTS arrec_cota_itr        NUMERIC(15,2),
    ADD COLUMN IF NOT EXISTS arrec_cota_fpm        NUMERIC(15,2),
    ADD COLUMN IF NOT EXISTS arrec_impostos_geral  NUMERIC(15,2),
    ADD COLUMN IF NOT EXISTS arrec_transferencias  NUMERIC(15,2),
    ADD COLUMN IF NOT EXISTS arrec_receita_servicos NUMERIC(15,2),
    ADD COLUMN IF NOT EXISTS arrec_receita_patrimonial NUMERIC(15,2),
    ADD COLUMN IF NOT EXISTS arrec_receitas_correntes  NUMERIC(15,2),
    ADD COLUMN IF NOT EXISTS arrec_fonte_rreo      TEXT,
    ADD COLUMN IF NOT EXISTS arrec_atualizado_em   TIMESTAMPTZ;

-- ============================================================================
-- 2. ÍNDICES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_mf_arrec_fonte ON municipios_financeiro(arrec_fonte_rreo)
    WHERE arrec_fonte_rreo IS NOT NULL;

-- ============================================================================
-- 3. VIEW — Arrecadação de impostos por município com nomes amigáveis
-- ============================================================================

CREATE OR REPLACE VIEW v_arrecadacao_impostos AS
SELECT
    m.municipio_id,
    m.nome AS municipio,
    m.uf,
    mf.exercicio,

    -- Impostos próprios
    mf.arrec_iptu,
    mf.arrec_iss,
    mf.arrec_itbi,
    mf.arrec_irrf,

    -- Cotas-partes de impostos estaduais/federais
    mf.arrec_cota_icms,
    mf.arrec_cota_ipva,
    mf.arrec_cota_itr,
    mf.arrec_cota_fpm,

    -- Totais derivados
    COALESCE(mf.arrec_iptu, 0) + COALESCE(mf.arrec_iss, 0)
        + COALESCE(mf.arrec_itbi, 0) + COALESCE(mf.arrec_irrf, 0)
        + COALESCE(mf.arrec_cota_icms, 0) + COALESCE(mf.arrec_cota_ipva, 0)
        + COALESCE(mf.arrec_cota_itr, 0) + COALESCE(mf.arrec_cota_fpm, 0)
        AS total_impostos_calculado,

    mf.arrec_receitas_correntes,
    mf.arrec_transferencias,

    -- Razão impostos próprios / receitas correntes
    ROUND(
        100.0 * (COALESCE(mf.arrec_iptu, 0) + COALESCE(mf.arrec_iss, 0)
               + COALESCE(mf.arrec_itbi, 0) + COALESCE(mf.arrec_irrf, 0))
        / NULLIF(mf.arrec_receitas_correntes, 0),
        2
    ) AS razao_impostos_proprios_pct,

    -- Razão transferências / receitas correntes (dependência)
    ROUND(
        100.0 * COALESCE(mf.arrec_transferencias, 0)
        / NULLIF(mf.arrec_receitas_correntes, 0),
        2
    ) AS razao_transferencias_pct

FROM municipios_financeiro mf
JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
WHERE mf.arrec_fonte_rreo IS NOT NULL;

-- ============================================================================
-- 4. VIEW — Resumo por estado (agregado)
-- ============================================================================

CREATE OR REPLACE VIEW v_arrecadacao_por_estado AS
SELECT
    uf,
    exercicio,
    COUNT(*) AS num_municipios,
    SUM(arrec_iptu) AS total_iptu,
    SUM(arrec_iss) AS total_iss,
    SUM(arrec_itbi) AS total_itbi,
    SUM(arrec_cota_icms) AS total_cota_icms,
    SUM(arrec_cota_ipva) AS total_cota_ipva,
    SUM(arrec_cota_fpm) AS total_cota_fpm,
    SUM(arrec_receitas_correntes) AS total_receitas_correntes,
    SUM(arrec_transferencias) AS total_transferencias,
    ROUND(AVG(
        100.0 * (COALESCE(arrec_iptu, 0) + COALESCE(arrec_iss, 0)
               + COALESCE(arrec_itbi, 0) + COALESCE(arrec_irrf, 0))
        / NULLIF(arrec_receitas_correntes, 0)
    ), 2) AS media_razao_impostos_pct
FROM v_arrecadacao_impostos
GROUP BY uf, exercicio
ORDER BY uf, exercicio;

-- ============================================================================
-- 5. GRANTS
-- ============================================================================

GRANT SELECT ON v_arrecadacao_impostos TO cognee;
GRANT SELECT ON v_arrecadacao_por_estado TO cognee;
