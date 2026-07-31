# Plano: Skills de Manutenção para TransfereGov API

## Diagnóstico do Estado Atual

### Subsistemas do Projeto

| # | Subsistema | Escopo | Skills Existentes | GAP |
|---|-----------|--------|-------------------|-----|
| 1 | **Extração** | CLI + API Transferegov, Pydantic, cache | `transferegov-api` ✅ | OK |
| 2 | **Enriquecimento** | 25+ scripts, 8 fases, 10+ APIs externas | NENHUMA | CRÍTICO |
| 3 | **PostgreSQL** | 20+ tabelas, 6 views, 19 migrations, upsert | NENHUMA | CRÍTICO |
| 4 | **Dashboard** | 68 gráficos, 17 módulos, Dash 4.3+ | `transferegov-charts` ✅ | Parcial |
| 5 | **API Web** | FastAPI, 38 endpoints, 8 routers, 4 services | NENHUMA | ALTO |
| 6 | **RAG** | Qdrant + LocalAI, embeddings 768d, personas | NENHUMA | ALTO |
| 7 | **LocalAI** | 7 modelos, VRAM, benchmarks, gerenciamento | NENHUMA | ALTO |
| 8 | **Cron Jobs** | DOU worker, Qdrant indexer, dossier | NENHUMA | MÉDIO |
| 9 | **CLI/Tools** | run.sh, followup, redator oficial | NENHUMA | MÉDIO |
| 10 | **Testes** | 4 arquivos pytest (tests/), cobertura baixa | NENHUMA | MÉDIO |

### Skills Existentes (5)

1. `transferegov-api` v2.0 — Extração (bom, completo)
2. `transferegov-charts` v1.0 — Gráficos (bom, com pitfalls SICONFI)
3. `transferegov-dashboard` v1.0 — Dashboard legado (substituído por src/dash_app.py + src/graphs/)
4. `transferegov-mcp-integration` v1.0 — MCP setup (bom)
5. `brazilian-gov-data` v1.0 — Padrões gov APIs (bom)

### Skills Genéricas Relevantes

- `data-extraction-pipeline` — Pattern genérico
- `systematic-debugging` — Debug 4 fases
- `plan` — Modo planejamento

---

## Plano de Criação: 7 Novas Skills

### Prioridade 1 (CRÍTICO) — Criar imediatamente

#### Skill 1: `transferegov-enrichment`

**Por quê**: O pipeline de enriquecimento tem 25+ scripts com 25 pitfalls documentados,
dependências entre fases, rate limits, APIs externas que quebram, e nenhuma skill que
guie um agente na manutenção. É o subsistema mais frágil e com mais falhas potenciais.

**Conteúdo**:
- Mapeamento completo das 8 fases + scripts auxiliares
- Tabela de dependências entre fases (ex: ibge.py ANTES de ibge_agregados.py)
- Comandos exatos para cada fase com --dry-run
- Checklist de troubleshooting por API fonte (BrasilAPI, IBGE, SICONFI, Câmara, TSE, Senado, etc.)
- Pitfalls 1-25 do enrichers/AGENTS.md traduzidos para guia de ação
- Rate limits e bloqueios de IP por API
- Como verificar cobertura antes de criar gráficos
- Multi-year enrichment (DCA 2023-2025, RREO por ano)
- Comandos SQL de verificação de cobertura

**Trigger**: "manutenção enricher", "enriquecimento quebrou", "siconfi falhou", "fase X do pipeline", "rate limit API gov"

---

#### Skill 2: `transferegov-database`

**Por quê**: 20+ tabelas, 19 migrations (com numeração inconsistente — migration_014 e _015 duplicados),
6 views, funções upsert, e connection pooling. Nenhum skill cobre manutenção do schema,
criação de migrations, ou debug de queries SQL.

