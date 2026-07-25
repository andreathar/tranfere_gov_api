-- ============================================================================
-- TransfereGov — Migration: Views Cruzadas Enriquecidas
-- ============================================================================
-- Banco: transferegov_db
-- Data: 2026-07-23
-- ============================================================================

-- ============================================================================
-- 1. Tabela de mapeamento beneficiário → IBGE
-- ============================================================================

CREATE TABLE IF NOT EXISTS beneficiario_ibge_map (
    beneficiario_id INTEGER PRIMARY KEY REFERENCES beneficiarios(beneficiario_id),
    municipio_id INTEGER REFERENCES municipios_ibge(municipio_id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 2. View: Planos com dados IBGE (enriquecida)
-- ============================================================================

DROP VIEW IF EXISTS v_planos_enriquecidos CASCADE;
CREATE VIEW v_planos_enriquecidos AS
SELECT
    pa.*,
    b.nome AS municipio_nome,
    b.cnpj AS municipio_cnpj,
    mi.municipio_id AS ibge_id,
    mi.regiao AS ibge_regiao,
    mi.mesorregiao AS ibge_mesorregiao,
    mi.microrregiao AS ibge_microrregiao,
    mi.populacao AS ibge_populacao,
    mi.idhm AS ibge_idhm,
    pd.sigla_partido AS parlamentar_partido,
    pd.uf AS parlamentar_uf,
    pd.situacao AS parlamentar_situacao,
    pd.escolaridade AS parlamentar_escolaridade,
    pd.gabinete_telefone AS parlamentar_telefone,
    pd.gabinete_email AS parlamentar_email,
    sm.display_site AS situacao_display,
    sm.categoria AS situacao_categoria
FROM planos_acao pa
LEFT JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
LEFT JOIN beneficiario_ibge_map bm ON pa.beneficiario_id = bm.beneficiario_id
LEFT JOIN municipios_ibge mi ON bm.municipio_id = mi.municipio_id
LEFT JOIN parlamentares_dados pd ON pa.parlamentar_nome = pd.nome
LEFT JOIN situacoes_map sm ON pa.plano_acao_situacao = sm.valor_api;

-- ============================================================================
-- 3. View: Resumo por Finalidade da Política Pública + Estado
-- ============================================================================

DROP VIEW IF EXISTS v_resumo_por_politica_estado CASCADE;
CREATE VIEW v_resumo_por_politica_estado AS
SELECT
    b.uf,
    pa.politicas_publicas,
    COUNT(*) AS total_planos,
    SUM(pa.valor_total) AS valor_total,
    COUNT(DISTINCT pa.parlamentar_nome) AS parlamentares,
    COUNT(DISTINCT pa.beneficiario_id) AS municipios,
    SUM(CASE WHEN pa.plano_acao_situacao = 'CIENTE' THEN pa.valor_total ELSE 0 END) AS valor_ciente,
    SUM(CASE WHEN pa.plano_acao_situacao = 'IMPEDIDO' THEN pa.valor_total ELSE 0 END) AS valor_impedido,
    SUM(CASE WHEN pa.plano_acao_situacao = 'IMPEDIDO_REJEICAO_PLANO_TRABALHO' THEN pa.valor_total ELSE 0 END) AS valor_rejeitado
FROM planos_acao pa
JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
WHERE pa.politicas_publicas IS NOT NULL AND pa.politicas_publicas != ''
  AND b.uf IS NOT NULL
GROUP BY b.uf, pa.politicas_publicas
ORDER BY valor_total DESC;

-- ============================================================================
-- 4. View: Resumo por Objeto + Parlamentar
-- ============================================================================

DROP VIEW IF EXISTS v_resumo_por_objeto_parlamentar CASCADE;
CREATE VIEW v_resumo_por_objeto_parlamentar AS
SELECT
    o.objeto_id,
    LEFT(o.descricao, 60) AS objeto_descricao,
    pa.parlamentar_nome,
    pa.plano_acao_situacao,
    COUNT(*) AS total_planos,
    SUM(pa.valor_total) AS valor_total,
    COUNT(DISTINCT pa.beneficiario_id) AS municipios,
    pd.sigla_partido AS parlamentar_partido,
    pd.uf AS parlamentar_uf
FROM planos_acao pa
JOIN objetos o ON pa.objeto_id = o.objeto_id
LEFT JOIN parlamentares_dados pd ON pa.parlamentar_nome = pd.nome
WHERE pa.parlamentar_nome IS NOT NULL AND pa.parlamentar_nome != ''
GROUP BY o.objeto_id, objeto_descricao, pa.parlamentar_nome, pa.plano_acao_situacao,
         pd.sigla_partido, pd.uf
ORDER BY valor_total DESC;

-- ============================================================================
-- 5. View: Ranking de parlamentares com enriquecimento
-- ============================================================================

DROP VIEW IF EXISTS v_ranking_parlamentares_enriquecido CASCADE;
CREATE VIEW v_ranking_parlamentares_enriquecido AS
SELECT
    pa.parlamentar_nome,
    pd.sigla_partido,
    pd.uf AS parlamentar_uf,
    pd.situacao,
    pd.escolaridade,
    COUNT(*) AS total_planos,
    SUM(pa.valor_total) AS valor_total,
    COUNT(DISTINCT pa.beneficiario_id) AS municipios,
    COUNT(DISTINCT pa.objeto_id) AS objetos,
    STRING_AGG(DISTINCT b.uf, ', ' ORDER BY b.uf) AS ufs_beneficiarios,
    ROUND(AVG(pa.valor_total), 2) AS valor_medio
FROM planos_acao pa
LEFT JOIN parlamentares_dados pd ON pa.parlamentar_nome = pd.nome
LEFT JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
WHERE pa.parlamentar_nome IS NOT NULL AND pa.parlamentar_nome != ''
GROUP BY pa.parlamentar_nome, pd.sigla_partido, pd.uf, pd.situacao, pd.escolaridade
ORDER BY valor_total DESC;

-- ============================================================================
-- 6. View: Top combinações Parlamentar × Município
-- ============================================================================

DROP VIEW IF EXISTS v_parlamentar_municipio CASCADE;
CREATE VIEW v_parlamentar_municipio AS
SELECT
    pa.parlamentar_nome,
    pd.sigla_partido,
    b.nome AS municipio,
    b.uf,
    mi.regiao AS ibge_regiao,
    mi.populacao AS ibge_populacao,
    COUNT(*) AS planos,
    SUM(pa.valor_total) AS valor_total,
    STRING_AGG(DISTINCT pa.plano_acao_situacao, ', ') AS situacoes
FROM planos_acao pa
LEFT JOIN parlamentares_dados pd ON pa.parlamentar_nome = pd.nome
LEFT JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
LEFT JOIN beneficiario_ibge_map bm ON pa.beneficiario_id = bm.beneficiario_id
LEFT JOIN municipios_ibge mi ON bm.municipio_id = mi.municipio_id
WHERE pa.parlamentar_nome IS NOT NULL AND pa.parlamentar_nome != ''
GROUP BY pa.parlamentar_nome, pd.sigla_partido, b.nome, b.uf, mi.regiao, mi.populacao
ORDER BY valor_total DESC;

-- ============================================================================
-- 7. GRANTS
-- ============================================================================

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO cognee;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO cognee;
