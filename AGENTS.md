# AGENTS.md — TransfereGov API

Projeto Python para extração, validação, enriquecimento e análise de Planos de Ação do
sistema Transferegov (Transferências Especiais / Emendas Pix) do Governo Federal.

**Pipeline**: Extração → Validação (Pydantic) → PostgreSQL (upsert) → Enriquecimento (IBGE, BrasilAPI, Câmara, SICONFI, TSE, Senado, FNDE, TCU) → RAG v3 (Qdrant + LocalAI) → Dashboard 68 gráficos + API 38 endpoints

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
python3 src/verify_graphs.py              # auditoria dos 68 gráficos

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
├── graphs/                   Pacote gráficos (17 módulos, 68 gráficos)
│   ├── registry.py             @register_chart decorator + CHART_REGISTRY
│   ├── theme.py                Theme tokens + TODAS_UFS + CORES_SITUACAO
│   ├── parlamentar.py 3 | socioeconomico.py 3 | analitico.py 2
│   ├── fiscal.py 3 | siconfi.py 10 | arrecadacao.py 13 | geoespacial.py 3
│   ├── impacto_social.py 2 | hierarquico.py 4 | economico.py 7
│   ├── prefeitos.py 2 | financas.py 6 | economia_cruzada.py 2
│   ├── intel_politica.py 5 | intel_proposicoes.py 1
│   ├── radar_diario.py 1 | votacoes.py 1
├── graph_factory.py          Shim backward-compat → src.graphs
├── graph_tools.py            MCP Tools (@mcp_enabled)
├── verify_graphs.py          Suíte auditoria gráficos
├── deputado_followup.py      CLI followup deputado
├── prefeito_followup.py      CLI followup prefeito
├── redator_transferegov.py   Redator documentos oficiais
├── localai_manager.py        Gerencia VRAM GPU e exclusividade de modelos
├── localai_client.py         Cliente HTTP para chat completion LocalAI
├── mcp_tool_bridge.py        Ponte MCP ↔ modelos locais
├── api/                      FastAPI (ver src/api/AGENTS.md)
│   ├── app.py                  App principal
│   ├── routes/                 8 routers (deputados, prefeitos, analytics, auditoria, diario, compras, vereadores, fnde)
│   ├── services/               4 services (db, camara, mcp, analytics)
│   └── static/                 Frontend SPA
└── enrichers/                Pipeline enriquecimento (ver src/enrichers/AGENTS.md)
    ├── pipeline.py              Orquestrador fases 1-3
    ├── validacao.py 1a | ibge.py 1b | ibge_agregados.py 1d
    ├── siconfi.py 1e (DCA+RREO) | camara.py 2
    ├── mapear_municipios.py 1c | compras.py | saude_educacao.py
    ├── datajud.py | completar_deputados.py | discricionarias_sync.py
    ├── tse_prefeitos.py 7a | tse_vereadors.py 7b | tse_deputados.py
    ├── senado.py 8 | fnde.py | tcu_compras.py
    ├── rag_qdrant_indexer.py | rag_persona.py
    ├── diario_oficial_worker.py | sync_proposicoes.py
    ├── votacoes_camara.py | votacoes_temas.py
config/settings.py            API, DB, paths, ENRICH_*
data/                         schema.sql, migrations 002-014, swagger.yaml
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
| `emendas_discricionarias` | Portal Transp. | Emendas discricionárias sincronizadas |
| `beneficiario_processos` | DataJud | Processos judiciais vinculados a beneficiários |
| `compras_municipios` | Compras gov.br | Compras públicas por município |
| `saude_municipios` | CNES/DATASUS | Indicadores de saúde municipal |
| `educacao_municipios` | INEP/MEC | Indicadores de educação municipal |
| `violencia_municipios` | ISP/青少年 | Indicadores de violência municipal |
| `diario_oficial_atos` | DOU (web) | Atos publicados no Diário Oficial da União |
| `parlamentar_alertas` | Pipeline | Alertas gerados automaticamente para deputados |
| `parlamentar_proposicoes` | Câmara API | Proposições legislativas dos deputados |
| `votacoes_camara` | Câmara API | Votações e votos nominais |
| `votos_camara` | Câmara API | Votos individuais por deputado |
| `parlamentares_personas_v2` | LocalAI + RAG | Personas analíticas geradas por IA |
| `fnde_repasses` | FNDE/MEC | Repasses educacionais do FNDE |

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
| 4 | `compras.py` | Compras gov.br | `compras_municipios` |
| 5 | `saude_educacao.py` | CNES/DATASUS/INEP | `saude_municipios`, `educacao_municipios` |
| 6 | `datajud.py` | DataJud CNJ | `beneficiario_processos` |
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
| GET | `/api/v1/prefeitos/search?q=` | Busca prefeitos |
| GET | `/{id}/perfil` | Perfil prefeito |
| GET | `/{id}/emendas` | Emendas por município |
| GET | `/api/v1/analytics/resumo` | Resumo geral do banco |
| GET | `/api/v1/analytics/por-estado` | Métricas por UF |
| GET | `/api/v1/analytics/por-situacao` | Métricas por situação |
| GET | `/api/v1/analytics/por-parlamentar` | Métricas por parlamentar |
| GET | `/api/v1/auditoria/dados` | Auditoria dos dados |
| GET | `/api/v1/auditoria/qualidade` | Indicadores qualidade |
| GET | `/api/v1/auditoria/cobertura` | Cobertura de enriquecimento |
| GET | `/api/v1/diario/buscar?q=` | Busca Diário Oficial |
| GET | `/api/v1/diario/atos` | Atos publicados recentes |
| GET | `/api/v1/compras/buscar?q=` | Busca compras públicas |
| GET | `/api/v1/compras/por-municipio` | Compras agregadas |
| GET | `/api/v1/vereadores/buscar?q=` | Busca vereadores |
| GET | `/{id}/perfil` | Perfil vereador |
| GET | `/{id}/votos` | Votos nominais |
| GET | `/api/v1/fnde/repasses` | Repasses FNDE |
| GET | `/api/v1/fnde/por-municipio` | Represses por município |
| GET | `/api/v1/fnde/por-estado` | Represses por estado |
| GET | `/api/v1/fnde/resumo` | Resumo FNDE |
| GET | `/api/v1/fnde/historico` | Histórico de repasses |

