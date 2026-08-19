# Testes dos Reasoning Services e Cognee

**Data:** 16 de agosto de 2026
**Escopo:** verificar se os novos MCPs de raciocínio podem orientar melhorias no Cognee do TransfereGov API, sem escrever no grafo nem alterar datasets.

## Resultado executivo

A integração ainda não está pronta para uso operacional conjunto:

1. `decision-matrix` e `structured-reflection` foram descobertos e chamados.
2. Ambos foram rejeitados pelo serviço remoto com `ENGINE_NOT_IN_PLAN` / `not_entitled` no plano `trial`.
3. O MCP Cognee respondeu, mas o cliente conectado foi identificado como **Visual Studio Code 1.133.0**, com dataset padrão `visual_studio_code_memory`.
4. O dataset esperado pelo projeto, `claude_project_tranfere_gov_api`, não apareceu na listagem disponível.
5. A busca `recall` no tenant configurado retornou `404 Not Found` para `/api/v1/recall`.
6. A visualização e a listagem de dados por dataset foram rejeitadas porque o MCP remoto está em modo API, e essas operações exigem modo direto.
7. Nenhuma operação de escrita (`remember`/ingestão/cognify) foi executada.
8. Já existe uma implementação local em `src/mcp/reasoning_engine.py`; seus cinco testes funcionais passaram.

## Configuração observada

O arquivo de configuração do Gemini contém:

- `structured-reflection` → `https://reasoning.services/tools/structured-reflection/mcp`;
- `decision-matrix` → `https://reasoning.services/tools/decision-matrix/mcp`;
- `sequential-thinking` → servidor local via `@modelcontextprotocol/server-sequential-thinking`;
- `cognee` → `cognee-mcp@latest` apontando para o tenant Cognee Cloud configurado.

O projeto declara o dataset `claude_project_tranfere_gov_api` em `.claude/settings.json`, mas o cliente MCP desta sessão é o cliente do VS Code e declara `visual_studio_code_memory` como dataset padrão. Isso explica parte da divergência: o isolamento por agente não está sendo aplicado de forma uniforme entre clientes.

## Testes realizados

| Teste | Resultado | Interpretação |
|---|---|---|
| Descoberta de reasoning services | Passou | Os servidores estão registrados no ambiente |
| Início de decision matrix | Bloqueado | Engine não incluído no plano `trial` |
| Início de structured reflection | Bloqueado | Engine não incluído no plano `trial` |
| Identidade do MCP Cognee | Passou | Cliente = VS Code 1.133.0 |
| Listagem de datasets | Passou parcialmente | Tenant responde, mas não mostra o dataset do projeto |
| Recall híbrido | Falhou com HTTP 404 | Endpoint/API do tenant incompatível com o MCP usado ou rota removida |
| Visualização por dataset | Bloqueado | Recurso disponível somente em modo direto |
| Listagem de itens por dataset | Bloqueado | Recurso disponível somente em modo direto |
| Escrita no Cognee | Não executado | Evitado para preservar dados durante diagnóstico |

O teste isolado foi executado com a configuração padrão do projeto. Os cinco casos passaram; o processo completo retornou falha somente porque o `pytest` aplica `--cov-fail-under=7` globalmente e um arquivo isolado produz 1% de cobertura total. Isso não representa falha funcional da `ReasoningEngine`.

## Como os reasoning services podem melhorar o Cognee

### 1. Decision matrix para governança de fontes

Usar a matriz para decidir, antes da ingestão, se um artefato deve ir para:

- memória de sessão;
- conhecimento permanente do Cognee;
- índice vetorial/Qdrant;
- documentação versionada;
- nenhuma camada.

Critérios recomendados: estabilidade do fato, custo de atualização, sensibilidade, valor para recuperação e duplicação com RAG v8.

### 2. Structured reflection para revisão de dossiês

Aplicar reflexão estruturada a resultados do RAG antes de persistir fatos duráveis:

- separar fato observado, inferência e hipótese;
- apontar fonte e data;
- identificar contradições entre PostgreSQL, Qdrant e Cognee;
- exigir confirmação humana para alegações sensíveis;
- gerar uma decisão de persistência auditável.

### 3. Sequential thinking para pipelines de enriquecimento

