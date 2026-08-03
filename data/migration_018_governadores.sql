-- Migration 018: Tabela governadores_dados e view v_governadores_resumo

CREATE TABLE IF NOT EXISTS governadores_dados (
    uf VARCHAR(2) PRIMARY KEY,
    nome_governador VARCHAR(150) NOT NULL,
    nome_vice VARCHAR(150),
    sigla_partido VARCHAR(20) NOT NULL,
    coligacao TEXT,
    ano_eleicao INT DEFAULT 2022,
    votos_t1 INT DEFAULT 0,
    pct_votos_t1 NUMERIC(5,2) DEFAULT 0.0,
    votos_t2 INT DEFAULT 0,
    pct_votos_t2 NUMERIC(5,2) DEFAULT 0.0,
    situacao VARCHAR(50) DEFAULT 'ELEITO',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE governadores_dados IS 'Governadores eleitos dos 26 estados + DF (TSE 2022)';
COMMENT ON COLUMN governadores_dados.uf IS 'Sigla do estado (PK)';
COMMENT ON COLUMN governadores_dados.nome_governador IS 'Nome do governador eleito';
COMMENT ON COLUMN governadores_dados.sigla_partido IS 'Partido político do governador';

-- View consolidando Governador + Total Emendas Pix para a UF + Deputados da mesma UF
CREATE OR REPLACE VIEW v_governadores_resumo AS
SELECT
    g.uf,
    g.nome_governador,
    g.sigla_partido AS partido_governador,
    g.coligacao,
    g.votos_t2,
    g.pct_votos_t2,
    COALESCE(COUNT(DISTINCT pd.deputado_id), 0) AS total_deputados_uf,
    COALESCE(SUM(CASE WHEN pd.sigla_partido = g.sigla_partido THEN 1 ELSE 0 END), 0) AS deputados_mesmo_partido,
    COALESCE(e.valor_total, 0.0) AS valor_total_emendas_uf,
    COALESCE(e.total_planos, 0) AS total_planos_uf
FROM governadores_dados g
LEFT JOIN parlamentares_dados pd ON pd.uf = g.uf
LEFT JOIN v_resumo_por_estado e ON e.uf = g.uf
GROUP BY g.uf, g.nome_governador, g.sigla_partido, g.coligacao, g.votos_t2, g.pct_votos_t2, e.valor_total, e.total_planos;
