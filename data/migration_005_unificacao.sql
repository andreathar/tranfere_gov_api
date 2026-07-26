-- migration_005_unificacao.sql

BEGIN;

-- 1. Tabela para armazenar Convênios / Transferências Discricionárias
CREATE TABLE IF NOT EXISTS emendas_discricionarias (
    codigo_emenda TEXT PRIMARY KEY,
    numero_convenio TEXT,
    ano INTEGER,
    parlamentar_nome TEXT,
    beneficiario_nome TEXT,
    beneficiario_cnpj TEXT,
    valor_total NUMERIC(15,2),
    status_execucao TEXT,
    data_assinatura DATE,
    objeto TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Drop view antiga se existir
DROP VIEW IF EXISTS v_emendas_unificadas;

-- 3. View Unificada (Pix + Convênios)
CREATE VIEW v_emendas_unificadas AS
-- Transferências Especiais (Pix)
SELECT
    pa.emenda_codigo AS codigo_emenda,
    'TRANSFERENCIA_ESPECIAL' AS modalidade,
    pa.emenda_ano AS ano,
    pa.parlamentar_nome,
    b.nome AS beneficiario_nome,
    b.cnpj AS beneficiario_cnpj,
    b.uf AS beneficiario_uf,
    ibge.municipio_id AS beneficiario_ibge,
    pa.valor_total,
    pa.plano_acao_situacao AS status_execucao,
    pa.objeto_id::TEXT AS objeto,
    pa.extracted_at AS updated_at
FROM planos_acao pa
LEFT JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
LEFT JOIN beneficiario_ibge_map ibge ON b.beneficiario_id = ibge.beneficiario_id
WHERE pa.parlamentar_nome IS NOT NULL AND pa.emenda_codigo IS NOT NULL

UNION ALL

-- Transferências Discricionárias (Convênios)
SELECT
    codigo_emenda,
    'TRANSFERENCIA_DISCRICIONARIA' AS modalidade,
    ano,
    parlamentar_nome,
    beneficiario_nome,
    beneficiario_cnpj,
    NULL AS beneficiario_uf,
    NULL AS beneficiario_ibge,
    valor_total,
    status_execucao,
    objeto,
    updated_at
FROM emendas_discricionarias
WHERE parlamentar_nome IS NOT NULL AND codigo_emenda IS NOT NULL;

COMMIT;
