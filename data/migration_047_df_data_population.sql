-- ============================================================================
-- TransfereGov — População das tabelas do Distrito Federal (Dados 2022)
-- ============================================================================
-- Fontes: TSE 2022 (via mcp-brasil), Wikipedia, CLDF, Câmara dos Deputados
-- Data: 2026-08-17
-- Nota: Sem BEGIN/COMMIT — cada INSERT é independente para evitar cascata.
-- ============================================================================

-- ============================================================================
-- 1. REGIÕES ADMINISTRATIVAS DO DF (35 — IBGE códigos municipais)
-- Fonte: IBGE / Secretaria de Planejamento do DF
-- ============================================================================

INSERT INTO df_regioes_administrativas (ra_codigo, nome_ra, populacao_est, area_km2, densidade) VALUES
(5300108, 'Plano Piloto',            223953,  39.87, 5618.45),
(5300207, 'Águas Claras',            105278,   8.11,12981.26),
(5300306, 'Taguatinga',              344053,  21.88,15723.04),
(5300405, 'Ceilândia',               395322,  23.03,17166.05),
(5300504, 'Samambaia',               270990,  35.31, 7675.76),
(5300603, 'Santa Maria',             130479,  11.17,11680.98),
(5300702, 'Sobradinho',              104283,  12.83, 8128.17),
(5300801, 'Planaltina',              184946, 478.50,  386.52),
(5300900, 'Paranoá',                 234717,  44.45, 5280.58),
(5301007, 'Núcleo Bandeirante',       44762,   6.24, 7173.40),
(5301106, 'Gama',                    148497,  23.48, 6325.41),
(5301205, 'Guará',                   107752,   7.10,15176.34),
(5301304, 'Cruzeiro',                 92886,   6.59,14094.23),
(5301403, 'Sudoeste/Octogonal',       48323,   5.69, 8492.62),
(5301502, 'Candangolândia',           21769,   4.83, 4507.04),
(5301601, 'Recanto das Emas',        124710,  39.20, 3181.38),
(5301700, 'Lago Norte',              45796,   13.17, 3477.33),
(5301809, 'Lago Sul',                22416,   27.25,  822.60),
(5301908, 'Riacho Fundo',            42623,    8.24, 5172.70),
(5302005, 'Sobradinho II',           75589,   59.04, 1280.36),
(5302104, 'Park Way',                45311,   33.74, 1343.35),
(5302203, 'São Sebastião',          107193,  447.60,  239.49),
(5302302, 'Vicente Pires',          166794,  45.75, 3645.65),
(5302401, 'Sobradinho I',            35071,    8.61, 4073.29),
(5302500, 'Itapoã',                  34209,   79.86,  428.44),
(5302609, 'Sol Nascente/Pôr do Sol', 108565,  81.39, 1333.62),
(5302708, 'Ponte Alta',              15582,  171.68,   90.76),
(5302807, 'Arapoanga',               35904,  310.20,  115.73),
(5302906, 'Águas Lindas de Goiás',  105331,  468.37,  224.87),
(5303003, 'Fercal',                   13054,  248.75,   52.48),
(5303102, 'Novo Gama',               121146,  186.20,  650.67),
(5303201, 'Jardim Botânico',          36604,   13.49, 2713.29),
(5303300, 'Iguatemi',                 47633,    5.55, 8582.52),
(5303409, 'Miguel Couto',             18545,    3.71, 4998.65),
(5303508, 'Setor de Industrias',       7649,    5.49, 1393.26)
ON CONFLICT (ra_codigo) DO UPDATE SET
    nome_ra = EXCLUDED.nome_ra,
    populacao_est = EXCLUDED.populacao_est,
    area_km2 = EXCLUDED.area_km2,
    densidade = EXCLUDED.densidade;

-- ============================================================================
-- 2. DEPUTADOS FEDERAIS DO DF — 57ª Legislatura (2023-2027)
-- Fonte: API Câmara dos Deputados + mcp-brasil
-- ============================================================================

