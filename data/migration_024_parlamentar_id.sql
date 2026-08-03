-- ============================================================================
-- TransfereGov — Migration 024: Identificador consistente de parlamentares
-- ============================================================================
-- Banco: transferegov_db
-- Data: 2026-07-29
-- ============================================================================
--
-- Contexto:
--   O código de emenda (ex: 202641610002) contém embutido o ID do deputado
--   no sistema TransfereGov (posições 5-8, ex: 4161 = Marcos Pereira).
--   Esse ID nunca era extraído — toda relação entre tabelas dependia de
--   match por nome (frágil). Esta migration extrai e padroniza o uso do
--   parlamentar_id em todo o esquema.
--
-- Mudanças:
--   1. Adiciona parlamentar_id às tabelas parlamentares e planos_acao
--   2. Atualiza parse_emenda() para também retornar parlamentar_id
--   3. Atualiza upsert_plano_acao() para aceitar parlamentar_id
--   4. Backfill dos IDs existentes
-- ============================================================================

-- ============================================================================
-- 1. parlamentar_id na tabela parlamentares
-- ============================================================================

ALTER TABLE parlamentares ADD COLUMN IF NOT EXISTS parlamentar_id INTEGER;

-- Índice + constraint UNIQUE (cada deputado tem um ID único no TransfereGov)
CREATE UNIQUE INDEX IF NOT EXISTS idx_parlamentares_parlamentar_id
    ON parlamentares(parlamentar_id);
ALTER TABLE parlamentares ADD CONSTRAINT IF NOT EXISTS parlamentares_parlamentar_id_key
    UNIQUE USING INDEX idx_parlamentares_parlamentar_id;

-- ============================================================================
-- 2. parlamentar_id na tabela planos_acao (extraído do emenda_codigo)
-- ============================================================================

ALTER TABLE planos_acao ADD COLUMN IF NOT EXISTS parlamentar_id INTEGER;

CREATE INDEX IF NOT EXISTS idx_pa_parlamentar_id
    ON planos_acao(parlamentar_id);

-- ============================================================================
-- 3. Backfill — extrair parlamentar_id do emenda_codigo
-- ============================================================================
-- O emenda_codigo tem formato YYYYDDDDNNN onde:
--   YYYY = ano (chars 1-4)
--   DDDD = parlamentar_id (chars 5-8)
--   NNN  = sequencial da emenda (chars 9+)

-- 3a. Preencher parlamentares.parlamentar_id
UPDATE parlamentares p
SET parlamentar_id = SUBSTRING(e.emenda_codigo FROM 5 FOR 4)::INTEGER
FROM (
    SELECT DISTINCT ON (parlamentar_nome)
        parlamentar_nome,
        emenda_codigo
    FROM planos_acao
    WHERE emenda_codigo ~ '^\d{10,12}$'
      AND parlamentar_nome IS NOT NULL
      AND parlamentar_nome != ''
) e
WHERE p.nome = e.parlamentar_nome
  AND p.parlamentar_id IS NULL;

-- 3b. Preencher planos_acao.parlamentar_id
UPDATE planos_acao
SET parlamentar_id = SUBSTRING(emenda_codigo FROM 5 FOR 4)::INTEGER
WHERE emenda_codigo ~ '^\d{10,12}$'
  AND parlamentar_id IS NULL;

-- ============================================================================
-- 4. Atualizar função parse_emenda() — agora retorna parlamentar_id
-- ============================================================================

