-- ============================================================================
-- TransfereGov — Migration 015: Tabela e Views de Senadores (Dados Senado API)
-- ============================================================================
-- Banco: transferegov_db
-- Data: 2026-07-26
-- Fonte: Senado Federal — API REST (lista, detalhe, votações, relatorias)
-- ============================================================================

BEGIN;

-- 1. Tabela de Perfil dos Senadores
CREATE TABLE IF NOT EXISTS senadores_dados (
    senador_codigo INTEGER PRIMARY KEY,        -- Código na API do Senado
    nome_completo TEXT NOT NULL,
    nome_parlamentar TEXT,
    sigla_partido TEXT,
    uf CHAR(2),
    email TEXT,
    telefone TEXT,
    foto_url TEXT,
    mandato_inicio DATE,
    mandato_fim DATE,
    legislatura INTEGER,
    situacao TEXT DEFAULT 'EM EXERCÍCIO',      -- EM EXERCÍCIO, LICENCIADO, etc.
    total_votacoes INTEGER DEFAULT 0,
    total_relatorias INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Indexação
CREATE INDEX IF NOT EXISTS idx_senadores_partido ON senadores_dados (sigla_partido);
CREATE INDEX IF NOT EXISTS idx_senadores_uf ON senadores_dados (uf);
CREATE INDEX IF NOT EXISTS idx_senadores_nome ON senadores_dados (nome_completo);

-- 3. View Canônica: Senadores com Dados Enriquecidos
DROP VIEW IF EXISTS v_senadores_completo CASCADE;
CREATE VIEW v_senadores_completo AS
SELECT
    s.senador_codigo,
    s.nome_completo,
    s.nome_parlamentar,
    s.sigla_partido AS partido,
    s.uf,
    s.email,
    s.telefone,
    s.foto_url,
    s.mandato_inicio,
    s.mandato_fim,
    s.legislatura,
    s.situacao,
    s.total_votacoes,
    s.total_relatorias,
    -- Dados IBGE da UF (população estimada da sede do estado)
    e.nome AS estado_nome,
    e.regiao AS regiao,
    -- Emendas Pix do estado (agregado)
    COALESCE(em.total_emendas_uf, 0) AS total_emendas_estado,
    COALESCE(em.valor_total_emendas_uf, 0.00) AS valor_emendas_estado,
    -- Indicadores derivados
    ROUND(
        COALESCE(em.valor_total_emendas_uf, 0) /
        NULLIF((SELECT SUM(populacao) FROM municipios_ibge WHERE uf = s.uf), 0),
        2
    ) AS emendas_per_capita_estado,
    s.updated_at
FROM senadores_dados s
LEFT JOIN (
    SELECT DISTINCT uf, nome, regiao
    FROM municipios_ibge
) e ON s.uf = e.uf
LEFT JOIN (
    SELECT
        m.uf,
        COUNT(pa.id) AS total_emendas_uf,
        SUM(pa.valor_total) AS valor_total_emendas_uf
    FROM planos_acao pa
    JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
    JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
    JOIN municipios_ibge m ON bm.municipio_id = m.municipio_id
    GROUP BY m.uf
) em ON s.uf = em.uf;

-- 4. View Resumo: Senadores por Partido
DROP VIEW IF EXISTS v_senadores_por_partido CASCADE;
CREATE VIEW v_senadores_por_partido AS
SELECT
    sigla_partido AS partido,
    COUNT(*) AS total_senadores,
    COUNT(DISTINCT uf) AS total_ufs,
    ARRAY_AGG(DISTINCT uf ORDER BY uf) AS ufs,
    SUM(total_votacoes) AS total_votacoes,
    SUM(total_relatorias) AS total_relatorias
FROM senadores_dados
WHERE situacao = 'EM EXERCÍCIO'
GROUP BY sigla_partido
ORDER BY total_senadores DESC;

-- 5. View Resumo: Senadores por UF
DROP VIEW IF EXISTS v_senadores_por_uf CASCADE;
CREATE VIEW v_senadores_por_uf AS
SELECT
    uf,
    COUNT(*) AS total_senadores,
    ARRAY_AGG(nome_completo ORDER BY nome_completo) AS nomes,
    ARRAY_AGG(sigla_partido ORDER BY nome_completo) AS partidos
FROM senadores_dados
WHERE situacao = 'EM EXERCÍCIO'
GROUP BY uf
ORDER BY uf;

-- 6. Grants
GRANT ALL PRIVILEGES ON TABLE senadores_dados TO cognee;
GRANT ALL PRIVILEGES ON v_senadores_completo TO cognee;
GRANT ALL PRIVILEGES ON v_senadores_por_partido TO cognee;
GRANT ALL PRIVILEGES ON v_senadores_por_uf TO cognee;

COMMIT;