Usar o servidor local como orquestrador de diagnóstico, não como banco de memória:

1. identificar a pergunta;
2. selecionar fontes;
3. consultar cada fonte;
4. comparar evidências;
5. classificar confiança;
6. decidir se atualiza Cognee/Qdrant;
7. registrar o motivo.

## Recomendações priorizadas

### P0 — corrigir conectividade e identidade

1. Confirmar, no cliente que executará o projeto, qual tenant Cognee e qual dataset estão ativos.
2. Alinhar o cliente VS Code, Claude e Gemini para o mesmo dataset explícito, ou documentar deliberadamente datasets separados.
3. Validar a versão do `cognee-mcp` compatível com o tenant. O `404` em `/api/v1/recall` indica incompatibilidade de rota, não apenas ausência de dados.
4. Não enviar conteúdo ao grafo até o `recall` e a enumeração do dataset funcionarem.

### P1 — criar uma camada de decisão antes da ingestão

Parte dessa camada já existe em `ReasoningEngine.route_cognee_query()` e `ReasoningEngine.pre_cognify_synthesis()`. O próximo passo é conectá-las ao fluxo de ingestão/consulta com uma política explícita de persistência, mantendo o comportamento atual como fallback quando os serviços remotos não estiverem disponíveis.

Implementar uma função local de política, por exemplo `should_persist_memory(fact)`, com saída estruturada:

```json
{
  "destination": "session|cognee|qdrant|repository|discard",
  "confidence": 0.0,
  "sources": [],
  "reason": "",
  "requires_review": false
}
```

A função pode usar `decision-matrix` quando o plano permitir; até lá, deve existir uma política determinística local para não bloquear o pipeline.

### P1 — separar responsabilidades

- **Cognee:** relações, decisões, conceitos estáveis, contexto de agentes e trilhas de proveniência.
- **Qdrant/RAG v8:** recuperação semântica de chunks operacionais e dados atualizados.
- **PostgreSQL:** fonte de verdade relacional e valores numéricos.
- **Git:** regras, código, prompts e decisões versionadas.

Cognee não deve substituir PostgreSQL nem virar cópia integral do código.

### P2 — medir antes/depois

Criar um golden set com perguntas sobre arquitetura, decisões e relações do projeto e medir:

- precisão factual;
- cobertura de fontes;
- latência;
- duplicação entre Cognee e Qdrant;
- taxa de respostas sem evidência;
- custo de ingestão e atualização.

## Limitações deste ensaio

- Os engines pagos dos reasoning services não puderam executar no plano atual.
- O servidor Cognee remoto não permitiu inspeção por dataset no modo API.
- O recall não pôde ser comparado antes/depois porque a rota respondeu `404`.
- Nenhum dado foi gravado, portanto ainda não há benchmark de qualidade de recuperação.

## Próximo ensaio recomendado

Depois de corrigir tenant, dataset e rota do Cognee:

1. criar um dataset de teste isolado, por exemplo `tranferegov_reasoning_lab`;
2. ingerir somente três artefatos pequenos: `AGENTS.md`, `docs/RAG.md` e uma decisão técnica curta;
3. executar perguntas idênticas em `CHUNKS`, `GRAPH_COMPLETION` e `HYBRID_COMPLETION`;
4. usar structured reflection para classificar cada resposta como fato, inferência ou sem evidência;
5. comparar com a recuperação do Qdrant;
6. só então decidir o que merece persistência no dataset oficial.

## Sessão de acompanhamento — 2026-08-16 (mesma data, sessão Claude Code)

**Escopo:** usar de fato os MCPs de reasoning.services disponíveis nesta sessão (não apenas
descobri-los) e fechar a recomendação P1 do ensaio anterior (camada de decisão antes da
ingestão). A arquitetura de datasets por agente (`claude_project_*`, `codex_project_*`,
`hermes_global`) já havia sido corrigida no mesmo dia — ver
`/mnt/data/Projects_SSD/docs/cognee-architecture.json` — então essa parte não foi reaberta aqui.

### O que mudou em relação ao ensaio anterior