**Conteúdo**:
- Schema completo das 20+ tabelas (dim + fact + enriquecimento)
- Ordem correta das migrations (docs/MIGRATIONS.md como fonte)
- Padrões de migration:命名, números, colunas
- Padrão upsert_plano_acao() e como criar novos upserts
- Views existentes e como mantê-las
- Connection pooling (psycopg2.pool, min=2, max=10)
- Comandos SQL de verificação de integridade
- Como adicionar coluna/tabela nova (migration + enricher + view)
- Padrão de colunas nullable vs NOT NULL
- Decimal → float conversion no db_service
- Padrão RealDictCursor para APIs

**Trigger**: "criar migration", "schema do banco", "tabela nova", "query SQL", "upsert", "conexao banco"

---

### Prioridade 2 (ALTO) — Criar em seguida

#### Skill 3: `transferegov-api-webapp`

**Por quê**: FastAPI com 38 endpoints, 8 routers, 4 services, padrão fallback
(busca local → Câmara → degrada graceful), SPA vanilla com Plotly.js, e nenhuma
skill para manutenção. Novos endpoints seguem padrão específico que o agente precisa conhecer.

**Conteúdo**:
- Estrutura: app.py → routes/ → services/ → static/
- Padrão de rota: decorator + db_service + fallback camara_service
- Padrão de fallback: local DB → API Câmara → degrade graceful
- Como criar novo endpoint (route + service function + DB query)
- Padrão de paginação e filtros
- SPA vanilla: index.html + app.js (1400+ linhas) + Plotly.js
- CORS config, startup events
- Padrão MCP-Brasil integration (executar_lote, executar_lote_async)
- Cache em memoria com TTL no camara_service
- Testes: como testar endpoints (pytest + httpx)
- Padrão Decimal → float para JSON serialization
- Convenções de URL: /api/v1/{recurso}/{acao}

**Trigger**: "criar endpoint", "rota nova", "API FastAPI", "fallback", "serviço", "SPA frontend"

---

#### Skill 4: `transferegov-rag`

**Por quê**: Pipeline RAG v3 com Qdrant + LocalAI, 6 tipos de chunks, embeddings 768d,
Multi-Query com 5 queries temáticas, e personas geradas por IA. Sistema complexo
com múltiplos pontos de falha (GPU, dimensão de embedding, collection state).

**Conteúdo**:
- Arquitetura: PostgreSQL → Qdrant (indexer) → LocalAI (persona)
- 6 tipos de chunks: perfil, proposicao, emenda, voto, diario_oficial, conexao_politica
- Modelo: nomic-embed-text-v1.5 (768d), NUNCA misturar dimensões
- Collection: deputados_perfis
- Comandos: cron-qdrant, cron-dossie, --rebuild, --nome, --lote
- 5 queries temáticas do Multi-Query RAG
- Troubleshooting: Qdrant down, embedding model not loaded, empty chunks
- Verificação de integridade: quantos deputados indexados, qualidade dos chunks
- RAG_MIN_CHUNKS / RAG_MAX_CHUNKS thresholds
- Persona versioning (RAG_PERSONA_VERSION)
- Reindexação seletiva vs rebuild completo

**Trigger**: "RAG", "Qdrant", "persona", "dossiê", "indexação", "embedding", "chunks"

---

#### Skill 5: `transferegov-localai`

**Por quê**: 7 modelos categorizados, gerenciamento de VRAM, benchmarks, e dependência
cruzada com RAG + votacoes_temas + diario_oficial. Erros de GPU (OOM, RPC EOF)
são os bugs mais difíceis de debugar.

