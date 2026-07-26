-- migration_014_proposicoes.sql: Adiciona tabela para armazenar proposições da Câmara

CREATE TABLE IF NOT EXISTS parlamentar_proposicoes (
    proposicao_id INTEGER PRIMARY KEY,
    deputado_id INTEGER REFERENCES parlamentares_dados(deputado_id),
    parlamentar_nome TEXT,
    sigla_tipo VARCHAR(20),
    numero INTEGER,
    ano INTEGER,
    ementa TEXT,
    resumo_ia TEXT,
    data_apresentacao DATE,
    link_inteiro_teor VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_prop_deputado ON parlamentar_proposicoes(deputado_id);
CREATE INDEX IF NOT EXISTS idx_prop_nome ON parlamentar_proposicoes(parlamentar_nome);
