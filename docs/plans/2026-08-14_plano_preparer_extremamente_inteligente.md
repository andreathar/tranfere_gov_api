# Plano — Preparer Extremamente Inteligente

**Data**: 2026-08-14
**Escopo**: Elevar o `PromptPreparer` (`src/analysts/preparer.py`) de um
sumarizador de passe único para um pipeline de *reasoning* estruturado em
estágios, com inventário de fatos verificável, auto-correção e loop de feedback
data-driven.

**Premissa**: quanto melhor estruturado o *reasoning* do preparer, mais
eficientes os analistas — eles passam a consumir fatos verificados de forma
programática, em vez de re-parsear prosa e re-verificar números.

---

## Status de implementação (2026-08-14)

| Fase | Status | Notas |
|------|--------|-------|
| 0 — Instrumentação | pendente | `preparer_event_log` (event_type='preparer') |
| 1 — Reasoning em estágios | ✅ implementada | protocolo 6 estágios + parse tolerante a acentos + compat retroativa |
| 2 — Contrato numérico traceável | pendente | valores canônicos + inventário JSON p/ analista |
| 3 — Auto-correção (repair pass) | ✅ implementada | repair cirúrgico + fallback preservando repair_attempts |
| 4 — Self-consistency | pendente | config-gated |
| 5 — Prompt adaptativo | pendente | schema de extração por analista + cache |
| 6 — Feedback data-driven | pendente | dashboard/flag QC |

### Implementado (detalhes)

- `base.valores_rs_sem_fonte()` — fonte única de verdade para "valores sem
  fonte" (usada por `taxa_invencao_rs` e pelo repair pass).
- `Briefing` ganhou `inventario`, `agrupamento`, `verificacao`, `repair_used`,
  `repair_attempts`.
- `_build_prep_prompt` → protocolo em 6 estágios (INVENTÁRIO → AGRUPAMENTO →
  BRIEFING → FACT TABLE → VERIFICAÇÃO → KEY INSIGHTS).
- `_parse_response` → extrai os estágios, tolerante a acentos, compatível com o
  formato antigo.
- `_validate_fidelity` → cross-check da VERIFICAÇÃO (log de divergências).
- `prepare()` → loop de repair pass (até `PREPARER_MAX_REPAIR_ATTEMPTS=2`) antes
  do fallback cru.
- Testes: `tests/test_preparer_fase3.py` (11 testes). Suíte: 407 passed,
  coverage 20.06% (gate 7%).

---

## Contexto atual (lido no código)

### Preparer hoje (`src/analysts/preparer.py`)

| Função | Linha | Papel atual |
|--------|-------|-------------|
| `_truncar_chunks_seletivo` | 88 | Truncamento seletivo por tipo |
| `class Briefing` | 123 | `text`, `fact_table`, `insights`, `validation_pass`, `raw_fallback`, `chunks_pre_count` |
| `_system_prompt` | 185 | 6 linhas genéricas ("preserve números, seja conciso") |
| `_build_prep_prompt` | 196 | Passe único: seção + persona + chunks + 6 instruções + formato estrito |
| `_parse_response` | 281 | Parse heurístico dos cabeçalhos `---BRIEFING---` / `---FACT TABLE---` / `---KEY INSIGHTS---` |
| `_parse_alternativos` | 323 | Fallbacks de parse (JSON, Markdown, labels) |
| `_validate_fidelity` | 386 | Check pós-hoc: todo R$ do briefing existe nos chunks |
| `_build_fallback` | 436 | Fallback cru (chunks crus) quando preparação falha |
| `prepare` | 464 | Orquestra: prompt → chamada → parse → fidelity → fallback |

### Consumo pelos analistas (`src/analysts/base.py`)

- `_format_briefing` injeta: `text` + fact table (se pipe-rich) + insights.
- Analistas podem sobrescrever `build_prompt` (ex.: `cruzamento.py` injeta os
  **valores reais** de emendas PIX direto no prompt do analista).

### Observabilidade disponível (melhorias do usuário)

