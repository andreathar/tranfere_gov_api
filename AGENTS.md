# AGENTS.md — TransfereGov API

Projeto Python para extração, validação, enriquecimento e análise de Planos de Ação do
sistema Transferegov (Transferências Especiais / Emendas Pix) do Governo Federal.

**Pipeline**: Extração → Validação (Pydantic) → PostgreSQL (upsert) → Enriquecimento (IBGE, BrasilAPI, Câmara, SICONFI) → Dashboard 38 gráficos + API

---

## Comandos

```bash
source .venv/bin/activate

# Extração
./run.sh discover                          # listar objetos disponíveis
./run.sh cemiterios --db                   # extrair objeto 301 + banco
./run.sh negados --csv --db               # negados/perdidos + CSV + banco
./run.sh all --db                          # todos os objetos + banco
python3 src/transferegov_extract.py --objeto all --ano 2026 --programa 25 --situacao-api IMPEDIDO --db --csv
# Flags: --db --csv --programa N --uf UF --situacao-api S -v

# Importação
./run.sh import                            # importa JSONs de output/json/

# Relatórios
./run.sh report resumo|estado|negados|top\ 10|municipio\ SP|emenda
./run.sh report sql "SELECT ..."

# Enriquecimento (pós-extração)
python3 -m src.enrichers.validacao [--dry-run] [--limit N]
python3 -m src.enrichers.ibge [--dry-run] [--uf UF]
python3 -m src.enrichers.mapear_municipios [--dry-run]
python3 -m src.enrichers.siconfi [--dry-run] [--uf UF] [--limit N] [--ano ANO] [--rreo]
python3 -m src.enrichers.camara [--dry-run] [--limit N]
python3 -m src.enrichers.tse_prefeitos [--dry-run] [--uf UF] [--ano ANO]
python3 -m src.enrichers.tse_vereadors [--dry-run] [--uf UF] [--ano ANO]
python3 -m src.enrichers.senado [--dry-run] [--limit N]
python3 -m src.enrichers.pipeline --fase all [--dry-run] [--limit N]

# Dashboard + MCP
python3 src/dash_app.py                    # http://localhost:8050 + http://localhost:8050/_mcp
python3 src/verify_graphs.py              # auditoria dos 38 gráficos

# API
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000

# Followup
python3 src/deputado_followup.py "AFONSO FLORENCE"    # por nome
python3 src/deputado_followup.py --ranking             # ranking deputados
python3 src/prefeito_followup.py "Amapá"               # por município
python3 src/prefeito_followup.py --ranking             # ranking prefeituras

# Redator oficial
./run.sh redator nota-tecnica --parlamentar "AFONSO FLORENCE" --ano 2026
./run.sh redator oficio --dest "Governador" --cargo "Governador" --assunto "Relatório" --corpo "..."
./run.sh redator parecer --processo "001/2026" --consulta "Análise"
./run.sh redator despacho --assunto "Encaminhamento" --texto "..."
./run.sh redator validar --arquivo "docs/nota.txt" --tipo nota_tecnica
./run.sh redator listar-tipos

# Banco
psql -U cognee -h 127.0.0.1 -d transferegov_db
```

---

## Convenções

- **Language**: PT-BR (comentários, logs, CLI)
- **Style**: ruff (line-length 99, target py311) / mypy strict / pytest
- **Config**: `config/settings.py` — importar via `from config.settings import X`, NUNCA hardcodar paths
- **Paths**: usar `config.settings.OUTPUT_*` para saídas
- **DB**: `upsert_plano_acao()` para import idempotente
- **Commit**: mensagens PT-BR, sem emoji

---

## Estrutura

