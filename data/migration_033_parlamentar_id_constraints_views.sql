-- migration_019_parlamentar_id_constraints_views.sql
-- Ajusta UNIQUE constraint e índices da parlamentar_beneficiario
-- Recria views que ainda JOINam por parlamentar_nome para usar parlamentar_id

BEGIN;

-- ============================================================================
-- 1. parlamentar_beneficiario: adiciona coluna + UNIQUE constraint e índices
-- ============================================================================
-- Adiciona coluna parlamentar_id (ainda não existia nesta tabela)
ALTER TABLE parlamentar_beneficiario ADD COLUMN IF NOT EXISTS parlamentar_id INTEGER REFERENCES parlamentares(parlamentar_id);

-- Popula via match exato de nome com a tabela parlamentares
UPDATE parlamentar_beneficiario pb
SET parlamentar_id = p.parlamentar_id
FROM parlamentares p
WHERE pb.parlamentar_nome = p.nome
  AND pb.parlamentar_id IS NULL;

-- Remove constraint antiga baseada em nome
ALTER TABLE parlamentar_beneficiario DROP CONSTRAINT IF EXISTS parlamentar_beneficiario_parlamentar_nome_beneficiario_id_e_key;

-- Remove índice antigo em parlamentar_nome
DROP INDEX IF EXISTS idx_pb_parlamentar;

-- Cria UNIQUE INDEX baseado em parlamentar_id
-- NOTA: como parlamentar_id é populado para todos os registros Pix (origem planos_acao),
-- esta constraint funciona para o caso principal.
CREATE UNIQUE INDEX IF NOT EXISTS idx_pb_unique_id ON parlamentar_beneficiario(parlamentar_id, beneficiario_id, emenda_codigo);

-- Índice direto por parlamentar_id para consultas
CREATE INDEX IF NOT EXISTS idx_pb_parlamentar_id ON parlamentar_beneficiario(parlamentar_id);

-- Mantém parlamentar_nome como fallback (para consultas que ainda o usam)
-- mas sem unique constraint
CREATE INDEX IF NOT EXISTS idx_pb_parlamentar_nome ON parlamentar_beneficiario(parlamentar_nome);

-- ============================================================================
-- 2. Views — recriadas com JOIN por parlamentar_id
-- ============================================================================

-- --------------------------------------------------------------------------
-- v_parlamentar_municipio
-- --------------------------------------------------------------------------
DROP VIEW IF EXISTS v_parlamentar_municipio;
CREATE VIEW v_parlamentar_municipio AS
SELECT
    pa.parlamentar_nome,
    pa.parlamentar_id,
    pd.sigla_partido,
    b.nome AS municipio,
    b.uf,
    mi.regiao AS ibge_regiao,
    mi.populacao AS ibge_populacao,
    COUNT(*) AS planos,
    SUM(pa.valor_total) AS valor_total,
    STRING_AGG(DISTINCT pa.plano_acao_situacao, ', ') AS situacoes
FROM planos_acao pa
LEFT JOIN parlamentares_dados pd ON pa.parlamentar_id = pd.parlamentar_id
LEFT JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
LEFT JOIN beneficiario_ibge_map bm ON pa.beneficiario_id = bm.beneficiario_id
LEFT JOIN municipios_ibge mi ON bm.municipio_id = mi.municipio_id
WHERE pa.parlamentar_nome IS NOT NULL AND pa.parlamentar_nome != ''
GROUP BY pa.parlamentar_nome, pa.parlamentar_id, pd.sigla_partido,
         b.nome, b.uf, mi.regiao, mi.populacao
ORDER BY SUM(pa.valor_total) DESC;

