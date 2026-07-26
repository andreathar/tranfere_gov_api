-- Migration 016: Votações da Câmara dos Deputados
-- Tabelas para armazenar todas as votações e votos nominais de 2026
--
-- Fonte: API Dados Abertos da Câmara
--   GET /votacoes  → votações (sessões de plenário/comissões)
--   GET /votacoes/{id}/votos  → votos nominais de cada deputado

BEGIN;

-- ============================================================
-- Tabela de votações (sessões de plenário e comissões)
-- ============================================================
CREATE TABLE IF NOT EXISTS votacoes_camara (
    votacao_id       TEXT PRIMARY KEY,          -- ID da API (ex: "977414")
    data_registro    TIMESTAMPTZ,               -- dataHoraRegistro
    descricao        TEXT,                       -- descrição da votação
    aprovacao        BOOLEAN,                   -- sim/não
    proposicao_id    INTEGER,                   -- ID da proposição vinculada
    proposicao_ementa TEXT,                      -- ementa da proposição
    tipo_evento      TEXT,                       -- tipo do evento (Plenário, CCJC, etc.)
    sigla_orgao      TEXT,                       -- órgão (PLEN, CCJC, etc.)
    situacao         TEXT,                       -- situação da votação
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Tabela de votos nominais (cada deputado × cada votação)
-- ============================================================
CREATE TABLE IF NOT EXISTS votos_camara (
    id               SERIAL PRIMARY KEY,
    votacao_id       TEXT NOT NULL REFERENCES votacoes_camara(votacao_id),
    deputado_id      INTEGER NOT NULL,           -- ID do deputado na Câmara
    deputado_nome    TEXT,                        -- nomeCivil
    deputado_urna    TEXT,                        -- nomeEleitoral
    sigla_partido    TEXT,                        -- partido
    sigla_uf         TEXT,                        -- UF
    tipo_voto        TEXT NOT NULL,               -- Sim, Não, Abstenção, Obstrução, Liberado, etc.
    em_segredo       BOOLEAN DEFAULT FALSE,       -- voto em segredo?
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (votacao_id, deputado_id)              -- um voto por deputado por votação
);

-- ============================================================
-- Índices para consultas rápidas
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_votos_deputado ON votos_camara(deputado_id);
CREATE INDEX IF NOT EXISTS idx_votos_votacao ON votos_camara(votacao_id);
CREATE INDEX IF NOT EXISTS idx_votos_partido_uf ON votos_camara(sigla_partido, sigla_uf);
CREATE INDEX IF NOT EXISTS idx_votacoes_data ON votacoes_camara(data_registro DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_votos_tipo ON votos_camara(tipo_voto);

-- ============================================================
-- View para consulta completa (deputado + votação + voto)
-- ============================================================
CREATE OR REPLACE VIEW v_votos_completo AS
SELECT
    v.votacao_id,
    v.deputado_id,
    v.deputado_nome,
    v.deputado_urna,
    v.sigla_partido,
    v.sigla_uf,
    v.tipo_voto,
    v.em_segredo,
    vc.data_registro,
    vc.descricao,
    vc.aprovacao,
    vc.proposicao_id,
    vc.proposicao_ementa,
    vc.sigla_orgao,
    vc.tipo_evento
FROM votos_camara v
JOIN votacoes_camara vc ON v.votacao_id = vc.votacao_id;

-- ============================================================
-- View para resumo por deputado
-- ============================================================
CREATE OR REPLACE VIEW v_resumo_votos_deputado AS
SELECT
    deputado_id,
    deputado_urna AS nome,
    sigla_partido AS partido,
    sigla_uf AS uf,
    COUNT(*) AS total_votacoes,
    SUM(CASE WHEN tipo_voto = 'Sim' THEN 1 ELSE 0 END) AS votos_sim,
    SUM(CASE WHEN tipo_voto = 'Não' THEN 1 ELSE 0 END) AS votos_nao,
    SUM(CASE WHEN tipo_voto = 'Abstenção' THEN 1 ELSE 0 END) AS abstencoes,
    SUM(CASE WHEN tipo_voto = 'Obstrução' THEN 1 ELSE 0 END) AS obstrucoes,
    SUM(CASE WHEN tipo_voto IN ('Liberado', 'Art. 17') THEN 1 ELSE 0 END) AS liberados,
    ROUND(100.0 * SUM(CASE WHEN tipo_voto = 'Sim' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS pct_sim,
    MIN(data_registro) AS primeira_votacao,
    MAX(data_registro) AS ultima_votacao
FROM v_votos_completo
GROUP BY deputado_id, deputado_urna, sigla_partido, sigla_uf;

-- ============================================================
-- View para resumo por votação (quantidade de votos por tipo)
-- ============================================================
CREATE OR REPLACE VIEW v_resumo_votacao AS
SELECT
    vc.votacao_id,
    vc.data_registro,
    vc.descricao,
    vc.aprovacao,
    vc.sigla_orgao,
    vc.proposicao_ementa,
    COUNT(*) AS total_votos,
    SUM(CASE WHEN v.tipo_voto = 'Sim' THEN 1 ELSE 0 END) AS sims,
    SUM(CASE WHEN v.tipo_voto = 'Não' THEN 1 ELSE 0 END) AS naos,
    SUM(CASE WHEN v.tipo_voto = 'Abstenção' THEN 1 ELSE 0 END) AS abstencoes,
    SUM(CASE WHEN v.tipo_voto = 'Obstrução' THEN 1 ELSE 0 END) AS obstrucoes
FROM votacoes_camara vc
LEFT JOIN votos_camara v ON vc.votacao_id = v.votacao_id
GROUP BY vc.votacao_id, vc.data_registro, vc.descricao, vc.aprovacao,
         vc.sigla_orgao, vc.proposicao_ementa;

-- ============================================================
-- Controle de extração (evitar re-fetch desnecessário)
-- ============================================================
CREATE TABLE IF NOT EXISTS votacoes_extract_log (
    id               SERIAL PRIMARY KEY,
    ano              INTEGER NOT NULL,
    total_votacoes   INTEGER DEFAULT 0,
    total_votos      INTEGER DEFAULT 0,
    data_inicio      TEXT,               -- data_inicio usada na busca
    data_fim         TEXT,               -- data_fim usada na busca
    executado_em     TIMESTAMPTZ DEFAULT NOW()
);

COMMIT;
