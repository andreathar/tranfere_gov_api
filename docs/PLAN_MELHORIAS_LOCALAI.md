# Plano de Melhorias — Integração LocalAI & Processos

**Data**: 2026-07-28
**Escopo**: Arquitetura de integração com modelos locais (LocalAI), qualidade de código,
testes, e organização de processos.

---

## Diagnóstico

### Módulos Analisados

| Módulo | Linhas | Responsabilidade |
|--------|--------|-----------------|
| `src/localai_manager.py` | 79 | Gerenciar exclusividade VRAM |
| `src/localai_client.py` | 582 | Cliente HTTP (chat, embeddings, streaming, jobs, DataFrame) |
| `src/mcp_tool_bridge.py` | 926 | Converter MCP tools → OpenAI format + agentic loop |
| `src/enrichers/rag_qdrant_indexer.py` | 779 | Indexar dados no Qdrant |
| `src/enrichers/rag_persona.py` | 819 | Gerar dossies via RAG multi-query |
| `src/enrichers/diario_oficial_worker.py` | 315 | NER do Diário Oficial via LLM |
| `src/enrichers/votacoes_temas.py` | 120 | Classificar temas de votações via LLM |
| `src/http_cache.py` | 82 | Cache TTL em arquivo JSON |
| `config/settings.py` | 199 | Configuração centralizada |

---

## Problemas Encontrados

### P1 — HTTP Client Duplicado (CRÍTICO)

`localai_manager.py` usa **requests** (síncrono, sem retry configurável).
`localai_client.py` e `mcp_tool_bridge.py` usam **httpx** (sync + async).

Isso significa:
- Duas dependências HTTP para o mesmo destino
- `LocalAIManager` não tem retry nem cache — falha na primeira tentativa
- `MCPToolBridge._post()` duplica a lógica de retry de `LocalAIClient._post()` sem cache

### P2 — Cache de Respostas LLM por 7 Dias (CRÍTICO)

`localai_client.py:430` — `_post()` usa TTL de 604800s (7 dias) para cache de LLM.

Problemas:
- Respostas não-determinísticas (LLM com temperature>0) são cacheadas
- Se o modelo muda/atualiza, cache fica obsoleto
- Se o prompt muda levemente, o cache retorna resultado antigo
- Não há mecanismo de invalidação seletiva (só cache_clear nuclear)

**Solução**: Cache apenas para embeddings (determinísticos). Para chat, usar TTL curto
(5 min) ou desabilitar. Separar cache de embeddings do cache de chat.

### P3 — Erro de Lógica no `is_model_loaded` (MÉDIO)

`localai_manager.py:40-41`:
```python
except requests.Timeout:
    return True  # timeout = modelo carregado?!
```

Timeout pode significar GPU sobrecarregada, não modelo carregado. Deveria
retornar `False` ou `None` (desconhecido) e deixar o caller decidir.

### P4 — `asyncio.get_event_loop()` Deprecado (MÉDIO)

`mcp_tool_bridge.py` usa `asyncio.get_event_loop().run_until_complete()` em 4
lugares. Deprecated desde Python 3.10, causa RuntimeError se chamado dentro de
um event loop ativo (ex: FastAPI, Dash).

### P5 — `run.sh` Porta Inconsistente (BAIXO)

`run.sh:90` diz porta 8080, `src/api/app.py` diz 8000. A AGENTS.md documenta 8000.

### P6 — Duplicação no `rag_persona.py` (MÉDIO)

`generate_persona_analysis()` e `_generate_with_client()` fazem essencialmente
a mesma coisa (retrieve → prompt → LLM → quality check). A primeira chama
`ensure_model_loaded` + cria client; a segunda recebe client pronto.
No modo lote (`_run_lote`), `_generate_with_client` é chamado, mas
`generate_persona_analysis` continua existindo e não é usada no lote.

### P7 — MCPToolBridge Monolítico (MÉDIO)

926 linhas com 6 responsabilidades distintas:
1. Descoberta de tools MCP
2. Conversão para formato OpenAI
3. Mapeamento de handlers Python
4. Mock de Context do FastMCP
5. Agentic loop (chat + tool calls)
6. HTTP client próprio

Deveria ser decomposto em módulos menores.

### P8 — Falta de Circuit Breaker (MÉDIO)