1. `decision-matrix` continua bloqueado: `start_decision_analysis_tool` retornou
   `{"status":"denied","verdict":"not_entitled","reason":"ENGINE_NOT_IN_PLAN","plan":"trial"}`.
   O `witness` da resposta lista os engines realmente concedidos no plano trial:
   `formal-logic`, `free-will`, `graph-of-thought`, `recursive-companion`, `sequential-thinking`.
   `decision-matrix` e `structured-reflection` (o nome usado no ensaio anterior) não estão
   nessa lista — ambos exigem upgrade de plano.
2. `graph-of-thought` (servidor `92ee41c2-...`, ferramentas `seed`/`generate`/`score`/`aggregate`/
   `extract_pattern`/`visualize`/`status`) **funcionou de ponta a ponta**: seed → generate (3
   ramos) → score (3) → aggregate (síntese) → extract_pattern. Isso não tinha sido testado no
   ensaio anterior, que só tentou `decision-matrix` e `structured-reflection`.
3. Conclusão prática: para este workspace, `graph-of-thought` é o substituto funcional real de
   `structured-reflection` enquanto o plano `trial` não for atualizado — não `decision-matrix`.

### Uso do graph-of-thought para decidir o que implementar

Sessão `tranferegov-cognee-improve-2026-08-16`: o problema seedado foi "como melhorar o
funcionamento do Cognee dado que decision-matrix está bloqueado e falta uma política de
persistência". Três ramos gerados, pontuados e sintetizados:

| Ramo | Score | Motivo |
|---|---|---|
| Implementar `should_persist_memory()` local determinístico | 0.85 | Fecha o gap P1 sem depender de serviço externo pago; testável isoladamente |
| Conectar `route_cognee_query()` a chamadas HTTP reais (:8011/:8000/cloud) | 0.40 | Sem credenciais testáveis neste ambiente de código; risco de integrar contra URL errada |
| Usar graph-of-thought como padrão de operação antes de persistências sensíveis | 0.65 | Bom processo, mas não vira código no repositório — complementa a opção 1 |

Os dois ramos de maior pontuação foram agregados na decisão implementada abaixo.

### O que foi implementado

`ReasoningEngine.should_persist_memory(fact, source=None)` em
[src/mcp/reasoning_engine.py](../src/mcp/reasoning_engine.py) — a política determinística de
persistência recomendada como P1 no ensaio anterior, com a saída estruturada já especificada:

```json
{"destination": "session|cognee|qdrant|repository|discard", "confidence": 0.0, "sources": [], "reason": "", "requires_review": false}
```

Ordem de checagem: (1) limite de escopo do Cognee — nunca dado de domínio/pessoal/político
(CPF, beneficiário, voto de deputado etc.), conforme `scope_boundary` em
`docs/cognee-architecture.json`; (2) segredos/credenciais — nunca persistir; (3) ruído
transitório de execução (tool-trace, stdout/stderr, texto muito curto) → `session`; (4)
linguagem de decisão/causa-raiz/incidente estável → `cognee`; (5) trechos de
documentação/referência → `qdrant` (evita duplicar o RAG v8); (6) default conservador →
`cognee` com confiança baixa e `requires_review=true`.

Ela **não** faz nenhuma chamada de rede — é o fallback local permanente enquanto
`decision-matrix` remoto não for liberado, não um placeholder temporário.

Testes: 7 novos casos em `tests/test_reasoning_engine.py` (12 no total no arquivo), todos
passando isoladamente (`pytest tests/test_reasoning_engine.py`). O mesmo problema de cobertura
global do ensaio anterior se aplica a uma execução isolada do arquivo.

### O que ainda não foi feito (fica para o próximo ensaio)

- Conectar `should_persist_memory()` e `route_cognee_query()` ao fluxo real de ingestão dos
  plugins Cognee (hooks em `~/.claude/plugins/cache/cognee/...`) — esses hooks rodam fora deste
  repositório e não têm `ontology_key` nem política de persistência hoje, conforme já registrado
  em `cognee-architecture.json`.
- Testar `decision-matrix` de novo após um eventual upgrade de plano do reasoning.services.
- O recall 404 e a identidade de cliente (VS Code vs Claude vs Codex) do ensaio anterior não
  foram reabertos nesta sessão — fora do escopo desta rodada, que focou em código testável no
  repositório.
