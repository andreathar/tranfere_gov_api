-- ============================================================================
-- TransfereGov — Migration 013: Atos do Diário Oficial
-- ============================================================================
-- Banco: transferegov_db
-- Objetivo: Estruturar dados extraídos do Diário Oficial (DOU/Municipais)
-- e configurar tabelas de monitoramento (alertas) para a equipe.
-- ============================================================================

CREATE TABLE IF NOT EXISTS diario_oficial_atos (
    ato_id              SERIAL PRIMARY KEY,
    data_publicacao     DATE NOT NULL,
    fonte               VARCHAR(50) NOT NULL, -- 'DOU' ou 'QUERIDO_DIARIO'
    orgao               VARCHAR(255),         -- Ex: 'Prefeitura de Campinas', 'Ministério da Saúde'
    tipo_ato            VARCHAR(100),         -- Portaria, Licitação, Nomeação, etc. (extraído via LLM)
    texto_bruto         TEXT NOT NULL,
    resumo_ia           TEXT,
    valor_financeiro    NUMERIC(15, 2),
    entidades_citadas   JSONB,                -- Array de pessoas/empresas citadas (extraído via LLM)
    link_original       TEXT,
    
    processado_em       TIMESTAMPTZ DEFAULT NOW(),
    hash_conteudo       VARCHAR(64) UNIQUE NOT NULL -- md5 do texto para evitar duplicidade
);

CREATE INDEX IF NOT EXISTS idx_do_data ON diario_oficial_atos(data_publicacao DESC);
CREATE INDEX IF NOT EXISTS idx_do_tipo ON diario_oficial_atos(tipo_ato);
CREATE INDEX IF NOT EXISTS idx_do_orgao ON diario_oficial_atos(orgao);
CREATE INDEX IF NOT EXISTS idx_do_entidades ON diario_oficial_atos USING GIN (entidades_citadas);

CREATE TABLE IF NOT EXISTS parlamentar_alertas (
    alerta_id           SERIAL PRIMARY KEY,
    parlamentar_nome    VARCHAR(255) NOT NULL,
    ato_id              INTEGER REFERENCES diario_oficial_atos(ato_id) ON DELETE CASCADE,
    nivel_relevancia    INTEGER DEFAULT 1,    -- 1 a 5, calculado pelo LLM
    notificado          BOOLEAN DEFAULT FALSE,
    criado_em           TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pa_nome ON parlamentar_alertas(parlamentar_nome);

GRANT ALL PRIVILEGES ON diario_oficial_atos TO cognee;
GRANT ALL PRIVILEGES ON parlamentar_alertas TO cognee;
GRANT ALL PRIVILEGES ON SEQUENCE diario_oficial_atos_ato_id_seq TO cognee;
GRANT ALL PRIVILEGES ON SEQUENCE parlamentar_alertas_alerta_id_seq TO cognee;
