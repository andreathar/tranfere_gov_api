# AGENTS.md — TransfereGov API

Projeto Python para extração, validação, enriquecimento e análise de Planos de Ação do
sistema Transferegov (Transferências Especiais / Emendas Pix) do Governo Federal.

**Pipeline**: Extração → Validação (Pydantic) → PostgreSQL (upsert) → Enriquecimento (IBGE, BrasilAPI, Câmara, SICONFI, TSE, Senado, FNDE, TCU, Discursos, Governadores) → RAG v7 (Qdrant + LocalAI, multi-analista) → Dashboard 74 gráficos + API 43 endpoints

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
python3 src/transferegov_extract.py --objeto all --ano 2026 --parlamentar 4291 --csv --db  # propostas de um deputado
python3 src/transferegov_extract.py --objeto all --ano 2026 --parlamentar 4291 --negados  # só negadas
# Flags: --db --csv --programa N --uf UF --situacao-api S --parlamentar ID -v

# Extração via Portal da Transparência (discricionárias + PIX)
./run.sh transparencia --nome-autor "ADAIL FILHO" --ano 2024
./run.sh transparencia --nome-autor "ADAIL FILHO" --ano 2024 --db --csv --json
./run.sh transparencia --nome-autor "ADAIL FILHO" --ano 2024 --apenas-discricionarias
./run.sh transparencia --parlamentar 4291 --ano 2024                   # busca nome no banco local
python3 src/extrator_transparencia.py --nome-autor "ADAIL FILHO" --ano 2024 --relatorio
python3 src/extrator_transparencia.py --nome-autor "ADAIL FILHO" --ano 2024 --apenas-discricionarias --db --csv
# Flags: --nome-autor N --ano N --parlamentar ID --db --csv --json --relatorio --apenas-discricionarias -v

# Extração de propostas discricionárias (sistema voluntárias, acesso guest)
python3 -m src.extrator_discricionarias detalhar --id-proposta 2035559 --id-convenio 1163065 --json --db
python3 -m src.extrator_discricionarias buscar --uf SP --detalhar
python3 -m src.extrator_discricionarias buscar --emenda 11228

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
python3 -m src.enrichers.estados_financeiro [--dry-run] [--uf UF] [--ano ANO] [--rreo]
python3 -m src.enrichers.camara [--dry-run] [--limit N]
python3 -m src.enrichers.tse_prefeitos [--dry-run] [--uf UF] [--ano ANO]
python3 -m src.enrichers.tse_vereadors [--dry-run] [--uf UF] [--ano ANO]
python3 -m src.enrichers.senado [--dry-run] [--limit N]
python3 -m src.enrichers.camara_discursos [--ano ANO] [--limit N] [--resumo]
python3 -m src.enrichers.governadores [--dry-run] [--limit N]
python3 -m src.enrichers.violencia [--dry-run] [--uf UF] [--ano ANO]
python3 -m src.enrichers.pipeline --fase all [--dry-run] [--limit N]

# Diagnóstico Qdrant & RAG Efficiency
./run.sh qdrant-status                          # painel de status da indexação
./run.sh qdrant-staleness                       # deputados desatualizados vs checkpoint
./run.sh rag-efficiency --politico-id 4291      # RAG Efficiency Metrics (Retrieval + Generation)
./run.sh logit-lens-runner --run-id 1           # Logit Lens Offline Panel (Emergence Layer)

# vLLM (engine alternativa ao LocalAI)
./run.sh vllm start|stop|status|chat            # gerencia server vLLM local (porta 8001)
./run.sh vllm-bench                             # benchmark comparativo vLLM vs LocalAI

