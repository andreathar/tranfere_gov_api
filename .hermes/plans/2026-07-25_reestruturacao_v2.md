# Plano de Reestruturação — tranfere_gov_api (v2)

**Data:** 2026-07-25
**Objetivo:** Eliminar duplicação massiva, corrigir nomenclatura, reorganizar diretórios,
              padronizar código compartilhado, e modernizar a estrutura do projeto.

---

## Auditoria Completa

### Contagens Gerais

| Categoria | Qtd | LOC |
|-----------|-----|-----|
| Scripts Python ativos (src/) | 28 | 10.200+ |
| Dashboard standalone (HTML) | 5 | 4.415 |
| Enrichers | 14 | 1.800+ |
| API routes/services | 9 | ~800 |
| Testes | 5 | ~1.000 |
| Shell scripts (fora run.sh) | 4 | ~300 |
| Migrations SQL | 8 | 38.000+ |
| Docs/planos | 7 | ~2.670 |
| Arquivos órfãos | 5+ | — |

---

### Problemas Críticos

#### 1. DUPLAÇÃO MASSIVA DE `get_connection()` — 14 ocorrências

```python
# Mesmo bloco copy-paste em 14 arquivos:
def get_connection():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASS,
    )
```

| Arquivo | Linha |
|---------|-------|
| src/dashboard.py | 45 |
| src/dashboard_deputados.py | 72 |
| src/dashboard_emendas.py | 80 |
| src/dashboard_cross_analysis.py | 86 |
| src/dashboard_cross_fiscal.py | 63 |
| src/graph_factory.py | 62 |
| src/deputado_followup.py | 25 |
| src/enrichers/compras.py | 30 |
| src/enrichers/camara.py | 26 |
| src/enrichers/validacao.py | 26 |
| src/enrichers/saude_educacao.py | 51 |
| src/enrichers/ibge_agregados.py | 60 |
| src/enrichers/siconfi.py | 93 |
| src/enrichers/ibge.py | 17 |

#### 2. DUPLAÇÃO MASSIVA DE `fmt_brl()` / `fmt_num()` / `fmt_pct()` — 18 ocorrências

| Função | Arquivos que a repetem |
|--------|----------------------|
| `fmt_brl()` | 7 arquivos (cada um redefine) |
| `fmt_num()` | 6 arquivos |
| `fmt_pct()` | 4 arquivos |

Variantes: `format_brl()` (2 arquivos), `fmt_brl()` (5 arquivos) — nomes diferentes, mesma lógica.

#### 3. MIGRATION NUMBERING COM COLLISIONS

```
migration_003_datajud.sql       ← qual é o "3" correto?
migration_003_enrichment.sql    ← colide com datajud
migration_003_ibge_agregados.sql ← colide com datajud
migration_003_unificacao.sql    ← colide com datajud
migration_004_enriched_views.sql ← colide com siconfi
migration_004_siconfi.sql       ← colide com enriched_views
```

4 arquivos começam com `003_`, 2 com `004_`. Sem sequência lógica.

#### 4. DASHBOARD FRAGMENTADO — 5 arquivos, 4415 LOC duplicadas

| Arquivo | LOC | Tipo |
|---------|-----|------|
| dashboard.py | 483 | Standalone HTML |
| dashboard_deputados.py | 1.277 | Standalone HTML |
| dashboard_emendas.py | 957 | Standalone HTML |
| dashboard_cross_analysis.py | 955 | Standalone HTML |
| dashboard_cross_fiscal.py | 743 | Standalone HTML |

Todos compartilham: `get_connection()`, `query_df()`, `fmt_brl/num/pct()`, `estilo_fig()`.

**Existe também `dash_app.py`** (Dash 4.3+ interativo) que já é o dashboard moderno.
Os 5 standalone HTML são **DEPRECATED** mas ainda presentes.

#### 5. MÓDULOS GRÁFICOS COMPETIDORES

| Módulo | LOC | Descrição |
|--------|-----|-----------|
| graph_factory.py | 1.811 | Registro central CHART_REGISTRY + 27 gráficos |
| graph_generator.py | 314 | Gerador modular alternativo (4 gráficos) |

`graph_generator.py` é um protótipo antigo superseded por `graph_factory.py`.

#### 6. ENRICHERS COM Sobreposição