Fallback: busca local → enriquece API Câmara → degrada graceful. Docs: `/docs` (Swagger), `/redoc`.

---

## Redator Oficial

Gera documentos seguindo Manual de Redação da Presidência 3ª edição. Tipos: `oficio`, `nota_tecnica`, `parecer`, `despacho`, `portaria`, `ata`.

- **Data por extenso**: `"Brasília, 25 de julho de 2026."`
- **Pronomes**: 27 entradas em 4 tiers (Excelentíssimo → Vossa Magnificência)
- **Fechos**: APENAS "Respeitosamente," (superior) / "Atenciosamente," (igual)
- **Legado**: memorando/aviso → convertido automaticamente para OFÍCIO

---

## RAG v3 & Integração LocalAI

### Arquitetura LocalAI

Três módulos para integração com modelos locais via API compatível OpenAI:

- **LocalAIManager (`src/localai_manager.py`)**: Gerencia exclusividade de VRAM na GPU. Antes de chamar qualquer modelo, faz varredura (`is_model_loaded`) e descarrega inativos (`unload_model` via `/backend/shutdown`), eliminando erros de estouro (OOM / RPC EOF). Função principal: `ensure_model_loaded(model)`.
- **LocalAIClient (`src/localai_client.py`)**: Cliente HTTP síncrono para chat completion. Trata retry, timeout e parsing de streaming.
- **MCP Tool Bridge (`src/mcp_tool_bridge.py`)**: Ponte entre ferramentas MCP e modelos locais. Permite que agentes MCP invoquem LLMs locais para tarefas de análise e redação.

### Modelos Validados e Categorizados (`config/settings.py`)

| Alias | Modelo | Uso | Velocidade |
|-------|--------|-----|------------|
| `gemma` | `gemma-4-e2b-it` | Padrao RAG, redacao PT-BR | 36.8 tok/s |
| `fast` | `qwen2.5-1.5b-instruct-q4-k-m` | Triagem diaria, NER | 88.9 tok/s |
| `analysis` | `llama-3.1-8b-q4-k-m` | Analise investigativa profunda | 7.7 tok/s |
| `code` | `Qwen2.5-Coder-7B-Instruct-GGUF` | Codigo | -- |
| `general` | `gemma-4-e2b-it` | Uso geral | 36.8 tok/s |
| `embedding` | `nomic-embed-text-v1.5` | Embeddings Qdrant | -- |
| `router` | `intelligent-router` | Roteamento inteligente | -- |

### Pipeline RAG v3

- **Indexador (`src/enrichers/rag_qdrant_indexer.py`)**: Indexa dados de deputados no Qdrant com 6 tipos de chunks: perfil, emendas, despesas CEAP, proposicoes, votacoes e atas do Diario Oficial. Roda via `./run.sh cron-qdrant`.
- **Persona (`src/enrichers/rag_persona.py`)**: Multi-Query RAG v3 com 5 queries tematicas no Qdrant:
  1. Padrao de votos nominais
  2. Emendas PIX e valores por municipio
  3. Proposicoes legislativas
  4. Atos do Diario Oficial
  5. Conexoes politicas municipais (TSE x Emendas): cruza partido do deputado x prefeito eleito no municipio receptor para identificar apadrinhamento local / fisiologismo.
- Roda via `./run.sh cron-dossie`.

### Benchmark

- **Suite (`scripts/benchmark_models.py`)**: Avalia automaticamente modelos com pontuacao de qualidade (0-100), velocidade e preenchimento de secoes analiticas.

---

## Cron Jobs

| Job | Comando | Frequencia | Descricao |
|-----|---------|------------|-----------|
| Diario Oficial | `./run.sh cron-diario` | Diaria | Baixa DOU e gera resumo de atos |
| Qdrant Indexer | `./run.sh cron-qdrant` | Semanal | Indexa dados de deputados no Qdrant (6 chunk types) |
| Dossie Persona | `./run.sh cron-dossie` | Sob demanda | Gera personas analiticas via Multi-Query RAG v3 |

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
15. VRAM LocalAI: sempre invocar `localai_manager.ensure_model_loaded(model)` antes de requisições pesadas para evitar crash de GPU
16. Qdrant: collection `deputados_perfis` requer embedding `nomic-embed-text-v1.5` (768d) — não misturar dimensões
17. MCP Tool Bridge: `mcp_tool_bridge.py` depende de `localai_manager` — verificar GPU antes de invocar
18. Diario Oficial: worker (`diario_oficial_worker.py`) faz scraping web — quebra se layout do DOU mudar

---

## Referência

- `references/mcp-brasil/` — MCP server gov.br (533 tools, 70 features)
- `docs/MIGRATIONS.md` — Ordem correta das migrations (002-014)
- `data/schema.sql` — Schema completo do banco