# Dashboard + MCP
python3 src/dash_app.py                    # http://localhost:8050 + http://localhost:8050/_mcp
python3 src/verify_graphs.py              # auditoria dos 74 gráficos

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
- **Python**: usar SEMPRE `.venv/bin/python` (ex: `.venv/bin/python -m pytest`, `.venv/bin/python -m mypy src/`) — o `python3` do shell pode ser shim pyenv sem pytest/mypy
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
├── graphs/                   Pacote gráficos (18 módulos, 74 gráficos)
│   ├── registry.py             @register_chart decorator + CHART_REGISTRY
│   ├── theme.py                Theme tokens + TODAS_UFS + CORES_SITUACAO
│   ├── parlamentar.py 3 | socioeconomico.py 3 | analitico.py 2
│   ├── fiscal.py 3 | siconfi.py 10 | arrecadacao.py 13 | geoespacial.py 3
│   ├── impacto_social.py 2 | hierarquico.py 4 | economico.py 7
│   ├── prefeitos.py 2 | financas.py 6 | economia_cruzada.py 2
│   ├── intel_politica.py 5 | intel_proposicoes.py 1
│   ├── radar_diario.py 1 | votacoes.py 1 | governadores.py 6
├── graph_factory.py          Shim backward-compat → src.graphs
├── graph_tools.py            MCP Tools (@mcp_enabled)
├── verify_graphs.py          Suíte auditoria gráficos
├── deputado_followup.py      CLI followup deputado
├── prefeito_followup.py      CLI followup prefeito
├── extrator_transparencia.py Extrator de emendas via Portal da Transparência (discricionárias + PIX)
├── extrator_discricionarias.py Extrator de propostas do sistema de discricionárias (acesso guest)
├── redator_transferegov.py   Redator documentos oficiais
├── localai_manager.py        Gerencia VRAM GPU e exclusividade de modelos
├── localai_client.py         Cliente HTTP para chat completion LocalAI
├── models_config.py          Leitura/alteração das YAMLs de modelos do LocalAI (CPU/GPU, gpu_layers)
├── local_vllm.py             Gerencia servidor vLLM local (start/stop/status/chat, porta 8001)
├── modal_vllm_server.py      Server vLLM na nuvem Modal (GPU cloud, Llama-70B)
├── qdrant_status.py          Painel de status da indexação Qdrant
├── qdrant_staleness.py       Staleness do Qdrant vs checkpoint
├── analysts/                 RAG v7: 7 analistas especialistas + PromptPreparer
│   ├── base.py                 AnalystBase + AnalystResult (ABC)
│   ├── router.py               Filtra chunks por analista (chunk types)
│   ├── preparer.py             PromptPreparer: sintetiza chunks → Briefing + Fact Table
│   ├── classificador.py | perfil.py | tematicas.py | cruzamento.py
│   └── alinhamento.py | discursos.py | anomalias.py
├── mcp_tool_bridge.py        Ponte MCP ↔ modelos locais
├── rag_efficiency_collector.py Coleta de métricas (hit rate, faithfulness)
├── api/                      FastAPI (ver src/api/AGENTS.md)
│   ├── app.py                  App principal
│   ├── routes/                 8 routers (deputados, prefeitos, analytics, auditoria, diario, compras, vereadores, fnde)
│   ├── services/               4 services (db, camara, mcp, analytics)
│   └── static/                 Frontend SPA
└── enrichers/                Pipeline enriquecimento (ver src/enrichers/AGENTS.md)
    ├── pipeline.py              Orquestrador fases 1-9
    ├── validacao.py 1a | ibge.py 1b | ibge_agregados.py 1d
    ├── siconfi.py 1e (DCA+RREO) | camara.py 2
    ├── mapear_municipios.py 1c | compras.py | saude_educacao.py
    ├── datajud.py | completar_deputados.py | discricionarias_sync.py
    ├── tse_prefeitos.py 7a | tse_vereadors.py 7b | tse_deputados.py
    ├── senado.py 8 | camara_discursos.py 9 | fnde.py | tcu_compras.py
    ├── governadores.py (TSE 2022) | violencia.py (ISP-RJ/Atlas)
    ├── rag_qdrant_indexer.py | rag_persona.py
    ├── diario_oficial_worker.py | sync_proposicoes.py
    ├── votacoes_camara.py | votacoes_temas.py
