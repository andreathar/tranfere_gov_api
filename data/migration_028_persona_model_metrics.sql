-- Migration 028: Adiciona colunas de modelo_usado e score_qualidade em parlamentares_personas

ALTER TABLE parlamentares_personas
ADD COLUMN IF NOT EXISTS modelo_usado VARCHAR(100) DEFAULT 'llama-3.2-3b-instruct:q4_k_m',
ADD COLUMN IF NOT EXISTS score_qualidade NUMERIC(5,2) DEFAULT 0.0;

COMMENT ON COLUMN parlamentares_personas.modelo_usado IS 'Identificador do modelo LocalAI utilizado na geração da persona';
COMMENT ON COLUMN parlamentares_personas.score_qualidade IS 'Pontuação de qualidade da persona gerada (0 a 100)';