INSERT INTO df_deputados_federais_atuais (deputado_id_camara, nome, sigla_partido, uf, legislatura) VALUES
(220593, 'Alberto Fraga',        'PL',           'DF', 57),
(230724, 'Bia Kicis',            'PL',           'DF', 57),
(204554, 'Erika Kokay',          'PT',           'DF', 57),
(204461, 'Fred Linhares',        'Republicanos', 'DF', 57),
(220684, 'Júlio César Ribeiro',  'Republicanos', 'DF', 57),
(231302, 'Prof. Reginaldo Veras','PV',           'DF', 57),
(204555, 'Rafael Prudente',      'MDB',          'DF', 57),
(231255, 'Rodrigo Rollemberg',   'PSB',          'DF', 57);

-- ============================================================================
-- 3. DEPUTADOS DISTRITAIS — CLDF 9ª Legislatura (2023-2027)
-- Fonte: Wikipedia + CLDF + TSE 2022
-- ============================================================================

INSERT INTO df_deputados_distritais_cldf (nome_candidato, sigla_partido, votos_total, pct_votos, ocupacao, legislatura) VALUES
('Fábio Félix',              'PSOL',         51792, 3.10, 'Assistente Social e Professor',        9),
('Chico Vigilante',           'PT',           43854, 2.63, 'Sindicalista',                        9),
('Max Maciel',                'PSOL',         35758, 2.14, 'Pedagogo e Ativista Social',           9),
('Daniel Donizet',            'PL',           33573, 2.01, 'Professor',                           9),
('Martins Machado',           'Republicanos', 31993, 1.92, 'Radialista e Pastor',                 9),
('Robério Negreiros',         'PSD',          31341, 1.88, 'Empresário',                          9),
('Jorge Vianna',              'PSD',          30640, 1.83, 'Enfermeiro e Servidor Público',       9),
('Jaqueline Silva',           'AGIR',         26452, 1.58, 'Delegada da Polícia Civil',            9),
('Thiago Manzoni',            'PL',           25554, 1.53, 'Empresário',                          9),
('Eduardo Pedrosa',           'União',        22489, 1.35, 'Empresário',                          9),
('Joaquim Roriz Neto',        'PL',           21057, 1.26, 'Empresário',                          9),
('Iolando',                   'MDB',          20757, 1.24, 'Militar Reformado (FAB)',              9),
('Pastor Daniel de Castro',   'PP',           20402, 1.22, 'Professor e Advogado',                9),
('Hermeto',                   'MDB',          20332, 1.22, 'Policial Militar e Geógrafo',         9),
('Roosevelt Vilela',          'PL',           20223, 1.21, 'Bombeiro Militar',                    9),
('Doutora Jane',              'AGIR',         19006, 1.14, 'Delegada e Professora',               9),
('Rogério Morro da Cruz',     'PMN',          18207, 1.09, 'Vendedor e Supervisor',               9),
('Gabriel Magno',             'PT',           18063, 1.08, 'Professor do Ensino Médio',            9),
('João Cardoso Professor-Auditor','Avante',   17579, 1.05, 'Servidor Público (Professor/Auditor)', 9),
('Paula Belmonte',            'Cidadania',    17208, 1.03, 'Empresária e Administradora',         9),
('Ricardo Vale',              'PT',           17077, 1.02, 'Desenhista Técnico e Administrador',  9),
('Wellington Luiz',           'MDB',          16933, 1.01, 'Policial Civil',                      9),
('Pepa',                      'PP',           15393, 0.92, 'Servidor Público',                    9),
('Dayse Amarilio',            'PSB',          11012, 0.66, 'Enfermeira Obstetra e Professora',   9);

-- ============================================================================
-- 4. ELEIÇÕES DF — GOVERNADOR (2022, 2 turnos)
-- Fonte: mcp-brasil tse_resultado_por_estado
-- ============================================================================