- `localai_event_log` + `localai_chain_snapshot` (migração 046, com índices).
- Auto-hook best-effort em `localai_client._post()` (L766) → `record_event`.
- `dossie_analyst_qc` (migração 045) — resultado de QC dos analistas.
- API `/api/v1/localai/*`, CLI `localai-observability`, `localai_inspector.py`,
  `logit_lens_probe.py`.

---

## Fase 0 — Instrumentação do preparer (baseline mensurável)

**Problema**: hoje não há dado sobre o próprio preparer (taxa de
`validation_pass`, fallback, latency, tokens, QC por seção). Sem baseline, as
próximas fases não têm como provar melhoria.

**Entregas**:
1. Gravar eventos de preparação reutilizando `localai_event_log` com
   `event_type='preparer'` (payload JSONB — não precisa de tabela nova):
   - `section_title`, `analyst`, `num_chunks`, `prompt_chars`,
     `parse_ok`, `validation_pass`, `repair_used`, `fallback_used`,
     `latency_ms`, `tokens` (se exposto), `qc_pass` (link com
     `dossie_analyst_qc`).
2. Hook best-effort em `prepare()` (mesmo padrão do client: `try/except pass`
   — telemetria nunca quebra a geração).
3. Consulta/dashboard: `validation_pass`, `fallback_rate`, `qc_pass` por seção
   e por analista.

**Critério de aceite**: 3 queries úteis documentadas + hook cobrindo `prepare`
e `prepare_async` (se existir).

---

## Fase 1 — Reasoning em estágios (chain-of-thought explícita) ⭐ núcleo

**Problema**: o prompt atual pede o briefing de uma vez. O modelo decide o que
é número importante *durante* a redação, sem nunca "fixar" os fatos antes —
é a origem de totais fabricados e de números que o QC reprova.

**Entregas** (redesenho de `_build_prep_prompt`):

Protocolo de **4 estágios obrigatórios**, cada um com cabeçalho parseável,
na *mesma* resposta:

1. `---INVENTÁRIO---` — *scratchpad de fatos*. Uma linha por fato:
   `entidade | valor | unidade | tema | fonte=[chunk]`. Todos os números são
   fixados aqui, ANTES de qualquer síntese.
2. `---AGRUPAMENTO---` — agrupa as linhas do inventário por tema relevante à
   persona + `section_title` (sem novos números).
3. `---BRIEFING---` — síntese escrita SOMENTE a partir do inventário. Nenhum
   número novo; cada número referencia uma linha do inventário.
4. `---VERIFICAÇÃO---` — self-check: re-lista cada R$/%/data usada no
   BRIEFING e na FACT TABLE e cruza com o INVENTÁRIO, marcando
   `OK | FALTA_FONTE | CONFLITO`.

**Por que funciona**: o modelo "pina" os números no inventário antes de
escrever. A síntese fica ancorada no que ele próprio registrou, e a
VERIFICAÇÃO vira **machine-checkable**: `_parse_response` extrai os 4 blocos e
`_validate_fidelity` passa a cruzar também a VERIFICAÇÃO com os chunks
(auto-check do modelo + check determinístico).

**Testes (TDD)**:
- parse dos 4 blocos;
- verificação machine-checkable (VERIFICAÇÃO cruza com chunks);
- regressão dos 54 testes RAG.

---

## Fase 2 — Contrato numérico traceável + valores canônicos

**Problema**: a FACT TABLE já sugere `fonte` no "Detalhe", mas não é
obrigatória nem validada. E o modelo tende a reagregar totais que já existem
nos resumos.

**Entregas**:
1. **Fonte obrigatória** em toda linha da FACT TABLE (ex.:
   `| Total Emendas PIX | Deputado | R$ 28.788.030,99 | [PARLAMENTAR_RESUMO] |`)
   + validação programática de que cada R$ tem fonte no chunk.
2. **Injeção de valores canônicos** no prompt (estender o padrão já usado no
   `cruzamento.py`): lista de agregados reais (totais por área, totais PIX,
   etc.) para o modelo NÃO reagregar — reforça a instrução 5 atual.
3. **Inventário estruturado para o analista**: parsear o `---INVENTÁRIO---`
   em JSON e injetá-lo no prompt do analista (via `_format_briefing` /
   `build_prompt`). **Aqui mora o ganho de eficiência**: analistas passam a
   consumir fatos verificados programaticamente, não re-parseando prosa.

