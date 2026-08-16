# Smart Tools

O server raiz expoe 4 meta-tools que vao alem de consultas individuais — elas permitem descobrir, planejar e executar consultas combinadas.

## `listar_features`

Lista todas as features ativas com status de autenticacao.

```
→ listar_features()
← 27 features ativas:
   ibge (9 tools) ✓
   bacen (9 tools) ✓
   transparencia (18 tools) ✓ (com chave)
   ...
```

Util para o LLM saber quais APIs estao disponiveis antes de montar uma estrategia.

---

## `recomendar_tools`

Recebe uma pergunta em linguagem natural e recomenda 3-5 tools relevantes.

```
→ recomendar_tools("Quais os maiores gastos do governo federal em 2024?")
← Recomendacao:
   1. transparencia_consultar_despesas — despesas por funcao/UF/ano
   2. transparencia_buscar_contratos — contratos federais
   3. tcu_buscar_acordaos — acordaos sobre gastos irregulares
```

**Como funciona:**
1. `build_catalog()` gera um catalogo markdown de todas as tools (cacheado)
2. Envia o catalogo + a pergunta para `claude-haiku-4-5-20251001`
3. O LLM seleciona as tools mais relevantes com justificativa

**Requer:** `ANTHROPIC_API_KEY`

---

## `planejar_consulta`

Cria um plano de execucao estruturado para consultas que envolvem multiplas APIs. Retorna etapas com dependencias, parametros e estrategia de combinacao.

```
→ planejar_consulta("Compare gastos de saude em SP e MG nos ultimos 3 anos")
← Plano de Execucao:
   Etapa 1: tce_sp_consultar_despesas (SP, funcao=saude, 2022-2024)
   Etapa 2: [depende de contexto] buscar dados de MG
   Etapa 3: comparar per capita usando populacao do IBGE
   Estrategia: enriquecimento + comparacao
```

**Modelo de dados:**

```python
class EtapaPlano(BaseModel):
    ordem: int           # Sequencia de execucao
    tool: str            # Nome da tool
    parametros: dict     # Parametros sugeridos
    depende_de: list     # Etapas que devem completar antes
    justificativa: str   # Por que essa etapa

class PlanoConsulta(BaseModel):
    objetivo: str
    etapas: list[EtapaPlano]
    estrategia: str      # enriquecimento, comparacao, etc.
```

**Estrategias suportadas:**
- **Enriquecimento** — adiciona contexto de outra API (ex: populacao do IBGE para calcular per capita)
- **Comparacao** — mesma metrica de fontes diferentes (ex: gastos SP vs MG)
- **Contextualizacao** — dados complementares (ex: votacao + proposicao + autor)
- **Paralelismo** — consultas independentes executadas juntas

**Requer:** `ANTHROPIC_API_KEY`

---

## `executar_lote`

Executa ate 10 tool calls em paralelo numa unica chamada MCP. Reduz round-trips entre o LLM e o server.

```
→ executar_lote([
    {"tool": "bacen_indicadores_atuais", "params": {}},
    {"tool": "ibge_listar_estados", "params": {}},
    {"tool": "brasilapi_consultar_taxa", "params": {"sigla": "SELIC"}}
  ])
← [resultado1, resultado2, resultado3]  # Executados em paralelo
```

**Como funciona:**
1. `build_dispatch(registry)` mapeia nome de tool → funcao async
2. `asyncio.gather()` executa todas em paralelo
3. Retorna array de resultados na mesma ordem

**Limites:** Maximo 10 queries por chamada.

---

## Quando usar cada uma

| Situacao | Tool |
|----------|------|
| "O que posso consultar?" | `listar_features` |
| "Qual tool devo usar para X?" | `recomendar_tools` |
| "Como combino dados de varias APIs?" | `planejar_consulta` |
| "Preciso de varios dados de uma vez" | `executar_lote` |

### Fluxo combinado

Para consultas complexas, o fluxo ideal e:

```
1. planejar_consulta("minha pergunta complexa")
   → Recebe plano com etapas e dependencias

2. executar_lote([etapas independentes])
   → Executa etapas sem dependencias em paralelo

3. executar_lote([etapas dependentes])
   → Executa etapas que precisavam dos resultados anteriores

4. LLM sintetiza os resultados
```

## Tool Search

Com 309 tools disponiveis, enviar todas ao LLM seria ineficiente. O mcp-brasil oferece 3 modos de discovery, configuravel via `MCP_BRASIL_TOOL_SEARCH`:

| Valor | Comportamento |
|-------|---------------|
| `bm25` (default) | Filtra para top-10 relevantes por contexto |
| `code_mode` | Discovery progressivo + sandbox Python ([ver docs](code-mode.md)) |
| `none` | Todas as 309 tools visiveis |

### BM25 (padrao)

Filtra automaticamente:

- Analisa o contexto da conversa
- Ranqueia tools por relevancia (BM25 scoring)
- Retorna apenas as top-10 mais relevantes
- Meta-tools (`listar_features`, `recomendar_tools`, etc.) sempre ficam visiveis

### Code Mode (experimental)

Substitui todas as tools por 4 meta-tools de discovery: `get_tags`, `search`, `get_schema` e `execute`. O LLM descobre tools sob demanda e pode encadear chamadas em um sandbox Python.

Ideal para workflows complexos que combinam 3+ APIs. Requer `pydantic-monty` (ja incluso no pacote). Faz fallback automatico para BM25 se nao disponivel.

**Documentacao completa:** [Code Mode](code-mode.md)
