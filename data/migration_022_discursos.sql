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