config/settings.py            API, DB, paths, ENRICH_*
data/                         schema.sql, migrations 002-040, swagger.yaml
scripts/                      db_inspect.sh, run_siconfi_batch.sh, logit_lens_runner.py
docs/                         MIGRATIONS.md, manual.txt, plans/
output/                       Gitignored (xlsx, csv, json, logs)
```

---

## API TransfereGov

- **Endpoint**: `GET https://especiais.transferegov.sistema.gov.br/maisbrasil-transferencia-especial-backend/api/public/plano-acao/listagem`
- **Detail**: `GET .../plano-acao/{planoAcaoId}` (mais campos: emendaParlamentarId, beneficiario, objeto, modalidade)
- **Auth**: NENHUMA (público) | **IP**: pode bloquear fora do Brasil | **Timeout**: 60s, 3 retries
- **Auth**: NENHUMA (público) | **IP**: pode bloquear fora do Brasil | **Timeout**: 60s, 3 retries
- **Pagination**: `pageSize=100`, `pageNumber=1..N`, break when empty
- **Response key**: `listaPlanosAcao` (NÃO `data`/`content`/`items`)

### Parâmetros de Query

| Param | Exemplo | Param | Exemplo |
|-------|---------|-------|---------|
| `objetoExecucao` | `301` | `programaId` | `25` (Transf. Especiais) |
| `objetoExecucaoAno` | `2026` | `planoAcaoSituacao` | `IMPEDIDO` |
| `uf` | `SP`, `AL` | `parlamentar` | `4291` |
| `emenda` | `11228` | `beneficiario` | `9858` |

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
| `estados_financeiro` | SICONFI esfera estadual | Dados financeiros dos governos de estado (DCA + RREO A03: ICMS, IPVA, ITCD, FPE, FUNDEB, RCL) |
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
| `parlamentar_discursos` | Câmara API | Discursos de deputados em plenário/comissões |
| `governadores_dados` | TSE 2022 (manual) | Governadores eleitos: votos 1º/2º turno, partido, coligação |
| `violencia_municipios` | ISP-RJ (DuckDB) + Atlas IPEA | Indicadores de violência municipal |
| `fnde_repasses` | FNDE/MEC | Repasses educacionais do FNDE |

Schema completo: `data/schema.sql`, migrations: `data/migration_002-025*.sql` (ver `docs/MIGRATIONS.md`)

---

## Pipeline Enriquecimento

| Fase | Script | Fonte | Destino |
|------|--------|-------|---------|
| 1a | `validacao.py` | BrasilAPI (CNPJ) | `validacao_cnpj` |
| 1b | `ibge.py` | IBGE (localidades) | `municipios_ibge` |
| 1c | `mapear_municipios.py` | Fuzzy match | `beneficiario_ibge_map` |
| 1d | `ibge_agregados.py` | IBGE (agregados) | `municipios_ibge` (pop, PIB, área) |
| 1e | `siconfi.py` | SICONFI (DCA + RREO A03) | `municipios_financeiro` |
| 1e2 | `estados_financeiro.py` | SICONFI esfera estadual (DCA + RREO A03) | `estados_financeiro` |
| 2 | `camara.py` | Câmara Deputados | `parlamentares_dados` |
| 3 | `pipeline.py` | SQL JOIN | `parlamentar_beneficiario` |
| 4 | `compras.py` | Compras gov.br | `compras_municipios` |
| 5 | `saude_educacao.py` | CNES/DATASUS/INEP | `saude_municipios`, `educacao_municipios` |
| 6 | `datajud.py` | DataJud CNJ | `beneficiario_processos` |
| 7a | `tse_prefeitos.py` | TSE (DuckDB) | `prefeitos_dados` |
| 7b | `tse_vereadors.py` | TSE (DuckDB) | `vereadores_dados` |
| 8 | `senado.py` | Senado API REST | `senadores_dados` |
| 9 | `camara_discursos.py` | Câmara Dados Abertos | `parlamentar_discursos` |
| aux | `governadores.py` | TSE 2022 (manual) | `governadores_dados` |
| aux | `violencia.py` | ISP-RJ (DuckDB) + Atlas IPEA | `violencia_municipios` |

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
| GET | `/api/v1/governadores` | Lista governadores (filtros partido/região) |
| GET | `/api/v1/governadores/ranking/emendas` | Ranking por emendas Pix na UF |
| GET | `/api/v1/governadores/ranking/alinhamento` | Alinhamento partidário com bancada federal |
| GET | `/api/v1/governadores/triangulo-politico` | Triângulo político deputado×prefeito×governador |
| GET | `/api/v1/governadores/{uf}/perfil` | Perfil do governador + SICONFI + bancada |

