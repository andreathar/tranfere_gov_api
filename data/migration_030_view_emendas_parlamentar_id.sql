-- migration_016_view_emendas_parlamentar_id.sql
-- Adiciona parlamentar_id à view v_emendas_unificadas
-- Permite que gráficos e queries façam JOIN exato por ID em vez de ILIKE/normalização

BEGIN;

DROP VIEW IF EXISTS v_emendas_unificadas;

CREATE VIEW v_emendas_unificadas AS
-- Transferências Especiais (Pix)
SELECT
    pa.emenda_codigo AS codigo_emenda,
    'TRANSFERENCIA_ESPECIAL' AS modalidade,
    pa.emenda_ano AS ano,
    pa.parlamentar_nome,
    pa.parlamentar_id,
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
-- Emendas discricionárias não têm parlamentar_id — usam NULL
SELECT
    codigo_emenda,
    'TRANSFERENCIA_DISCRICIONARIA' AS modalidade,
    ano,
    parlamentar_nome,
    NULL::int AS parlamentar_id,
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