**Testes**: todo R$ da FACT TABLE tem fonte; valores canônicos aparecem na
fact table; `_format_briefing` injeta o JSON do inventário.

---

## Fase 3 — Loop de auto-correção (repair pass)

**Problema**: hoje, `_validate_fidelity` falhou → `_build_fallback()` (perde
toda a síntese). É o pior cenário: os analistas recebem chunks crus.

**Entregas**:
1. **Repair pass**: se a fidelity falhar, rodar um segundo prompt cirúrgico:
   *"sua saída continha valores sem fonte: [lista]. Corrija apenas estes,
   mantendo o restante."* → revalidar.
2. **Re-parse assistido**: se o parse falhar, rodar re-parse com exemplo do
   schema (em vez de cair direto no fallback).
3. **Fallback só como último recurso** (após repair + re-parse falharem).

**Efeito**: converte "perde tudo" em "corrige o número" → `validation_pass`
sobe, `raw_fallback` cai.

**Testes**: repair corrige sem perder síntese; fallback só após repair falhar.

---

## Fase 4 — Self-consistency seletiva (opcional, config-gated)

**Problema**: em seções de alto valor, um único draft pode ser bom em números
mas fraco em cobertura temática.

**Entregas**:
- Para seções configuradas (ex.: as que o QC mais reprova): 2 drafts com
  ênfases distintas (um numérico, um temático) → score por fidelity + cobertura
  → escolher o melhor.
- Gate por config (custo ~2x). Não é default.

---

## Fase 5 — Prompt adaptativo por analista (esquema de extração alvo)

**Problema**: "preserve todos os números" é genérico. Cada analista consome
campos específicos (TEMÁTICAS → totais por área; CRUZAMENTO → emendas por
município).

**Entregas**:
1. Cada analista declara um **schema de extração alvo** (campos obrigatórios +
   fontes canônicas).
2. `_build_prep_prompt` auto-gera a seção `CAMPOS OBRIGATÓRIOS` a partir do
   schema → o preparer extrai o que é *consumido downstream*.
3. **Cache** por `(seção, analista, hash dos chunks)` → economia de tokens
   (medido na observabilidade).

---

## Fase 6 — Ciclo de feedback data-driven (fecha o loop)

**Entregas**:
1. Consultas unindo: `preparer_event_log` (validation_pass, repair, fallback)
   × `dossie_analyst_qc` (QC do analista) × `localai_event_log`
   (latência/falhas de infra).
2. Regra: seção com QC reprovado recorrente → flag automática para revisar o
   prompt do preparer daquela seção/persona.
3. `logit_lens_probe` nos briefings para auditoria visual da eficiência do
   RAG → preparer.

---

## Ordem de execução e dependências

```
Fase 0 (baseline) ──► Fase 1 (reasoning) ──► Fase 2 (contrato numérico)
      │                      │                        │
      └──► Fase 3 (repair) ──┘                        │
      │                                               ▼
      └──► Fase 5 (adaptativo) ◄── Fase 6 (feedback)  Fase 4 (opcional)
```

- **Núcleo do "extremamente inteligente"**: Fases 0–3.
- **Camada de custo/loop**: Fases 4–6.
- Fase 2 depende da Fase 1 (o inventário é o insumo do contrato).
- Fase 6 depende da Fase 0 (precisa do baseline).

---

## Métricas de sucesso

| Métrica | Hoje | Alvo após Fases 0–3 |
|---------|------|---------------------|
| `validation_pass` rate | desconhecida (sem dado) | ≥ 90% |
| `raw_fallback` rate | desconhecida | < 10% |
| `qc_pass` por seção | desconhecida | ↑ mensurável |
| Tokens/latência por briefing | desconhecida | estável (trade-off da Fase 4 documentado) |

---

## Testes a preservar/estender

- Regressão: suíte RAG (54 testes focados) + suíte completa (396 testes).
- Novos: parse dos 4 estágios; verificação machine-checkable; repair pass;
  fonte obrigatória; injeção de valores canônicos; cache (Fase 5).