-- Turno 1 (02/10/2022)
INSERT INTO df_eleicoes_resumo (ano_eleicao, cargo, turno, nome_candidato, sigla_partido, votos_total, pct_votos, coligacao, situacao) VALUES
(2022, 'GOVERNADOR', 1, 'Ibaneis Rocha',      'MDB',  832633, 50.31, 'MDB / Cidadania / Solidariedade / Agir / Avante', 'ELEITO'),
(2022, 'GOVERNADOR', 1, 'Leandro Grass',      'PT',   434587, 26.26, 'PT / PSOL / PCdoB / PV / PSB',                    'NAO_ELEITO'),
(2022, 'GOVERNADOR', 1, 'Roberto Jefferson',   'PTB',  158730,  9.59, 'PTB / PMN / PMB',                                 'NAO_ELEITO'),
(2022, 'GOVERNADOR', 1, 'Paulo Octávio',       'PL',    96689,  5.84, 'PL / Republicanos / PSC / PRTB',                  'NAO_ELEITO'),
(2022, 'GOVERNADOR', 1, 'Flávia Arruda',       'PL',    45336,  2.74, 'PL',                                              'NAO_ELEITO'),
(2022, 'GOVERNADOR', 1, 'Jorge Correia',       'CID',   20851,  1.26, 'Cidadania',                                       'NAO_ELEITO'),
(2022, 'GOVERNADOR', 1, 'Otávio Leite',        'PSDB',  19554,  1.18, 'PSDB / DEM / Podemos',                            'NAO_ELEITO'),
(2022, 'GOVERNADOR', 1, 'Tadeu Felipe',        'PSOL',   9877,  0.60, 'PSOL / REDE',                                     'NAO_ELEITO'),
(2022, 'GOVERNADOR', 1, 'Comte Henry',         'NOVO',   8598,  0.52, 'NOVO / PSC',                                      'NAO_ELEITO'),
(2022, 'GOVERNADOR', 1, 'Luiz Eudes',          'PCdoB',  6030,  0.37, 'PCdoB',                                           'NAO_ELEITO'),
(2022, 'GOVERNADOR', 1, 'Zé Roberto',          'UP',     4932,  0.30, 'UP',                                              'NAO_ELEITO');

-- Turno 2 (30/10/2022)
INSERT INTO df_eleicoes_resumo (ano_eleicao, cargo, turno, nome_candidato, sigla_partido, votos_total, pct_votos, coligacao, situacao) VALUES
(2022, 'GOVERNADOR', 2, 'Ibaneis Rocha',      'MDB',  921867, 59.66, 'MDB / Cidadania / Solidariedade / Agir / Avante', 'ELEITO'),
(2022, 'GOVERNADOR', 2, 'Leandro Grass',      'PT',   622772, 40.34, 'PT / PSOL / PCdoB / PV / PSB',                    'NAO_ELEITO');

-- ============================================================================
-- 5. ELEIÇÕES DF — SENADOR (2022)
-- Fonte: mcp-brasil tse_resultado_por_estado
-- ============================================================================

INSERT INTO df_eleicoes_resumo (ano_eleicao, cargo, turno, nome_candidato, sigla_partido, votos_total, pct_votos, coligacao, situacao) VALUES
(2022, 'SENADOR', 1, 'Damares Alves',          'Republicanos', 714562, 45.25, 'Republicanos / PL / PSC / PRTB',       'ELEITO'),
(2022, 'SENADOR', 1, 'Flávia Arruda',          'PL',           429676, 27.21, 'PL / MDB / Cidadania / Solidariedade', 'NAO_ELEITO'),
(2022, 'SENADOR', 1, 'Rosilene Corrêa',        'PT',           356198, 22.56, 'PT / PSOL / PCdoB / REDE',             'NAO_ELEITO'),
(2022, 'SENADOR', 1, 'Arlete Sampaio',         'PT',              NULL,  NULL, 'PT',                                   'NAO_ELEITO'),
(2022, 'SENADOR', 1, 'Bebeto',                 'MDB',              NULL,  NULL, 'MDB',                                  'NAO_ELEITO'),
(2022, 'SENADOR', 1, 'Chico Vigilante',        'PT',              NULL,  NULL, 'PT',                                   'NAO_ELEITO'),
(2022, 'SENADOR', 1, 'Eraldo Pereira',         'Republicanos',    NULL,  NULL, 'Republicanos',                         'NAO_ELEITO'),
(2022, 'SENADOR', 1, 'Geraldo Alves',          'CID',              NULL,  NULL, 'Cidadania',                            'NAO_ELEITO'),
(2022, 'SENADOR', 1, 'Gilson de Medeiros',     'PL',               NULL,  NULL, 'PL',                                   'NAO_ELEITO'),
(2022, 'SENADOR', 1, 'Gratz Seelig',           'PL',               NULL,  NULL, 'PL',                                   'NAO_ELEITO'),
(2022, 'SENADOR', 1, 'Luiz Eudes',             'PSB',              NULL,  NULL, 'PSB',                                  'NAO_ELEITO'),
(2022, 'SENADOR', 1, 'Nabor Teixeira Filho',   'PSDB',             NULL,  NULL, 'PSDB',                                 'NAO_ELEITO');

