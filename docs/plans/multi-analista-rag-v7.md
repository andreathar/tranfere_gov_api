# Plano: Multi-Analista RAG v7

## Problema

O sistema atual (RAG v6) usa um **único prompt monolítico** que pede para o LLM
produzir 6 seções de uma só vez. Isso causa:

1. **Profundidade sacrificada** — o modelo tenta cobrir tudo mas não aprofunda nada
2. **Janela de contexto estourada** — ~7K tokens locais forçam truncamento agressivo
3. **Qualidade inconsistente** — seções como "ALINHAMENTO POLITICO" são sistematicamente
   puladas porque o prompt não deixa explícito o suficiente
4. **14 queries misturadas** — todo chunk vai para o mesmo pool RRF, sem separação temática
5. **Debug difícil** — quando a qualidade falha, não sabemos qual seção específica causou

## Solução: Multi-Analista Especializado

Em vez de **1 LLM genérico**, usamos **N analistas especialistas**, cada um com:

- **Subconjunto de queries** — apenas as relevantes para sua seção
- **Prompt curto e focado** — 300-500 tokens, otimizado para uma única tarefa
- **LLM call independente** — cada analista gera sua seção em separado
- **Quality check próprio** — critérios específicos por tipo de análise
- **Tolerância a falhas** — se um analista falha, os outros continuam

## Arquitetura

```
[Contexto Qdrant] ─→ 14 queries (batch embed + RRF, como hoje)
                           │
                           ▼
              ┌─────────────────────┐
              │   DATA ROUTER v7    │  (NOVO)
              │  Filtra chunks por  │
              │  tipo para cada     │
              │  analista           │
              └─────────┬───────────┘
                        │
          ┌──────┬──────┬──────┬──────┬──────┬──────┐
          │      │      │      │      │      │      │
          ▼      ▼      ▼      ▼      ▼      ▼      ▼
   ┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌──────────┐
   │Classif.││ Perfil ││Áreas   ││Cruzam. ││Alinha. ││Discursos││Anomalias │
   │Política││Biográf.││Temát.  ││Dados   ││Polít.  ││Plenário││Fisiolog. │
   └───┬────┘└───┬────┘└───┬────┘└───┬────┘└───┬────┘└───┬────┘└────┬─────┘
       │         │         │         │         │         │          │
       └─────────┴─────────┴─────────┴─────────┴─────────┴──────────┘
                                     ▼
                            ┌────────────────┐
                            │   ASSEMBLER    │  (NOVO)
                            │  Concatena +   │
                            │  ordena seções │
                            └───────┬────────┘
                                    ▼
                            ┌────────────────┐
                            │  Quality Check │  (REFORMULADO)
                            │  Global (7/7)  │
                            └───────┬────────┘
                     ▼
             ┌────────────────┐
             │  Save to DB    │  (igual)
             └────────────────┘
```

## Os 7 Analistas Especialistas (+1 opcional)

### 0. **Classificador Político** — Seção "CLASSIFICAÇÃO POLÍTICA"
| Item | Detalhe |
|------|---------|
| **Queries** | Q1 (votos alinhamento), Q13 (discursos ideologia) |
| **Chunks** | `[VOTO]`, `[DISCURSO_PLENARIO]` |
| **Tarefa** | Classificar GOVERNO/OPOSIÇÃO/INDEPENDENTE com % de alinhamento |
| **Prompt** | ~300 tokens — "Analise os votos nominais e determine o alinhamento..." |
| **QC próprio** | Deve conter uma das 3 palavras-chave + % numérica |
| **Tempo estimado** | ~30s |

### 1. **Analista Biográfico** — Seção "PERFIL BIO-POLÍTICO"
| Item | Detalhe |
|------|---------|
| **Queries** | Perfil direto, Q5 (resumo), Q2 (proposições) |
| **Chunks** | `[PERFIL]`, `[PARLAMENTAR_RESUMO]` |
| **Tarefa** | Resumo conciso: partido, estado, formação, comissões, tempo de mandato |
| **Prompt** | ~250 tokens — "Com base nos dados de perfil, produza um resumo bio-político..." |
| **QC próprio** | Mínimo 80 chars, deve conter partido/estado |
| **Tempo estimado** | ~20s |

### 2. **Analista de Áreas Temáticas** — Seção "ÁREAS TEMÁTICAS PRIORITÁRIAS"
| Item | Detalhe |
|------|---------|
| **Queries** | Q3 (emendas Pix), Q4 (discricionárias), Q2 (proposições), Q14 (discursos temas) |
| **Chunks** | `[EMENDA]`, `[EMENDA_DISCRICIONARIA]`, `[PROPOSICAO]`, `[DISCURSO_PLENARIO]` |
| **Tarefa** | Mapear onde o dinheiro vai (R$) vs. o que ele propõe (PLs) vs. o que ele fala (discursos). Ranking por valor. |
| **Prompt** | ~400 tokens — "Compare o volume de capital alocado por área temática..." |
| **QC próprio** | Mínimo 2 áreas listadas com valores R$ |
| **Tempo estimado** | ~40s |