| Script | Fonte | Sobreposição |
|--------|-------|-------------|
| compras.py | PNCP/Compras.gov.br (dados abertos) | Mesma API |
| tcu_compras.py | mcp-brasil (Compras.gov.br via TCU) | Mesma API, via proxy diferente |

`saude_educacao.py` — saudável, mas não referenciado no pipeline.py.

---

### Problemas Moderados

#### 7. GITIGNORE INCOMPLETO

Faltam no `.gitignore`:
- `.mypy_cache/`
- `.ruff_cache/`
- `.pytest_cache/`
- `node_modules/`
- `transferegov_api.egg-info/`
- `.codegraph/`
- `.omo/`
- `.playwright-mcp/`
- `*.egg-info/`

`google-cloud-sdk/` está listado mas **ainda existe no repo** (provavelmente commitado antes do .gitignore).

#### 8. SHELL SCRIPTS MAL POSICIONADOS

| Script | Local Atual | Local Correto |
|--------|-------------|---------------|
| run_siconfi_batch.sh | src/ | scripts/ |
| run_siconfi_full.sh | src/ | scripts/ |
| db_inspect.sh | scripts/ | OK (ou consolidar no run.sh) |

#### 9. ARQUIVOS ÓRFÃOS / STALE

| Arquivo | Problema |
|---------|----------|
| list_tools.py (root) | Script de debug de uma vez, não pertence ao root |
| GEMINI.md | 0 LOC, arquivo vazio |
| .codegraph/ | Diretório vazio |
| .omo/ | Run continuation JSONs — não deveria estar no repo |
| MCP_BRASIL_INTEGRATION_PLAN.md | 319 LOC — plano antigo, integrado ou obsoleto? |
| PLANO_MCP_BRASIL_MUNICIPIOS.md | 229 LOC — outro plano, possivelmente stale |
| transferegov_api.egg-info/ | Build artifact, deve ser gitignored |

#### 10. PYPROJECT.TOML vs REQUIREMENTS.TXT INCONSISTÊNCIAS

`requirements.txt` tem dependências que `pyproject.toml` não tem:
- `fastapi>=0.115`
- `uvicorn[standard]>=0.32`
- `fastmcp[code-mode]>=3.2.3`
- `anthropic>=0.40`

E pyproject.toml tem `duckdb` que requirements.txt não lista explicitamente como core.

#### 11. AGENTS.md DESATUALIZADO

- Não lista novos enrichers: `saude_educacao`, `datajud`, `tcu_compras`, `compras`, `ibge_agregados`, `siconfi`
- Não lista novas rotas API: `analytics`, `auditoria`, `compras`, `diario`
- Não lista `scripts/` (cross_analysis_tse_transferegov.py, test_tse_datasets.py)
- Não menciona `dash_app.py` como o dashboard principal (ainda referencia standalone)
- Porta web descrita inconsistente: AGENTS.md diz 8000, run.sh usa 8080

#### 12. DOCUMENTAÇÃO FRAGMENTADA

7 arquivos de docs/planos no projeto, com overlap:
- AGENTS.md (438 LOC) — principal
- README.md (65 LOC) — provavelmente mínimo
- GEMINI.md (0 LOC) — vazio
- .github/copilot-instructions.md (6 LOC) — quase vazio
- MCP_BRASIL_INTEGRATION_PLAN.md (319 LOC) — plano antigo
- PLANO_MCP_BRASIL_MUNICIPIOS.md (229 LOC) — plano antigo
- docs/strategy.md (48 LOC) — strategy
- docs/manual.txt (1567 LOC) — manual extenso, provavelmente desatualizado

---

## Fases de Execução

### Fase A: Limpeza de Baixo Risco (nenhuma quebra de import)