Fallback: busca local → enriquece API Câmara → degrada graceful. Docs: `/docs` (Swagger), `/redoc`.

---

## Redator Oficial

Gera documentos seguindo Manual de Redação da Presidência 3ª edição. Tipos: `oficio`, `nota_tecnica`, `parecer`, `despacho`, `portaria`, `ata`.

- **Data por extenso**: `"Brasília, 25 de julho de 2026."`
- **Pronomes**: 27 entradas em 4 tiers (Excelentíssimo → Vossa Magnificência)
- **Fechos**: APENAS "Respeitosamente," (superior) / "Atenciosamente," (igual)
- **Legado**: memorando/aviso → convertido automaticamente para OFÍCIO

---

## RAG v7 & Integração LocalAI

### Arquitetura LocalAI

Três módulos para integração com modelos locais via API compatível OpenAI:

- **LocalAIManager (`src/localai_manager.py`)**: Gerencia exclusividade de VRAM na GPU. Antes de chamar qualquer modelo, faz varredura (`is_model_loaded`) e descarrega inativos (`unload_model` via `/backend/shutdown`), eliminando erros de estouro (OOM / RPC EOF). Funções principais: `ensure_model_loaded(model)`, `wait_for_model_loaded()` (com timeout), `warmup_model()` (pré-carregamento).
- **LocalAIClient (`src/localai_client.py`)**: Cliente HTTP síncrono para chat completion. Trata retry via circuit breaker, timeout e parsing de streaming.
- **MCP Tool Bridge (`src/mcp_tool_bridge.py`)**: Ponte entre ferramentas MCP e modelos locais. Permite que agentes MCP invoquem LLMs locais para tarefas de análise e redação.

### Modelos Validados e Categorizados (`config/settings.py`)

| Alias | Modelo | Uso | Timeout |
|-------|--------|-----|---------|
| `dossie` | `llama-3.2-3b-instruct:q4_k_m` | **Padrão RAG v7** (dossiês, 100/100 benchmark) | 240s |
| `analysis` | `agente-dossie-investigativo` | Análise investigativa profunda (agente customizado) | 300s |
| `fast` | `agente-dossie-rapido` | Triagem rápida (83.9 tok/s) | 60s |
| `gemma` | `zero-gemma4-e4b-openzero-q5-k-m` | Redação PT-BR, reasoning (21.9 tok/s, gpu_layers=40) | 180s |
| `code` | `Qwen2.5-Coder-7B-Instruct-GGUF` | Código | 180s |
| `general` | `llama-3.2-3b-instruct:q4_k_m` | Uso geral | 180s |
| `embedding` | `embeddinggemma-300m` | Embeddings Qdrant (768d) | 30s |
| `router` | `intelligent-router` | Roteamento inteligente | 15s |
| `fallback` | `llama-3.2-3b-instruct:q4_k_m` | **Fallback RAG** (`RAG_FALLBACK_MODEL`, se QC reprovar) | 240s |
| `preparer` | `zero-gemma4-e4b-openzero-q5-k-m` | PromptPreparer RAG v7 (`PREPARER_MODEL`, síntese de chunks) | 180s |

> `config/settings.py` agora carrega `.env` (`load_dotenv()`) e suporta **vLLM**: local (`USE_LOCAL_VLLM`, porta 8001) e nuvem Modal (`USE_MODAL_VLLM`, Llama-70B). `src/models_config.py` lê/altera as YAMLs reais de `/mnt/data/Projects_SSD/LocalAI/models/` (backend CPU/GPU, gpu_layers).

### Pipeline RAG v7

- **Indexador (`src/enrichers/rag_qdrant_indexer.py`)**: Indexa dados de deputados no Qdrant com **23 tipos de chunks** (perfil, emenda, voto, proposicao, discurso_plenario, conexao_politica, risco_judicial, compras_municipio, demografia, indicadores sociais, FNDE, etc.). Modos:
  - `./run.sh cron-qdrant --limit 10` — indexa N deputados mais relevantes
  - `./run.sh cron-qdrant --nome "Nome"` — indexa deputado específico
  - `./run.sh cron-qdrant --diff --limit 50` — **modo incremental**: pula chunks com hash inalterado (mais rápido)
  - `./run.sh cron-qdrant --limit 600` — **modo todos deputados**: para processar todos os deputados, `--limit` alto é obrigatório, pois `--todos` é ignorado para cargo deputado.
  - `./run.sh cron-qdrant --types voto,emenda` — indexa **apenas tipos específicos**
  - `./run.sh cron-qdrant --rebuild` — limpa e reindexa tudo do zero
  - `./run.sh cron-qdrant --checkpoint` — força criação da tabela de checkpoint