-- --------------------------------------------------------------------------
-- v_planos_enriquecidos
-- --------------------------------------------------------------------------
DROP VIEW IF EXISTS v_planos_enriquecidos;
CREATE VIEW v_planos_enriquecidos AS
SELECT
    pa.id,
    pa.plano_acao_id,
    pa.plano_acao_codigo,
    pa.objeto_id,
    pa.programa_id,
    pa.beneficiario_id,
    pa.plano_acao_situacao,
    pa.plano_trabalho_situacao,
    pa.codigo_emenda_formatado,
    pa.valor_custeio,
    pa.valor_investimento,
    pa.valor_total,
    pa.politicas_publicas,
    pa.motivo_impedimento,
    pa.numero_parceria,
    pa.data_atualizacao_plano_acao,
    pa.data_atualizacao_plano_trabalho,
    pa.extracted_at,
    pa.extract_source,
    pa.emenda_codigo,
    pa.parlamentar_nome,
    pa.parlamentar_id,
    pa.emenda_ano,
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
    sm.display_site AS situacao_display,
    sm.categoria AS situacao_categoria
FROM planos_acao pa
LEFT JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
LEFT JOIN beneficiario_ibge_map bm ON pa.beneficiario_id = bm.beneficiario_id
LEFT JOIN municipios_ibge mi ON bm.municipio_id = mi.municipio_id
LEFT JOIN parlamentares_dados pd ON pa.parlamentar_id = pd.parlamentar_id
LEFT JOIN situacoes_map sm ON pa.plano_acao_situacao = sm.valor_api;

-- --------------------------------------------------------------------------
-- v_ranking_parlamentares_enriquecido
-- --------------------------------------------------------------------------
DROP VIEW IF EXISTS v_ranking_parlamentares_enriquecido;
CREATE VIEW v_ranking_parlamentares_enriquecido AS
SELECT
    pa.parlamentar_nome,
    pa.parlamentar_id,
    pd.sigla_partido,
    pd.uf AS parlamentar_uf,
    pd.situacao,
    pd.escolaridade,
    COUNT(*) AS total_planos,
    SUM(pa.valor_total) AS valor_total,
    COUNT(DISTINCT pa.beneficiario_id) AS municipios,
    COUNT(DISTINCT pa.objeto_id) AS objetos,
    STRING_AGG(DISTINCT b.uf::text, ', ' ORDER BY b.uf::text) AS ufs_beneficiarios,
    ROUND(AVG(pa.valor_total), 2) AS valor_medio
FROM planos_acao pa
LEFT JOIN parlamentares_dados pd ON pa.parlamentar_id = pd.parlamentar_id
LEFT JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
WHERE pa.parlamentar_nome IS NOT NULL AND pa.parlamentar_nome != ''
GROUP BY pa.parlamentar_nome, pa.parlamentar_id, pd.sigla_partido,
         pd.uf, pd.situacao, pd.escolaridade
ORDER BY SUM(pa.valor_total) DESC;

-- --------------------------------------------------------------------------
-- v_resumo_por_objeto_parlamentar
-- --------------------------------------------------------------------------
DROP VIEW IF EXISTS v_resumo_por_objeto_parlamentar;
CREATE VIEW v_resumo_por_objeto_parlamentar AS
SELECT
    o.objeto_id,
    LEFT(o.descricao, 60) AS objeto_descricao,
    pa.parlamentar_nome,
    pa.parlamentar_id,
    pa.plano_acao_situacao,
    COUNT(*) AS total_planos,
    SUM(pa.valor_total) AS valor_total,
    COUNT(DISTINCT pa.beneficiario_id) AS municipios,
    pd.sigla_partido AS parlamentar_partido,
    pd.uf AS parlamentar_uf
FROM planos_acao pa
JOIN objetos o ON pa.objeto_id = o.objeto_id
LEFT JOIN parlamentares_dados pd ON pa.parlamentar_id = pd.parlamentar_id
WHERE pa.parlamentar_nome IS NOT NULL AND pa.parlamentar_nome != ''
GROUP BY o.objeto_id, LEFT(o.descricao, 60),
         pa.parlamentar_nome, pa.parlamentar_id, pa.plano_acao_situacao,
         pd.sigla_partido, pd.uf
ORDER BY SUM(pa.valor_total) DESC;

COMMIT;
