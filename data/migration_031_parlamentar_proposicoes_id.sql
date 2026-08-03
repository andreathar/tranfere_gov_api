-- migration_031_parlamentar_proposicoes_id.sql
-- Adiciona parlamentar_id (TransfereGov) à tabela parlamentar_proposicoes
-- Permite JOIN direto com planos_acao sem depender de nome

BEGIN;

ALTER TABLE parlamentar_proposicoes ADD COLUMN IF NOT EXISTS parlamentar_id INTEGER REFERENCES parlamentares(parlamentar_id);

-- Popular parlamentar_id via planos_acao (bridge nome → id)
UPDATE parlamentar_proposicoes pp
SET parlamentar_id = (
    SELECT pa.parlamentar_id
    FROM planos_acao pa
    WHERE pa.parlamentar_nome = pp.parlamentar_nome
      AND pa.parlamentar_id IS NOT NULL
    LIMIT 1
)
WHERE pp.parlamentar_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_prop_parlamentar_id ON parlamentar_proposicoes(parlamentar_id);

COMMIT;