```
src/
├── transferegov_extract.py   CLI principal (extração + DB)
├── db_utils.py               get_connection(), query_df() centralizados
├── formatters.py             fmt_brl(), fmt_num(), fmt_pct()
├── schemas.py                Pydantic schemas
├── dash_app.py               Dash 4.3+ Web + MCP Hub (porta 8050)
├── graphs/                   Pacote gráficos (12 módulos, 38 gráficos)
│   ├── registry.py             @register_chart decorator + CHART_REGISTRY
│   ├── theme.py                Theme tokens + TODAS_UFS + CORES_SITUACAO
│   ├── parlamentar.py          2 charts | socioeconomico.py 3 charts
│   ├── fiscal.py 2 | siconfi.py 10 | arrecadacao.py 3 | geoespacial.py 3
│   ├── impacto_social.py 2 | analitico.py 2 | hierarquico.py 3
│   ├── prefeitos.py 2 | economico.py 5
├── graph_factory.py          Shim backward-compat → src.graphs
├── graph_tools.py            MCP Tools (@mcp_enabled)
├── verify_graphs.py          Suíte auditoria gráficos
├── deputado_followup.py      CLI followup deputado
├── prefeito_followup.py      CLI followup prefeito
├── redator_transferegov.py   Redator documentos oficiais
├── api/                      FastAPI (ver src/api/AGENTS.md)
│   ├── app.py                  App principal
│   ├── routes/                 /api/v1/deputados/*, analytics, auditoria
│   ├── services/               db, camara, mcp, analytics
│   └── static/                 Frontend SPA
└── enrichers/                Pipeline enriquecimento (ver src/enrichers/AGENTS.md)
    ├── pipeline.py              Orquestrador fases 1-3
    ├── validacao.py 1a | ibge.py 1b | ibge_agregados.py 1d
    ├── siconfi.py 1e (DCA+RREO) | camara.py 2
    ├── mapear_municipios.py 1c | compras.py | saude_educacao.py
    ├── datajud.py | completar_deputados.py | discricionarias_sync.py
    ├── tse_prefeitos.py 7a | tse_vereadors.py 7b | tse_deputados.py
config/settings.py            API, DB, paths, ENRICH_*
data/                         schema.sql, migrations 002-012, swagger.yaml
scripts/                      db_inspect.sh, run_siconfi_batch.sh
docs/                         MIGRATIONS.md, manual.txt, plans/
output/                       Gitignored (xlsx, csv, json, logs)
```

---

## API TransfereGov

- **Endpoint**: `GET https://especiais.transferegov.sistema.gov.br/maisbrasil-transferencia-especial-backend/api/public/plano-acao/listagem`
- **Auth**: NENHUMA (público) | **IP**: pode bloquear fora do Brasil | **Timeout**: 60s, 3 retries
- **Pagination**: `pageSize=100`, `pageNumber=1..N`, break when empty
- **Response key**: `listaPlanosAcao` (NÃO `data`/`content`/`items`)

### Parâmetros de Query

| Param | Exemplo | Param | Exemplo |
|-------|---------|-------|---------|
| `objetoExecucao` | `301` | `programaId` | `25` (Transf. Especiais) |
| `objetoExecucaoAno` | `2026` | `planoAcaoSituacao` | `IMPEDIDO` |
| `uf` | `SP`, `AL` | `parlamentar` / `emenda` | `4291` / `11228` |

### Situações API

`AGUARDANDO_CIENCIA` · `PLANO_TRABALHO_EM_ELABORACAO` · `CIENTE` · `IMPEDIDO` · `IMPEDIDO_REJEICAO_PLANO_TRABALHO` · `APROVADO` · `REPROVADO` · `CANCELADO` · `EM_EXECUCAO` · `CONCLUIDO` · `NAO_CUMPROU`

---

## PostgreSQL

**Banco**: `transferegov_db` · `127.0.0.1:5432` · `cognee`/`cognee`

### Schema Core

**Tabelas dimensão**: `objetos`, `programas`, `beneficiarios`, `parlamentares`, `emendas`, `politicas_publicas`, `situacoes_map`
**Tabela fato**: `planos_acao` (22 colunas + `emenda_codigo`, `parlamentar_nome`, `emenda_ano`)
**Controle**: `extract_log`

### Views

| View | Descrição |
|------|-----------|
| `v_planos_completo` | Join completo com parlamentar + situação |
| `v_negados` | IMPEDIDO, REPROVADO, CANCELADO, NAO_CUMPROU |
| `v_resumo_por_estado` | Por UF + situação |
| `v_resumo_por_objeto` | Por objeto + total parlamentares |
| `v_resumo_por_parlamentar` | Totais por parlamentar/ano |
| `v_arrecadacao_impostos` | Arrecadação por município (IPTU/ISS/ICMS/FPM) |
| `v_arrecadacao_por_estado` | Arrecadação agregada por estado |

**Funções**: `upsert_plano_acao()` (import idempotente), `parse_emenda()` (extrai emenda/parlamentar/ano)

### Tabelas Enriquecimento

| Tabela | Fonte | Descrição |
|--------|-------|-----------|
| `validacao_cnpj` | BrasilAPI | Validação CNPJ (razão social, situação, porte) |
| `municipios_ibge` | IBGE API | Municípios (código, nome, UF, região, pop, PIB) |
| `beneficiario_ibge_map` | Fuzzy match | Liga beneficiários a códigos IBGE |
| `municipios_financeiro` | SICONFI (DCA+RREO) | Dados financeiros + 15 colunas arrecadação |
| `parlamentares_dados` | Câmara | Perfil completo deputados |
| `parlamentar_beneficiario` | SQL JOIN | Agregação parlamentar×município×emenda |
| `prefeitos_dados` | TSE (DuckDB) | Prefeitos eleitos (2020/2024) |
| `vereadores_dados` | TSE (DuckDB) | Candidatos a vereador (2020/2024) |
| `senadores_dados` | Senado API | Perfil completo senadores em exercício |

