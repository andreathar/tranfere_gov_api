# Refatoração dos Analistas RAG — Dossiês Cross-Data Confiáveis e Eficientes

> **Data:** 2026-08-10 · **Projeto:** tranfere_gov_api · **Versão alvo:** RAG v8

**Goal:** Refatorar o pipeline multi-analista (RAG v7) para gerar dossiês cross-data
mais confiáveis, eficientes e generalizáveis a qualquer tipo de político (deputado,
senador, prefeito, governador, vereador).

**Architecture:** Retenção da arquitetura Qdrant → PromptPreparer → Analistas, com 4
mudanças estruturais: (1) briefing único por dossiê (1 chamada de preparação, não 7);
(2) fusão de analistas redundantes e criação de um analista de "rede política"
(cross-official); (3) saída estruturada JSON + QC determinístico por schema, com
fidelidade R$ unificada; (4) dimensão `tipo_politico` no Qdrant e no pipeline para
gerar dossiês de qualquer cargo.

**Tech Stack:** Python 3.11 (py311, ruff line-length 99, mypy strict, pytest),
Qdrant (deputados_perfis, 69.780 points), LocalAI (:8080), llama-3.2-3b-instruct:q4_k_m
(analista, ~2.3 GiB), zero-gemma4-e4b-openzero-q5-k-m (preparer, 21.9 tok/s), RTX 3060
6 GB VRAM, PostgreSQL transferegov_db.

---

## Contexto atual (evidências coletadas 2026-08-10)

| Métrica | Valor | Observação |
|---|---|---|
| Personas no DB | 1.221 | só **12** em RAG_PERSONA_VERSION=7; resto é v2–v6 (stale) |
| QC das personas | 737 ok / 149 fail / 335 NULL | 28% sem aprovação ou falharam |
| Chunks no Qdrant | 69.780 | 23 chunk types, coleção `deputados_perfis` |
| Queries temáticas | **31** | skill/memória dizem 15 — desatualizados |
| Modelos | llama-3.2-3b (analista), zero-gemma4 (preparer) | não co-residem em 6 GB → série |
| Custo LLM por dossiê | até 14 chamadas | 7 analistas × (preparer + análise) |
| Consumidores | `GET /api/v1/deputados/{id}/dossie` + aba Dash "Dossiê IA" | contrato markdown livre |

### Problemas identificados no scan

1. **Ineficiência (14 chamadas LLM/dossiê).** Cada analista roda `PromptPreparer`
   separado nos próprios chunks filtrados (`base.py:316`). O `cruzamento` já consome
   TODOS os chunks e re-sintetiza o mesmo contexto. Preparação é 7× redundante.
2. **Redundância entre analistas.** `classificador` e `alinhamento` consomem o mesmo
   par `[VOTO]+[DISCURSO_PLENARIO]` e ambos calculam "% de alinhamento com o governo".
3. **Cross-data fraco.** Só `cruzamento` e `anomalias` cruzam fontes. Não existe
   analista de **rede política**: deputado × prefeito × senador × governador × vereador
   (chunks `[PREFEITO]`, `[SENADOR]`, `[VEREADORES_RESUMO]`, `[CONEXAO_POLITICA]`,
   `[ESTADO_FINANCEIRO]` já existem no indexador mas nenhum analista os explora a fundo).
4. **QC raso em 4 analistas.** `classificador`/`alinhamento`/`discursos`/`perfil`
   validam por presença de keywords (ex.: contagem de backticks em `discursos.py:79`).
   Não há schema, nem verificação de que os números citados existem (perfil nem tem R$).
5. **Duas implementações de fidelidade R$ divergentes.** `base.py:taxa_invencao_rs`
   (parse numérico BR/US + tolerância 2%) vs `preparer.py:_validate_fidelity`
   (normalização de string). Podem discordar sobre o mesmo valor.
6. **Sem harness de avaliação.** Não há como medir "melhor". `scripts/benchmark_models.py`
   mede velocidade, não qualidade de dossiê.
7. **Só deputados.** `rag_persona.py` indexa/busca por `deputado_id` fixo; senadores
   (81), prefeitos (5.545), governadores (27) e vereadores (179.487) já estão no banco
   e na API (porta 8001) mas fora do RAG.
