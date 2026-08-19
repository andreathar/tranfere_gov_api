# Decision Review Skill (graph-of-thought)

Usa o engine `graph-of-thought` do reasoning.services para revisar, de forma estruturada,
decisões e incidentes reais de uma sessão de trabalho — não hipóteses genéricas — e deixa um
registro durável e legível (`docs/decision_reviews.md`) para as próximas sessões consultarem
antes de repetir o mesmo tipo de erro.

## Por que graph-of-thought e não decision-matrix

O plano `trial` deste workspace bloqueia `decision-matrix` (`ENGINE_NOT_IN_PLAN`/`not_entitled`
— confirmado 2026-08-16 e reconfirmado 2026-08-17). O `witness` do próprio erro lista o que
está concedido: `formal-logic`, `free-will`, `graph-of-thought`, `recursive-companion`,
`sequential-thinking`. `graph-of-thought` é o único desses já testado e comprovado nesta
sessão para este tipo de uso. **Sempre teste `decision-matrix` primeiro com uma chamada
barata** (ver passo 0) — se o plano for atualizado no futuro, ele vira uma opção melhor para
comparar opções lado a lado; até lá, `graph-of-thought` é o caminho real, não um substituto
temporário para ser trocado assim que possível.

## Quando usar

- Depois de qualquer sequência de troubleshooting com 3+ tentativas que falharam por causas
  raiz **genuinamente diferentes** (não 3 retentativas do mesmo erro).
- Antes ou depois de uma ação com risco sobre recurso compartilhado da máquina (VRAM, serviço
  `:8011`, saldo de API) — especialmente se algo deu errado.
- Quando o usuário pedir explicitamente para "avaliar decisões/processos".
- Periodicamente, ao fechar uma sessão longa e multi-etapas, como fechamento do trabalho.

## Procedimento

### 0. Sanity check no decision-matrix (barato, sempre fazer primeiro)

```
mcp__<servidor-decision-matrix>__start_decision_analysis_tool(
  topic="sanity check: decision-matrix liberado?", options=["sim","nao"]
)
```

Se retornar `ENGINE_NOT_IN_PLAN`, siga com graph-of-thought abaixo. Se funcionar, o plano
mudou — use decision-matrix para comparar as opções lado a lado ao invés do fluxo abaixo, e
atualize esta nota.

### 1. Seed — declare o problema real, com contexto concreto

```
mcp__<servidor-graph-of-thought>__seed(
  session_id="<projeto>-decision-review-<data>",
  problem="<descrição concreta do que aconteceu — decisões, incidentes, tentativas reais desta sessão, não um cenário genérico>"
)
```

### 2. Generate — 3 a 5 lições candidatas, ancoradas em eventos reais

Cada uma deve citar o que de fato aconteceu (um erro específico, uma escolha específica), não
uma boa prática abstrata. `generate(session_id, parent_id, thoughts=[...])`.

### 3. Score — cada candidata, com justificativa concreta

`score(session_id, node_id, score, reasoning)`. Critérios sugeridos: custo real do que deu
errado (ex.: serviço compartilhado caiu vs. só perdeu tempo), quão generalizável é a lição,
quanta evidência real a sessão deu para ela (uma amostra única pontua mais baixo que um padrão
repetido).

### 4. Aggregate — sintetize as de maior nota numa regra operacional

`aggregate(session_id, parent_ids=[...], synthesis="<regra consolidada e acionável>")`.

### 5. extract_pattern — feche a sessão de raciocínio

`extract_pattern(session_id)` — não precisa de `got_learn`/memória externa; o registro durável
é o passo 6.

### 6. Registrar em `docs/decision_reviews.md`

Anexe uma nova seção (não sobrescreva as anteriores) com: data, contexto de uma linha, a
tabela de lições pontuadas, a síntese consolidada, e opcionalmente o diagrama Mermaid de
`visualize(session_id)`. Isso é a camada de memória real deste skill — funciona independente
da saúde do Cognee (que, no momento em que este skill foi criado, tinha problemas confirmados
de confiabilidade — ver `docs/cognee-reliability-plan.md`).

## Exemplo completo já registrado

Ver a primeira entrada de `docs/decision_reviews.md` (2026-08-17) — revisão real da própria
saga de bootstrap do Cognee/LocalAI desta sessão, usada como referência de formato.
