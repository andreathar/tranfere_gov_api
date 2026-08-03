-- Migration 016: Tabela de discursos parlamentares (Câmara dos Deputados)
-- Cria tabela para armazenar discursos de cada deputado no plenário/comissões
-- Dependências: migration_003 (parlamentares_dados)

CREATE TABLE IF NOT EXISTS parlamentar_discursos (
    id SERIAL PRIMARY KEY,
    deputado_id INTEGER REFERENCES parlamentares_dados(deputado_id),
    data_hora_inicio TIMESTAMP,
    fase_evento VARCHAR(255),
    tipo_discurso VARCHAR(255),
    keywords TEXT,
    sumario TEXT,
    transcricao TEXT,
    url_texto TEXT,
    CONSTRAINT uk_discurso_hora UNIQUE (deputado_id, data_hora_inicio)
);

CREATE INDEX IF NOT EXISTS idx_discursos_deputado ON parlamentar_discursos(deputado_id);
CREATE INDEX IF NOT EXISTS idx_discursos_data ON parlamentar_discursos(data_hora_inicio);
CREATE INDEX IF NOT EXISTS idx_discursos_deputado_data ON parlamentar_discursos(deputado_id, data_hora_inicio DESC);