| # | Ação | Risco | Verificação |
|---|------|-------|-------------|
| A1 | Atualizar `.gitignore` — adicionar `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `node_modules/`, `transferegov_api.egg-info/`, `.codegraph/`, `.omo/`, `.playwright-mcp/`, `*.egg-info/` | Baixo | `git status` mostra menos arquivos |
| A2 | Deletar `GEMINI.md` (0 LOC) | Baixo | `ls GEMINI.md` → not found |
| A3 | Deletar `list_tools.py` do root | Baixo | `ls list_tools.py` → not found |
| A4 | Deletar `.codegraph/` (vazio) | Baixo | `ls .codegraph/` → not found |
| A5 | Mover `src/run_siconfi_batch.sh` → `scripts/run_siconfi_batch.sh` | Baixo | `ls src/run_siconfi*` → not found |
| A6 | Mover `src/run_siconfi_full.sh` → `scripts/run_siconfi_full.sh` | Baixo | idem |
| A7 | Atualizar `run.sh` — padronizar porta (8000 vs 8080) | Baixo | `grep port run.sh` → 8000 |
| A8 | Consolidar `pyproject.toml` dependencies com `requirements.txt` | Baixo | `pip install -e .` OK |
| A9 | Rodar `ruff check src/ tests/` e `ruff format --check src/` — baseline | Baixo | Erros reportados, nenhum fix ainda |

**Verificação Fase A:** `pytest` passa, `git status` mostra menos ruído.

---

### Fase B: Extração de Código Compartilhado (refactor de alto impacto)

| # | Ação | Risco | Verificação |
|---|------|-------|-------------|
| B1 | Criar `src/db_utils.py` com `get_connection()` e `query_df()` centralizados | Baixo | `python3 -c "from src.db_utils import get_connection"` OK |
| B2 | Criar `src/formatters.py` com `fmt_brl()`, `fmt_num()`, `fmt_pct()`, `format_brl()` consolidados | Baixo | `python3 -c "from src.formatters import fmt_brl"` OK |
| B3 | Substituir `get_connection()` em TODOS os 14 arquivos por `from src.db_utils import get_connection` | Médio | `grep -rn "def get_connection" src/` → 0 resultados |
| B4 | Substituir `fmt_brl/fmt_num/fmt_pct` em TODOS os 6 arquivos por imports | Médio | `grep -rn "def fmt_brl\|def fmt_num\|def fmt_pct" src/` → 0 resultados |
| B5 | Rodar `pytest` e `ruff check` após cada arquivo | Baixo | Todos passam |

**Verificação Fase B:** `pytest` passa, `ruff check` passa, `grep -rn "def get_connection" src/` retorna só `db_utils.py`.

---

### Fase C: Renomeação e Consolidação de Migrations

| # | Ação | Risco | Verificação |
|---|------|-------|-------------|
| C1 | Renomear migrations com sequência real: `002` → `002`, `003_enrichment` → `003`, `003_ibge_agregados` → `004`, `003_unificacao` → `005`, `003_datajud` → `006`, `004_enriched_views` → `007`, `004_siconfi` → `008`, `005_novas_fontes` → `009` | Médio | `ls data/migration_*.sql` mostra sequência sem gaps |
| C2 | Criar `data/MIGRATIONS.md` com a ordem correta e descrição | Baixo | Doc existe |
| C3 | Rodar `schema.sql` completo (rebuild) para validar que migrations são idempotentes | Alto | `psql ... -f data/schema.sql` OK |

**Verificação Fase C:** Schema reconstruído do zero, todas as tabelas criadas.

---

### Fase D: Reorganização de Diretórios

| # | Ação | Risco | Verificação |
|---|------|-------|-------------|
| D1 | Criar `src/dashboard/` e mover 5 dashboards standalone para lá (ou deletar se deprecated) | Médio | Imports atualizados |
| D2 | Decidir sobre `graph_generator.py`: deletar ou mover para `archive/` | Baixo | Não referenciado por graph_factory |
| D3 | Consolidar `compras.py` + `tcu_compras.py` (sobreposição de API) | Médio | Um script, testes passam |
| D4 | Mover `scripts/db_inspect.sh` conteúdo para `run.sh` como subcomando `inspect` | Baixo | `./run.sh inspect` funciona |
| D5 | Mover planos stale para `docs/plans/`: `MCP_BRASIL_INTEGRATION_PLAN.md`, `PLANO_MCP_BRASIL_MUNICIPIOS.md` | Baixo | `ls *.md` no root mostra só AGENTS/README |
| D6 | Mover `docs/manual.txt` e `docs/strategy.md` para `docs/` (já estão lá) — OK | N/A | Nada a fazer |

**Estrutura alvo:**
```
tranfere_gov_api/
├── src/
│   ├── transferegov_extract.py   # CLI principal
│   ├── db_utils.py               # NOVO: get_connection(), query_df()
│   ├── formatters.py             # NOVO: fmt_brl(), fmt_num(), fmt_pct()
│   ├── schemas.py
│   ├── http_cache.py
│   ├── db_import.py
│   ├── db_report.py
│   ├── deputado_followup.py
│   │
│   ├── dashboard/                # NOVO: consolidar 5 standalone HTML
│   │   ├── __init__.py
│   │   ├── main.py               # dashboard.py renomeado
│   │   ├── deputados.py          # dashboard_deputados.py
│   │   ├── emendas.py            # dashboard_emendas.py
│   │   ├── cross_analysis.py     # dashboard_cross_analysis.py
│   │   └── cross_fiscal.py       # dashboard_cross_fiscal.py
│   │
│   ├── dash_app.py               # Dash interativo (principal)
│   ├── graph_factory.py          # 1811 LOC, 27 gráficos
│   ├── graph_tools.py            # MCP tools
│   ├── verify_graphs.py
│   │
│   ├── api/                      # FastAPI (inalterado)
│   │   ├── app.py
│   │   ├── routes/
│   │   └── services/
│   │
│   └── enrichers/                # Pipeline de enriquecimento
│       ├── pipeline.py
│       ├── validacao.py
│       ├── ibge.py
│       ├── ibge_agregados.py
│       ├── mapear_municipios.py
│       ├── camara.py
│       ├── siconfi.py
│       ├── compras.py            # UNIFICADO (absorve tcu_compras)
│       ├── saude_educacao.py
│       ├── datajud.py
│       ├── completar_deputados.py
│       └── discricionarias_sync.py
│
├── scripts/                      # CLI utilities
│   ├── run_siconfi_batch.sh      # Movido de src/
│   ├── run_siconfi_full.sh       # Movido de src/
│   └── cross_analysis_tse_transferegov.py
│
├── config/
├── data/
├── docs/
│   └── plans/                    # Planos antigos movidos aqui
├── tests/
├── output/                       # gitignored
└── run.sh
```

---

### Fase E: Sincronização de Config e Docs

| # | Ação | Risco | Verificação |
|---|------|-------|-------------|
| E1 | Sincronizar `pyproject.toml` ↔ `requirements.txt` (source of truth = pyproject.toml) | Baixo | `pip install -e ".[dev]"` OK |
| E2 | Atualizar `AGENTS.md` — adicionar novos enrichers, novas rotas API, nova estrutura | Baixo | Doc reflete código real |
| E3 | Atualizar `README.md` — instruções de setup modernizadas | Baixo | Doc existe |
| E4 | Deletar `MCP_BRASIL_INTEGRATION_PLAN.md` e `PLANO_MCP_BRASIL_MUNICIPIOS.md` (ou mover para `docs/plans/`) | Baixo | Root limpo |
| E5 | Criar `src/enrichers/AGENTS.md` atualizado com todos os enrichers | Baixo | Doc existe |

**Verificação Final:**
```bash
# Syntax check
ruff check src/ tests/ config/

