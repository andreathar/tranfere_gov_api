-- ============================================================================
-- TransfereGov — Migration: Dados Financeiros Municipais (SICONFI/Tesouro)
-- ============================================================================
-- Banco: transferegov_db
-- Data: 2026-07-23
-- Fonte: API SICONFI — Declaração de Contas Anuais (DCA)
-- API: https://apidatalake.tesouro.gov.br/ords/siconfi/tt/dca
-- ============================================================================

-- ============================================================================
-- 1. TABELA — Dados financeiros por município/ano
-- ============================================================================
-- Uma linha por município por exercício. Dados extraídos da DCA (Declaração
-- de Contas Anuais), que consolida receitas, despesas, ativos e passivos.

CREATE TABLE IF NOT EXISTS municipios_financeiro (
    municipio_id        INTEGER NOT NULL REFERENCES municipios_ibge(municipio_id),
    exercicio           INTEGER NOT NULL,

    -- Receitas
    receitas_correntes      NUMERIC(15,2),   -- Receitas Correntes (DCA-Anexo I-AB)
    receitas_capital        NUMERIC(15,2),   -- Receitas de Capital
    receitas_orcamentarias  NUMERIC(15,2),   -- Receitas Orçamentárias
    receitas_transferencias NUMERIC(15,2),   -- Transferências Correntes
    receitas_nao_operacionais NUMERIC(15,2), -- Receitas Não Operacionais

    -- Despesas
    despesas_correntes      NUMERIC(15,2),   -- Despesas Correntes
    despesas_capital        NUMERIC(15,2),   -- Despesas de Capital
    despesas_orcamentarias  NUMERIC(15,2),   -- Despesas Orçamentárias
    despesas_financeiras    NUMERIC(15,2),   -- Despesas Financeiras
    despesas_totais         NUMERIC(15,2),   -- Total de Despesas

    -- Resultados
    resultado_orcamentario  NUMERIC(15,2),   -- Resultado Orçamentário
    resultado_primario      NUMERIC(15,2),   -- Resultado Primário
    resultado_financeiro    NUMERIC(15,2),   -- Resultado Financeiro

    -- Patrimônio / Endividamento
    divida_ativa            NUMERIC(15,2),   -- Dívida Ativa
    divida_passiva          NUMERIC(15,2),   -- Dívida Passiva Consolidada
    ativo_imobilizado       NUMERIC(15,2),   -- Ativo Imobilizado
    patrimonio_liquido      NUMERIC(15,2),   -- Patrimônio Líquido

    -- Metadados
    fonte                   TEXT DEFAULT 'SICONFI/DCA',
    atualizado_em           TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (municipio_id, exercicio)
);

-- ============================================================================
-- 2. ÍNDICES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_mf_exercicio ON municipios_financeiro(exercicio);
CREATE INDEX IF NOT EXISTS idx_mf_municipio ON municipios_financeiro(municipio_id);

-- ============================================================================
-- 3. GRANTS
-- ============================================================================

GRANT ALL PRIVILEGES ON municipios_financeiro TO cognee;
