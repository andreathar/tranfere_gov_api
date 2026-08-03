-- migration_038: performance do frontend (rankings, discursos, votações).
--
-- Indexes compostos para as queries mais pesadas servidas pela API:
--   1. Ranking de vereadores por UF + partido (filtros do frontend, 430k linhas);
--   2. Discursos por parlamentar em ordem cronológica (timeline da aba Discursos);
--   3. Emendas discricionárias por parlamentar (nova sub-tab do deputado).

CREATE INDEX IF NOT EXISTS idx_vereadors_uf_partido_situacao
    ON vereadores_dados (uf, sigla_partido, situacao_candidatura);

CREATE INDEX IF NOT EXISTS idx_discursos_parlamentar_data
    ON parlamentar_discursos (parlamentar_id, data_hora_inicio DESC);

CREATE INDEX IF NOT EXISTS idx_ed_parlamentar_id_ano
    ON emendas_discricionarias (parlamentar_id, ano);

-- Votações recentes (aba nacional de votações): data é o filtro principal.
CREATE INDEX IF NOT EXISTS idx_votacoes_data
    ON votacoes_camara (data_registro DESC);