### 3. **Analista de Cruzamento (Pragmatismo)** — Seção "CRUZAMENTO DE DADOS"
| Item | Detalhe |
|------|---------|
| **Queries** | TODAS (visão 360°) |
| **Chunks** | Todos disponíveis |
| **Tarefa** | Identificar contradições: "votou contra, mas destinou emendas para base do governo" |
| **Prompt** | ~350 tokens — "Cruze os dados de votação, emendas e discursos..." |
| **QC próprio** | Deve conter ao menos 1 insight de contradição ou alinhamento |
| **Tempo estimado** | ~50s |

### 4. **Analista de Alinhamento Político** — Seção "ALINHAMENTO POLÍTICO E DISSENSO"
| Item | Detalhe |
|------|---------|
| **Queries** | Q1 (votos), Q13 (discursos ideologia) |
| **Chunks** | `[VOTO]`, `[DISCURSO_PLENARIO]` |
| **Tarefa** | % de alinhamento com governo, pautas de dissenso, obstrução |
| **Prompt** | ~300 tokens — "Analise os votos nominais computando alinhamento com o governo..." |
| **QC próprio** | Deve conter % numérica de alinhamento + menção a pautas específicas |
| **Tempo estimado** | ~30s |

### 5. **Analista de Discursos** — Seção "POSICIONAMENTO PÚBLICO E DISCURSOS"
| Item | Detalhe |
|------|---------|
| **Queries** | Q13 (discursos ideologia), Q14 (tópicos recorrentes) |
| **Chunks** | `[DISCURSO_PLENARIO]` |
| **Tarefa** | Análise profunda de discursos: ideologia, pautas, tom, contradições retórica vs. ação |
| **Prompt** | ~400 tokens — "Analise os discursos do plenário. Extraia posicionamento ideológico..."
  Inclui: tags/keywords, posicionamento, tom, bandeiras, consistência temporal,
  contradições entre discurso e voto/ação |
| **QC próprio** | Deve conter ao menos 3 tags/keywords extraídas + classificação ideológica |
| **Tempo estimado** | ~40s |

### 6. **Analista de Anomalias e Fisiologismo** — Seção "ANOMALIAS E FISIOLOGISMO"
| Item | Detalhe |
|------|---------|
| **Queries** | Q3 (emendas), Q10 (conexão política TSE), Q11 (risco judicial), Q12 (compras) |
| **Chunks** | `[EMENDA]`, `[CONEXAO_POLITICA]`, `[RISCO_JUDICIAL]`, `[COMPRAS_MUNICIPIO]` |
| **Tarefa** | Red flags: concentração suspeita, apadrinhamento, risco judicial |
| **Prompt** | ~400 tokens — "Atue como auditor de contas públicas. Identifique red flags..." |
| **QC próprio** | Deve apontar ao menos 1 anomalia (ou declarar "Nada anormal") |
| **Tempo estimado** | ~40s |

### 6. (Opcional) **Analista de Indicadores Sociais** — Seção extra
| Item | Detalhe |
|------|---------|
| **Queries** | Q7 (IBGE demografia), Q8 (saúde/educação), Q9 (FNDE) |
| **Chunks** | `[DEMOGRAFIA_MUNICIPIO]`, `[INDICADORES_SOCIAIS]`, `[FNDE_REPASSES]` |
| **Tarefa** | Correlacionar emendas com necessidades reais dos municípios |
| **Prompt** | ~350 tokens — "Compare o volume de emendas com indicadores sociais..." |
| **QC próprio** | Deve cruzar ao menos 1 indicador social com valor de emenda |

## Estimativa de Tempo

| Estágio | Tempo |
|---------|-------|
| Busca contexto (14 queries + RRF) | ~30s (batch embed) |
| Analista 0 - Classificador | ~30s |
| Analista 1 - Perfil | ~20s |
| Analista 2 - Áreas | ~40s |
| Analista 3 - Cruzamento | ~50s |
| Analista 4 - Alinhamento | ~30s |
| Analista 5 - Discursos | ~40s |
| Analista 6 - Anomalias | ~40s |
| Assembly + QC + Save | ~5s |
| **Total por deputado** | **~285s (~4 min 45s)** |

vs. atual ~150s — **1,6x mais lento, mas qualidade muito superior.**

Se necessário, podemos rodar analistas independentes (0, 1, 4, 5) em paralelo
com analistas pesados (2, 3, 6) usando `ThreadPoolExecutor`.