Se o LocalAI cai, todos os callers retry 3 vezes e falham. Não há:
- Circuit breaker para evitar spam de requests a um servidor morto
- Fallback graceful (ex: resposta "servidor indisponível" em vez de exceção)
- Métricas de falha por modelo

### P9 — Sem Testes para LocalAI (BAIXO)

5 test files para 84 source files. Zero testes para:
- `LocalAIManager` (mock de HTTP)
- `LocalAIClient` (chat, cache, retry)
- `MCPToolBridge` (tool discovery, agent loop)
- `rag_persona.py` (integration test com mock Qdrant)

### P10 — Sem Roteamento Centralizado de Modelos (BAIXO)

Cada script escolhe seu modelo diretamente via `LOCALAI_MODELS["fast"]` etc.
Não há política centralizada que considere:
- Disponibilidade do modelo
- Carga atual da GPU
- Prioridade da tarefa
- Fallback se o modelo首选 estiver indisponível

---

## Plano de Melhorias

### Fase 1 — Correções Críticas (1-2 dias)

#### 1.1 Unificar HTTP Client em `localai_manager.py`

**Objetivo**: Migrar `requests` → `httpx` no `LocalAIManager`.

```
localai_manager.py:
  - Trocar requests por httpx (sync)
  - Adicionar retry (3 tentativas, backoff exponencial)
  - Adicionar timeout configurável via settings
  - Fixar is_model_loaded: timeout → return False (não True)
```

**Arquivos**: `src/localai_manager.py`, `config/settings.py`

#### 1.2 Corrigir Cache de Respostas LLM

**Objetivo**: Separar cache de embeddings (determinístico, TTL longo) de cache
de chat (não-determinístico, TTL curto ou desabilitado).

```
localai_client.py:
  - _post() endpoint /chat/completions → ttl=300 (5 min) ou None
  - _post() endpoint /embeddings → ttl=604800 (7 dias) — manter
  - Adicionar flag enable_cache por tipo de chamada

http_cache.py:
  - Adicionar cache_invalidate(pattern) para invalidar por prefixo
```

**Arquivos**: `src/localai_client.py`, `src/http_cache.py`

#### 1.3 Corrigir Porta no `run.sh`

```
run.sh:90:
  -m uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8080
  →
  -m uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

**Arquivo**: `run.sh`

---

### Fase 2 — Qualidade de Código (2-3 dias)

#### 2.1 Refatorar `MCPToolBridge` em Módulos Menores

**Objetivo**: Decompor o monolito de 926 linhas.

```
src/mcp_tool_bridge.py (atual: 926 linhas)
  →
src/mcp/
  ├── __init__.py           (exportar MCPToolBridge)
  ├── discovery.py           (discover_tools, search_tools, TOOL_CATEGORIES)
  ├── schema_converter.py    (to_openai_tools, _function_to_openai_schema)
  ├── handler_map.py         (_build_handler_map, _resolve_handler, _wrap_no_ctx)
  ├── agent_loop.py          (agent_chat, aagent_chat)
  └── bridge.py              (MCPToolBridge - orquestra os módulos acima)
```

**Arquivos**: Novo pacote `src/mcp/`, refatorar imports em `src/localai_client.py`,
`src/dash_app.py`, `src/graph_tools.py`.

#### 2.2 Eliminar `asyncio.get_event_loop()` Deprecado

Substituir por:
```python
import asyncio
asyncio.run(self.discover_tools())  # para contextos sync isolados
```
ou criar um helper `_run_sync(coro)` que detecta se já há loop ativo.

**Arquivo**: `src/mcp_tool_bridge.py` (ou o novo `src/mcp/bridge.py`)

#### 2.3 Consolidar `_build_messages`

Criar um helper compartilhado em vez de duplicar em `LocalAIClient` e `MCPToolBridge`.

**Arquivos**: `src/localai_client.py`, `src/mcp_tool_bridge.py`

#### 2.4 Simplificar `rag_persona.py`

Mesclar `generate_persona_analysis()` com `_generate_with_client()`:
- Função única `generate_persona_analysis(ai_client=None)` — cria client se None
- Modo lote passa o client, modo single cria um novo

**Arquivo**: `src/enrichers/rag_persona.py`

#### 2.5 Fixar `votacoes_temas.py` — `ensure_model_loaded` no Loop

Chamar `ensure_model_loaded` uma vez antes do loop, não dentro de `generate_theme()`.

**Arquivo**: `src/enrichers/votacoes_temas.py`

---

### Fase 3 — Observabilidade & Resiliência (2-3 dias)

#### 3.1 Circuit Breaker para LocalAI

Implementar padrão circuit breaker simples:

```python
# src/localai_circuit.py
class LocalAICircuitBreaker:
    """Circuit breaker: OPEN (bloqueia) após N falhas consecutivas,
    HALF-OPEN (testa) após cooldown, CLOSED (normal)."""

    states: OPEN | HALF_OPEN | CLOSED
    failure_threshold = 5
    recovery_timeout = 60s