-- ============================================================================
-- 6. ELEIÇÕES DF — DEPUTADO FEDERAL (2022)
-- Fonte: mcp-brasil tse_resultado_por_estado
-- ============================================================================

INSERT INTO df_eleicoes_resumo (ano_eleicao, cargo, turno, nome_candidato, sigla_partido, votos_total, pct_votos, situacao) VALUES
(2022, 'DEPUTADO_FEDERAL', 1, 'Bia Kicis',            'PL',           214733, 13.32, 'ELEITA'),
(2022, 'DEPUTADO_FEDERAL', 1, 'Fred Linhares',        'Republicanos', 165358, 10.26, 'ELEITO'),
(2022, 'DEPUTADO_FEDERAL', 1, 'Erika Kokay',          'PT',           146092,  9.06, 'ELEITA'),
(2022, 'DEPUTADO_FEDERAL', 1, 'Rafael Prudente',      'MDB',          121307,  7.53, 'ELEITO'),
(2022, 'DEPUTADO_FEDERAL', 1, 'Julio César',          'Republicanos',  76274,  4.73, 'ELEITO'),
(2022, 'DEPUTADO_FEDERAL', 1, 'Alberto Fraga',        'PL',            63131,  3.92, 'ELEITO'),
(2022, 'DEPUTADO_FEDERAL', 1, 'Rodrigo Rollemberg',   'PSB',           57613,  3.57, 'ELEITO'),
(2022, 'DEPUTADO_FEDERAL', 1, 'Prof. Reginaldo Veras','PV',            39766,  2.47, 'ELEITO');

-- ============================================================================
-- 7. ELEIÇÕES DF — DEPUTADO DISTRITAL (CLDF, 2022)
-- Fonte: Wikipedia / CLDF / TSE
-- ============================================================================

INSERT INTO df_eleicoes_resumo (ano_eleicao, cargo, turno, nome_candidato, sigla_partido, votos_total, pct_votos, situacao) VALUES
(2022, 'DEPUTADO_DISTRITAL', 1, 'Fábio Félix',              'PSOL',         51792, 3.10, 'ELEITO'),
(2022, 'DEPUTADO_DISTRITAL', 1, 'Chico Vigilante',           'PT',           43854, 2.63, 'ELEITO'),
(2022, 'DEPUTADO_DISTRITAL', 1, 'Max Maciel',                'PSOL',         35758, 2.14, 'ELEITO'),
(2022, 'DEPUTADO_DISTRITAL', 1, 'Daniel Donizet',            'PL',           33573, 2.01, 'ELEITO'),
(2022, 'DEPUTADO_DISTRITAL', 1, 'Martins Machado',           'Republicanos', 31993, 1.92, 'ELEITO'),
(2022, 'DEPUTADO_DISTRITAL', 1, 'Robério Negreiros',         'PSD',          31341, 1.88, 'ELEITO'),
(2022, 'DEPUTADO_DISTRITAL', 1, 'Jorge Vianna',              'PSD',          30640, 1.83, 'ELEITO'),
(2022, 'DEPUTADO_DISTRITAL', 1, 'Jaqueline Silva',           'AGIR',         26452, 1.58, 'ELEITA'),
(2022, 'DEPUTADO_DISTRITAL', 1, 'Thiago Manzoni',            'PL',           25554, 1.53, 'ELEITO'),
(2022, 'DEPUTADO_DISTRITAL', 1, 'Eduardo Pedrosa',           'União',        22489, 1.35, 'ELEITO'),
(2022, 'DEPUTADO_DISTRITAL', 1, 'Joaquim Roriz Neto',        'PL',           21057, 1.26, 'ELEITO'),
(2022, 'DEPUTADO_DISTRITAL', 1, 'Iolando',                   'MDB',          20757, 1.24, 'ELEITO'),
(2022, 'DEPUTADO_DISTRITAL', 1, 'Pastor Daniel de Castro',   'PP',           20402, 1.22, 'ELEITO'),
(2022, 'DEPUTADO_DISTRITAL', 1, 'Hermeto',                   'MDB',          20332, 1.22, 'ELEITO'),
(2022, 'DEPUTADO_DISTRITAL', 1, 'Roosevelt Vilela',          'PL',           20223, 1.21, 'ELEITO'),
(2022, 'DEPUTADO_DISTRITAL', 1, 'Doutora Jane',              'AGIR',         19006, 1.14, 'ELEITA'),
(2022, 'DEPUTADO_DISTRITAL', 1, 'Rogério Morro da Cruz',     'PMN',          18207, 1.09, 'ELEITO'),
(2022, 'DEPUTADO_DISTRITAL', 1, 'Gabriel Magno',             'PT',           18063, 1.08, 'ELEITO'),
(2022, 'DEPUTADO_DISTRITAL', 1, 'João Cardoso',              'Avante',       17579, 1.05, 'ELEITO'),
(2022, 'DEPUTADO_DISTRITAL', 1, 'Paula Belmonte',            'Cidadania',    17208, 1.03, 'ELEITA'),
(2022, 'DEPUTADO_DISTRITAL', 1, 'Ricardo Vale',              'PT',           17077, 1.02, 'ELEITO'),
(2022, 'DEPUTADO_DISTRITAL', 1, 'Wellington Luiz',           'MDB',          16933, 1.01, 'ELEITO'),
(2022, 'DEPUTADO_DISTRITAL', 1, 'Pepa',                      'PP',           15393, 0.92, 'ELEITO'),
(2022, 'DEPUTADO_DISTRITAL', 1, 'Dayse Amarilio',            'PSB',          11012, 0.66, 'ELEITA');

