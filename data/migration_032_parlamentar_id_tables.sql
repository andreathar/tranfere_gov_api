-- migration_032_parlamentar_id_tables.sql
-- Adiciona parlamentar_id às tabelas que ainda não possuem a coluna
-- Permite JOIN exato por ID em vez de nome nas views e queries

BEGIN;

-- ============================================================================
-- 1. emendas_discricionarias
-- ============================================================================
ALTER TABLE emendas_discricionarias ADD COLUMN IF NOT EXISTS parlamentar_id INTEGER REFERENCES parlamentares(parlamentar_id);

-- Popula via match exato de nome com a tabela parlamentares (dimensão)
UPDATE emendas_discricionarias ed
SET parlamentar_id = p.parlamentar_id
FROM parlamentares p
WHERE ed.parlamentar_nome = p.nome
  AND ed.parlamentar_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_ed_parlamentar_id ON emendas_discricionarias(parlamentar_id);

-- ============================================================================
-- 2. parlamentar_alertas
-- ============================================================================
ALTER TABLE parlamentar_alertas ADD COLUMN IF NOT EXISTS parlamentar_id INTEGER REFERENCES parlamentares(parlamentar_id);

-- Popula via match exato de nome
UPDATE parlamentar_alertas pa
SET parlamentar_id = p.parlamentar_id
FROM parlamentares p
WHERE pa.parlamentar_nome = p.nome
  AND pa.parlamentar_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_pa_parlamentar_id ON parlamentar_alertas(parlamentar_id);

-- ============================================================================
-- 3. parlamentares_dados (necessário para os JOINs das views)
-- ============================================================================
ALTER TABLE parlamentares_dados ADD COLUMN IF NOT EXISTS parlamentar_id INTEGER REFERENCES parlamentares(parlamentar_id);

-- Popula via match exato de nome com a tabela parlamentares (dimensão)
UPDATE parlamentares_dados pd
SET parlamentar_id = p.parlamentar_id
FROM parlamentares p
WHERE pd.nome = p.nome
  AND pd.parlamentar_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_pd_parlamentar_id ON parlamentares_dados(parlamentar_id);

COMMIT;