```

Integrar em `LocalAIClient._post()` e `MCPToolBridge._post()`.

**Arquivo novo**: `src/localai_circuit.py`

#### 3.2 Métricas de Uso de Modelos

```python
# src/localai_metrics.py
class LocalAIMetrics:
    """Rastreia chamadas por modelo: latência, tokens, erros."""

    def record_call(self, model: str, latency_ms: float, tokens: int, error: bool)
    def summary(self) -> dict  # por modelo
    def export_prometheus(self) -> str  # formato Prometheus
```

Integrar em `LocalAIClient._post()` — hook mínimo, sem overhead.

**Arquivo novo**: `src/localai_metrics.py`

#### 3.3 Health Check Integrado

Adicionar ao `LocalAIManager`:
- `health_check(model=None)` → status de cada modelo carregado
- Usar no início de cada pipeline (rag, votacoes_temas, diario_oficial)
- Logar estado da GPU antes de iniciar batch pesado

**Arquivo**: `src/localai_manager.py`

#### 3.4 Timeouts por Modelo

Configurar timeout diferente por modelo (os rápidos precisam menos, os pesados mais):

```python
LOCALAI_MODEL_TIMEOUTS = {
    "fast": 60,       # qwen2.5-1.5b: 88.9 tok/s
    "gemma": 120,     # gemma-4-e2b: 36.8 tok/s
    "analysis": 300,  # llama-3.1-8b: 7.7 tok/s
    "embedding": 30,  # nomic: CPU, rápido
}
```

**Arquivo**: `config/settings.py`, `src/localai_client.py`

---

### Fase 4 — Testes (2-3 dias)

#### 4.1 Testes Unitários — LocalAI

```python
tests/test_localai_manager.py
  - test_get_all_models (mock httpx)
  - test_is_model_loaded_true/false/timeout
  - test_unload_model_success/failure
  - test_ensure_model_loaded_unloads_others

tests/test_localai_client.py
  - test_chat_basic
  - test_chat_json_with_markdown_wrapper
  - test_chat_json_repair
  - test_embed_batch
  - test_cache_hit_miss
  - test_retry_on_failure
  - test_classify_batch
  - test_enrich_column
```

#### 4.2 Testes Unitários — MCPToolBridge

```python
tests/test_mcp_tool_bridge.py
  - test_to_openai_tools_format
  - test_function_to_openai_schema
  - test_handler_map_resolution
  - test_wrap_no_ctx
  - test_agent_chat_single_turn
  - test_agent_chat_max_turns
```

#### 4.3 Testes de Integração — RAG

```python
tests/test_rag_persona.py
  - test_search_context_multiquery (mock Qdrant)
  - test_build_analysis_prompt_adapts
  - test_validate_prompt_size_truncates
  - test_check_quality_all_sections
  - test_generate_persona_analysis (mock Qdrant + LocalAI)
```

**Arquivos**: `tests/test_localai_*.py`, `tests/test_mcp_*.py`, `tests/test_rag_*.py`

---

### Fase 5 — Otimizações (1-2 dias)

#### 5.1 Roteamento Centralizado de Modelos

Criar um router que escolhe o melhor modelo disponível:

```python
# src/model_router.py
class ModelRouter:
    """Escolhe o melhor modelo para uma tarefa dado VRAM, latência e qualidade."""

    def select(self, task_type: str) -> str:
        """
        task_type:
          - "ner" → fast (qwen2.5-1.5b)
          - "analysis" → gemma (padrão) ou llama (se dados >5k tokens)
          - "classification" → fast
          - "embedding" → nomic
          - "dossier" → RAG_LLM_MODEL
        """
