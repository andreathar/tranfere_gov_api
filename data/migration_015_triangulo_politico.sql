-- Migration 015: Views de Inteligência Política (Triângulo Político e Dinastias Familiares)

-- 1. View Triângulo Político Municipal (Deputado -> Prefeito -> Vereadores Eleitos por Partido)
CREATE OR REPLACE VIEW v_triangulo_politico AS
SELECT 
    pd.deputado_id,
    pd.nome AS deputado_nome,
    pd.sigla_partido AS partido_deputado,
    b.uf,
    b.nome AS municipio_nome,
    bm.municipio_id,
    pr.prefeito_nome,
    pr.sigla_partido AS partido_prefeito,
    pr.coligacao AS prefeito_coligacao,
    CASE 
        WHEN pd.sigla_partido = pr.sigla_partido THEN 'MESMO PARTIDO'
        WHEN pr.coligacao ILIKE CONCAT('%', pd.sigla_partido, '%') THEN 'COLIGADO'
        ELSE 'OPOSICAO / DIVERGENTE'
    END AS relacao_partidaria_prefeito,
    COUNT(DISTINCT v.sq_candidato) AS vereadores_eleitos_partido_dep,
    COUNT(DISTINCT pa.plano_acao_id) AS total_planos_acao,
    SUM(pa.valor_total) AS total_emendas_brl
FROM planos_acao pa
JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
JOIN parlamentares_dados pd ON pa.parlamentar_nome = pd.nome_urna OR pa.parlamentar_nome = pd.nome
JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
JOIN prefeitos_dados pr ON bm.municipio_id = pr.municipio_id
LEFT JOIN vereadores_dados v ON bm.municipio_id = v.municipio_id 
    AND v.sigla_partido = pd.sigla_partido 
    AND v.situacao_candidatura ILIKE '%ELEITO%'
WHERE pd.sigla_partido IS NOT NULL
GROUP BY 
    pd.deputado_id, pd.nome, pd.sigla_partido, b.uf, b.nome, bm.municipio_id,
    pr.prefeito_nome, pr.sigla_partido, pr.coligacao;

-- 2. View Dinastias Familiares (Sobrenomes coincidentes no mesmo estado/município)
CREATE OR REPLACE VIEW v_dinastias_politicas AS
SELECT 
    pd.deputado_id,
    pd.nome AS deputado_nome,
    pd.sigla_partido AS partido_deputado,
    b.uf,
    b.nome AS municipio_nome,
    pr.prefeito_nome,
    pr.sigla_partido AS partido_prefeito,
    split_part(pd.nome, ' ', array_length(string_to_array(pd.nome, ' '), 1)) AS sobrenome_comum,
    SUM(pa.valor_total) AS total_emendas_brl
FROM planos_acao pa
JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
JOIN parlamentares_dados pd ON pa.parlamentar_nome = pd.nome_urna OR pa.parlamentar_nome = pd.nome
JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
JOIN prefeitos_dados pr ON bm.municipio_id = pr.municipio_id
WHERE split_part(pd.nome, ' ', array_length(string_to_array(pd.nome, ' '), 1)) = 
      split_part(pr.prefeito_nome, ' ', array_length(string_to_array(pr.prefeito_nome, ' '), 1))
  AND length(split_part(pd.nome, ' ', array_length(string_to_array(pd.nome, ' '), 1))) > 3
GROUP BY 
    pd.deputado_id, pd.nome, pd.sigla_partido, b.uf, b.nome, pr.prefeito_nome, pr.sigla_partido;
