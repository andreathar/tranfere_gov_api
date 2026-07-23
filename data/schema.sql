-- ============================================================================
-- TransfereGov — Schema Completo do Banco de Dados
-- ============================================================================
-- Banco: transferegov_db
-- Usuário: cognee
-- Última atualização: 2026-07-23
-- ============================================================================

-- Extensões
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================================
-- 1. TABELAS DIMENSÃO (entity tables)
-- ============================================================================

-- Objetos de execução (301=Cemitérios, 662=Outros, etc.)
CREATE TABLE IF NOT EXISTS objetos (
    id              SERIAL PRIMARY KEY,
    objeto_id       INTEGER UNIQUE NOT NULL,
    descricao       TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Programas
CREATE TABLE IF NOT EXISTS programas (
    id              SERIAL PRIMARY KEY,
    programa_id     INTEGER UNIQUE NOT NULL,
    programa_codigo TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Beneficiários (municípios)
CREATE TABLE IF NOT EXISTS beneficiarios (
    id              SERIAL PRIMARY KEY,
    beneficiario_id INTEGER UNIQUE NOT NULL,
    nome            TEXT NOT NULL,
    cnpj            TEXT,
    uf              CHAR(2),
    ente_id         INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Parlamentares (extraído de codigo_emenda_formatado)
CREATE TABLE IF NOT EXISTS parlamentares (
    id              SERIAL PRIMARY KEY,
    nome            TEXT NOT NULL,
    UF              CHAR(2),
    partido         TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(nome)
);

-- Emendas parlamentares
CREATE TABLE IF NOT EXISTS emendas (
    id              SERIAL PRIMARY KEY,
    emenda_codigo   TEXT UNIQUE NOT NULL,
    ano             INTEGER,
    tipo            TEXT,
    parlamentar_id  INTEGER REFERENCES parlamentares(id),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Políticas públicas
CREATE TABLE IF NOT EXISTS politicas_publicas (
    id              SERIAL PRIMARY KEY,
    politica_codigo TEXT UNIQUE NOT NULL,
    descricao       TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Mapeamento situações (display site → valor API)
CREATE TABLE IF NOT EXISTS situacoes_map (
    id              SERIAL PRIMARY KEY,
    valor_api       TEXT UNIQUE NOT NULL,
    display_site    TEXT NOT NULL,
    categoria       TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 2. TABELA FATO — Planos de Ação
-- ============================================================================

CREATE TABLE IF NOT EXISTS planos_acao (
    id                          SERIAL PRIMARY KEY,
    plano_acao_id               INTEGER UNIQUE NOT NULL,
    plano_acao_codigo           TEXT NOT NULL,

    -- FKs
    objeto_id                   INTEGER REFERENCES objetos(objeto_id),
    programa_id                 INTEGER REFERENCES programas(programa_id),
    beneficiario_id             INTEGER REFERENCES beneficiarios(beneficiario_id),

    -- Situações
    plano_acao_situacao         TEXT NOT NULL,
    plano_trabalho_situacao     TEXT,

    -- Parlamentar / emenda
    codigo_emenda_formatado     TEXT,
    emenda_codigo               TEXT,
    parlamentar_nome            TEXT,
    emenda_ano                  INTEGER,

    -- Valores
    valor_custeio               NUMERIC(15,2) DEFAULT 0,
    valor_investimento          NUMERIC(15,2) DEFAULT 0,
    valor_total                 NUMERIC(15,2) DEFAULT 0,

    -- Políticas públicas
    politicas_publicas          TEXT,

    -- Impedimentos
    motivo_impedimento          TEXT,
    numero_parceria             TEXT,

    -- Metadados
    data_atualizacao_plano_acao TIMESTAMPTZ,
    data_atualizacao_plano_trabalho TIMESTAMPTZ,

    -- Controle
    extracted_at                TIMESTAMPTZ DEFAULT NOW(),
    extract_source              TEXT DEFAULT 'api_publica'
);

-- ============================================================================
-- 3. TABELA DE CONTROLE — Log de Extrações
-- ============================================================================

CREATE TABLE IF NOT EXISTS extract_log (
    id              SERIAL PRIMARY KEY,
    objeto_id       INTEGER,
    ano             INTEGER NOT NULL,
    total_registros INTEGER NOT NULL,
    total_negados   INTEGER,
    extracted_at    TIMESTAMPTZ DEFAULT NOW(),
    source          TEXT DEFAULT 'api_publica',
    notes           TEXT
);

-- ============================================================================
-- 4. ÍNDICES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_pa_codigo ON planos_acao(plano_acao_codigo);
CREATE INDEX IF NOT EXISTS idx_pa_situacao ON planos_acao(plano_acao_situacao);
CREATE INDEX IF NOT EXISTS idx_pa_objeto ON planos_acao(objeto_id);
CREATE INDEX IF NOT EXISTS idx_pa_beneficiario ON planos_acao(beneficiario_id);
CREATE INDEX IF NOT EXISTS idx_pa_programa ON planos_acao(programa_id);
CREATE INDEX IF NOT EXISTS idx_pa_emenda ON planos_acao(codigo_emenda_formatado);
CREATE INDEX IF NOT EXISTS idx_pa_valor ON planos_acao(valor_total DESC);
CREATE INDEX IF NOT EXISTS idx_pa_extracted ON planos_acao(extracted_at);
CREATE INDEX IF NOT EXISTS idx_pa_parlamentar ON planos_acao(parlamentar_nome);
CREATE INDEX IF NOT EXISTS idx_pa_emenda_codigo ON planos_acao(emenda_codigo);
CREATE INDEX IF NOT EXISTS idx_pa_emenda_ano ON planos_acao(emenda_ano);
CREATE INDEX IF NOT EXISTS idx_ben_uf ON beneficiarios(uf);
CREATE INDEX IF NOT EXISTS idx_ben_nome ON beneficiarios(nome);
CREATE INDEX IF NOT EXISTS idx_obj_id ON objetos(objeto_id);
CREATE INDEX IF NOT EXISTS idx_emp_parlamentar ON emendas(parlamentar_id);
CREATE INDEX IF NOT EXISTS idx_emp_ano ON emendas(ano);

-- ============================================================================
-- 5. VIEWS PARA RELATÓRIOS
-- ============================================================================

-- View completa (join de tudo)
CREATE OR REPLACE VIEW v_planos_completo AS
SELECT
    pa.plano_acao_id, pa.plano_acao_codigo,
    pa.plano_acao_situacao, pa.plano_trabalho_situacao,
    pa.codigo_emenda_formatado, pa.emenda_codigo,
    pa.parlamentar_nome, pa.emenda_ano,
    pa.valor_custeio, pa.valor_investimento, pa.valor_total,
    pa.politicas_publicas, pa.motivo_impedimento, pa.numero_parceria,
    pa.data_atualizacao_plano_acao, pa.extracted_at,
    o.objeto_id AS objeto_codigo, o.descricao AS objeto_descricao,
    pr.programa_codigo,
    b.nome AS beneficiario_nome, b.cnpj AS beneficiario_cnpj, b.uf AS beneficiario_uf,
    sm.display_site AS situacao_display, sm.categoria AS situacao_categoria
FROM planos_acao pa
LEFT JOIN objetos o ON pa.objeto_id = o.objeto_id
LEFT JOIN programas pr ON pa.programa_id = pr.programa_id
LEFT JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
LEFT JOIN situacoes_map sm ON pa.plano_acao_situacao = sm.valor_api;

-- Negados / Perdidos
CREATE OR REPLACE VIEW v_negados AS
SELECT * FROM v_planos_completo
WHERE plano_acao_situacao IN ('REPROVADO','IMPEDIDO','IMPEDIDO_REJEICAO_PLANO_TRABALHO','CANCELADO','NAO_CUMPROU')
ORDER BY valor_total DESC;

-- Resumo por estado + situação
CREATE OR REPLACE VIEW v_resumo_por_estado AS
SELECT b.uf, pa.plano_acao_situacao,
    COUNT(*) AS total_planos, SUM(pa.valor_total) AS valor_total
FROM planos_acao pa
JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
WHERE b.uf IS NOT NULL
GROUP BY b.uf, pa.plano_acao_situacao
ORDER BY b.uf, valor_total DESC;

-- Resumo por objeto
CREATE OR REPLACE VIEW v_resumo_por_objeto AS
SELECT o.objeto_id, o.descricao,
    COUNT(*) AS total_planos, SUM(pa.valor_total) AS valor_total,
    COUNT(DISTINCT pa.beneficiario_id) AS total_municipios,
    COUNT(DISTINCT pa.parlamentar_nome) AS total_parlamentares,
    SUM(CASE WHEN pa.plano_acao_situacao IN ('REPROVADO','IMPEDIDO','IMPEDIDO_REJEICAO_PLANO_TRABALHO','CANCELADO','NAO_CUMPROU') THEN 1 ELSE 0 END) AS negados
FROM planos_acao pa
JOIN objetos o ON pa.objeto_id = o.objeto_id
GROUP BY o.objeto_id, o.descricao
ORDER BY valor_total DESC;

-- Resumo por parlamentar
CREATE OR REPLACE VIEW v_resumo_por_parlamentar AS
SELECT pa.parlamentar_nome, pa.emenda_ano,
    COUNT(*) AS total_planos, SUM(pa.valor_total) AS valor_total,
    COUNT(DISTINCT pa.beneficiario_id) AS total_municipios,
    SUM(CASE WHEN pa.plano_acao_situacao IN ('REPROVADO','IMPEDIDO','IMPEDIDO_REJEICAO_PLANO_TRABALHO','CANCELADO','NAO_CUMPROU') THEN 1 ELSE 0 END) AS negados
FROM planos_acao pa
WHERE pa.parlamentar_nome IS NOT NULL
GROUP BY pa.parlamentar_nome, pa.emenda_ano
ORDER BY valor_total DESC;

-- ============================================================================
-- 6. DADOS INICIAIS — Mapeamento de situações
-- ============================================================================

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
-- 7. FUNÇÃO DE UPSERT (importação idempotente)
-- ============================================================================

CREATE OR REPLACE FUNCTION upsert_plano_acao(
    p_plano_acao_id           INTEGER,
    p_plano_acao_codigo       TEXT,
    p_objeto_id               INTEGER,
    p_objeto_descricao        TEXT,
    p_programa_id             INTEGER,
    p_programa_codigo         TEXT,
    p_beneficiario_id         INTEGER,
    p_beneficiario_nome       TEXT,
    p_beneficiario_cnpj       TEXT,
    p_uf                      TEXT,
    p_ente_id                 INTEGER,
    p_plano_acao_situacao     TEXT,
    p_plano_trabalho_situacao TEXT,
    p_codigo_emenda_formatado TEXT,
    p_valor_custeio           NUMERIC,
    p_valor_investimento      NUMERIC,
    p_valor_total             NUMERIC,
    p_politicas_publicas      TEXT,
    p_motivo_impedimento      TEXT,
    p_numero_parceria         TEXT,
    p_data_atualizacao_plano  TEXT,
    p_data_atualizacao_trabalho TEXT
) RETURNS INTEGER AS $$
DECLARE
    v_objeto_pk INTEGER;
    v_programa_pk INTEGER;
    v_beneficiario_pk INTEGER;
    v_existing_id INTEGER;
BEGIN
    -- Upsert objeto
    INSERT INTO objetos (objeto_id, descricao)
    VALUES (p_objeto_id, p_objeto_descricao)
    ON CONFLICT (objeto_id) DO UPDATE SET descricao = EXCLUDED.descricao
    RETURNING objeto_id INTO v_objeto_pk;

    -- Upsert programa
    IF p_programa_id IS NOT NULL THEN
        INSERT INTO programas (programa_id, programa_codigo)
        VALUES (p_programa_id, COALESCE(p_programa_codigo, ''))
        ON CONFLICT (programa_id) DO UPDATE SET programa_codigo = EXCLUDED.programa_codigo
        RETURNING programa_id INTO v_programa_pk;
    END IF;

    -- Upsert beneficiário
    IF p_beneficiario_id IS NOT NULL THEN
        INSERT INTO beneficiarios (beneficiario_id, nome, cnpj, uf, ente_id)
        VALUES (p_beneficiario_id, p_beneficiario_nome, p_beneficiario_cnpj, p_uf, p_ente_id)
        ON CONFLICT (beneficiario_id) DO UPDATE SET
            nome = EXCLUDED.nome,
            cnpj = EXCLUDED.cnpj,
            uf = EXCLUDED.uf,
            ente_id = EXCLUDED.ente_id
        RETURNING id INTO v_beneficiario_pk;
    END IF;

    -- Upsert plano de ação
    INSERT INTO planos_acao (
        plano_acao_id, plano_acao_codigo,
        objeto_id, programa_id, beneficiario_id,
        plano_acao_situacao, plano_trabalho_situacao,
        codigo_emenda_formatado,
        valor_custeio, valor_investimento, valor_total,
        politicas_publicas, motivo_impedimento, numero_parceria,
        data_atualizacao_plano_acao, data_atualizacao_plano_trabalho
    ) VALUES (
        p_plano_acao_id, p_plano_acao_codigo,
        v_objeto_pk, v_programa_pk, v_beneficiario_pk,
        p_plano_acao_situacao, p_plano_trabalho_situacao,
        p_codigo_emenda_formatado,
        COALESCE(p_valor_custeio, 0), COALESCE(p_valor_investimento, 0), COALESCE(p_valor_total, 0),
        p_politicas_publicas, p_motivo_impedimento, p_numero_parceria,
        NULLIF(p_data_atualizacao_plano, '')::TIMESTAMPTZ,
        NULLIF(p_data_atualizacao_trabalho, '')::TIMESTAMPTZ
    )
    ON CONFLICT (plano_acao_id) DO UPDATE SET
        plano_acao_codigo = EXCLUDED.plano_acao_codigo,
        plano_acao_situacao = EXCLUDED.plano_acao_situacao,
        plano_trabalho_situacao = EXCLUDED.plano_trabalho_situacao,
        codigo_emenda_formatado = EXCLUDED.codigo_emenda_formatado,
        valor_custeio = EXCLUDED.valor_custeio,
        valor_investimento = EXCLUDED.valor_investimento,
        valor_total = EXCLUDED.valor_total,
        politicas_publicas = EXCLUDED.politicas_publicas,
        motivo_impedimento = EXCLUDED.motivo_impedimento,
        numero_parceria = EXCLUDED.numero_parceria,
        data_atualizacao_plano_acao = EXCLUDED.data_atualizacao_plano_acao,
        data_atualizacao_plano_trabalho = EXCLUDED.data_atualizacao_plano_trabalho,
        extracted_at = NOW()
    RETURNING id INTO v_existing_id;

    RETURN v_existing_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 8. FUNÇÃO PARA PARSEAR EMENDA
-- ============================================================================

CREATE OR REPLACE FUNCTION parse_emenda(p_codigo TEXT)
RETURNS TABLE(emenda TEXT, parlamentar TEXT, ano INTEGER) AS $$
BEGIN
    IF p_codigo IS NULL OR p_codigo = '' THEN
        RETURN;
    END IF;
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
