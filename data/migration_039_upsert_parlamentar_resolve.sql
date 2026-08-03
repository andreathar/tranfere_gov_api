-- migration_039: resolve parlamentar_id canonico (por NOME) antes de gravar
-- planos_acao/emendas no upsert_plano_acao.
--
-- Motivo: o id derivado do codigo da emenda (digitos 5-8, ex: 202230610003 -> 3061)
-- colide com o parlamentar_id canonico (ex: 4291, 220714) ja referenciado por emendas,
-- parlamentares_dados etc. O ON CONFLICT (nome) DO UPDATE trocava o id e quebrava a FK
-- emendas_parlamentar_id_fkey (54 erros) ou violava idx_parlamentares_parlamentar_id (12).
--
-- Novo fluxo:
--   1. resolve parlamentar por NOME (mantem id canonico);
--   2. senao adota id derivado ja existente (evita UNIQUE);
--   3. senao cria novo parlamentar com o id derivado.
-- Depois grava emendas e planos_acao com o id RESOLVIDO, mantendo o JOIN do RAG
-- (pa.parlamentar_id IN (SELECT parlamentar_id FROM parlamentares_dados WHERE deputado_id=...)).
-- Mantem a correcao da migration_037 (RETURNING beneficiario_id).

CREATE OR REPLACE FUNCTION public.upsert_plano_acao(p_plano_acao_id integer, p_plano_acao_codigo text, p_objeto_id integer, p_objeto_descricao text, p_programa_id integer, p_programa_codigo text, p_beneficiario_id integer, p_beneficiario_nome text, p_beneficiario_cnpj text, p_uf text, p_ente_id integer, p_plano_acao_situacao text, p_plano_trabalho_situacao text, p_codigo_emenda_formatado text, p_valor_custeio numeric, p_valor_investimento numeric, p_valor_total numeric, p_politicas_publicas text, p_motivo_impedimento text, p_numero_parceria text, p_data_atualizacao_plano text, p_data_atualizacao_trabalho text)
 RETURNS integer
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_objeto_pk INTEGER;
    v_programa_pk INTEGER;
    v_beneficiario_pk INTEGER;
    v_existing_id INTEGER;
    v_emenda_codigo TEXT;
    v_parlamentar_nome TEXT;
    v_emenda_ano INTEGER;
    v_parlamentar_id INTEGER;
    v_parlamentar_id_derivado INTEGER;
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

    -- Upsert beneficiario (chave natural)
    IF p_beneficiario_id IS NOT NULL THEN
        INSERT INTO beneficiarios (beneficiario_id, nome, cnpj, uf, ente_id)
        VALUES (p_beneficiario_id, p_beneficiario_nome, p_beneficiario_cnpj, p_uf, p_ente_id)
        ON CONFLICT (beneficiario_id) DO UPDATE SET
            nome = EXCLUDED.nome,
            cnpj = EXCLUDED.cnpj,
            uf = EXCLUDED.uf,
            ente_id = EXCLUDED.ente_id
        RETURNING beneficiario_id INTO v_beneficiario_pk;
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
        v_parlamentar_id_derivado := CASE
            WHEN length(v_emenda_codigo) >= 8
            THEN SUBSTRING(v_emenda_codigo FROM 5 FOR 4)::INTEGER
            ELSE NULL
        END;
        v_parlamentar_id := v_parlamentar_id_derivado;
    END IF;

    -- Resolver parlamentar na dimensao ANTES de gravar emendas/planos_acao.
    -- 1) prioriza NOME existente (mantem o parlamentar_id canonico ja referenciado);
    -- 2) senao adota id derivado ja existente (evita violacao UNIQUE);
    -- 3) senao cria novo parlamentar com o id derivado.
    IF v_parlamentar_nome IS NOT NULL AND v_parlamentar_nome != '' THEN
        SELECT p.parlamentar_id INTO v_parlamentar_id
        FROM parlamentares p
        WHERE p.nome = v_parlamentar_nome
        LIMIT 1;

        IF v_parlamentar_id IS NULL AND v_parlamentar_id_derivado IS NOT NULL THEN
            SELECT p.parlamentar_id INTO v_parlamentar_id
            FROM parlamentares p
            WHERE p.parlamentar_id = v_parlamentar_id_derivado
            LIMIT 1;
        END IF;

        IF v_parlamentar_id IS NULL THEN
            INSERT INTO parlamentares (nome, parlamentar_id, uf, partido)
            VALUES (v_parlamentar_nome, v_parlamentar_id_derivado, NULL, NULL)
            ON CONFLICT (nome) DO UPDATE SET
                parlamentar_id = parlamentares.parlamentar_id
            RETURNING parlamentar_id INTO v_parlamentar_id;
        END IF;
    END IF;

    -- Upsert emenda na tabela de dimensao (id resolvido)
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

    -- Upsert plano de acao (id resolvido)
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

    RETURN v_existing_id;
END;
$function$