Schema completo: `data/schema.sql`, migrations: `data/migration_002-014*.sql` (ver `docs/MIGRATIONS.md`)

---

## Pipeline Enriquecimento

| Fase | Script | Fonte | Destino |
|------|--------|-------|---------|
| 1a | `validacao.py` | BrasilAPI (CNPJ) | `validacao_cnpj` |
| 1b | `ibge.py` | IBGE (localidades) | `municipios_ibge` |
| 1c | `mapear_municipios.py` | Fuzzy match | `beneficiario_ibge_map` |
| 1d | `ibge_agregados.py` | IBGE (agregados) | `municipios_ibge` (pop, PIB, área) |
| 1e | `siconfi.py` | SICONFI (DCA + RREO A03) | `municipios_financeiro` |
| 2 | `camara.py` | Câmara Deputados | `parlamentares_dados` |
| 3 | `pipeline.py` | SQL JOIN | `parlamentar_beneficiario` |
| 7a | `tse_prefeitos.py` | TSE (DuckDB) | `prefeitos_dados` |
| 7b | `tse_vereadors.py` | TSE (DuckDB) | `vereadores_dados` |
| 8 | `senado.py` | Senado API REST | `senadores_dados` |

Detalhes completos: `src/enrichers/AGENTS.md`

---

## Dashboard + MCP

- **URL**: `http://localhost:8050` | **MCP**: `http://localhost:8050/_mcp`
- **Pré-renderização**: `dcc.Graph(figure=safe_build_chart(...))` no layout inicial
- **Anti-falha**: `safe_build_chart()` em `src/dash_app.py:34` — envolve com try/except, retorna card informativo em caso de erro
- **Novos gráficos**: criar módulo em `src/graphs/` com `@register_chart` — import automático via `__init__.py`
- **MCP Tools** (`src/graph_tools.py`): `list_registered_charts()`, `inspect_chart_health()`, `get_chart_data_summary()`, `register_custom_graph()`

---

## Web App (FastAPI)

`src/api/` — Painel de Inteligência Parlamentar

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/deputados/search?q=` | Busca (DB + API Câmara) |
| GET | `/{id}/perfil` | Perfil deputado |
| GET | `/{id}/emendas` | Emendas do deputado |
| GET | `/{id}/emendas/resumo` | Resumo agregado |
| GET | `/{id}/despesas?ano=` | Despesas CEAP |
| GET | `/{id}/comissoes` | Comissões |
| GET | `/{id}/votacoes` | Últimas votações |
| GET | `/{id}/proposicoes` | Proposições legislativas |

Fallback: busca local → enriquece API Câmara → degrada graceful. Docs: `/docs` (Swagger), `/redoc`.

---

## Redator Oficial

Gera documentos seguindo Manual de Redação da Presidência 3ª edição. Tipos: `oficio`, `nota_tecnica`, `parecer`, `despacho`, `portaria`, `ata`.

- **Data por extenso**: `"Brasília, 25 de julho de 2026."`
- **Pronomes**: 27 entradas em 4 tiers (Excelentíssimo → Vossa Magnificência)
- **Fechos**: APENAS "Respeitosamente," (superior) / "Atenciosamente," (igual)
- **Legado**: memorando/aviso → convertido automaticamente para OFÍCIO

---

## Pitfalls

1. **Response key**: `listaPlanosAcao` (não `data`/`content`/`items`)
2. `planoTrabalhoSituacao` pode ser `None`
3. `total` no response = total real — comparar com acumulado
4. Arrow backend: `.fillna("").astype(str).str.len()` (não `.map(len)`)
5. Valores monetários: `pd.to_numeric` antes de exportar
6. IP pode ser bloqueado fora do Brasil (TCP timeout)
7. `--db` é idempotente (upsert) — seguro rodar múltiplas vezes
8. Cache TTL: `output/.http_cache/` — limpar com `cache_clear()`
9. Config centralizada: **NUNCA** hardcodar URLs/paths
10. Módulos compartilhados: `src/db_utils.py` + `src/formatters.py` — NÃO redefinir
11. `IMPEDIDO` = Restrição Técnica | `IMPEDIDO_REJEICAO_PLANO_TRABALHO` = Rejeição
12. Novos gráficos: `@register_chart` em módulo `src/graphs/`, auto-import via `__init__.py`
13. Connection pooling: `psycopg2.pool.ThreadedConnectionPool` (min=2, max=10)
14. RREO A03 (`--rreo`): usa `nr_periodo=6` (consolidação anual), parser normaliza acentos

---

## Referência

- `references/mcp-brasil/` — MCP server gov.br (533 tools, 70 features)
- `docs/MIGRATIONS.md` — Ordem correta das migrations (002-012)
- `data/schema.sql` — Schema completo do banco
