-- ============================================================================
-- TransfereGov — Migration 036: Inserir 130 deputados faltantes em parlamentares
-- ============================================================================
-- Banco: transferegov_db
-- Data: 2026-07-30
-- ============================================================================
--
-- Contexto:
--   A tabela parlamentares contém apenas deputados que autoram emendas PIX
--   no TransfereGov (470 registros). No entanto, parlamentares_dados (Câmara
--   dos Deputados) possui 512 registros — 130 deles sem parlamentar_id porque
--   o deputado correspondente não existe em parlamentares (nunca usaram
--   Transferências Especiais / Emendas PIX).
--
--   Migration 035 adicionou parlamentar_id em votos_camara e
--   parlamentares_personas mas o backfill deixou NULL para esses 130
--   porque parlamentares_dados.parlamentar_id era NULL.
--
-- Solução:
--   1. INSERT dos 130 deputados em parlamentares usando deputado_id da Câmara
--      como parlamentar_id sintético (sem colisão: deputado_id ~73k-236k,
--      parlamentar_id TransfereGov ~1k-9k).
--   2. UPDATE parlamentares_dados.parlamentar_id = deputado_id.
--   3. Re-backfill votos_camara, parlamentares_personas e
--      parlamentar_proposicoes via JOIN com parlamentares_dados.
--   4. Backfill emendas_discricionarias via nome_normalizado.
--   5. Backfill parcial de parlamentar_alertas via nome_normalizado.
-- ============================================================================

BEGIN;

-- ============================================================================
-- PARTE 1: Inserir 130 deputados faltantes em parlamentares
-- ============================================================================

INSERT INTO parlamentares (nome, uf, partido, parlamentar_id)
SELECT
    d.nome,
    d.uf,
    d.sigla_partido,
    d.deputado_id  -- Câmara ID como parlamentar_id sintético (sem colisão)
FROM parlamentares_dados d
WHERE d.parlamentar_id IS NULL;

-- Verificação
DO $$
DECLARE
    inserted_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO inserted_count
    FROM parlamentares p
    JOIN parlamentares_dados d ON d.deputado_id = p.parlamentar_id
    WHERE d.parlamentar_id IS NULL;

    RAISE NOTICE 'PARTE 1: % deputados inseridos em parlamentares com deputado_id como parlamentar_id', inserted_count;
END $$;

-- ============================================================================
-- PARTE 2: Vincular parlamentares_dados aos novos parlamentares
-- ============================================================================

UPDATE parlamentares_dados d
SET parlamentar_id = d.deputado_id
WHERE d.parlamentar_id IS NULL
  AND EXISTS (
      SELECT 1 FROM parlamentares p
      WHERE p.parlamentar_id = d.deputado_id
  );

-- Verificação
DO $$
DECLARE
    remaining INTEGER;
BEGIN
    SELECT COUNT(*) INTO remaining
    FROM parlamentares_dados WHERE parlamentar_id IS NULL;
    RAISE NOTICE 'PARTE 2: % parlamentares_dados ainda sem parlamentar_id (esperado: 0)', remaining;
END $$;

-- ============================================================================
-- PARTE 3: Re-backfill votos_camara
-- ============================================================================

UPDATE votos_camara vc
SET parlamentar_id = pad.parlamentar_id
FROM parlamentares_dados pad
WHERE vc.deputado_id = pad.deputado_id
  AND pad.parlamentar_id IS NOT NULL
  AND vc.parlamentar_id IS NULL;

-- Verificação
DO $$
DECLARE
    remaining INTEGER;
BEGIN
    SELECT COUNT(*) INTO remaining FROM votos_camara WHERE parlamentar_id IS NULL;
    RAISE NOTICE 'PARTE 3: % votos_camara ainda sem parlamentar_id', remaining;
END $$;

-- ============================================================================
-- PARTE 4: Re-backfill parlamentares_personas
-- ============================================================================

UPDATE parlamentares_personas pp
SET parlamentar_id = pad.parlamentar_id
FROM parlamentares_dados pad
WHERE pp.deputado_id = pad.deputado_id
  AND pad.parlamentar_id IS NOT NULL
  AND pp.parlamentar_id IS NULL;

-- Verificação
DO $$
DECLARE
    remaining INTEGER;
BEGIN
    SELECT COUNT(*) INTO remaining FROM parlamentares_personas WHERE parlamentar_id IS NULL;
    RAISE NOTICE 'PARTE 4: % parlamentares_personas ainda sem parlamentar_id', remaining;
END $$;

