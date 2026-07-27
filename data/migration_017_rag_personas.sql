-- Migration 017: Schema robusto para parlamentares_personas + índices
-- Data: 2026-07-26
-- Descrição: Recria parlamentares_personas com colunas novas (contexto_rag, versao_prompt, fontes_usadas)
--           e constraint UNIQUE para 1 persona por deputado por versão.

BEGIN;

-- 1. Criar tabela nova (se não existir)
CREATE TABLE IF NOT EXISTS parlamentares_personas_v2 (
    id SERIAL PRIMARY KEY,
    deputado_id INTEGER NOT NULL REFERENCES parlamentares_dados(deputado_id),
    query_text TEXT,
    contexto_rag TEXT,                          -- chunks recuperados do Qdrant (auditoria)
    analise_gerada TEXT,
    versao_prompt INTEGER DEFAULT 1,            -- versionamento para regeneração
    fontes_usadas TEXT[],                       -- ex: {'emendas','votos','proposicoes'}
    data_analise TIMESTAMPTZ DEFAULT NOW(),
    duracao_segundos NUMERIC,
    UNIQUE (deputado_id, versao_prompt)
);

-- 2. Se a tabela antiga existir, migrar dados e trocar o nome
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'parlamentares_personas')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'parlamentares_personas_v2')
    THEN
        -- Renomear tabela antiga para backup
        ALTER TABLE parlamentares_personas RENAME TO parlamentares_personas_backup;
        -- Renomear nova para o nome final
        ALTER TABLE parlamentares_personas_v2 RENAME TO parlamentares_personas;
        -- Migrar dados antigos (apenas colunas que existem na tabela nova)
        INSERT INTO parlamentares_personas (deputado_id, query_text, analise_gerada, data_analise, duracao_segundos)
        SELECT deputado_id, query_text, analise_gerada, data_analise, duracao_segundos
        FROM parlamentares_personas_backup
        ON CONFLICT (deputado_id, versao_prompt) DO NOTHING;
        -- Dropar backup
        DROP TABLE IF EXISTS parlamentares_personas_backup;
    ELSIF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'parlamentares_personas_v2') THEN
        -- Só renomear se a _v2 ainda existe
        ALTER TABLE parlamentares_personas_v2 RENAME TO parlamentares_personas;
    END IF;
END $$;

-- 3. Garantir que a tabela final existe (nem antiga nem _v2)
CREATE TABLE IF NOT EXISTS parlamentares_personas (
    id SERIAL PRIMARY KEY,
    deputado_id INTEGER NOT NULL REFERENCES parlamentares_dados(deputado_id),
    query_text TEXT,
    contexto_rag TEXT,
    analise_gerada TEXT,
    versao_prompt INTEGER DEFAULT 1,
    fontes_usadas TEXT[],
    data_analise TIMESTAMPTZ DEFAULT NOW(),
    duracao_segundos NUMERIC,
    UNIQUE (deputado_id, versao_prompt)
);

-- 4. Adicionar colunas faltantes em tabelas antigas (caso migration anterior tenha criado sem elas)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'parlamentares_personas' AND column_name = 'contexto_rag') THEN
        ALTER TABLE parlamentares_personas ADD COLUMN contexto_rag TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'parlamentares_personas' AND column_name = 'versao_prompt') THEN
        ALTER TABLE parlamentares_personas ADD COLUMN versao_prompt INTEGER DEFAULT 1;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'parlamentares_personas' AND column_name = 'fontes_usadas') THEN
        ALTER TABLE parlamentares_personas ADD COLUMN fontes_usadas TEXT[];
    END IF;
END $$;

-- 5. Índices para performance
CREATE INDEX IF NOT EXISTS idx_personas_deputado ON parlamentares_personas(deputado_id);
CREATE INDEX IF NOT EXISTS idx_personas_versao ON parlamentares_personas(versao_prompt);
CREATE INDEX IF NOT EXISTS idx_personas_data ON parlamentares_personas(data_analise DESC);

-- 6. Constraint UNIQUE (se não existir)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'parlamentares_personas_deputado_versao_key'
    ) THEN
        ALTER TABLE parlamentares_personas
            ADD CONSTRAINT parlamentares_personas_deputado_versao_key
            UNIQUE (deputado_id, versao_prompt);
    END IF;
END $$;

COMMIT;
