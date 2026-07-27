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
| 015 | migration_015_senadores.sql | Tabela senadores_dados + views de senadores | 002 |
| 018 | migration_018_vereadores_em_exercicio.sql | Views de vereadores em exercício (frontend): v_vereadores_em_exercicio, v_vereadores_por_partido_resumo, v_vereadores_por_municipio | 014, 004 |

## Execução

```bash
# Schema base
psql -U cognee -h 127.0.0.1 -d transferegov_db -f data/schema.sql

# Migrations na ordem
for f in data/migration_00*.sql; do
    echo "Aplicando $f..."
    psql -U cognee -h 127.0.0.1 -d transferegov_db -f "$f"
done
```
