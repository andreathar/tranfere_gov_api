-- ============================================================================
-- TransfereGov — Migration: Tabelas para Relatórios
-- ============================================================================
-- Banco: transferegov_db
-- Data: 2026-07-23
-- ============================================================================

-- ============================================================================
-- 1. TABELA DIMENSÃO — Parlamentares
-- ============================================================================

CREATE TABLE IF NOT EXISTS parlamentares (
    id                  SERIAL PRIMARY KEY,
    nome                TEXT NOT NULL,
   UF                  CHAR(2),
    partido             TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(nome)
);

-- ============================================================================
-- 2. TABELA DIMENSÃO — Emendas
-- ============================================================================

CREATE TABLE IF NOT EXISTS emendas (
    id                  SERIAL PRIMARY KEY,
    emenda_codigo       TEXT UNIQUE NOT NULL,      -- ex: 202642740010
    ano                 INTEGER,                   -- 2026
    tipo                TEXT,                      -- ex: RP6, RP0, etc.
    parlamentar_id      INTEGER REFERENCES parlamentares(id),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 3. TABELA DIMENSÃO — Políticas Públicas
-- ============================================================================

CREATE TABLE IF NOT EXISTS politicas_publicas (
    id                  SERIAL PRIMARY KEY,
    politica_codigo     TEXT UNIQUE NOT NULL,      -- ex: 4
    descricao           TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 4. TABELA DE MAPEAMENTO — Situações (display site → valor API)
-- ============================================================================

CREATE TABLE IF NOT EXISTS situacoes_map (
    id                  SERIAL PRIMARY KEY,
    valor_api           TEXT UNIQUE NOT NULL,      -- ex: IMPEDIDO
    display_site        TEXT NOT NULL,             -- ex: Impedido por Restrição Técnica
    categoria           TEXT,                      -- negada, positiva, neutra
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Inserir mapeamentos conhecidos
INSERT INTO situacoes_map (valor_api, display_site, categoria) VALUES
    ('AGUARDANDO_CIENCIA',           'Aguardando Ciência',                          'neutra'),
    ('PLANO_TRABALHO_EM_ELABORACAO', 'Plano de Trabalho em Elaboração/Aguardando Envio para Análise', 'neutra'),
    ('CIENTE',                       'Ciente',                                      'neutra'),
    ('IMPEDIDO',                     'Impedido por Restrição Técnica',              'negada'),
    ('IMPEDIDO_REJEICAO_PLANO_TRABALHO', 'Impedido por Rejeição do Plano de Trabalho', 'negada'),
    ('APROVADO',                     'Aprovado',                                    'positiva'),
    ('REPROVADO',                    'Reprovado',                                   'negada'),
    ('CANCELADO',                    'Cancelado',                                   'negada'),
    ('EM_EXECUCAO',                  'Em Execução',                                 'positiva'),
    ('CONCLUIDO',                    'Concluído',                                   'positiva'),
    ('NAO_CUMPROU',                  'Não Cumpriu',                                 'negada')
ON CONFLICT (valor_api) DO UPDATE SET
    display_site = EXCLUDED.display_site,
    categoria = EXCLUDED.categoria;

-- ============================================================================
-- 5. COLUNAS EXTRAS EM planos_acao (parseadas de codigo_emenda_formatado)
-- ============================================================================

ALTER TABLE planos_acao ADD COLUMN IF NOT EXISTS emenda_codigo TEXT;
ALTER TABLE planos_acao ADD COLUMN IF NOT EXISTS parlamentar_nome TEXT;
ALTER TABLE planos_acao ADD COLUMN IF NOT EXISTS emenda_ano INTEGER;

-- ============================================================================
-- 6. ÍNDICES NOVOS
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_pa_parlamentar ON planos_acao(parlamentar_nome);
CREATE INDEX IF NOT EXISTS idx_pa_emenda_codigo ON planos_acao(emenda_codigo);
CREATE INDEX IF NOT EXISTS idx_pa_emenda_ano ON planos_acao(emenda_ano);
CREATE INDEX IF NOT EXISTS idx_emp_parlamentar ON emendas(parlamentar_id);
CREATE INDEX IF NOT EXISTS idx_emp_ano ON emendas(ano);

-- ============================================================================
-- 7. VIEWS ATUALIZADAS
-- ============================================================================

-- View completa com parlamentar parseado
CREATE OR REPLACE VIEW v_planos_completo AS
SELECT
    pa.plano_acao_id,
    pa.plano_acao_codigo,
    pa.plano_acao_situacao,
    pa.plano_trabalho_situacao,
    pa.codigo_emenda_formatado,
    pa.emenda_codigo,
    pa.parlamentar_nome,
    pa.emenda_ano,
    pa.valor_custeio,
    pa.valor_investimento,
    pa.valor_total,
    pa.politicas_publicas,
    pa.motivo_impedimento,
    pa.numero_parceria,
    pa.data_atualizacao_plano_acao,
    pa.extracted_at,
    o.objeto_id AS objeto_codigo,
    o.descricao AS objeto_descricao,
    pr.programa_codigo,
    b.nome AS beneficiario_nome,
    b.cnpj AS beneficiario_cnpj,
    b.uf AS beneficiario_uf,
    sm.display_site AS situacao_display,
    sm.categoria AS situacao_categoria
FROM planos_acao pa
LEFT JOIN objetos o ON pa.objeto_id = o.objeto_id
LEFT JOIN programas pr ON pa.programa_id = pr.programa_id
LEFT JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
LEFT JOIN situacoes_map sm ON pa.plano_acao_situacao = sm.valor_api;

-- Resumo por parlamentar
CREATE OR REPLACE VIEW v_resumo_por_parlamentar AS
SELECT
    pa.parlamentar_nome,
    pa.emenda_ano,
    COUNT(*) AS total_planos,
    SUM(pa.valor_total) AS valor_total,
    COUNT(DISTINCT pa.beneficiario_id) AS total_municipios,
    COUNT(DISTINCT pa.objeto_id) AS total_objetos,
    SUM(CASE WHEN pa.plano_acao_situacao IN ('REPROVADO','IMPEDIDO','IMPEDIDO_REJEICAO_PLANO_TRABALHO','CANCELADO','NAO_CUMPROU') THEN 1 ELSE 0 END) AS negados,
    SUM(CASE WHEN pa.plano_acao_situacao = 'EM_EXECUCAO' THEN 1 ELSE 0 END) AS em_execucao,
    SUM(CASE WHEN pa.plano_acao_situacao = 'CONCLUIDO' THEN 1 ELSE 0 END) AS concluidos
FROM planos_acao pa
WHERE pa.parlamentar_nome IS NOT NULL
GROUP BY pa.parlamentar_nome, pa.emenda_ano
ORDER BY valor_total DESC;

-- Resumo por UF com situação
CREATE OR REPLACE VIEW v_resumo_por_estado AS
SELECT
    b.uf,
    pa.plano_acao_situacao,
    COUNT(*) AS total_planos,
    SUM(pa.valor_total) AS valor_total
FROM planos_acao pa
JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
WHERE b.uf IS NOT NULL
GROUP BY b.uf, pa.plano_acao_situacao
ORDER BY b.uf, valor_total DESC;

-- Resumo por objeto
CREATE OR REPLACE VIEW v_resumo_por_objeto AS
SELECT
    o.objeto_id,
    o.descricao,
    COUNT(*) AS total_planos,
    SUM(pa.valor_total) AS valor_total,
    COUNT(DISTINCT pa.beneficiario_id) AS total_municipios,
    COUNT(DISTINCT pa.parlamentar_nome) AS total_parlamentares,
    SUM(CASE WHEN pa.plano_acao_situacao IN ('REPROVADO','IMPEDIDO','IMPEDIDO_REJEICAO_PLANO_TRABALHO','CANCELADO','NAO_CUMPROU') THEN 1 ELSE 0 END) AS negados
FROM planos_acao pa
JOIN objetos o ON pa.objeto_id = o.objeto_id
GROUP BY o.objeto_id, o.descricao
ORDER BY valor_total DESC;

-- Negados / Perdidos (atalho)
CREATE OR REPLACE VIEW v_negados AS
SELECT *
FROM v_planos_completo
WHERE plano_acao_situacao IN ('REPROVADO', 'IMPEDIDO', 'IMPEDIDO_REJEICAO_PLANO_TRABALHO', 'CANCELADO', 'NAO_CUMPROU')
ORDER BY valor_total DESC;

-- ============================================================================
-- 8. FUNÇÃO para parsear codigo_emenda_formatado
-- ============================================================================
-- Formato: "202642740010-LAÉRCIO OLIVEIRA" → emenda=202642740010, parlamentar=LAÉRCIO OLIVEIRA

CREATE OR REPLACE FUNCTION parse_emenda(p_codigo TEXT)
RETURNS TABLE(emenda TEXT, parlamentar TEXT, ano INTEGER) AS $$
BEGIN
    IF p_codigo IS NULL OR p_codigo = '' THEN
        RETURN;
    END IF;

    -- Formato: "AAAA...-NOME DO PARLAMENTAR"
    RETURN QUERY SELECT
        split_part(p_codigo, '-', 1) AS emenda,
        TRIM(split_part(p_codigo, '-', 2)) AS parlamentar,
        CASE
            WHEN length(split_part(p_codigo, '-', 1)) >= 4
            THEN SUBSTRING(split_part(p_codigo, '-', 1) FROM 1 FOR 4)::INTEGER
            ELSE NULL
        END AS ano;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- 9. GRANTS
-- ============================================================================

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO cognee;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO cognee;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO cognee;
