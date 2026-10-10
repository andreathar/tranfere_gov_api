-- ============================================================================
-- TransfereGov — Correção de df_regioes_administrativas (35 RAs oficiais)
-- ============================================================================
-- Contexto: a migration_047 populou 35 linhas, mas 6 delas não são RAs oficiais
-- do DF (municípios de Goiás / entradas duplicadas) e faltavam 6 RAs oficiais
-- reais. Esta migration corrige a tabela para casar 1:1 com a camada oficial
-- GDF/IBRAM 2025 "Territorio/Regioes_Administrativas_DF_2025" (35 RAs, usada
-- no CARTO DW — ver docs/CARTO_INTEGRATION.md seção 9).
-- Data: 2026-08-21
-- Sem BEGIN/COMMIT — cada statement é independente.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Remove linhas que NÃO são RAs oficiais do DF ou são duplicatas.
--    - Águas Lindas de Goiás, Novo Gama, Iguatemi, Miguel Couto: municípios/
--      bairros de Goiás (RIDE), não são Regiões Administrativas do DF.
--    - Ponte Alta: não existe como RA independente na camada oficial 2025
--      (bairro dentro de Planaltina/Recanto das Emas).
--    - Sobradinho I: duplicata de "Sobradinho" (RA-VI); nunca existiu como RA
--      separada na camada oficial, apenas "Sobradinho" e "Sobradinho II".
--    Verificado sem FKs em beneficiario_ibge_map, municipios_ibge,
--    cldf_deputado_ra_impacto, cldf_ra_emendas_resumo antes da remoção.
-- ----------------------------------------------------------------------------
DELETE FROM df_regioes_administrativas
WHERE ra_codigo IN (5302906, 5303102, 5303300, 5303409, 5302708, 5302401);

-- ----------------------------------------------------------------------------
-- 2. Insere as 6 RAs oficiais que faltavam.
--    População: Censo 2022 IBGE, via IPEDF/Codeplan (informe demográfico) e
--    Wikipédia (tabela cruzada com Correio Braziliense, 21/03/2024).
--    Área/latitude/longitude: calculados a partir do polígono oficial GDF/
--    IBRAM 2025 já publicado no CARTO DW (ST_AREA/ST_CENTROID), mais preciso
--    que estimativas de terceiros — validado contra Wikipédia para Varjão
--    (1,63 km² calculado vs 1,650 km² publicado — diferença < 1%).
--    Água Quente: RA institucionalizada após o Censo 2022; população estava
--    contabilizada dentro de Recanto das Emas na época — populacao_est fica
--    NULL até uma fonte oficial pós-2022 (ex.: PDAD-A 2024/Codeplan) publicar
--    o valor desagregado.
-- ----------------------------------------------------------------------------
INSERT INTO df_regioes_administrativas
    (ra_codigo, nome_ra, populacao_est, area_km2, densidade, latitude, longitude)
VALUES
    (5303600, 'Brazlândia',      55561, 470.90,  118.00, -15.626243, -48.135054),
    (5303601, 'Arniqueira',      42320,  13.38, 3163.53, -15.861720, -48.011589),
    (5303602, 'SCIA',            36042,   7.40, 4870.54, -15.777561, -47.992176),
    (5303603, 'Riacho Fundo II', 65658,  38.53, 1704.28, -15.920648, -48.025715),
    (5303604, 'Varjão',           8609,   1.63, 5281.60, -15.709629, -47.879596),
    (5303605, 'Água Quente',      NULL,   9.52,    NULL, -15.944188, -48.233100);

COMMENT ON TABLE df_regioes_administrativas IS
    'Regiões Administrativas do DF (35, oficiais, camada GDF/IBRAM 2025). '
    'População: Censo 2022 IBGE/Codeplan onde disponível (Água Quente NULL — '
    'RA institucionalizada após o Censo). Corrigida via migration_052 '
    '(remove não-RAs de GO e duplicatas; adiciona 6 RAs faltantes).';