## Pacote de Módulos

```
src/analysts/                     # NOVO pacote
├── __init__.py                   # Registry: ANALYST_REGISTRY, orchestrator
├── base.py                       # Classe AnalystBase
├── router.py                     # Mapeia chunk types → analistas
├── classificador.py              # Analyst 0
├── perfil.py                     # Analyst 1
├── tematicas.py                  # Analyst 2
├── cruzamento.py                 # Analyst 3
├── alinhamento.py                # Analyst 4
├── anomalias.py                  # Analyst 5
└── social.py                     # Analyst 6 (opcional)

src/enrichers/rag_persona.py      # MODIFICADO — usa novo pipeline
```

## Estrutura de cada Analista

```python
# src/analysts/base.py
class AnalystBase(ABC):
    analyst_id: str        # "classificador"
    section_title: str     # "CLASSIFICACAO POLITICA"
    required_chunks: list  # ["[VOTO]", "[DISCURSO_PLENARIO]"]
    min_chunks: int        # 2

    @abstractmethod
    def build_prompt(self, context: list[str], nome: str) -> str: ...

    @abstractmethod
    def quality_check(self, output: str) -> tuple[bool, float]: ...

    def run(self, context: list[str], nome: str, llm_model: str) -> AnalystResult:
        prompt = self.build_prompt(context, nome)
        resposta = localai_client.chat(prompt=prompt, ...)
        qc_pass, qc_score = self.quality_check(resposta)
        return AnalystResult(
            section=self.section_title,
            content=resposta,
            quality_ok=qc_pass,
            quality_score=qc_score,
        )
```

## Modificações no `rag_persona.py`

### Fluxo Atual (v6):
```python
context_list = search_context_multiquery(dep_id)  # 14 queries → 1 pool
prompt = build_analysis_prompt(context_list, nome)  # 1 prompt gigante
resposta = llm.chat(prompt)  # 1 call
qualidade = _check_quality(resposta)  # 1 QC
```

### Novo Fluxo (v7):
```python
context_list = search_context_multiquery(dep_id)  # mesma busca
analysts = get_analysts_for_data(context_list)     # router: quais ativar?
results = []
for analyst in analysts:
    filtered = router.filter(context_list, analyst.required_chunks)
    result = analyst.run(filtered, nome, llm_model)
    results.append(result)

# Assembly
dossier = assemble_dossier(results)  # concatena na ordem
qualidade = all(r.quality_ok for r in results)  # QC global
score = score_qualidade_eval(dossier)  # score tradicional
```

### Nova função `assemble_dossier()`:
```python
def assemble_dossier(results: list[AnalystResult]) -> str:
    secoes = []
    for r in results:
        secoes.append(f"## {r.section_title}\n{r.content}")
    return "\n\n".join(secoes)
```

### Nova função `get_analysts_for_data()`:
```python
def get_analysts_for_data(context_list: list[str]) -> list[AnalystBase]:
    """Ativa apenas analistas com dados suficientes."""
    active = [CLASSIFICADOR, PERFIL]  # sempre ativos
    src = _count_sources(context_list)
    if src["emendas"] > 0:
        active.append(TEMATICAS)
    if src["votos"] > 0:
        active.append(ALINHAMENTO)
    if src["conexao_politica"] > 0 or src["risco_judicial"] > 0:
        active.append(ANOMALIAS)
    # CRUZAMENTO ativo se tiver 3+ fontes diferentes
    total_types = sum(1 for v in src.values() if v > 0)
    if total_types >= 3:
        active.append(CRUZAMENTO)
    return active
```

## Prompt de cada Analista (exemplos reais)

### Classificador Político:
```
Você é um analista de classificação política especializado em votos nominais.
Classifique o deputado {nome} em uma das categorias abaixo com base APENAS nos votos fornecidos.

DADOS DE VOTAÇÃO:
{filtered_context}

REGRAS:
- GOVERNO: votou com o governo em >60% das pautas relevantes
- OPOSIÇÃO: votou contra o governo em >60% das pautas relevantes
- INDEPENDENTE: sem padrão claro ou equilibrado
- Se não houver dados de voto, classifique como "SEM DADOS"

SAÍDA (apenas o texto abaixo, sem explicações adicionais):
**CLASSIFICAÇÃO POLÍTICA**: [GOVERNO | OPOSIÇÃO | INDEPENDENTE | SEM DADOS]
**Fundamentação**: [2-3 frases com base nos votos citados, incluindo % aproximado]
```

