# Integracao LocalAI — Modelos Locais, Gerenciamento de VRAM e Agentic Loop

Documentacao da infraestrutura de IA local do projeto TransfereGov. Coberta completa dos
tres modulos que compoem o sistema, desde o gerenciamento de GPU ate o loop agentic
com ferramentas governamentais.

---

## Sumario

1. [Visao Geral](#visao-geral)
2. [Pre-requisitos](#pre-requisitos)
3. [Modelos Configurados](#modelos-configurados)
4. [Gerenciamento de VRAM](#gerenciamento-de-vram)
5. [Cliente OpenAI-Compativel](#cliente-openai-compativel)
6. [MCP Tool Bridge](#mcp-tool-bridge)
7. [Consumidores](#consumidores)
8. [Benchmarks](#benchmarks)
9. [Variaveis de Ambiente](#variaveis-de-ambiente)
10. [Troubleshooting](#troubleshooting)
11. [Exemplos de Uso](#exemplos-de-uso)

---

## Visao Geral

A infraestrutura de IA local e composta por tres modulos que trabalham em camadas:

```
  Camada Aplicacional
  +------------------------------------------+
  |  rag_persona  |  votacoes_temas  |  ...   |  Consumidores
  +------------------------------------------+
  |  MCPToolBridge (15 categorias de tools)  |  Bridge
  +------------------------------------------+
  |  LocalAIClient (chat, embed, classify)   |  Cliente
  +------------------------------------------+
  |  LocalAIManager (VRAM exclusiva)         |  Gerenciador
  +------------------------------------------+
  |  LocalAI Server (http://localhost:8080)   |  Servidor
  +------------------------------------------+
```

### Modulo 1: LocalAIManager (`src/localai_manager.py`)

Responsavel pelo gerenciamento exclusivo de VRAM na GPU. Garante que apenas um modelo
esteja carregado por vez, descarregando inativos antes de invocar um novo.

### Modulo 2: LocalAIClient (`src/localai_client.py`)

Cliente HTTP que expoe uma API de alto nivel sobre o endpoint OpenAI-compatible do LocalAI.
Inclui chat síncrono e assincrono, streaming, classificacao em lote, embeddings, jobs
assincronos, enriquecimento de DataFrames e integracao com o MCPToolBridge.

### Modulo 3: MCPToolBridge (`src/mcp_tool_bridge.py`)

Ponte entre as ferramentas MCP (FastMCP) do mcp-brasil e o formato OpenAI function calling.
Permite que modelos locais invoquem automaticamente tools governamentais (camara, IBGE,
SICONFI, Diario Oficial, etc.) em um loop agentic de multiplas iteracoes.

---

## Pre-requisitos

### Servidor LocalAI

O sistema depende de uma instancia do LocalAI rodando com suporte a GPU (CUDA).

- **URL padrao**: `http://localhost:8080/v1`
- **Compatibilidade**: API OpenAI (`/v1/chat/completions`, `/v1/embeddings`, `/v1/models`)
- **Endpoints administrativos**: `/backend/monitor`, `/backend/shutdown`
- **Endpoint de jobs**: `/v1/jobs` (quando disponivel — fallback síncrono automatico)

O LocalAI deve estar configurado com backends GPU (cuda13-llama-cpp ou similar) e os
modelos GGUF ja baixados.

### GPU

- **Memoria minima**: variavel conforme os modelos carregados (ver tabela abaixo)
- **Exclusividade**: o `LocalAIManager` garante que apenas um modelo utiliza VRAM por vez
- **Monitoramento**: via `/backend/monitor` (retorna status de carregamento)

### Servicos Dependentes

| Servico | URL | Uso |
|---------|-----|-----|
| PostgreSQL | `127.0.0.1:5432` | Persistencia de resultados, personas, NER |
| Qdrant | `http://localhost:6333` | Busca vetorial para RAG (colecao `deputados_perfis`) |
| MCP-Brasil | via FastMCP | 435+ tools governamentais para o agentic loop |

---

## Modelos Configurados

Sete categorias de modelos estao registradas em `config.settings.LOCALAI_MODELS`:

| Chave | Modelo | Uso Principal | Velocidade |
|-------|--------|---------------|------------|
| `gemma` | `gemma-4-e2b-it` | Analise de dossies, redacao em PT-BR | 36.8 tok/s |
| `analysis` | `llama-3.1-8b-q4-k-m` | Analise investigativa profunda, auditoria | 7.7 tok/s |
| `code` | `Qwen2.5-Coder-7B-Instruct-GGUF` | Geracao e analise de codigo | -- |
| `fast` | `qwen2.5-1.5b-instruct-q4-k-m` | Triagem diaria, NER, classificacao rapida | 88.9 tok/s |
| `general` | `gemma-4-e2b-it` | Uso geral (mesmo que gemma) | 36.8 tok/s |
| `embedding` | `nomic-embed-text-v1.5` | Vetores de embedding (768 dim) | -- |
| `router` | `intelligent-router` | Roteamento inteligente de queries | -- |

**Modelo padrao**: `gemma-4-e2b-it` (definido como `LOCALAI_DEFAULT_MODEL`).

### Configuracao no settings.py

```python
LOCALAI_BASE_URL = os.getenv("LOCALAI_BASE_URL", "http://localhost:8080/v1")
LOCALAI_TIMEOUT = int(os.getenv("LOCALAI_TIMEOUT", "300"))   # segundos
LOCALAI_MAX_RETRIES = int(os.getenv("LOCALAI_MAX_RETRIES", "3"))

LOCALAI_MODELS = {
    "gemma": "gemma-4-e2b-it",
    "analysis": "llama-3.1-8b-q4-k-m",
    "code": "Qwen2.5-Coder-7B-Instruct-GGUF",
    "fast": "qwen2.5-1.5b-instruct-q4-k-m",
    "general": "gemma-4-e2b-it",
    "embedding": "nomic-embed-text-v1.5",
    "router": "intelligent-router",
}

LOCALAI_DEFAULT_MODEL = LOCALAI_MODELS["gemma"]
```

---

## Gerenciamento de VRAM

O `LocalAIManager` (singleton acessivel via `from src.localai_manager import manager`)
implementa exclusividade de VRAM: apenas um modelo deve estar na memoria da GPU por vez.

### Metodos

| Metodo | Descricao |
|--------|-----------|
| `get_all_models()` | Retorna lista de IDs de todos os modelos configurados no LocalAI |
| `is_model_loaded(model_id)` | Verifica se um modelo especifico esta na memoria (via `/backend/monitor`) |
| `unload_model(model_id)` | Forca o descarregamento do backend de um modelo (via `/backend/shutdown`) |
| `ensure_model_loaded(target_model)` | Garante exclusividade: descarrega todos os outros e mantem apenas o alvo |

### Padrao de uso: ensure_model_loaded

Todo consumidor DEVE chamar `ensure_model_loaded()` antes de invocar um modelo.
Isso evita erros OOM (Out of Memory) e RPC EOF que ocorrem quando dois modelos
competem pela mesma VRAM.

```python
from src.localai_manager import manager as localai_manager
from config.settings import LOCALAI_MODELS

# 1. Garantir exclusividade de VRAM
llm_model = LOCALAI_MODELS["gemma"]
localai_manager.ensure_model_loaded(llm_model)

# 2. Agora e seguro invocar o modelo
from src.localai_client import LocalAIClient
client = LocalAIClient(model=llm_model)
resposta = client.chat("Analise o plano de acao...")
```

### Fluxo interno do ensure_model_loaded

```
ensure_model_loaded("gemma-4-e2b-it")
  |
  +-- get_all_models()          --> lista todos os modelos registrados
  |
  +-- para cada modelo m != target:
  |     +-- is_model_loaded(m)  --> verifica via /backend/monitor
  |     +-- unload_model(m)     --> descarrega via /backend/shutdown
  |
  +-- "O ambiente esta limpo e pronto para invocar gemma-4-e2b-it"
```

**Nota**: a chamada `is_model_loaded()` retorna `True` em caso de timeout da requisicao
HTTP (3s), assumindo que o modelo esta ocupado e nao deve ser interrompido.

---

## Cliente OpenAI-Compativel

O `LocalAIClient` (`src/localai_client.py`) e o ponto de entrada principal para
todas as operacoes de IA local. Acesso singleton via `get_localai_client()`.

### Inicializacao

```python
from src.localai_client import LocalAIClient, get_localai_client

# Instancia com config padrao
client = get_localai_client()

# Instancia com config customizada
client = LocalAIClient(
    base_url="http://localhost:8080/v1",
    model="gemma-4-e2b-it",
    timeout=300,
)
```

### Metodos de Chat

#### `chat(prompt, *, system, model, temperature, max_tokens) -> str`

Chat completion síncrono simples. Retorna a resposta como string.

- **system**: prompt de sistema opcional
- **temperature**: padrao 0.3 (baixa variabilidade)
- **max_tokens**: padrao 2048
- **cache**: respostas sao cacheadas por 7 dias (TTL 604800s)

#### `achat(prompt, *, system, model, temperature, max_tokens) -> str`

Versao assincrona do `chat`. Mesma interface, retorna `str`.

#### `chat_json(prompt, *, system, model, temperature, max_tokens) -> Any`

Chat que espera JSON como resposta. Instrui o modelo a retornar apenas JSON valido,
faz limpeza automatica de wrappers markdown, e parseia com `json_repair` (fallback
para `json.loads`).

- **temperature**: padrao 0.1 (quase deterministico)

#### `chat_stream(prompt, *, system, model, temperature, max_tokens) -> Iterator[str]`

Chat com streaming. Faz yield de chunks de texto conforme recebidos via SSE.

```python
for chunk in client.chat_stream("Descreva o plano de acao..."):
    print(chunk, end="", flush=True)
```

### Classificacao em Lote

#### `classify_batch(texts, *, labels, model, batch_size) -> list[str]`

Classifica textos em labels predefinidos usando chamadas em lote.

- **texts**: sequencia de strings para classificar
- **labels**: categorias permitidas (ex: `["APROVADO", "NEGADO", "PENDENTE"]`)
- **batch_size**: padrao 10 textos por chamada ao LLM

O metodo numeraca os textos, envia ao LLM com instrucao de retornar apenas as labels
uma por linha, e faz parsing do resultado. Se o LLM retornar menos labels que textos,
o label padrao (primeiro da lista) e usado como fallback.

### Embeddings

#### `embed(texts, *, model) -> list[list[float]]`

Gera vetores de embedding para uma lista de textos. Usa o modelo `nomic-embed-text-v1.5`
por padrao (768 dimensoes).

```python
vectors = client.embed(["texto 1", "texto 2", "texto 3"])
# vectors[0] -> [0.012, -0.034, ...] (768 floats)
```

### Jobs Assincronos

#### `submit_job(prompt, *, system, model, callback_url, metadata) -> dict`

Submete um job assincrono ao endpoint `/v1/jobs` do LocalAI. Se o endpoint nao estiver
disponivel (HTTP 404), faz fallback automatico para execucao síncrona via `_sync_fallback`.

#### `poll_job(job_id) -> dict`

Verifica o status de um job assincrono.

#### `wait_for_job(job_id, *, poll_interval, max_wait) -> dict`

Bloqueia ate o job completar ou atingir o timeout. Estados finais: `completed`/`succeeded`
(retorna resultado) ou `failed`/`cancelled` (levanta `RuntimeError`).

- **poll_interval**: padrao 2.0 segundos
- **max_wait**: padrao 600.0 segundos (10 minutos)

### Helpers de DataFrame

#### `enrich_column(df, column, *, task, new_column, model, batch_size) -> pd.DataFrame`

Aplica uma tarefa de IA em cada valor de uma coluna do DataFrame. A instrucao `task`
deve conter `{text}` como placeholder que sera substituido pelo valor da coluna.

```python
df = client.enrich_column(
    df,
    "motivo_impedimento",
    task="Classifique o motivo: {text}",
    new_column="motivo_categoria",
)
```

- **new_column**: padrao e `f"{column}_ai"`
- **batch_size**: padrao 10
- Erros sao tratados individualmente (registro recebe `ERRO: ...`)

#### `summarize_plans(df, *, group_by, value_col, situation_col, model) -> pd.DataFrame`

Gera resumos de IA para grupos de planos de acao. Faz aggregate por `group_by` (default:
`parlamentar_nome`), contagem e soma por situacao, e envia ao LLM para gerar narrativa
analitica de ate 3 frases.

### Integracao com Tool Calling

#### `chat_with_tools(prompt, *, system, model, categories, max_tools, max_turns) -> dict`

Chat com acesso a ferramentas MCP via `MCPToolBridge.agent_chat()`. O modelo pode chamar
tools governamentais automaticamente para responder perguntas.

#### `achat_with_tools(prompt, *, system, model, categories, max_tools, max_turns) -> dict`

Versao assincrona do `chat_with_tools`.

### Health Check

#### `health() -> dict`

Verifica se o LocalAI esta respondendo e lista os modelos disponiveis.

Retorno quando operacional:
```python
{
    "status": "ok",
    "base_url": "http://localhost:8080/v1",
    "models_count": 5,
    "models": ["gemma-4-e2b-it", "llama-3.1-8b-q4-k-m", ...]
}
```

Retorno em caso de erro:
```python
{"status": "error", "error": "...", "base_url": "http://localhost:8080/v1"}
```

### Mecanismos Internos

#### Cache HTTP

Todas as chamadas passam por `cache_get`/`cache_set` (modulo `src/http_cache.py`)
com TTL padrao de 7 dias (604800 segundos). O cache usa hash do payload como chave.

#### Retry com Backoff

Em caso de falha, o cliente repete a requisicao ate `LOCALAI_MAX_RETRIES` vezes
(padrao 3) com backoff exponencial (2^attempt segundos).

---

## MCP Tool Bridge

O `MCPToolBridge` (`src/mcp_tool_bridge.py`) converte ferramentas MCP (FastMCP) do
mcp-brasil para o formato OpenAI function calling, permitindo que modelos locais invoquem
tools governamentais.

### Categorias de Tools (TOOL_CATEGORIES)

15 categorias estao definidas para filtragem:

| Categoria | Prefixos / Descricao |
|-----------|---------------------|
| `transferegov` | `transferegov` |
| `camara` | `camara` |
| `senado` | `senado` |
| `tse` | `tse` |
| `ibge` | `ibge` |
| `siconfi` | `siconfi` |
| `compras` | `compras`, `pncp`, `contratosgovbr`, `dadosabertos` |
| `saude` | `saude`, `farmacia_popular`, `rename`, `denasus`, `imunizacao`, `opendatasus` |
| `educacao` | `inep`, `fnde` |
| `seguranca` | `atlas_violencia`, `forum_seguranca`, `mj`, `sinesp` |
| `ambiental` | `ibama`, `inpe` |
| `financeiro` | `bacen`, `bcb_olinda`, `b3`, `bndes`, `bps` |
| `judicial` | `datajud`, `jurisprudencia`, `tcu` |
| `diario_oficial` | `diario_oficial` |
| `dashboard` | `list_registered_charts`, `inspect_chart_health`, `get_chart_data_summary` |
| `meta` | `listar_features`, `recomendar_tools`, `planejar_consulta`, `executar_lote`, `listar_datasets_disponiveis` |

### Descoberta de Tools

O bridge usa tres mecanismos de descoberta:

1. **`discover_tools()`**: Varre o servidor MCP listando tools registradas via
   `mcp.list_tools()`, incluindo o `_tool_cache` interno do mcp-brasil.

2. **`search_tools_via_mcp()`**: Usa a meta-tool `search_tools` do mcp-brasil
   para busca em linguagem natural (BM25 search transform).

3. **`_build_handler_map()`**: Mapeamento direto de funcoes Python dos modulos
   mcp-brasil (sem necessidade de session MCP). Modulos importados:
   - `mcp_brasil.data.ibge.tools`
   - `mcp_brasil.data.camara.tools`
   - `mcp_brasil.data.transferegov.tools`
   - `mcp_brasil.data.siconfi.tools`
   - `mcp_brasil.data.brasilapi.tools`
   - `mcp_brasil.data.transparencia.tools`
   - `mcp_brasil.data.bacen.tools`
   - `mcp_brasil.data.diario_oficial.tools`
   - `mcp_brasil.agentes.redator.tools`

Cada funcao Python e envelopada com `_wrap_no_ctx()`, que injeta um mock minimo do
parametro `ctx` do FastMCP, permitindo chamada sem sessao MCP.

### Conversao para OpenAI Format

`to_openai_tools(categories, max_tools, search, include_meta)` converte tools MCP
para o formato:

```json
[{
    "type": "function",
    "function": {
        "name": "camara_buscar_deputado",
        "description": "...",
        "parameters": {"type": "object", "properties": {...}, "required": [...]}
    }
}]
```

Meta-tools (`search_tools`, `call_tool`, etc.) sao incluidas automaticamente quando
`include_meta=True`, permitindo que o modelo descubra e invoque qualquer uma das
435+ tools do mcp-brasil.

### Execucao de Tools

`execute_tool(name, arguments)` resolve e executa uma tool seguindo esta cadeia:

1. **Handler customizado** (registrado via `register_tool()`)
2. **Handler map** (funcao Python do mcp-brasil, resolvido direto)
3. **MCP call_tool** (fallback via sessao MCP — pode falhar sem session)

### Agentic Loop

`agent_chat()` implementa o loop completo chat + tool calling:

```
1. Montar tools_schema (to_openai_tools com categorias filtradas)
2. Montar messages (system prompt + user prompt)
3. Para cada turn (ate max_turns):
   a. Enviar payload para LocalAI (/chat/completions)
   b. Se a resposta NAO contem tool_calls -> retornar texto final
   c. Se contem tool_calls:
      - Para cada tool_call: parsear arguments, executar tool
      - Adicionar resultado como "role": "tool" nas messages
      - Continuar para proximo turn
4. Retornar: {"response", "tool_calls", "turns", "tools_available"}
```

**Parametros**:

| Parametro | Padrao | Descricao |
|-----------|--------|-----------|
| `max_tools` | 30 | Maximo de tools expostas ao modelo |
| `max_turns` | 5 | Maximo de iteracoes tool -> response |
| `temperature` | 0.3 | Temperatura do modelo |
| `include_meta_tools` | True | Incluir search_tools, recomendar_tools, etc. |

**System prompt padrao** (quando nao fornecido):

> Voce e um assistente de IA com acesso a ferramentas de dados governamentais brasileiros.
> Use as ferramentas disponíveis para responder perguntas sobre transferencias, emendas,
> municipios, financas publicas e dados abertos.

**Retorno**:

```python
{
    "response": "Texto final gerado pelo modelo",
    "tool_calls": [
        {"tool": "camara_buscar_deputado", "arguments": {"nome": "..."}, "result_preview": "..."}
    ],
    "turns": 3,
    "tools_available": 28
}
```

### Registro de Tools Customizadas

```python
bridge = get_mcp_bridge()
bridge.register_tool(
    name="meu_tool_custom",
    description=" descricao da tool",
    parameters={"type": "object", "properties": {...}},
    handler=minha_funcao,
    category="local",
)
```

---

## Consumidores

### rag_persona (`src/enrichers/rag_persona.py`)

Gerador de dossies analiticos de deputados. Implementa RAG v2 (multi-query) com 5
queries tematicas:

1. Padrao de voto e alinhamento politico em votacoes nominais
2. Emendas parlamentares Pix e valores por municipio
3. Proposicoes legislativas e areas tematicas
4. Atos no diario oficial e fiscalizacao
5. Conexao politica local (partido do deputado x prefeito eleito)

**Fluxo**:

```
search_context_multiquery(deputado_id)
  +-- para cada query: search_context_qdrant() -> chunks do Qdrant
  +-- merge + dedup de chunks
  |
build_analysis_prompt(contexto, tipos_dados)
  +-- prompt adaptativo baseado no volume de dados
  |
generate_persona_analysis(prompt)
  +-- localai_manager.ensure_model_loaded(RAG_LLM_MODEL)
  +-- LocalAIClient.chat(prompt)
  |
_save_persona()
  +-- salva no DB com contexto_rag + fontes_usadas
```

**Configuracao**:

```python
RAG_LLM_MODEL = "gemma-4-e2b-it"
RAG_MIN_CHUNKS = 3    # Minimo para gerar persona
RAG_MAX_CHUNKS = 30   # Maximo por deputado no contexto final
RAG_BATCH_SIZE = 50   # Batch para embedding
RAG_PERSONA_VERSION = 3
```

**Uso**:

```bash
python3 -m src.enrichers.rag_persona --nome "Afonso Florence" --regerar
./run.sh cron-dossie --nome "Afonso Florence"
./run.sh cron-dossie --lote 50
```

### votacoes_temas (`src/enrichers/votacoes_temas.py`)

Classificacao de temas de votacoes da Camera dos Deputados via LLM.

Para cada votacao na tabela `votacoes_camara` que ainda nao possui tema, usa o modelo
`general` (gemma-4-e2b-it) para classificar o assunto em um termo conciso (ex: "Saude",
"Orcamento", "Seguranca Publica").

**Prompt**: analisa `descricao` e `proposicao_ementa` da votacao e retorna o tema
principal em 1 a 3 palavras. Temperature 0.1 para respostas deterministicas.

**Fluxo**:

```python
localai_manager.ensure_model_loaded(LOCALAI_MODELS["general"])
ai_client = LocalAIClient(model=llm_model)
resposta = ai_client.chat(prompt=prompt, system=..., temperature=0.1)
```

**Uso**:

```bash
python3 -m src.enrichers.votacoes_temas --limit 50
```

### diario_oficial_worker (`src/enrichers/diario_oficial_worker.py`)

Worker de processamento do Diario Oficial Unificado. Busca atos via MCP
(`diario_oficial_buscar_diario_unificado`) e usa o modelo `fast`
(qwen2.5-1.5b-instruct-q4-k-m) para extrair entidades (NER).

**Dados extraidos por ato**:

- `tipo_ato`: Portaria, Licitacao, Nomeacao, Repasse, Lei, Convenio, etc.
- `orgao`: Entidade que assinou ou publicou
- `valor_financeiro`: Valor monetario (ou null)
- `entidades_citadas`: Lista de entidades mencionadas
- `resumo`: Resumo do conteudo
- `data_publicacao`: Data no formato YYYY-MM-DD
- `link`: URL da publicacao

**Fluxo**:

```python
ai_client = LocalAIClient(model=LOCALAI_MODELS["fast"])
resposta_llm = ai_client.chat_json(prompt=..., system=NER_PROMPT)
itens = resposta_llm if isinstance(resposta_llm, list) else resposta_llm.get("itens", [])
```

**Uso**:

```python
from src.enrichers.diario_oficial_worker import process_diario_oficial
itens = await process_diario_oficial(
    query="licitacao hospitalar",
    escopo="ambos",
    data_inicio="2026-01-01",
    data_fim="2026-06-30",
)
```

---

## Benchmarks

O script `scripts/benchmark_models.py` avalia modelos com o prompt de dossie de um
deputado real e mede:

- Tempo de geracao (segundos)
- Tokens por segundo (estimado)
- Tamanho da resposta (chars)
- Score de qualidade automatico (cobertura de secoes esperadas)
- Custo de memoria (via `/backend/monitor`)

### Modelos Candidatos

| Modelo | Backend | GPU Layers |
|--------|---------|------------|
| llama-3.1-8b-q4-k-m | cuda13-llama-cpp | 24 |
| llama-3.1-8b-dossie | cuda13-llama-cpp | 33 |
| llama-3.2-3b-instruct:q4_k_m | cuda13-llama-cpp | 999 |
| qwen2.5-1.5b-instruct-q4-k-m | cuda13-llama-cpp | 32 |
| qwen3.5-9b-dossie | llama-cpp | 30 |
| minicpm5-1b-claude-opus-fable5-v2-thinking | llama-cpp | -- |

### Secoes Esperadas no Dossie

O score de qualidade verifica presenca de 9 secoes no texto gerado:

1. PERFIL
2. AREAS TEMATICAS
3. CRUZAMENTO
4. PADRAO DE VOTO
5. EMENDAS
6. PROPOSICOES
7. INDICADORES
8. RISCOS
9. CONCLUSAO

### Formula de Score

```
score_secoes = (secoes_encontradas / 9) * 100
densidade = min(palavras / 400, 1.0) * 20     # bonus ate 20 pts
numeros_bonus = 10 (se menciona R$ ou %)       # bonus 10 pts
score_total = min(score_secoes + densidade + numeros_bonus, 100)
```

### Uso

```bash
python3 scripts/benchmark_models.py
python3 scripts/benchmark_models.py --nome "Afonso Florence"
python3 scripts/benchmark_models.py --modelos llama-3.1-8b-dossie qwen3.5-9b-dossie
python3 scripts/benchmark_models.py --exportar resultado_benchmark.json
```

---

## Variaveis de Ambiente

| Variavel | Padrao | Descricao |
|----------|--------|-----------|
| `LOCALAI_BASE_URL` | `http://localhost:8080/v1` | URL base do servidor LocalAI |
| `LOCALAI_TIMEOUT` | `300` | Timeout em segundos para requisicoes |
| `LOCALAI_MAX_RETRIES` | `3` | Numero maximo de retentativas |
| `RAG_LLM_MODEL` | `gemma-4-e2b-it` | Modelo usado no RAG e dossies |
| `QDRANT_URL` | `http://localhost:6333` | URL do servidor Qdrant |
| `QDRANT_COLLECTION` | `deputados_perfis` | Nome da colecao vetorial |

Todas as variaveis sao lidas via `os.getenv()` em `config/settings.py`.

---

## Troubleshooting

### Modelo nao carrega / OOM na GPU

**Causa**: Dois modelos tentando usar VRAM ao mesmo tempo.

**Solucao**: Sempre chamar `ensure_model_loaded()` antes de qualquer operacao:

```python
from src.localai_manager import manager as localai_manager
localai_manager.ensure_model_loaded("gemma-4-e2b-it")
```

### LocalAI retornando 500 "is not currently loaded"

**Causa**: Modelo foi descarregado ou nunca carregado.

**Solucao**: Chamar `ensure_model_loaded()` que carrega automaticamente via
lazy-loading do LocalAI.

### "no grpc backend found"

**Causa**: Backend GPU (ex: cuda13-llama-cpp) nao esta configurado no LocalAI.

**Solucao**: Verificar se o LocalAI foi iniciado com o backend correto e se os
modelos GGUF estao no diretorio de modelos.

### Retry excedido / Timeout

**Causa**: Modelo muito grande para a VRAM disponivel ou servidor sobrecarregado.

**Solucao**:
1. Usar modelo mais leve (`fast` ao inves de `analysis`)
2. Aumentar `LOCALAI_TIMEOUT` via variavel de ambiente
3. Verificar uso de GPU com `nvidia-smi`

### Jobs assincronos retornando 404

**Causa**: Endpoint `/v1/jobs` nao disponivel na versao do LocalAI.

**Comportamento**: O `submit_job()` faz fallback automatico para execucao síncrona.
Nenhuma acao necessaria.

### MCP Tool Bridge nao encontra tools

**Causa**: Servidor MCP-Brasil nao esta ativo ou modulo nao importado.

**Solucao**: Verificar que o mcp-brasil esta instalado e que `mcp_brasil.server.mcp`
esta acessivel. O bridge usa lazy import para evitar circular dependencies.

### Cache stale

**Causa**: Respostas cacheadas por 7 dias podem ficar desatualizadas.

**Solucao**: Limpar o cache HTTP manualmente em `output/.http_cache/` ou ajustar
o TTL via `ENRICH_CACHE_TTL`.

---

## Exemplos de Uso

### Chat Simples

```python
from src.localai_client import get_localai_client
from src.localai_manager import manager as localai_manager
from config.settings import LOCALAI_MODELS

model = LOCALAI_MODELS["gemma"]
localai_manager.ensure_model_loaded(model)

client = get_localai_client()
resposta = client.chat(
    "Resuma o plano de acao 12345: construcao de ponte no municipio de Arapiraca-AL",
    system="Voce e um analista de politicas publicas.",
    temperature=0.3,
)
print(resposta)
```

### Classificacao de Planos

```python
labels = ["APROVADO", "IMPEDIDO", "REPROVADO", "CANCELADO"]
textos = [
    "Plano aprovado pela comissao tecnica",
    "Impedido por restricao tecnica — documentacao incompleta",
    "Rejeitado pelo plano de trabalho",
]
resultados = client.classify_batch(textos, labels=labels)
# ["APROVADO", "IMPEDIDO", "REPROVADO"]
```

### Enriquecimento de DataFrame

```python
import pandas as pd

df = pd.DataFrame({
    "motivo_impedimento": [
        "Falta de documentacao fiscal",
        "Irregularidade na licitacao",
        "Prazo do plano expirado",
    ]
})

df = client.enrich_column(
    df,
    "motivo_impedimento",
    task="Classifique o motivo do impedimento em 1-3 palavras: {text}",
    new_column="categoria_motivo",
)
# df["categoria_motivo"] -> ["Documentacao", "Irregularidade", "Prazo"]
```

### Agentic Loop com Tools Governamentais

```python
from src.mcp_tool_bridge import get_mcp_bridge

bridge = get_mcp_bridge()

# Listar tools de uma categoria
tools_camara = bridge.list_tools(category="camara")

# Executar pergunta com tool calling automatico
resultado = bridge.agent_chat(
    "Quais deputados de Alagoas mais receberam emendas em 2025?",
    categories=["camara", "transferegov"],
    max_turns=5,
)

print(resultado["response"])
print(f"Tools chamadas: {len(resultado['tool_calls'])}")
print(f"Iteracoes: {resultado['turns']}")
```

### Via LocalAIClient (interface unificada)

```python
from src.localai_client import get_localai_client

client = get_localai_client()

# Mesmo agentic loop, mas via cliente
result = client.chat_with_tools(
    "Quais municipios de SP receberam emendas acima de R$ 1 milhao?",
    categories=["transferegov", "ibge"],
    max_turns=3,
)
print(result["response"])
```

### Streaming

```python
localai_manager.ensure_model_loaded(LOCALAI_MODELS["gemma"])
client = get_localai_client()

for chunk in client.chat_stream(
    "Gere um resumo executivo do plano de acao 67890:",
    system="Voce e um redator oficial.",
):
    print(chunk, end="", flush=True)
```

### Geração de Resumos por Parlamentar

```python
import pandas as pd

df = pd.read_sql("SELECT * FROM v_planos_completo", conn)

resumos = client.summarize_plans(
    df,
    group_by="parlamentar_nome",
    value_col="valor_total",
    situation_col="plano_acao_situacao",
)
# resumos -> DataFrame com colunas ["parlamentar_nome", "resumo_ia"]
```

### Health Check

```python
client = get_localai_client()
status = client.health()

if status["status"] == "ok":
    print(f"LocalAI operacional com {status['models_count']} modelos")
    for m in status["models"]:
        print(f"  - {m}")
else:
    print(f"Erro: {status['error']}")
```