CREATE OR REPLACE FUNCTION parse_emenda(p_codigo TEXT)
RETURNS TABLE(emenda TEXT, parlamentar TEXT, ano INTEGER, parlamentar_id INTEGER) AS $$
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
        END AS ano,
        CASE
            WHEN length(split_part(p_codigo, '-', 1)) >= 8
            THEN SUBSTRING(split_part(p_codigo, '-', 1) FROM 5 FOR 4)::INTEGER
            ELSE NULL
        END AS parlamentar_id;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- 5. Atualizar função upsert_plano_acao() — parlamentar_id + emenda_codigo
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
    v_emenda_codigo TEXT;
    v_parlamentar_nome TEXT;
    v_emenda_ano INTEGER;
    v_parlamentar_id INTEGER;
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

    -- Extrair campos da emenda (se codigo_emenda_formatado estiver presente)
    IF p_codigo_emenda_formatado IS NOT NULL AND p_codigo_emenda_formatado != '' THEN
        v_emenda_codigo := split_part(p_codigo_emenda_formatado, '-', 1);
        v_parlamentar_nome := TRIM(split_part(p_codigo_emenda_formatado, '-', 2));
        v_emenda_ano := CASE
            WHEN length(v_emenda_codigo) >= 4
            THEN SUBSTRING(v_emenda_codigo FROM 1 FOR 4)::INTEGER
            ELSE NULL
        END;
        v_parlamentar_id := CASE
            WHEN length(v_emenda_codigo) >= 8
            THEN SUBSTRING(v_emenda_codigo FROM 5 FOR 4)::INTEGER
            ELSE NULL
        END;
    END IF;

    -- Upsert plano de ação
    INSERT INTO planos_acao (
        plano_acao_id, plano_acao_codigo,
        objeto_id, programa_id, beneficiario_id,
        plano_acao_situacao, plano_trabalho_situacao,
        codigo_emenda_formatado, emenda_codigo, parlamentar_nome, emenda_ano, parlamentar_id,
        valor_custeio, valor_investimento, valor_total,
        politicas_publicas, motivo_impedimento, numero_parceria,
        data_atualizacao_plano_acao, data_atualizacao_plano_trabalho
    ) VALUES (
        p_plano_acao_id, p_plano_acao_codigo,
        v_objeto_pk, v_programa_pk, v_beneficiario_pk,
        p_plano_acao_situacao, p_plano_trabalho_situacao,
        p_codigo_emenda_formatado, v_emenda_codigo, v_parlamentar_nome, v_emenda_ano, v_parlamentar_id,
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
        emenda_codigo = EXCLUDED.emenda_codigo,
        parlamentar_nome = EXCLUDED.parlamentar_nome,
        emenda_ano = EXCLUDED.emenda_ano,
        parlamentar_id = EXCLUDED.parlamentar_id,
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

    -- Upsert parlamentar na tabela de dimensão (se tivermos os dados)
    IF v_parlamentar_nome IS NOT NULL AND v_parlamentar_nome != '' THEN
        INSERT INTO parlamentares (nome, parlamentar_id, uf, partido)
        VALUES (v_parlamentar_nome, v_parlamentar_id, NULL, NULL)
        ON CONFLICT (nome) DO UPDATE SET
            parlamentar_id = CASE
                WHEN EXCLUDED.parlamentar_id IS NOT NULL THEN EXCLUDED.parlamentar_id
                ELSE parlamentares.parlamentar_id
            END;
    END IF;

    -- Upsert emenda na tabela de dimensão
    IF v_emenda_codigo IS NOT NULL AND v_emenda_codigo != '' THEN
        INSERT INTO emendas (emenda_codigo, ano, parlamentar_id)
        VALUES (v_emenda_codigo, v_emenda_ano, v_parlamentar_id)
        ON CONFLICT (emenda_codigo) DO UPDATE SET
            ano = EXCLUDED.ano,
            parlamentar_id = CASE
                WHEN EXCLUDED.parlamentar_id IS NOT NULL THEN EXCLUDED.parlamentar_id
                ELSE emendas.parlamentar_id
            END;
    END IF;

    RETURN v_existing_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 6. FK da tabela emendas → parlamentares.parlamentar_id (em vez do SERIAL id)
-- ============================================================================

ALTER TABLE emendas DROP CONSTRAINT IF EXISTS emendas_parlamentar_id_fkey;

UPDATE emendas e
SET parlamentar_id = p.parlamentar_id
FROM parlamentares p
WHERE e.parlamentar_id = p.id
  AND p.parlamentar_id IS NOT NULL;

ALTER TABLE emendas ADD CONSTRAINT emendas_parlamentar_id_fkey
    FOREIGN KEY (parlamentar_id) REFERENCES parlamentares(parlamentar_id);

-- ============================================================================
-- 7. Grants
-- ============================================================================

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO cognee;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO cognee;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO cognee;