8. **`_ensure_tematicas_area_summary` é remendo.** Injeta chunk específico via busca
   dedicada (`__init__.py:85`). A refatoração deve absorver isso no routing/retrieval.

---

## Restrições (verificadas)

- VRAM 6 GB: preparer + analista NÃO co-residem → execução serial inevitável até
  trocar de modelo; o plano ataca o NÚMERO de chamadas, não o paralelismo.
- PT-BR em prompts, logs, commits; ruff/mypy strict/pytest obrigatórios.
- Modelos apenas do store LocalAI existente — nenhum download novo.
- Contrato público: `parlamentares_personas` (tabela) + endpoint `/dossie` + aba Dash.
- Gates AGENTS.md: mudança de arquitetura de runtime exige aprovação — este plano é a
  proposta; cada fase executa só após OK.

---

## Fases

### Fase 0 — Baseline observável (antes de tocar em qualquer analista)

**Objetivo:** métricas reproduzíveis de antes/depois. (Preferência explícita do usuário:
infraestrutura diagnóstica antes de mudança.)

**Arquivos:**
- Criar: `scripts/dossier_bench.py`
- Criar: `reports/dossier_bench/` (saída JSONL, gitignored ou versionado)

**Tarefas:**
1. Criar `scripts/dossier_bench.py` — CLI `--nomes "A,B" --lote 10 --saida reports/dossier_bench/run_YYYYMMDD_HHMM.jsonl`.
   Para cada deputado: roda `generate_persona_analysis`, grava por analista:
   `analyst_id, duracao_s, quality_score, quality_ok, chars, chunks_count,
   taxa_invencao_rs, briefing_chars, use_preparer`, mais totais do dossiê
   (`duracao_total, score_global, n_analistas_ativos, n_llm_calls_estimadas`).
2. Gravar linha por chamada LLM real (hook leve em `base.py:run` e `preparer.prepare`
   via `logging` estruturado) para contar chamadas reais.
3. Rodar baseline: `./run.sh cron-dossie --lote 10 --regerar` com bench → salvar
   `run_baseline_v7.jsonl`.
4. Validar: `python3 scripts/dossier_bench.py --compare run_baseline_v7.jsonl` (vazio
   ainda) — script deve rodar sem erro e gerar o JSONL.

**Verificação:** arquivo JSONL com ≥ 10 deputados, campos completos, sem exceção.

---

### Fase 1 — Briefing único por dossiê (eficiência: 14 → ~2-4 chamadas)

**Objetivo:** 1 preparação por dossiê (não 7). Analistas consomem o briefing
compartilhado + seus chunks filtrados.

**Arquivos:**
- Modificar: `src/analysts/base.py` (param `shared_briefing` em `run()`; `use_preparer`
  vira `prepare_own: bool = False`)
- Modificar: `src/analysts/__init__.py` (orquestração: prepara 1× antes do pool)
- Modificar: `src/analysts/preparer.py` (`prepare()` aceita contexto completo; sobe
  `PREPARER_MAX_CHUNKS` 8 → 14 com truncamento seletivo por tipo, não "corta do meio")
- Modificar: `src/analysts/tematicas.py` (continua data-first; usa briefing só como apoio)

**Tarefas:**
1. Em `base.py:run()`: novo param `shared_briefing: Briefing | None = None`; se
   fornecido, pula `PromptPreparer.prepare()` local. `use_preparer` mantido apenas como
   override de força.
2. Em `__init__.py:run_analyst_pipeline()`: preparar briefing único do contexto total
   (via `PromptPreparer` com `PREPARER_MAX_CHUNKS=14`, truncamento por tipo de chunk)
   ANTES de abrir o ThreadPool; passar `shared_briefing` a todos.
3. `preparer.py`: truncamento seletivo (mantém 1 chunk de cada tipo, priorizando tipos
   mais ricos: EMENDA > VOTO > PROPOSICAO > DISCURSO > CONEXAO > demais) em vez de
   `chunks[:meio] + chunks[meio+2:]` (`preparer.py:180`).
4. Rodar bench: `--compare run_baseline_v7.jsonl`. Meta: `n_llm_calls` por dossiê
   ≤ 8 (7 análises + 1 preparação; com fusão da Fase 2, ≤ 6).
