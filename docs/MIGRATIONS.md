# Migrations — Ordem de Execução

Aplicar na ordem abaixo. Todas usam `CREATE TABLE IF NOT EXISTS` (idempotente).

| # | Arquivo | Descrição | Pré-requisitos |
|---|---------|-----------|----------------|
| 002 | migration_002_relatorios.sql | Tabelas core: beneficiarios, parlamentares, planos_acao, emendas, etc. | schema.sql |
| 003 | migration_003_enrichment.sql | Enriquecimento: validacao_cnpj, municipios_ibge, beneficiario_ibge_map, parlamentares_dados, parlamentar_beneficiario | 002 |
| 004 | migration_004_ibge_agregados.sql | Colunas IBGE: populacao, pib, area_km2 em municipios_ibge | 003 + ibge.py |
| 005 | migration_005_unificacao.sql | Tabelas unificadas: emendas_discricionarias, v_emendas_unificadas | 002 |
| 006 | migration_006_datajud.sql | Cache DataJud: beneficiario_processos | 002 |
| 007 | migration_007_siconfi.sql | Dados financeiros: municipios_financeiro (SICONFI/Tesouro) | 003 + ibge.py |
| 008 | migration_008_enriched_views.sql | Views cruzadas enriquecidas | 003, 005 |
| 009 | migration_009_novas_fontes.sql | Compras, saúde, educação, violência + materialized views | 003, 005, 008 |
| 010 | migration_010_prefeitos.sql | Tabela prefeitos_dados + view v_prefeitos_completo | 003, 004 |
| 011 | migration_011_tse_deputados.sql | Colunas TSE em parlamentares_dados | 003 |
| 012 | migration_012_arrecadacao_impostos.sql | View v_arrecadacao_impostos | 003, 004, 007 |
| 013 | migration_013_diario_oficial.sql | Cache diário oficial | 002 |
| 014 | migration_014_vereadores.sql | Tabela vereadores_dados + views de vereadores | 003, 004 |
| 014 | migration_014_proposicoes.sql | Tabela parlamentar_proposicoes (proposições legislativas da Câmara) | 003 |
| 015 | migration_015_senadores.sql | Tabela senadores_dados + views de senadores | 002 |
| 015 | migration_015_triangulo_politico.sql | Views de inteligência política: v_triangulo_politico (Deputado→Prefeito→Vereadores por partido) | 003, 010, 014 |
| 015 | migration_015_discursos.sql | Tabela parlamentar_discursos (discursos de cada deputado no plenário/comissões via API Câmara) | 003 |
| 015 | migration_015_persona_model_metrics.sql | Colunas modelo_usado + score_qualidade em parlamentares_personas | 017 |
| 016 | migration_016_votacoes_camara.sql | Tabelas votacoes_camara (sessões de plenário/comissões) e votos_camara (votos nominais por deputado) | 003 |
| 016 | migration_016_governadores.sql | Tabela governadores_dados (TSE 2022) + view v_governadores_resumo | 002 |
| 016 | migration_016_view_emendas_parlamentar_id.sql | Adiciona parlamentar_id à view v_emendas_unificadas — JOIN exato por ID em vez de nome | 005, 022 |
| 017 | migration_017_rag_personas.sql | Tabela parlamentares_personas_v2 (personas analíticas com contexto_rag, versao_prompt, fontes_usadas) | 003 |
| 017 | migration_017_parlamentar_proposicoes_id.sql | Adiciona parlamentar_id (TransfereGov) à parlamentar_proposicoes | 014, 022 |
| 018 | migration_018_vereadores_em_exercicio.sql | Views de vereadores em exercício (frontend): v_vereadores_em_exercicio, v_vereadores_por_partido_resumo, v_vereadores_por_municipio | 014, 004 |
| 018 | migration_018_parlamentar_id_tables.sql | Adiciona parlamentar_id às tabelas restantes (JOIN exato por ID nas views/queries) | 022 |
| 019 | migration_019_fnde_repasses.sql | Tabela fnde_repasses (repasses educacionais FNDE: FUNDEB, PNAE, PNLD, PNATE por município) | 003 |
| 019 | migration_019_parlamentar_id_constraints_views.sql | UNIQUE/índices de parlamentar_beneficiario + views recriadas com JOIN por parlamentar_id | 003, 022 |
| 020 | migration_020_persona_rag_fixes.sql | Correções RAG v4: fontes_usadas TEXT→TEXT[], qualidade_ok, índices, view v_personas_audit | 017 |
| 021 | migration_021_discursos.sql | Tabela parlamentar_discursos (alternativa 015 — dep. FK deputado_id de parlamentares_dados) | 003 |
| 021 | migration_021_nome_normalizado.sql | Normalização de nomes via unaccent (colunas nome_normalizado) para JOINs robustos | 002 |
| 022 | migration_022_parlamentar_id.sql | Identificador consistente de parlamentares: ADD parlamentar_id em parlamentares/planos_acao/emendas, parse_emenda() e upsert_plano_acao() atualizados, FK emendas→parlamentares via parlamentar_id | 002 |
| 023 | migration_023_discursos_parlamentar_id.sql | Adiciona parlamentar_id em parlamentar_discursos | 015/021, 022 |
| 024 | migration_024_votos_personas_parlamentar_id.sql | Adiciona parlamentar_id em votos_camara + parlamentares_personas | 016, 017, 022 |
| 025 | migration_025_deputados_faltantes_parlamentares.sql | Insere 130 deputados faltantes na tabela parlamentares (parlamentar_id) | 002, 022 |
| 026 | migration_026_estados_financeiro.sql | Tabela estados_financeiro (SICONFI esfera estadual: DCA + RREO A03) | 003, 004 |
| 026 | migration_026_pix_sync_fix.sql | Fix upsert_plano_acao: RETURNING beneficiario_id; emendas PIX sincronizadas | 002, 022 |
| 027 | migration_027_upsert_parlamentar_resolve.sql | upsert_plano_acao resolve parlamentar_id canônico por NOME antes de gravar | 022, 026 |
| 028 | migration_028_frontend_perf.sql | Índices de performance do frontend: vereadores (uf, partido, situação), discursos (parlamentar, data), emendas discricionárias (parlamentar, ano), votações (data) | 003, 015, 021 |

## Execução

```bash
# Schema base
psql -U cognee -h 127.0.0.1 -d transferegov_db -f data/schema.sql

# Migrations na ordem
for f in $(ls data/migration_*.sql | sort); do
    echo "Aplicando $f..."
    psql -U cognee -h 127.0.0.1 -d transferegov_db -f "$f"
done
```
