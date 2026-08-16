# Code Mode

> **Status:** Experimental

Code Mode e um modo alternativo de discovery de tools que substitui a listagem direta por um fluxo progressivo de descoberta + sandbox Python para encadear chamadas.

Com 309 tools, enviar todos os schemas ao LLM de uma vez e caro em tokens. O Code Mode resolve isso com **discovery sob demanda** — o LLM busca, inspeciona e executa tools sem precisar ver todas de uma vez.

---

## Como ativar

```bash
MCP_BRASIL_TOOL_SEARCH=code_mode
```

Ou na config do cliente:

```json
{
  "mcpServers": {
    "mcp-brasil": {
      "command": "uvx",
      "args": ["--from", "mcp-brasil", "python", "-m", "mcp_brasil.server"],
      "env": {
        "MCP_BRASIL_TOOL_SEARCH": "code_mode"
      }
    }
  }
}
```

### Dependencia

Code Mode requer `pydantic-monty` (sandbox). Ja incluso no pacote:

```bash
pip install mcp-brasil
# ou explicitamente:
pip install "fastmcp[code-mode]"
```

Se `pydantic-monty` nao estiver instalado, o server faz **fallback automatico para BM25** com um warning no log.

---

## Como funciona

No modo padrao (BM25), o LLM ve `search_tools()` + `call_tool()`. No Code Mode, **todas as 309 tools ficam ocultas** e sao substituidas por 4 meta-tools de discovery:

```
┌─────────────┐     ┌──────────┐     ┌──────────────┐     ┌───────────┐
│  get_tags()  │ --> │ search() │ --> │ get_schema() │ --> │ execute() │
│  Categorias  │     │  Buscar  │     │  Parametros  │     │  Sandbox  │
└─────────────┘     └──────────┘     └──────────────┘     └───────────┘
```

### Fluxo em 4 etapas

**1. Browse** — `get_tags()` lista categorias disponiveis com contagem de tools:

```
→ get_tags()
← legislativo (37 tools)
  transparencia (18 tools)
  economia (18 tools)
  saude (48 tools)
  eleitoral (21 tools)
  ...
```

**2. Search** — `search()` busca tools por palavras-chave, filtrando por tags:

```
→ search(query="gastos deputado", tags=["legislativo"])
← camara_despesas_deputado: Despesas de um deputado especifico
  camara_detalhes_deputado: Informacoes detalhadas sobre um deputado
  transparencia_consultar_despesas: Despesas da administracao publica
```

**3. Inspect** — `get_schema()` retorna parametros detalhados de tools especificas:

```
→ get_schema(tools=["camara_despesas_deputado"], detail="detailed")
← ### camara_despesas_deputado
  Despesas de um deputado especifico
  **Parameters**
  - deputado_id (integer, required)
  - ano (integer, optional)
  - mes (integer, optional)
  - tipo (string, optional)
```

**4. Execute** — `execute()` roda codigo Python no sandbox, encadeando tools:

```python
→ execute(code="""
despesas_sp = await call_tool("camara_despesas_deputado", {
    "deputado_id": 204554,
    "ano": 2024
})
despesas_rj = await call_tool("camara_despesas_deputado", {
    "deputado_id": 178957,
    "ano": 2024
})
return {
    "SP": despesas_sp,
    "RJ": despesas_rj,
    "diferenca": "comparacao feita no sandbox"
}
""")
← {"SP": "...", "RJ": "...", "diferenca": "..."}
```

---

## Tools de discovery

| Tool | Input | Output |
|------|-------|--------|
| `get_tags()` | `detail` (opcional) | Tags com contagem de tools |
| `search(query, ...)` | `query` (string), `tags` (opcional), `detail`, `limit` | Tools ranqueadas por relevancia |
| `get_schema(tools, ...)` | `tools` (lista de nomes), `detail` | Schemas com parametros |
| `execute(code)` | `code` (string Python) | Resultado da execucao |

### Niveis de detalhe (`detail`)