5. Testes: `tests/analysts/test_shared_briefing.py` — preparer chamado 1× por pipeline;
   analista recebe briefing idêntico; fallback preservado.

**Verificação:** pytest verde; bench mostra queda de ~7 preparações para 1; QC scores
sem regressão vs baseline (Δ ≤ 5 pontos por analista).

---

### Fase 2 — Redesenho dos analistas (confiabilidade + cross-data real)

**Objetivo:** eliminar redundância, adicionar analista de rede política, saída
estruturada com QC determinístico.

**Arquivos:**
- Criar: `src/analysts/votacao.py` (fusão classificador+alinhamento)
- Criar: `src/analysts/rede_politica.py` (NOVO analista cross-official)
- Deletar: `src/analysts/classificador.py`, `src/analysts/alinhamento.py`
- Modificar: `src/analysts/router.py` (mapa de chunk types p/ votacao e rede_politica)
- Modificar: `src/analysts/__init__.py` (nova ordem, pesos do `calculate_global_score`)
- Modificar: `src/analysts/base.py` (helpers de QC estruturado + `taxa_invencao_rs` unificada)
- Modificar: `src/analysts/preparer.py` (`_validate_fidelity` passa a usar parse numérico)
- Modificar: `src/analysts/{perfil,tematicas,cruzamento,discursos,anomalias}.py` (saída JSON)

**Tarefas:**

2.1 **Fusão classificador + alinhamento → `votacao`.**
- Seções: "CLASSIFICAÇÃO POLÍTICA" + "ALINHAMENTO E DISSENSO" viram subseções de uma
  única chamada LLM (`votacao.py`), com chunks `[VOTO]`+`[DISCURSO_PLENARIO]`.
- 1 chamada em vez de 2; QC único: exige % + lista de pautas + dissenso.
- Atualizar `PESOS` em `__init__.py` (votacao 0.25, soma mantida 1.0).

2.2 **Novo analista `rede_politica` (cross-data real).**
- Chunks: `[CONEXAO_POLITICA]`, `[PREFEITO]`, `[SENADOR]`, `[VEREADORES_RESUMO]`,
  `[ESTADO_FINANCEIRO]`, `[EMENDA]`, `[DIARIO_OFICIAL]`.
- Seção: "REDE POLÍTICA E APADRINHAMENTO (CROSS-ESFERAS)".
- Tarefa: mapear rede do político — prefeitos aliados que recebem emendas, senador/
  governador do mesmo partido/coligação, vereadores do reduto, conexões DOU. Resposta
  em grafo markdown (lista de nós/arestas) + 3-5 insights.
- `min_chunks = 3`; ativação adaptativa normal.

2.3 **Saída estruturada + QC determinístico (todos os analistas).**
- Contrato JSON por analista: `{ "secoes": [...], "fatos": [{"categoria", "valor", "fonte_chunk_id"}], "flags": [...], "fidelidade_rs_ok": bool }` — com a narrativa markdown em `secoes` (mantém o formato atual de consumo).
- `base.py`: helper `qc_estruturado(output_json, schema, chunks)` → score 0-100:
  - schema válido (json.loads + campos obrigatórios) → senão 0;
  - cada `fato.valor` R$ validado contra `taxa_invencao_rs`;
  - `fonte_chunk_id` deve existir nos `_last_chunks` (rastreabilidade);
  - bônus por cobertura de seções.
- Substituir QCs por keyword dos 4 analistas rasos. `taxa_invencao_rs` vira o ÚNICO
  validador numérico; `preparer._validate_fidelity` reescrito por cima dele.

2.4 **Eliminar `_ensure_tematicas_area_summary`** como remendo: o router do `tematicas`
  ganha prioridade de ordenação (chunks de resumo por área no topo) e a busca dedicada
  vira fallback. (Absorve o fix de 2026-07-31 sem duplicar lógica.)

**Verificação:**
- `pytest tests/analysts/` — novo: `test_votacao_merged.py`, `test_rede_politica.py`,
  `test_qc_estruturado.py`, `test_fidelidade_unificada.py`.
- Bench vs baseline: QC scores por analista, taxa_invencao, `n_llm_calls` ≤ 6.
- Dossiê de exemplo (AFONSO FLORENCE) inspecionado: seções v8 + JSON válido.