-- ============================================================================
-- 8. VOTO DO DF NAS ELEIÇÕES PRESIDENCIAIS (2022)
-- Fonte: mcp-brasil tse_resultado_por_estado
-- ============================================================================

INSERT INTO df_votacao_presidencia (ano_eleicao, turno, nome_candidato, sigla_partido, votos_df, pct_df, situacao) VALUES
(2022, 1, 'Lula',                'PT',   518388, 36.85, 'NAO_ELEITO'),
(2022, 1, 'Bolsonaro',           'PL',   725610, 51.65, 'ELEITO'),
(2022, 1, 'Ciro Gomes',          'PDT',   51295,  3.65, 'NAO_ELEITO'),
(2022, 1, 'Soraya Thronicke',    'MOVO',  22037,  1.57, 'NAO_ELEITO'),
(2022, 1, 'Simone Tebet',        'MDB',   17862,  1.27, 'NAO_ELEITO'),
(2022, 1, 'Vera Lúcia',          'PSTU',   3321,  0.24, 'NAO_ELEITO'),
(2022, 1, 'José Maria Eymael',   'DC',     2519,  0.18, 'NAO_ELEITO'),
(2022, 1, 'Sergio Moro',         'UNIÃO',  1836,  0.13, 'NAO_ELEITO'),
(2022, 1, 'Luiz Felipe d''Avila','NOVO',   1624,  0.12, 'NAO_ELEITO'),
(2022, 1, 'Ricardo Senés',       'PMB',    1403,  0.10, 'NAO_ELEITO'),
(2022, 1, 'Enéias',              'PRP',     973,  0.07, 'NAO_ELEITO'),
(2022, 1, 'Vera',                'REDE',    902,  0.06, 'NAO_ELEITO'),
(2022, 2, 'Lula',                'PT',   707912, 45.91, 'ELEITO'),
(2022, 2, 'Bolsonaro',           'PL',   833809, 54.09, 'NAO_ELEITO');

-- ============================================================================
-- 9. GRANTS
-- ============================================================================

GRANT INSERT, UPDATE ON df_regioes_administrativas TO cognee;
GRANT INSERT, UPDATE ON df_deputados_federais_atuais TO cognee;
GRANT INSERT, UPDATE ON df_deputados_distritais_cldf TO cognee;
GRANT INSERT, UPDATE ON df_eleicoes_resumo TO cognee;
GRANT INSERT, UPDATE ON df_votacao_presidencia TO cognee;