### Analista de Anomalias:
```
Você é um auditor sênior de contas públicas especializado em detecção de
irregularidades no uso de emendas parlamentares. Analise os dados abaixo.

DADOS CRUZADOS (emendas + conexão política + risco judicial + compras):
{filtered_context}

INSTRUÇÕES:
1. Identifique CONCENTRAÇÃO ANORMAL: valores desproporcionais para municípios pequenos
2. Identifique APADRINHAMENTO: emendas para prefeituras do mesmo partido
3. Identifique RISCO JUDICIAL: beneficiários com processos ativos
4. Identifique CONFLITO DE INTERESSE: CNPJs suspeitos ou beneficiários recorrentes

SAÍDA:
**RED FLAGS IDENTIFICADAS**:
- [flag 1 com valores e dados concretos]
- [flag 2 com valores e dados concretos]

**RISCO JUDICIAL**: [resumo ou "N/I"]

Se nenhuma anomalia for identificada, escreva:
"Nenhuma anomalia significativa identificada nos dados disponíveis."
```

## Métricas de Qualidade por Analista

| Analista | Critério | Peso |
|----------|----------|------|
| 0 - Classificador | Contém GOVERNO/OPOSIÇÃO/INDEPENDENTE + % | 15% |
| 1 - Perfil | ≥80 chars + contém partido | 10% |
| 2 - Áreas Temáticas | ≥2 áreas com R$ | 20% |
| 3 - Cruzamento | ≥1 insight de contradição | 20% |
| 4 - Alinhamento | % numérica + pauta específica | 15% |
| 5 - Discursos | ≥3 tags + classificação ideológica | 10% |
| 6 - Anomalias | ≥1 flag OU "Nada anormal" | 10% |

Score geral = média ponderada (0-100). Aprovação ≥ 70.

## Plano de Implementação (Fases)

### Fase 1: Estrutura Base (1 dia)
- [ ] Criar `src/analysts/__init__.py` com `ANALYST_REGISTRY`
- [ ] Criar `src/analysts/base.py` com `AnalystBase`, `AnalystResult`
- [ ] Criar `src/analysts/router.py` com filtro por chunk type
- [ ] Escrever `assemble_dossier()`

### Fase 2: Analistas Core (2 dias)
- [ ] Implementar `classificador.py` (Analista 0)
- [ ] Implementar `perfil.py` (Analista 1)
- [ ] Implementar `tematicas.py` (Analista 2)
- [ ] Implementar `alinhamento.py` (Analista 4)

### Fase 3: Analistas Avançados (2 dias)
- [ ] Implementar `cruzamento.py` (Analista 3 — o mais complexo)
- [ ] Implementar `discursos.py` (Analista 5)
- [ ] Implementar `anomalias.py` (Analista 6)
- [ ] Implementar fallback para analistas sem dados

### Fase 4: Integração (1 dia)
- [ ] Modificar `rag_persona.py` para usar novo pipeline
- [ ] Implementar `get_analysts_for_data()` (router adaptativo)
- [ ] Quality check global + score ponderado
- [ ] Compatibilidade: `--modelo`, `--lote`, `--regerar`, `--nome`

### Fase 5: Testes e Ajuste Fino (1 dia)
- [ ] Testar com 5 deputados de diferentes perfis
- [ ] Ajustar prompts com base nos resultados reais
- [ ] Verificar economia de tokens vs. qualidade
- [ ] Benchmark de velocidade (single vs. multi)

### Fase 6: Regeneração Completa (8h de processamento)
- [ ] `./run.sh cron-dossie --regerar --lote 512`
- [ ] Monitorar taxas de aprovação por analista
- [ ] Ajustar thresholds se necessário

## Riscos e Mitigações

| Risco | Probabilidade | Mitigação |
|-------|--------------|-----------|
| 6 LLM calls por deputado é muito lento | Média | Rodar analistas leves (0,1,4) em paralelo com pesados (3,5) |
| Prompt de Cruzamento sem dados suficientes | Média | Ativar apenas se 3+ tipos de chunk presentes |
| Quality check reprova tudo no início | Alta | Modo "soft" nas primeiras 24h: loga mas não bloqueia |
| Consumo de tokens dobra | Alta | Prompts menores compensam; cada call é ~1/3 do prompt atual |
| Manutenção de 6 arquivos vs. 1 | Baixa | Classe base elimina duplicated boilerplate |

## Benefícios Esperados

1. **Seção "ALINHAMENTO POLITICO" sempre presente** — prompt dedicado resolve
2. **Análise mais profunda** — cada analista foca em seu tema
3. **Qualidade consistente (score 85-100)** — QC específico por seção
4. **Tolerância a falhas** — se um analista falha, os demais produzem
5. **Facilidade de debug** — logs mostram qual analista específico falhou
6. **Extensível** — novos analistas são só mais um módulo no registry
7. **Prompts menores** — cada um cabe confortavelmente em 7K tokens locais