- **Resiliência**: cada extrator de chunk type é isolado em try/except — falha em um não aborta os demais.
- **Checkpoint**: tabela `qdrant_index_checkpoint` no PostgreSQL armazena hash dos dados para detecção de mudanças.
- **Diagnóstico**: `./run.sh qdrant-status` (vetores/cobertura por tipo) e `./run.sh qdrant-staleness` (deputados desatualizados vs checkpoint).

- **Persona (`src/enrichers/rag_persona.py`)**: Multi-Query RAG v7 com **15 queries temáticas** (batch embedding) cobrindo todos os 23 chunk types + Reciprocal Rank Fusion (RRF, k=60):

  1. Padrão de votos, dissenso partidário e obstrução
  2. Proposições legislativas (PLs, PECs, PDLs)
  3. Emendas PIX por município e situação dos planos
  4. Emendas discricionárias (Portal Transparência)
  5. Resumo consolidado do deputado
  6. Dados financeiros SICONFI dos municípios
  7. Dados demográficos IBGE (população, PIB, IDHM)
  8. Indicadores sociais (saúde + educação)
  9. Repasses FNDE
  10. Conexões políticas (TSE x Emendas — apadrinhamento/fisiologismo)
  11. Risco judicial (DataJud)
  12. Compras públicas municipais
  13. Ideologia nos discursos de plenário
  14. Tópicos recorrentes e bandeiras públicas

- **7 analistas especialistas (`src/analysts/`)**: em vez de 1 prompt monolítico, cada analista recebe apenas os chunk types relevantes, com prompt focado, quality check próprio e tolerância a falhas:
  - `classificador` (GOVERNO/OPOSIÇÃO/INDEPENDENTE) · `perfil` (bio-político) · `tematicas` (áreas + R$) · `cruzamento` (contradições, exige 3+ fontes) · `alinhamento` (% + pautas) · `discursos` (tags/ideologia) · `anomalias` (red flags/auditoria)
  - Ativação adaptativa via `get_active_analysts()` — analistas sem dados suficientes são pulados
  - Assembly: `assemble_dossier()` concatena seções na ordem + `calculate_global_score()` (média ponderada 0-100, aprovação ≥ 70)
- **PromptPreparer (`src/analysts/preparer.py`)**: sintetiza até 8 chunks brutos → **Briefing estruturado + Fact Table + Insights** usando modelo rápido (`PREPARER_MODEL`), com **validação de fidelidade numérica R$** pós-geração — reduz tokens do analista principal em 5-10x e preserva exatidão
- **Retry com fallback**: se o modelo falhar ou reprovar no quality check, tenta automaticamente `RAG_FALLBACK_MODEL` (`RAG_MAX_RETRIES`)
- Roda via: `./run.sh cron-dossie --lote 50` ou `./run.sh cron-dossie --nome "Nome" --modelo llama-3.2-3b-instruct:q4_k_m`

### RAG Efficiency & Logit Lens
Métricas automáticas de performance do pipeline RAG:
1. **Retrieval Efficiency**: `hit_rate@k` e `mrr` baseados em um Golden Set dinâmico extraído do banco relacional (ex: total emendas, partido, UF).
2. **Generation Efficiency**: `faithfulness` via **juiz híbrido** — match lexical normalizado (exato/limite de palavra, sem custo de LLM) e LLM-as-a-judge só em caso ambíguo (RAG Answer vs Golden Answer).
3. **Groundedness via Logit Lens**: Pipeline offline (`scripts/logit_lens_runner.py`) usando HF `transformers` para medir em qual camada de atenção (emergence layer) o modelo sabe a resposta. Ajuda a distinguir grounding real de alucinação (guessing).
- Registrado no DB (`rag_efficiency_runs` e `rag_efficiency_metrics`). Dashboard visual na aba de Auditoria.