# Import check
python3 -c "from src.db_utils import get_connection, query_df"
python3 -c "from src.formatters import fmt_brl, fmt_num, fmt_pct"

# Duplication check
grep -rn "def get_connection" src/   # só db_utils.py
grep -rn "def fmt_brl" src/         # só formatters.py

# Tests
pytest tests/

# Full import tree
python3 -c "import src.transferegov_extract; import src.dash_app; import src.graph_factory"
```

---

## Priorização e Estimativas

| Fase | Esforço | Impacto | Dependências |
|------|---------|---------|-------------|
| **A** (limpeza) | 30 min | Baixo | Nenhuma |
| **B** (dedup código) | 2-3h | **ALTO** | Nenhuma |
| **C** (migrations) | 1h | Médio | Teste manual do schema |
| **D** (diretórios) | 1-2h | Médio | Fase B completa |
| **E** (config/docs) | 1h | Médio | Fases anteriores |
| **Total** | **5-8h** | | |

**Recomendação:** Começar pela Fase B (dedup de `get_connection` + formatters) — é o maior ganho de impacto vs esforço, e deixa o código muito mais manutenível.

---

## Riscos

1. **Migrations renomeadas** podem quebrar scripts que referenciam nomes antigos → mitigar com `data/MIGRATIONS.md`
2. **Dashboard standalone pode ser referenciado** por cron jobs ou scripts externos → verificar antes de mover
3. **`compras.py` vs `tcu_compras.py`** — podem ter funções legítimas diferentes → auditar antes de unificar
4. **Porta inconsistente** (8000 vs 8080) pode estar hardcoded em mais lugares → grep completo antes de fixar