---

### Fase 3 — Generalização por tipo de político ("cada político")

**Objetivo:** pipeline e indexador entendem `tipo_politico`; dossiês para qualquer cargo.

**Arquivos:**
- Modificar: `src/enrichers/rag_qdrant_indexer.py` (payload `tipo_politico`,
  `politico_id`; indexar senadores/governadores/prefeitos (top-500 por votos ou
  critério) /vereadores (top por município — NUNCA os 179k inteiros))
- Modificar: `src/enrichers/rag_persona.py` (`search_context_multiquery` e
  `generate_persona_analysis` aceitam `tipo_politico`; filtro Qdrant por payload)
- Modificar: `src/analysts/*.py` (prompts parametrizados por cargo: "deputado federal"
  → "senador"/"prefeito"/"governador"/"vereador"; `perfil.py` e `votacao.py` ajustam
  instruções por tipo)
- Modificar: `config/settings.py` (`RAG_PERSONA_VERSION = 8`; `RAG_MIN_CHUNKS`/`RAG_MAX_CHUNKS` por tipo)
- Modificar: `src/api/services/db_service.py` + `src/api/routes/*.py` (dossiê por tipo:
  `GET /api/v1/{tipo}/{id}/dossie`)
- Migração DB: `parlamentares_personas` → colunas `tipo_politico`, `politico_id`
  (nullable, default `deputado`/`deputado_id`)

**Tarefas:**
1. Indexador: adicionar `tipo_politico` ao payload de TODOS os pontos; função
   `index_politico(tipo, id)` reutilizando `_build_chunk_*`. Novos builders:
   `[SENADOR]` (atividade/relatorias), `[GOVERNADOR]` (emendas UF, SICONFI estadual),
   `[PREFEITO]` (já existe), `[VEREADORES_RESUMO]` (já existe, manter).
2. `rag_persona.py`: `search_context_multiquery(politico_id, tipo)` com
   `QueryFilter(must=[FieldCondition(key="tipo_politico", match=...), ...])`;
   `QUERIES_TEMATICAS` recebem variante por tipo (31 deputado + ~10-15 por cargo novo).
3. Analistas: template de prompts via `get_cargo(tipo)` (sing./pl. correto em PT-BR);
   `votacao` só ativa para cargos com votação (deputado/senador; vereador usa versão
   municipal), `rede_politica` e `anomalias` ativam para todos.
4. Migração + API: endpoint `/dossie` por tipo; versão default `deputado` mantém
   contrato atual (backward-compatible).
5. Regenerar deputados v7→v8 (12 atuais) e gerar 1 piloto de cada tipo novo
   (ex.: senador ALAN RICK, governador TARCÍSIO, prefeito RICARDO NUNES, vereador
   LUCAS PAVANATO) para validar prompts.

**Verificação:** 5 dossiês piloto (1 por cargo) com QC ≥ 70; endpoint por tipo
respondendo; pytest do router/filtros por tipo.

---

### Fase 4 — Backfill e workflow de regeneração

**Objetivo:** cobertura total em v8 com retomada segura (resume).

**Arquivos:**
- Modificar: `run.sh` (flags `cron-dossie --tipos deputado,senador --lote 50`)
- Modificar: `src/enrichers/rag_persona.py` (`main()` aceita `--tipos`; checkpoint
  por `(tipo, politico_id, versao)` para retomar)

**Tarefas:**
1. Checkpoint: tabela `dossie_checkpoint(tipo, politico_id, versao, status, updated_at)`
   — `status IN ('ok','fail','pendente')`; `--lote` consome pendentes em ordem.
2. Regenerar deputados em lotes de 50 (série, respeitando VRAM): 565 deputados.
3. Expandir para senadores (81) e governadores (27) — rápidos.
4. Prefeitos/vereadores: definir subconjunto indexável (ex.: prefeitos das 200 maiores
   cidades + vereadores mais votados por UF) — documentar como decisão de escopo.

**Verificação:** `SELECT tipo_politico, COUNT(*) FROM parlamentares_personas GROUP BY 1`
com cobertura ≥ 95% dos deputados; dossiê por cargo no Dash.

---