### Quality Check v7

Seções obrigatórias no dossiê: **CLASSIFICAÇÃO POLÍTICA** (GOVERNO/OPOSIÇÃO/INDEPENDENTE), PERFIL, ÁREAS TEMÁTICAS, CRUZAMENTO DE DADOS, ALINHAMENTO POLÍTICO, ANOMALIAS E FISIOLOGISMO — cada uma validada pelo QC do seu analista + score global ponderado.

### Benchmark

- **Suite (`scripts/benchmark_models.py`)**: Avalia automaticamente modelos com pontuação de qualidade (0-100), velocidade e preenchimento de seções analíticas.

---

## Cron Jobs

| Job | Comando | Frequencia | Descricao |
|-----|---------|------------|-----------|
| Diario Oficial | `./run.sh cron-diario` | Diaria | Baixa DOU e gera resumo de atos |
| Qdrant Indexer | `./run.sh cron-qdrant` | Semanal | Indexa dados de deputados no Qdrant (23 chunk types) |
| Dossie Persona | `./run.sh cron-dossie` | Sob demanda | Gera personas analiticas via Multi-Query RAG v7 |

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
13. Portal da Transparência: requer `TRANSPARENCIA_API_KEY` no `.env` (definir via variável de ambiente)
14. Connection pooling: `psycopg2.pool.ThreadedConnectionPool` (min=2, max=10)
15. RREO A03 (`--rreo`): usa `nr_periodo=6` (consolidação anual), parser normaliza acentos
16. VRAM LocalAI: sempre invocar `localai_manager.ensure_model_loaded(model)` antes de requisições pesadas para evitar crash de GPU
17. Qdrant: atualizado para **v1.19.0**. Collection `deputados_perfis` requer embedding `embeddinggemma-300m` (768d) — não misturar dimensões (nomic-embed-text-v1.5 foi substituído)
18. MCP Tool Bridge: `mcp_tool_bridge.py` depende de `localai_manager` — verificar GPU antes de invocar
19. Diario Oficial: worker (`diario_oficial_worker.py`) faz scraping web — quebra se layout do DOU mudar
20. RAG v7: `PREPARER_MODEL` (zero-gemma4, 21.9 tok/s) substituiu qwen2.5-1.5b no PromptPreparer — qwen dava timeout; cada analista tem QC próprio e ativação adaptativa (`get_active_analysts()`)
21. Migrations 015-025: série `parlamentar_id` unifica a identidade do parlamentar (JOIN por ID em vez de nome/ILIKE) — novas queries devem usar `parlamentar_id` quando disponível
22. vLLM: `USE_LOCAL_VLLM`/`USE_MODAL_VLLM` no `.env`; local roda na porta 8001 (não conflitar com LocalAI :8080). `models_config.py` altera YAMLs do LocalAI em disco — revisar antes de `docker restart`
23. **Qdrant Indexação em Lote**: Ao rodar `./run.sh cron-qdrant --todos`, o script ignora a flag se o tipo for `deputado`. Para processar todos os deputados de uma vez, é OBRIGATÓRIO passar `--limit 600` (ou valor maior).
24. **LocalAI GPU**: Modelos baixados da galeria (como `embeddinggemma-300m` e `gemma-4`) podem vir sem YAML local, caindo para CPU-fallback (`cpu-llama-cpp`). Para forçar aceleração via GPU, deve-se criar manualmente o YAML (ex: `embeddinggemma-300m.yaml`) definindo `backend: cuda13-llama-cpp` e `gpu_layers: 40`.
25. **Integração API Câmara**: Os scripts `votacoes_camara.py` e `camara_discursos.py` buscam dados nativamente da API REST da Câmara (dadosabertos.camara.leg.br) para 2026, ignorando o proxy local do DuckDB (utilizado para dados históricos do TSE).

---

## Referência

- `references/mcp-brasil/` — MCP server gov.br (533 tools, 70 features)
- `docs/MIGRATIONS.md` — Ordem correta das migrations (002-014)
- `data/schema.sql` — Schema completo do banco