```

Substituir as escolhas diretas nos scripts por chamadas ao router.

**Arquivo novo**: `src/model_router.py`

#### 5.2 Reutilizar Conexões HTTP

`LocalAIClient` cria um novo `httpx.Client` a cada chamada em `_post()`.
Deveria usar um client reutilizado (connection pooling do httpx):

```python
def __init__(self, ...):
    self._http_client = httpx.Client(timeout=self.timeout)
    self._http_async_client = httpx.AsyncClient(timeout=self.timeout)
```

**Arquivo**: `src/localai_client.py`

#### 5.3 Batch Embedding Otimizado

`rag_persona.py` chama `embed_text_batch(QUERIES_TEMATICAS)` (5 textos) — isso
já é bom. Mas `rag_qdrant_indexer.py` chama `embed_text_batch` por deputado.
Se tiver 500 deputados com ~20 chunks cada = 10.000 embeds.
Deveria agrupar tudo em batches maiores (500-1000) para melhor throughput.

**Arquivo**: `src/enrichers/rag_qdrant_indexer.py`

---

## Priorização

| Fase | Impacto | Esforço | Prioridade |
|------|---------|---------|------------|
| 1.1 Unificar HTTP Client | Alto | Baixo | P0 |
| 1.2 Corrigir Cache LLM | Alto | Baixo | P0 |
| 1.3 Fixar Porta | Baixo | Mínimo | P1 |
| 2.1 Refatorar MCPToolBridge | Alto | Médio | P1 |
| 2.2 Fix asyncio deprecado | Médio | Baixo | P1 |
| 2.3 Consolidar _build_messages | Médio | Baixo | P2 |
| 2.4 Simplificar rag_persona | Médio | Baixo | P2 |
| 2.5 Fix votacoes_temas loop | Médio | Mínimo | P2 |
| 3.1 Circuit Breaker | Alto | Médio | P2 |
| 3.2 Métricas de Modelos | Médio | Médio | P2 |
| 3.3 Health Check | Médio | Baixo | P2 |
| 3.4 Timeouts por Modelo | Médio | Baixo | P2 |
| 4.1-4.3 Testes | Alto | Médio | P2 |
| 5.1 Model Router | Médio | Médio | P3 |
| 5.2 Reutilizar Conexões | Médio | Baixo | P3 |
| 5.3 Batch Embedding | Baixo | Baixo | P3 |

---

## Dependências

- Fase 1 não depende de nada (correções isoladas)
- Fase 2 depende de Fase 1 (unificar client antes de refatorar bridge)
- Fase 3 depende de Fase 1 (circuit breaker precisa de client unificado)
- Fase 4 pode rodar em paralelo com Fase 2/3
- Fase 5 depende de Fase 1+2 (router precisa de client refatorado)

---

## Estimativas

| Fase | Dias | Difícil? |
|------|------|----------|
| Fase 1 | 1-2 | Não — correções cirúrgicas |
| Fase 2 | 2-3 | Moderado — refatoração com cuidado |
| Fase 3 | 2-3 | Moderado — padrões novos |
| Fase 4 | 2-3 | Não — testes com mocks |
| Fase 5 | 1-2 | Não — otimizações incrementais |
| **Total** | **8-13** | |

---

## Riscos

1. **Refatorar MCPToolBridge** pode quebrar imports em `dash_app.py`, `graph_tools.py`,
   `api/services/mcp_service.py` — testar após cada mudança
2. **Cache de LLM** pode ter consumers que dependem do cache de 7 dias (ex: cron jobs
   que rodam frequentemente) — validar com `./run.sh cron-dossie`
3. **Migrar requests → httpx** no manager: testar com LocalAI real antes de commit
4. **Testes**: precisam mockar Qdrant + LocalAI — criar fixtures compartilhadas

---

## Métricas de Sucesso

- [ ] Zero imports de `requests` nos módulos LocalAI (usar apenas `httpx`)
- [ ] Cache de chat com TTL ≤ 5min ou desabilitado
- [ ] `is_model_loaded` retorna `False` em timeout
- [ ] `run.sh` porta consistente (8000)
- [ ] MCPToolBridge < 400 linhas (após decomposição)
- [ ] Testes cobrindo: LocalAIManager, LocalAIClient, MCPToolBridge, rag_persona
- [ ] Circuit breaker funcional com logs
- [ ] Métricas de latência por modelo visíveis em logs