| Valor | O que retorna |
|-------|---------------|
| `"brief"` | Nome + descricao curta |
| `"detailed"` | Nome + descricao + parametros |
| `"full"` | Schema JSON completo |

---

## Sandbox

O `execute()` roda codigo Python em um sandbox isolado via `pydantic-monty`.

### Disponivel no sandbox

- `call_tool(name, params)` — unica funcao de acesso a tools
- Python stdlib (`json`, `math`, `asyncio`, etc.)
- `async/await` para chamadas de tools

### Nao disponivel

- Acesso ao sistema de arquivos
- Chamadas de rede (exceto via `call_tool`)
- Imports externos
- Estado global persistente

---

## Comparacao entre modos

| Aspecto | BM25 (padrao) | Code Mode | None |
|---------|---------------|-----------|------|
| **Env var** | `bm25` | `code_mode` | `none` |
| **Tools visiveis** | Top 10 por busca | 0 (substituidas por discovery) | Todas 309 |
| **Meta-tools** | `search_tools`, `call_tool` | `get_tags`, `search`, `get_schema`, `execute` | Nenhuma |
| **Encadeamento** | Manual (1 call por vez) | Automatico (sandbox Python) | Manual |
| **Custo de contexto** | Medio | Minimo (sob demanda) | Maximo |
| **Round-trips** | 1 por discovery | 3-4 (progressivo) | 0 |
| **Melhor para** | Uso geral | Workflows complexos, multi-API | Debug/testes |

---

## Quando usar Code Mode

**Use Code Mode quando:**
- Precisa combinar dados de 3+ APIs numa unica operacao
- Quer minimizar tokens de contexto (catalogo grande)
- O workflow e repetivel e pode ser expresso em codigo

**Use BM25 (padrao) quando:**
- A maioria das consultas e simples (1-2 tools)
- Quer respostas rapidas com menos round-trips
- Nao precisa de encadeamento programatico

**Use None quando:**
- Debugging ou desenvolvimento
- O LLM suporta contexto grande
- Quer ver todas as tools sem filtragem

---

## Exemplo pratico

### Cenario: comparar gastos de saude entre estados

```
User: "Compare os gastos com saude de SP e MG nos ultimos 3 anos"

LLM (Code Mode):
  1. get_tags()
     → [transparencia, saude, economia, legislativo, ...]

  2. search("gastos saude estado", tags=["transparencia"])
     → tce_sp_consultar_despesas, ibge_consultar_agregado, ...

  3. get_schema(["tce_sp_consultar_despesas", "ibge_consultar_agregado"])
     → parametros detalhados

  4. execute("""
     sp_2024 = await call_tool("tce_sp_consultar_despesas", {
         "funcao": "saude", "exercicio": 2024
     })
     sp_2023 = await call_tool("tce_sp_consultar_despesas", {
         "funcao": "saude", "exercicio": 2023
     })
     pop = await call_tool("ibge_consultar_agregado", {
         "tabela": "6579", "variavel": "9324",
         "localidade": "35", "nivel": "estado"
     })
     return {"SP_2024": sp_2024, "SP_2023": sp_2023, "populacao": pop}
     """)
     → Dados combinados em uma unica chamada
```

No modo BM25, isso exigiria multiplos round-trips separados. No Code Mode, o sandbox executa tudo de uma vez.

---

## Implementacao no mcp-brasil

```python
# src/mcp_brasil/server.py
from fastmcp.experimental.transforms.code_mode import (
    CodeMode, GetSchemas, GetTags, Search,
)

mcp.add_transform(
    CodeMode(
        discovery_tools=[
            GetTags(name="get_tags"),
            Search(name="search"),
            GetSchemas(),
        ],
    )
)
```

Fallback automatico para BM25 se `pydantic-monty` nao estiver disponivel.

---

## Links

- [Smart Tools](smart-tools.md) — Meta-tools do server raiz
- [Configuracao](configuration.md) — Variaveis de ambiente
- [Arquitetura](../concepts/architecture.md) — Como o projeto funciona
