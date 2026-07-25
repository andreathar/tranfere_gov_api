-- migration_011_tse_deputados.sql: Adiciona colunas eleitorais TSE na tabela parlamentares_dados

ALTER TABLE parlamentares_dados 
ADD COLUMN IF NOT EXISTS ano_eleicao INTEGER DEFAULT 2022,
ADD COLUMN IF NOT EXISTS situacao_eleitoral TEXT,
ADD COLUMN IF NOT EXISTS coligacao TEXT,
ADD COLUMN IF NOT EXISTS patrimonio_total NUMERIC(15,2) DEFAULT 0.00,
ADD COLUMN IF NOT EXISTS votos_totais INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS percentual_votos NUMERIC(5,2) DEFAULT 0.00;

COMMENT ON COLUMN parlamentares_dados.situacao_eleitoral IS 'Situação da candidatura no TSE (ex: ELEITO POR QP, ELEITO POR MÉDIA, SUPLENTE)';
COMMENT ON COLUMN parlamentares_dados.coligacao IS 'Nome da coligação ou federação partidária registrada no TSE';
COMMENT ON COLUMN parlamentares_dados.patrimonio_total IS 'Valor total dos bens declarados à Justiça Eleitoral (TSE)';