**Conteúdo**:
- 7 modelos: gemma, fast, analysis, code, general, embedding, router
- Velocidades validadas (36.8, 88.9, 7.7 tok/s)
- LocalAIManager: ensure_model_loaded(), is_model_loaded(), unload_model()
- LocalAIClient: chat completion, retry, timeout, streaming
- MCP Tool Bridge: ponte MCP ↔ LLM local
- GPU VRAM: gestão de exclusividade entre modelos
- Quando usar qual modelo (tabela de decisão)
- Benchmark suite: scripts/benchmark_models.py
- Troubleshooting: OOM, RPC EOF, modelo não encontrado
- Dual-backend: CUDA13 + Vulkan
- Config: LOCALAI_BASE_URL, LOCALAI_TIMEOUT, LOCALAI_MAX_RETRIES
- Dependências: votacoes_temas, diario_oficial_worker, rag_persona

**Trigger**: "LocalAI", "GPU", "VRAM", "modelo local", "benchmark", "OOM", "RPC EOF"

---

### Prioridade 3 (MÉDIO) — Criar quando possível

#### Skill 6: `transferegov-cron`

**Por quê**: 3 cron jobs (DOU diário, Qdrant semanal, dossier sob demanda) com
dependências externas (web scraping, Qdrant, LocalAI) que falham silenciosamente.

**Conteúdo**:
- 3 jobs: cron-diario, cron-qdrant, cron-dossie
- Dependências de cada job
- Como verificar status: logs, tabelas, Qdrant collection
- Troubleshooting: DOU layout mudou, Qdrant indisponível, GPU ocupada
- Como criar novo cron job no projeto
- Monitoramento: o que verificar periodicamente
- Frequências e SLAs

**Trigger**: "cron job", "diário oficial", "agendamento", "worker", "indexação automática"

---

#### Skill 7: `transferegov-testing`

**Por quê**: Testes existem mas são esparsos (test_schemas.py, test_extract.py, test_config.py,
test_deputado_followup.py). Cobertura baixa. Nenhuma skill guia criação de testes.

**Conteúdo**:
- Testes existentes: o que cobrem, o que falta
- Padrão pytest com fixtures (conexão DB, mock API)
- Como testar enrichers (dry-run pattern)
- Como testar endpoints FastAPI (httpx + TestClient)
- Como testar gráficos (safe_build_chart pattern)
- Mock de APIs externas (responses / httpx_mock)
- Fixtures de dados de teste
- CI/CD: como rodar testes automatizados
- Cobertura mínima esperada

**Trigger**: "testar", "pytest", "cobertura", "teste unitário", "mock"

---

## Atualização de Skills Existentes

### `transferegov-charts` → v2.0
- Adicionar módulos novos: economia_cruzada, intel_politica, intel_proposicoes, radar_diario, votacoes
- Atualizar contagem: 57 → 68 gráficos em 17 módulos
- Adicionar referência a novos módulos no template

### `transferegov-dashboard` → v2.0 ou remover
- Skill referencia src/dashboard.py (legado) — atualizar para src/dash_app.py
- Adicionar MCP Hub (/ _mcp endpoint)
- Adicionar verify_graphs.py como ferramenta de auditoria

### `transferegov-api` → v2.1
- Adicionar referência a src/api/ (FastAPI web app)
- Atualizar se houver mudanças no CLI

---

## Ordem de Execução

```
Fase 1 (agora):
  [1] transferegov-enrichment    ← mais frágil, mais falhas
  [2] transferegov-database      ← base de tudo

Fase 2 (depois):
  [3] transferegov-api-webapp    ← 38 endpoints sem guia
  [4] transferegov-rag           ← sistema complexo

Fase 3 (quando possível):
  [5] transferegov-localai       ← depende de [4]
  [6] transferegov-cron          ← depende de [1,4,5]
  [7] transferegov-testing       ← cross-cutting

Atualizações:
  [8] transferegov-charts v2.0   ← módulos novos
  [9] transferegov-dashboard v2.0 ← corrigir referência
```

---

## Total

- **7 skills novas** (1+1+2+2+1+1 prioridades)
- **3 skills atualizadas** (charts, dashboard, api)
- **Cobertura**: 10/10 subsistemas com skill dedicada
- **Esfogo total estimado**: ~3-4h de criação serial
