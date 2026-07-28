# MCP Tool Bridge

Documentacao de `src/mcp_tool_bridge.py` -- ponte entre ferramentas MCP (mcp-brasil) e o formato OpenAI function calling, permitindo que modelos LocalAI invoquem tools governamentais e do dashboard.

---

## Sumario

1. [Visao Geral](#visao-geral)
2. [Arquitetura](#arquitetura)
3. [Categorias de Tools](#categorias-de-tools)
4. [Descoberta de Tools](#descoberta-de-tools)
5. [Conversao OpenAI Format](#conversao-openai-format)
6. [Agentic Loop](#agentic-loop)
7. [Dashboard Tools](#dashboard-tools)
8. [Uso com LocalAIClient](#uso-com-localaiclient)
9. [Comandos e Metodos](#comandos-e-metodos)
10. [Troubleshooting](#troubleshooting)

---

## Visao Geral

O `MCPToolBridge` resolve o problema de integracao entre o ecossistema MCP (Model Context Protocol, via mcp-brasil com 435+ tools) e modelos de linguagem locais que utilizam a API OpenAI function calling.

O mcp-brasil filtra tools via BM25 search transform para evitar sobrecarregar o LLM. O bridge contorna essa limitacao ao:

1. Descobrir tools MCP via introspecao e cache do `_tool_cache` do servidor.
2. Converter automaticamente o schema de cada tool para o formato OpenAI (`type: "function"`).
3. Mapear nomes de tools para funcoes Python diretamente (`_handler_map`), sem precisar de MCP session ativa.
4. Fornecer um agentic loop completo: o modelo decide quais tools chamar, o bridge executa e devolve resultados, e o ciclo repete ate o modelo gerar uma resposta textual.

**Instancia singleton**: `get_mcp_bridge()` retorna unica instancia do bridge.

```python
from src.mcp_tool_bridge import get_mcp_bridge

bridge = get_mcp_bridge()
```

---

## Arquitetura

```
                         +-----------------------+
                         |   Aplicacao / CLI     |
                         +-----------+-----------+
                                     |
                                     v
                         +-----------------------+
                         |     MCPToolBridge     |
                         |                       |
                         |  discover_tools()     |
                         |  to_openai_tools()    |
                         |  execute_tool()       |
                         |  agent_chat()         |
                         +-----------+-----------+
                                     |
                    +----------------+----------------+
                    |                |                 |
                    v                v                 v
          +----------------+ +-------------+ +-----------------+
          |  mcp-brasil    | | _handler_map| |  LocalAI API    |
          |  (FastMCP)     | | (import     | |  /chat/         |
          |                | |  direto)    | | completions     |
          |  list_tools()  | |             | |                 |
          |  call_tool()   | | ibge_*      | |  OpenAI format  |
          |                | | camara_*    | |  tools + msgs   |
          |  435+ tools    | | siconfi_*   | |                 |
          |  (BM25 filter) | | bacen_*     | +-----------------+
          +----------------+ | dou_*       |
                             | redator_*   |
                             +-------------+

Fluxo agentic loop:

  [Prompt] --> [LocalAI] --> [tool_calls?] --nao--> [Resposta final]
                 ^                 |
                 |                sim
                 |                 v
                 |         [execute_tool()]
                 |                 |
                 |                 v
                 |         [Result] --> [tool msg]
                 |                        |
                 +--- proximo turno ------+
```

---

## Categorias de Tools

O dicionario `TOOL_CATEGORIES` define 16 categorias para filtragem e classificacao das tools. Cada chave mapeia para uma lista de prefixos/nomes usados no match por substring:

| Categoria         | Prefixos / Filtros                                                           | Descricao                                           |
|-------------------|------------------------------------------------------------------------------|-----------------------------------------------------|
| `transferegov`    | `transferegov`                                                               | Dados do Transferegov (planos de acao, emendas)     |
| `camara`          | `camara`                                                                     | API da Camara dos Deputados                         |
| `senado`          | `senado`                                                                     | API do Senado Federal                               |
| `tse`             | `tse`                                                                        | Tribunal Superior Eleitoral (prefeitos, vereadores)  |
| `ibge`            | `ibge`                                                                       | IBGE (localidades, agregados, CEP)                  |
| `siconfi`         | `siconfi`                                                                    | SICONFI (DCA, RREO, finacas publicas municipais)    |
| `compras`         | `compras`, `pncp`, `contratosgovbr`, `dadosabertos`                          | Compras publicas, PNCP, Contratos.gov.br            |
| `saude`           | `saude`, `farmacia_popular`, `rename`, `denasus`, `imunizacao`, `opendatasus` | Dados de saude publica (CNES, farmacia, imunizacao)  |
| `educacao`        | `inep`, `fnde`                                                               | Educacao (INEP, FNDE, repasses escolares)           |
| `seguranca`       | `atlas_violencia`, `forum_seguranca`, `mj`, `sinesp`                         | Seguranca publica e violencia                       |
| `ambiental`       | `ibama`, `inpe`                                                              | Dados ambientais (IBAMA, INPE/Prodes)               |
| `financeiro`      | `bacen`, `bcb_olinda`, `b3`, `bndes`, `bps`                                 | Financas (Banco Central, B3, BNDES, PIB)            |
| `judicial`        | `datajud`, `jurisprudencia`, `tcu`                                           | Judiciario (DataJud CNJ, TCU)                       |
| `diario_oficial`  | `diario_oficial`                                                             | Diario Oficial da Uniao (DOU)                       |
| `dashboard`       | `list_registered_charts`, `inspect_chart_health`, `get_chart_data_summary`   | Graficos do Dash (4 tools do graph_tools.py)        |
| `meta`            | `listar_features`, `recomendar_tools`, `planejar_consulta`, `executar_lote`, `listar_datasets_disponiveis` | Meta-tools do mcp-brasil (introspecao e busca) |

A classificacao e feita por matching de substring contra o nome da tool (case-insensitive). A primeira categoria cujo prefixo bate determina a classificacao. Tools que nao batem em nenhuma categoria recebem `"outros"`.

---

## Descoberta de Tools

O bridge descobre tools por tres camadas:

### 1. introspecao via `mcp.list_tools()`

Metodo principal `discover_tools()`:

- Chama `mcp.list_tools()` para obter todas as tools registradas no FastMCP.
- Para cada tool, extrai `name`, `description` (truncada em 500 chars), `inputSchema`, tags do meta `fastmcp`, e classifica a categoria via `TOOL_CATEGORIES`.
- Resultado: lista de dicts com `{name, description, input_schema, category, tags}`.

### 2. Cache `_tool_cache` do servidor

Apos a introspecao, o bridge tenta acessar `mcp._mcp_server._tool_cache` -- o dicionario interno do FastMCP que contem todas as tools registradas (incluindo as escondidas pelo BM25 transform). Tools duplicadas sao ignoradas.

### 3. Meta-tools (busca dinamica)

As meta-tools `search_tools` e `call_tool` do mcp-brasil permitem que o modelo LLM descubra e invoque qualquer uma das 435+ tools em tempo de execucao, sem precisar carregadas todas no contexto.

**Cache**: `_tools_cache` armazena o resultado para chamadas subsequentes. Passe `force=True` para invalidar.

```python
tools = bridge.discover_tools(force=True)  # Forca redescoberta
```

---

## Conversao OpenAI Format

O metodo `to_openai_tools()` converte tools MCP para o formato esperado pela API OpenAI:

```python
tools_schema = bridge.to_openai_tools(
    categories=["camara", "ibge"],
    max_tools=50,
    search="deputado",
    include_meta=True,
)
```

**Formato de saida:**

```json
[
  {
    "type": "function",
    "function": {
      "name": "camara_buscar_deputado",
      "description": "Busca deputado por nome na API da Camara",
      "parameters": {
        "type": "object",
        "properties": {
          "nome": {
            "type": "string",
            "description": "Nome do deputado"
          }
        },
        "required": ["nome"]
      }
    }
  }
]
```

### Parametros do metodo

| Parametro         | Tipo               | Default | Descricao                                          |
|-------------------|--------------------|---------|----------------------------------------------------|
| `categories`      | `list[str] \| None`| `None`  | Filtrar por categorias (ex: `["camara", "ibge"]`)  |
| `max_tools`       | `int`              | `50`    | Limite maximo de tools (LocalAI pode ter limites)  |
| `search`          | `str \| None`      | `None`  | Filtro por texto no nome/descricao                  |
| `include_meta`    | `bool`             | `True`  | Incluir search_tools/call_tool (recomendado)        |

### Resolucao de handlers (`_handler_map`)

Tools do mcp-brasil que usam o formato `prefixo_nome` (ex: `ibge_municipios_por_uf`) sao resolvidas por importacao direta dos modulos do mcp-brasil:

- `mcp_brasil.data.ibge.tools`
- `mcp_brasil.data.camara.tools`
- `mcp_brasil.data.transferegov.tools`
- `mcp_brasil.data.siconfi.tools`
- `mcp_brasil.data.brasilapi.tools`
- `mcp_brasil.data.transparencia.tools`
- `mcp_brasil.data.bacen.tools`
- `mcp_brasil.data.diario_oficial.tools`
- `mcp_brasil.agentes.redator.tools`

Cada funcao e envolvida por `_wrap_no_ctx()`, que injeta um mock do `Context` do FastMCP para funcoes que exigem o parametro `ctx`.

### Introspecao de schema

`_function_to_openai_schema()` converte uma funcao Python em schema OpenAI por:

- Leitura de `inspect.signature()` para parametros, tipos e defaults.
- Parsing da secao `Args:` do docstring para descrições dos parametros.
- Mapeamento de tipos Python para JSON Schema (`int` -> `integer`, `float` -> `number`, `bool` -> `boolean`, resto -> `string`).

---

## Agentic Loop

O metodo `agent_chat()` implementa o ciclo completo de tool calling:

```
1. Montar tools_schema via to_openai_tools()
2. Construir messages[] com system prompt + user prompt
3. Enviar para LocalAI (POST /chat/completions)
4. Se resposta tem tool_calls:
   a. Para cada tool_call: execute_tool() com nome + argumentos
   b. Adicionar resultado como "role": "tool" nas messages
   c. Voltar ao passo 3
5. Se resposta nao tem tool_calls: retornar texto final
```

**Parametros:**

| Parametro           | Tipo               | Default                   | Descricao                              |
|---------------------|--------------------|---------------------------|----------------------------------------|
| `prompt`            | `str`              | (obrigatorio)             | Pergunta do usuario                    |
| `system`            | `str \| None`      | `None`                    | System prompt (gera um padrao se None) |
| `model`             | `str \| None`      | `LOCALAI_DEFAULT_MODEL`   | Modelo LocalAI a usar                  |
| `categories`        | `list[str] \| None`| `None`                    | Filtrar tools por categoria            |
| `max_tools`         | `int`              | `30`                      | Maximo de tools a expor                |
| `max_turns`         | `int`              | `5`                       | Maximo de iteracoes tool-calling       |
| `temperature`       | `float`            | `0.3`                     | Temperatura do modelo                  |
| `include_meta_tools`| `bool`             | `True`                    | Incluir meta-tools                     |

**Retorno:**

```python
{
    "response": "Texto final do modelo...",
    "tool_calls": [
        {"tool": "ibge_municipios_por_uf", "arguments": {"uf": "AL"}, "result_preview": "..."}
    ],
    "turns": 3,
    "tools_available": 42,
}
```

**Timeout e retry**: Chamadas HTTP ao LocalAI usam `httpx` com `LOCALAI_TIMEOUT` e retry exponencial (`2^attempt` segundos) ate `LOCALAI_MAX_RETRIES`.

**Versao async**: `aagent_chat()` oferece a mesma funcionalidade com `httpx.AsyncClient` e `await`.

### System prompt padrao

Quando `system=None`, o bridge gera automaticamente:

> "Voce e um assistente de IA com acesso a ferramentas de dados governamentais brasileiros. Use as ferramentas disponiveis para responder perguntas sobre transferencias, emendas, municipios, financas publicas e dados abertos."

Mais a lista das primeiras 20 tools disponiveis.

---

## Dashboard Tools

O modulo `src/graph_tools.py` expoe 4 ferramentas MCP via `@mcp_enabled` para gerenciamento autonomo dos 68 graficos do dashboard Dash:

### 1. `list_registered_charts()`

Lista todos os graficos registrados no `CHART_REGISTRY`, incluindo ID, titulo, descricao, categoria e controles interativos disponiveis.

### 2. `inspect_chart_health(chart_id?)`

Audita saude de todos os graficos ou de um especifico. Retorna:

- `is_ok` (bool): se o grafico tem dados validos.
- `num_traces` (int): numero de traces no Figure.
- `total_points` (int): total de pontos de dados.
- `status`: `"OPERACIONAL"` ou `"SEM DADOS (EMPTY)"` ou `"ERRO: ..."`.

### 3. `get_chart_data_summary(chart_id, uf_filter?, regiao_filter?)`

Executa o builder do grafico e retorna resumo estruturado (parametros aplicados, nomes dos traces, numero de traces) sem renderizar a imagem.

### 4. `register_custom_graph(id, title, description, category, sql_query, chart_type?, x_col?, y_col?)`

Permite que o agente IA crie e registre dinamicamente um novo grafico a partir de uma query SQL. Tipos suportados: `bar`, `scatter`, `pie`, `line`. O novo grafico e adicionado imediatamente ao dashboard e exposto via MCP.

---

## Uso com LocalAIClient

O bridge pode ser integrado diretamente com o `LocalAIClient` para composicao manual do agentic loop:

```python
from src.mcp_tool_bridge import get_mcp_bridge
from src.localai_client import get_localai_client

bridge = get_mcp_bridge()
client = get_localai_client()

# 1. Obter tools filtradas por categoria
tools_schema = bridge.to_openai_tools(
    categories=["camara", "ibge", "transferegov"],
    max_tools=30,
)

# 2. Chamar o cliente diretamente
messages = [
    {"role": "system", "content": "Assistente de dados governamentais."},
    {"role": "user", "content": "Quais municipios de Alagoas receberam emendas?"},
]
resp = client.chat(
    messages=messages,
    tools=tools_schema,
    temperature=0.3,
)

# 3. Processar tool_calls manualmente se necessario
tool_calls = resp["choices"][0]["message"].get("tool_calls", [])
for tc in tool_calls:
    name = tc["function"]["name"]
    args = json.loads(tc["function"]["arguments"])
    result = bridge.execute_tool_sync(name, args)
    # Adicionar resultado ao conversation e chamar novamente...
```

Ou usar o agentic loop pronto:

```python
result = bridge.agent_chat(
    "Quais municipios de Alagoas receberam emendas?",
    categories=["transferegov", "ibge"],
    max_turns=5,
)
print(result["response"])
```

---

## Comandos e Metodos

### MCPToolBridge

| Metodo                     | Async | Descricao                                           |
|----------------------------|-------|-----------------------------------------------------|
| `discover_tools(force?)`   | sim   | Descobre tools MCP (introspecao + cache)            |
| `list_tools(cat?, search?)`| --    | Lista tools filtradas (sync wrapper)                |
| `search_tools_via_mcp(q)`  | --    | Busca tools via meta-tool search_tools do mcp-brasil|
| `to_openai_tools(...)`     | --    | Converte tools MCP para formato OpenAI              |
| `execute_tool(name, args)` | sim   | Executa tool por nome (handler direto ou MCP)       |
| `execute_tool_sync(...)`   | --    | Versao sync de execute_tool                         |
| `register_tool(...)`       | --    | Registra tool customizada (nao-MCP) no bridge       |
| `agent_chat(prompt, ...)`  | --    | Agentic loop completo (chat + tool calling)         |
| `aagent_chat(prompt, ...)` | sim   | Versao async do agentic loop                        |

### Funcao modulo

| Funcao            | Descricao                              |
|-------------------|----------------------------------------|
| `get_mcp_bridge()`| Retorna instancia singleton do bridge  |

### Exemplo CLI

```python
from src.mcp_tool_bridge import get_mcp_bridge

bridge = get_mcp_bridge()

# Listar todas as tools da categoria "camara"
camara_tools = bridge.list_tools(category="camara")
for t in camara_tools:
    print(f"  {t['name']}: {t['description'][:80]}")

# Buscar tools por texto
results = bridge.list_tools(search="municipio")

# Converter para OpenAI e ver schema
schema = bridge.to_openai_tools(categories=["ibge"], max_tools=5)
import json
print(json.dumps(schema, indent=2, ensure_ascii=False))
```

---

## Troubleshooting

### Tool nao encontrada / "sem session"

**Causa**: A tool nao esta no `_handler_map` e o `call_tool` do MCP falhou sem session ativa.

**Solucao**: Verificar se o modulo correspondente esta disponivel no mcp-brasil:

```python
from src.mcp_tool_bridge import get_mcp_bridge
bridge = get_mcp_bridge()
bridge._handler_map = bridge._build_handler_map()
print(list(bridge._handler_map.keys())[:10])
```

### Erro de importacao nos modulos mcp-brasil

**Causa**: O pacote `mcp-brasil` nao esta instalado ou esta incompleto.

**Solucao**:

```bash
pip install mcp-brasil
# Verificar modulos disponiveis
python -c "import mcp_brasil.data.ibge.tools; print('OK')"
```

### LocalAI retornando erro de tools

**Causa**: Modelo local nao suporta function calling, ou schema com tipos invalidos.

**Solucao**: Usar modelos validados com suporte a function calling (gemma-4-e2b-it, llama-3.1-8b). Reduzir `max_tools` se o contexto do modelo for limitado.

### `_tools_cache` desatualizado

**Causa**: Tools foram registradas apos a primeira chamada a `discover_tools()`.

**Solucao**:

```python
tools = bridge.discover_tools(force=True)
```

### Meta-tools nao aparecem

**Causa**: `include_meta=False` foi passado, ou `search_tools`/`call_tool` nao estao registradas no mcp-brasil.

**Solucao**: Manter `include_meta=True` (padrao). As meta-tools sao essenciais para que o modelo descubra tools em tempo de execucao.

### Timeout no agentic loop

**Causa**: Modelo local lento ou tool externa demorando.

**Solucao**: Ajustar `LOCALAI_TIMEOUT` em `config/settings.py`, reduzir `max_turns`, ou usar modelo mais rapido (`qwen2.5-1.5b` a 88.9 tok/s).
