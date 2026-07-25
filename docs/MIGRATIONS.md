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