### Fase 5 — Avaliação e QA contínuo

**Objetivo:** medir qualidade de forma objetiva e manter a régua.

**Arquivos:**
- Criar: `tests/eval/golden_set.py` (10-15 políticos com fatos verificados no DB)
- Criar: `src/graphs/qualidade_dossies.py` (2-3 gráficos: distribuição QC score,
  pass-rate por analista, taxa invenção R$, duração média)
- Modificar: `src/dash_app.py` (aba "Qualidade Dossiês")
- Modificar: `scripts/dossier_bench.py` (modo `--golden`)

**Tarefas:**
1. Golden set: para cada político, 5-8 fatos-chave SQL-verificáveis (ex.: "emendas
   para COARI total R$ X", "votou SIM no PL 1234", "partido Y", "município reduto Z").
2. `--golden`: gera dossiê e mede recall de fatos (fato citado corretamente / total),
   taxa_invencao, precisão de classificação GOVERNO/OPOSIÇÃO vs. baseline manual.
3. Gráficos na aba nova; threshold de alerta: taxa_invencao > 5% ou recall < 60%
   marca dossiê como "revisar".
4. Rodar suite completa: `pytest`, `mypy src/analysts`, `ruff check src/analysts`.

**Verificação:** golden set ≥ 60% recall de fatos e taxa_invencao ≤ 5% no piloto;
gráficos aparecem na aba.

---

## Ordem de execução e gates

1. Fase 0 (baseline) → 2. Fase 1 (eficiência) → 3. Fase 2 (redesenho) → 4. Fase 3
   (tipos) → 5. Fase 4 (backfill) → 6. Fase 5 (QA).
- **Gate de aprovação** antes da Fase 1 e antes da Fase 3 (mudança de arquitetura de
  runtime/indexação — AGENTS.md).
- Cada fase termina com bench comparativo contra `run_baseline_v7.jsonl`.

## Riscos e tradeoffs

| Risco | Mitigação |
|---|---|
| Fusão classificador+alinhamento muda estrutura do dossiê | `RAG_PERSONA_VERSION=8`; endpoint mantém markdown; Dash renderiza v8 e v7 |
| JSON estruturado degrada narrativa no 3B | Híbrido: narrativa markdown dentro de `secoes[]`; QC valida campos, exibição usa narrativa |
| Briefing único de 14 chunks pode perder nuance por analista | Truncamento seletivo por tipo; analista ainda recebe seus chunks crus filtrados |
| Vereadores (179k) inviáveis para indexar tudo | Subconjunto documentado (top votos / maiores municípios); decisão de escopo explícita |
| Preparer + analista seguem em série na VRAM | Fase 1 reduz chamadas; paralelismo só quando co-residirem |
| Mudança de tabela persona | Colunas novas nullable; contratos antigos intactos; migração idempotente |

## Fora de escopo (deliberadamente)

- Troca de modelo LLM (llama-3.2-3b / zero-gemma) — VRAM impede upgrade; reavaliar com ADR próprio.
- Reindexar Qdrant com outro embedder (embeddinggemma-300m 768d já é o padrão).
- Dossiê em tempo real na API (mantém cron/batch).

## Arquivos resumo

| Ação | Arquivo |
|---|---|
| Criar | `scripts/dossier_bench.py`, `src/analysts/votacao.py`, `src/analysts/rede_politica.py`, `src/graphs/qualidade_dossies.py`, `tests/eval/golden_set.py`, `tests/analysts/*` |
| Modificar | `src/analysts/{base,preparer,router,__init__,perfil,tematicas,cruzamento,discursos,anomalias}.py`, `src/enrichers/{rag_persona,rag_qdrant_indexer}.py`, `src/api/services/db_service.py`, `src/api/routes/*.py`, `src/dash_app.py`, `config/settings.py`, `run.sh` |
| Deletar | `src/analysts/classificador.py`, `src/analysts/alinhamento.py` |

## Pós-entrega

- Atualizar skill `transferegov-rag` (31 queries, v8, tipos, bench) — skill atual está
  desatualizada (diz 5 queries/v3).
- Documentar decisão do subconjunto prefeitos/vereadores no ADR-style note em
  `docs/` (ou `.hermes/plans/` se preferir manter só plano).
