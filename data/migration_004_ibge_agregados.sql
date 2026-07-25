-- ============================================================================
-- TransfereGov — Migration 003: Enriquecimento IBGE Agregados
-- ============================================================================
-- Banco: transferegov_db
-- Data: 2026-07-24
-- Descrição: Adiciona colunas demográficas/econômicas à tabela municipios_ibge
--            (população, PIB, área territorial) via API de agregados do IBGE.
-- ============================================================================

-- ============================================================================
-- 1. NOVAS COLUNAS EM municipios_ibge
-- ============================================================================

ALTER TABLE municipios_ibge ADD COLUMN IF NOT EXISTS populacao BIGINT;
ALTER TABLE municipios_ibge ADD COLUMN IF NOT EXISTS pib NUMERIC(15, 2);
ALTER TABLE municipios_ibge ADD COLUMN IF NOT EXISTS area_km2 NUMERIC(12, 2);
ALTER TABLE municipios_ibge ADD COLUMN IF NOT EXISTS atualizado_em TIMESTAMPTZ;

-- ============================================================================
-- 2. COMENTÁRIOS NAS COLUNAS
-- ============================================================================

COMMENT ON COLUMN municipios_ibge.populacao IS 'População residente estimada (IBGE tabela 6579, var 9324)';
COMMENT ON COLUMN municipios_ibge.pib IS 'Produto Interno Bruto a preços correntes em R$ mil (IBGE tabela 5938, var 37)';
COMMENT ON COLUMN municipios_ibge.area_km2 IS 'Área territorial em km² (IBGE tabela 1301, var 615)';
COMMENT ON COLUMN municipios_ibge.atualizado_em IS 'Data/hora da última atualização dos agregados IBGE';

-- ============================================================================
-- 3. GRANTS
-- ============================================================================

GRANT ALL PRIVILEGES ON municipios_ibge TO cognee;