-- ============================================================================
-- PARTE 5: Backfill parlamentar_proposicoes
-- ============================================================================

UPDATE parlamentar_proposicoes pp
SET parlamentar_id = pad.parlamentar_id
FROM parlamentares_dados pad
WHERE pp.deputado_id = pad.deputado_id
  AND pad.parlamentar_id IS NOT NULL
  AND pp.parlamentar_id IS NULL;

-- Verificação
DO $$
DECLARE
    remaining INTEGER;
BEGIN
    SELECT COUNT(*) INTO remaining FROM parlamentar_proposicoes WHERE parlamentar_id IS NULL;
    RAISE NOTICE 'PARTE 5: % parlamentar_proposicoes ainda sem parlamentar_id', remaining;
END $$;

-- ============================================================================
-- PARTE 6: Backfill emendas_discricionarias via nome_normalizado
-- ============================================================================

UPDATE emendas_discricionarias ed
SET parlamentar_id = pad.parlamentar_id
FROM parlamentares_dados pad
WHERE ed.parlamentar_nome_normalizado = pad.nome_normalizado
  AND pad.parlamentar_id IS NOT NULL
  AND ed.parlamentar_id IS NULL;

-- Verificação
DO $$
DECLARE
    remaining INTEGER;
    distinct_authors INTEGER;
BEGIN
    SELECT COUNT(*) INTO remaining FROM emendas_discricionarias WHERE parlamentar_id IS NULL;
    SELECT COUNT(DISTINCT parlamentar_nome_normalizado) INTO distinct_authors
    FROM emendas_discricionarias WHERE parlamentar_id IS NULL;
    RAISE NOTICE 'PARTE 6: % emendas_discricionarias sem parlamentar_id (% autores distintos)', remaining, distinct_authors;
END $$;

-- ============================================================================
-- PARTE 7: Backfill parlamentar_alertas via nome_normalizado
-- ============================================================================

UPDATE parlamentar_alertas pa
SET parlamentar_id = pad.parlamentar_id
FROM parlamentares_dados pad
WHERE pa.parlamentar_nome = pad.nome
  AND pad.parlamentar_id IS NOT NULL
  AND pa.parlamentar_id IS NULL;

-- Verificação
DO $$
DECLARE
    remaining INTEGER;
BEGIN
    SELECT COUNT(*) INTO remaining FROM parlamentar_alertas WHERE parlamentar_id IS NULL;
    RAISE NOTICE 'PARTE 7: % parlamentar_alertas ainda sem parlamentar_id', remaining;
END $$;

-- ============================================================================
-- 8. Relatório final
-- ============================================================================

DO $$
DECLARE
    v_parlamentares INTEGER;
    v_parlamentares_dados INTEGER;
    v_votos INTEGER;
    v_personas INTEGER;
    v_proposicoes INTEGER;
    v_emendas INTEGER;
    v_alertas INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_parlamentares FROM parlamentares;
    SELECT COUNT(*) INTO v_parlamentares_dados FROM parlamentares_dados WHERE parlamentar_id IS NOT NULL;
    SELECT COUNT(*) INTO v_votos FROM votos_camara WHERE parlamentar_id IS NOT NULL;
    SELECT COUNT(*) INTO v_personas FROM parlamentares_personas WHERE parlamentar_id IS NOT NULL;
    SELECT COUNT(*) INTO v_proposicoes FROM parlamentar_proposicoes WHERE parlamentar_id IS NOT NULL;
    SELECT COUNT(*) INTO v_emendas FROM emendas_discricionarias WHERE parlamentar_id IS NOT NULL;
    SELECT COUNT(*) INTO v_alertas FROM parlamentar_alertas WHERE parlamentar_id IS NOT NULL;

    RAISE NOTICE '=== RESUMO MIGRATION 025 ===';
    RAISE NOTICE 'parlamentares:          % total', v_parlamentares;
    RAISE NOTICE 'parlamentares_dados:    % com parlamentar_id', v_parlamentares_dados;
    RAISE NOTICE 'votos_camara:           % com parlamentar_id', v_votos;
    RAISE NOTICE 'parlamentares_personas: % com parlamentar_id', v_personas;
    RAISE NOTICE 'parlamentar_proposicoes:% com parlamentar_id', v_proposicoes;
    RAISE NOTICE 'emendas_discricionarias:% com parlamentar_id', v_emendas;
    RAISE NOTICE 'parlamentar_alertas:    % com parlamentar_id', v_alertas;
END $$;

COMMIT;
