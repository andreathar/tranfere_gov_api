-- ============================================================================
-- TransfereGov — Migration: Dados Financeiros Estaduais (SICONFI/Tesouro)
-- ============================================================================
-- Banco: transferegov_db
-- Data: 2026-07-31
-- Fonte: API SICONFI — Declaração de Contas Anuais (DCA) + RREO Anexo 03
-- API: https://apidatalake.tesouro.gov.br/ords/siconfi/tt/dca
--      https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo
-- Esfera: ESTADUAL (id_ente = código IBGE do estado, ex: 35 = SP)
--
-- Complementa municipios_financeiro (migration_007/012) com os dados do
-- GOVERNO ESTADUAL em si — receitas, despesas, resultados, dívida e
-- arrecadação própria (ICMS, IPVA, ITCD, IRRF) + transferências (FPE, FUNDEB).
-- ============================================================================

CREATE TABLE IF NOT EXISTS estados_financeiro (
    uf                      VARCHAR(2) NOT NULL,
    exercicio               INTEGER NOT NULL,

    -- Receitas (DCA-Anexo I-AB)
    receitas_correntes      NUMERIC(18,2),   -- Receitas Correntes
    receitas_capital        NUMERIC(18,2),   -- Receitas de Capital
    receitas_orcamentarias  NUMERIC(18,2),   -- Receitas Orçamentárias
    receitas_transferencias NUMERIC(18,2),   -- Transferências Correntes
    receitas_nao_operacionais NUMERIC(18,2), -- Receitas Não Operacionais

    -- Despesas
    despesas_correntes      NUMERIC(18,2),   -- Despesas Correntes
    despesas_capital        NUMERIC(18,2),   -- Despesas de Capital
    despesas_orcamentarias  NUMERIC(18,2),   -- Despesas Orçamentárias
    despesas_financeiras    NUMERIC(18,2),   -- Despesas Financeiras
    despesas_totais         NUMERIC(18,2),   -- Total de Despesas

    -- Resultados
    resultado_orcamentario  NUMERIC(18,2),   -- Resultado Orçamentário
    resultado_primario      NUMERIC(18,2),   -- Resultado Primário
    resultado_financeiro    NUMERIC(18,2),   -- Resultado Financeiro

    -- Patrimônio / Endividamento
    divida_ativa            NUMERIC(18,2),   -- Dívida Ativa
    divida_passiva          NUMERIC(18,2),   -- Dívida Passiva Consolidada
    ativo_imobilizado       NUMERIC(18,2),   -- Ativo Imobilizado
    patrimonio_liquido      NUMERIC(18,2),   -- Patrimônio Líquido

    -- Arrecadação própria (RREO-Anexo 03, esfera estadual)
    arrec_icms              NUMERIC(18,2),   -- ICMS (integral do estado)
    arrec_ipva              NUMERIC(18,2),   -- IPVA
    arrec_itcd              NUMERIC(18,2),   -- ITCD/ITCMD
    arrec_irrf              NUMERIC(18,2),   -- IRRF
    arrec_cota_fpe          NUMERIC(18,2),   -- Cota-Parte do FPE
    arrec_fundeb            NUMERIC(18,2),   -- Transferências do FUNDEB
    arrec_impostos_geral    NUMERIC(18,2),   -- Impostos, Taxas e Contribuições de Melhoria
    arrec_transferencias    NUMERIC(18,2),   -- Transferências Correntes
    arrec_receita_servicos  NUMERIC(18,2),   -- Receita de Serviços
    arrec_receita_patrimonial NUMERIC(18,2), -- Receita Patrimonial
    arrec_receitas_correntes NUMERIC(18,2),  -- RECEITAS CORRENTES (I)
    arrec_rcl               NUMERIC(18,2),   -- RECEITA CORRENTE LÍQUIDA (III)

    -- Metadados
    arrec_fonte_rreo        VARCHAR(30),
    fonte                   TEXT DEFAULT 'SICONFI/DCA',
    atualizado_em           TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (uf, exercicio)
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_ef_exercicio ON estados_financeiro(exercicio);

COMMENT ON TABLE estados_financeiro IS 'Dados financeiros dos 26 estados + DF (SICONFI esfera estadual)';
COMMENT ON COLUMN estados_financeiro.uf IS 'Sigla da UF (PK)';
COMMENT ON COLUMN estados_financeiro.arrec_rcl IS 'Receita Corrente Líquida (RREO-Anexo 03, III)';
