# Plano de Melhorias — Eficiência e Qualidade das Personas Dossiê IA

**Data**: 27/07/2026
**Escopo**: Otimização do pipeline RAG v3 para geração de personas analíticas de deputados
**Arquivos impactados**: `rag_persona.py`, `rag_qdrant_indexer.py`, `config/settings.py`

---

## Sumário Executivo

O sistema atual gera personas via 5 consultas temáticas no Qdrant → prompt adaptativo → LLM. Identificamos **6 gargalos de eficiência** e **7 lacunas de qualidade**, além de **11 fontes de dados** presentes no banco mas não indexadas pelo RAG.

**Ganho estimado**: 50% redução de latência por deputado, 3x mais dados cruzados, personas 2-3x mais ricas.

---

## Fase 1 — Corrigir Gargalos de Eficiência (Alta Prioridade)

### 1.1 Eliminar Retrieva Duplo no Multi-Query (Crítico)

**Problema**: `generate_persona_analysis()` chama `search_context_multiquery()` internamente, e depois o caller (`main()` ou `_run_lote()`) chama **novamente** para obter o contexto para salvar. Cada deputado gera **10 buscas Qdrant** em vez de 5.

**Solução**: Retornar `context_list` de `generate_persona_analysis()` e reutilizar no save.

**Arquivo**: `src/enrichers/rag_persona.py`
**Esforço**: Baixo (~30 linhas)
**Impacto**: -50% chamadas Qdrant por deputado

```
# Antes (line 307 + 417):
context_list = search_context_multiquery(deputado_id)  # 5 queries
persona_text = _generate_with_client(client, deputado_id, nome, context_list)
context_list2 = search_context_multiquery(deputado_id)  # REPETIDO!
_save_persona(conn, deputado_id, persona_text, context_list2)

# Depois:
context_list = search_context_multiquery(deputado_id)  # 5 queries
persona_text = _generate_with_client(client, deputado_id, nome, context_list)
_save_persona(conn, deputado_id, persona_text, context_list)  # REUTILIZA
```

### 1.2 Reutilizar QdrantClient (Alto)

**Problema**: Cada chamada a `search_context_qdrant()` cria um **novo `QdrantClient(url=...)`**. Em batch com 50 deputados: 250+ conexões TCP.

**Solução**: Criar client uma vez, passar como parâmetro.

**Arquivo**: `src/enrichers/rag_persona.py`
**Esforço**: Baixo (~20 linhas)
**Impacto**: Eliminar overhead de conexão

### 1.3 Batch de Embeddings das Queries (Alto)

**Problema**: 5 embeddings sequenciais (1 por query temática) = 5 round-trips HTTP.

**Solução**: Chamar `embed_text_batch(QUERIES_TEMATICAS)` uma vez, iterar resultados.

**Arquivo**: `src/enrichers/rag_persona.py`
**Esforço**: Baixo (~15 linhas)
**Impacto**: -80% latência de embedding na recuperação

### 1.4 Mover ensure_model_loaded() Para Fora do Loop (Médio)

**Problema**: `ensure_model_loaded()` é chamado dentro de `search_context_qdrant()` (5x) + 1x para LLM = **6 scan completos de modelos por deputado**.

**Solução**: Chamar uma vez antes do loop multi-query.

**Arquivo**: `src/enrichers/rag_persona.py` + `src/localai_manager.py`
**Esforço**: Baixo (~10 linhas)
**Impacto**: -5 varreduras de GPU por deputado

### 1.5 Processamento Paralelo em Batch (Médio)

**Problema**: `_run_lote()` processa deputados sequencialmente. 50 deputados = 5-25 min.

**Solução**: Usar `concurrent.futures.ThreadPoolExecutor` com workers limitados (2-3 para não estourar VRAM).

**Arquivo**: `src/enrichers/rag_persona.py`
**Esforço**: Médio (~60 linhas)
**Impacto**: 2-3x throughput em batch

### 1.6 Usar RAG_BATCH_SIZE Definido (Baixo)

**Problema**: `RAG_BATCH_SIZE=50` existe em `settings.py` mas nunca é usado. Embeddings podem receber文本os longos demais.

**Solução**: Implementar chunking no `embed_text_batch()` do indexer.

**Arquivo**: `src/enrichers/rag_qdrant_indexer.py`
**Esforço**: Baixo (~15 linhas)
**Impacto**: Prevenir estouro de memória em deputados com muitos chunks

---

## Fase 2 — Melhorar Qualidade da Recuperação (Alta Prioridade)

### 2.1 Re-ranking por Score com RRF (Alto)

**Problema**: Chunks são ordenados por ordem de inserção (primeira query primeiro), não por relevância. Scores do Qdrant são descartados.

**Solução**: Implementar **Reciprocal Rank Fusion (RRF)** para combinar scores das 5 queries:

```python
def rrf_fusion(results_per_query: list[list], k: int = 60) -> list:
    """Combina resultados de múltiplas queries usando RRF."""
    scores = {}
    for query_results in results_per_query:
        for rank, chunk_id in enumerate(query_results):
            scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (k + rank + 1)
    return sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
```

**Arquivo**: `src/enrichers/rag_persona.py`
**Esforço**: Médio (~40 linhas)
**Impacto**: Chunks mais relevantes no prompt = personas mais precisas

### 2.2 Deduplicação Robusta (Alto)

**Problema**: Dedup usa prefixo de 100 chars (`c[:100]`). Emendas com texto repetitivo causam falsos positivos.

**Solução**: Hash MD5 do texto completo + normalização (lowercase, strip whitespace).

**Arquivo**: `src/enrichers/rag_persona.py`
**Esforço**: Baixo (~15 linhas)
**Impacto**: Eliminar falsos positivos na dedup

### 2.3 Incluir Tema da Votação no Chunk (Alto)

**Problema**: `votacoes_camara.tema` é preenchido por `votacoes_temas.py` mas o indexer ignora — votos são descritos apenas por `descricao` (texto bruto).

**Solução**: Adicionar `tema` ao texto do chunk de voto.

**Arquivo**: `src/enrichers/rag_qdrant_indexer.py`
**Esforço**: Baixo (~5 linhas)
**Impacto**: LLM pode analisar padrões temáticos de votação

### 2.4 Validar Tamanho do Prompt (Médio)

**Problema**: Sem validação de que prompt + contexto cabem na janela de contexto do modelo (8K para gemma-4-e2b-it).

**Solução**: Estimar tokens antes de enviar; truncar chunks ou reduzir `RAG_MAX_CHUNKS` se necessário.

**Arquivo**: `src/enrichers/rag_persona.py`
**Esforço**: Médio (~30 linhas)
**Impacto**: Prevenir respostas truncadas ou erros silenciosos

### 2.5 Corrigir Ano Hardcoded em Votos (Médio)

**Problema**: `_extract_votos()` hardcodifica "em 2026" no texto do chunk.

**Solução**: Usar `EXTRACT(YEAR FROM data_votacao)` e incluir ano real no texto.

**Arquivo**: `src/enrichers/rag_qdrant_indexer.py`
**Esforço**: Baixo (~5 linhas)
**Impacto**: Precisão temporal nos dados de votação

### 2.6 Melhorar Match por Nome (Médio)

**Problema**: JOINs usam `parlamentar_nome = pd.nome_urna OR pd.nome` — fragilmente, perde registros.

**Solução**: Normalizar nomes (lowercase, remover acentos, trim) e usar `unaccent()` do PostgreSQL.

**Arquivo**: `src/enrichers/rag_qdrant_indexer.py`
**Esforço**: Médio (~20 linhas)
**Impacto**: Mais emendas/conexões vinculadas corretamente

### 2.7 Loop de Feedback de Qualidade (Baixo)

**Problema**: Personas são geradas mas nunca validadas.

**Solução**: Adicionar verificação pós-geração:
1. Contar seções obrigatórias na persona (PERFIL, AREAS, etc.)
2. Detectar se dados disponíveis foram ignorados
3. Flag `qualidade_check` na tabela `parlamentares_personas`

**Arquivo**: `src/enrichers/rag_persona.py`
**Esforço**: Médio (~40 linhas)
**Impacto**: Identificar personas de baixa qualidade para regeneração

---

## Fase 3 — Novas Fontes de Dados no RAG (Média Prioridade)

### 3.1 Indexar Tema das Votações (Fácil)

**Dados já existem**: `votacoes_camara.tema` preenchido por `votacoes_temas.py`
**Mudança**: Adicionar `tema` ao texto do chunk em `_extract_votos()`
**Impacto**: LLM pode analisar "votou contra pauta de saúde X vezes"

### 3.2 Indexar Emendas Discricionárias (Fácil)

**Dados já existem**: Tabela `emendas_discricionarias` preenchida por `discricionarias_sync.py`
**Mudança**: Novo chunk type `emenda_discricionaria` no indexer + query temática correspondente
**Impacto**: Visão completa de emendas (PIX + discricionárias)

### 3.3 Enriquecer Emendas com Dados de Compras (Médio)

**Dados já existem**: Tabela `compras_municipios` preenchida por `compras.py`
**Mudança**: JOIN em `_extract_emendas()` para adicionar padrões de compras públicas
**Impacto**: "Município recebeu R$2M mas tem zero compras registradas — suspeito"

### 3.4 Enriquecer Emendas com Indicadores Sociais (Médio)

**Dados já existem**: `saude_municipios`, `educacao_municipios` preenchidos por `saude_educacao.py`
**Mudança**: JOIN em `_extract_emendas()` para adicionar indicadores de saúde/educação
**Impacto**: "Emenda para saúde mas município tem 0 médicos/1000 hab"

### 3.5 Usar v_triangulo_politico para Conexões (Médio)

**Dados já existem**: View `v_triangulo_politico` (migration 015)
**Mudança**: Substituir query atual de `_extract_prefeitos_aliados()` pela view
**Impacto**: Análise completa Deputado→Prefeito→Vereadores com alinhamento partidário

### 3.6 Indexar Processos Judiciais (Médio)

**Dados já existem**: Tabela `beneficiario_processos` preenchida por `datajud.py`
**Mudança**: Novo chunk type `risco_judicial` no indexer
**Impacto**: Sinal de risco para municípios com processos ativos

### 3.7 Adicionar Dados Demográficos (Médio)

**Dados já existem**: `municipios_ibge` com pop, PIB, IDHM (fase 1b/1d)
**Mudança**: JOIN em `_extract_emendas()` para enriquecer contexto municipal
**Impacto**: "Emenda de R$500K para município de 5K habitantes = R$100/capita"

### 3.8 Adicionar Repasses FNDE (Médio)

**Dados já existem**: Tabela `fnde_repasses` preenchida por `fnde.py`
**Mudança**: JOIN em `_extract_emendas()` para municípios que também recebem FNDE
**Impacto**: Cruzamento educação + emendas parlamentares

### 3.9 Estender Janela do Diário Oficial (Difícil)

**Problema**: Busca apenas últimos 30 dias
**Solução**: Backfill histórico + expandir para 90 dias
**Impacto**: Mais atos do DOU por deputado, histórico temporal

---

## Fase 4 — Arquitetura e Manutenibilidade (Baixa Prioridade)

### 4.1 Refatorar Conexões (Médio)

**Problema**: Conexões PostgreSQL gerenciadas inconsistently (context manager vs manual).
**Solução**: Padronizar uso de `with get_connection() as conn:` em todas as funções.

### 4.2 Configuração Externa das Queries (Baixo)

**Problema**: 5 queries temáticas hardcoded.
**Solução**: Mover para `config/settings.py` ou arquivo YAML.

### 4.3 Métricas de Performance (Baixo)

**Problema**: Sem telemetria de latência por etapa.
**Solução**: Adicionar timing em cada fase (embed, search, build_prompt, generate).

### 4.4 Versionamento de Prompt (Baixo)

**Problema**: `RAG_PERSONA_VERSION=3` manual.
**Solução**: Auto-incrementar baseado em mudanças no template.

---

## Priorização e Cronograma

| Fase | Itens | Esforço | Impacto | Prazo Sugerido |
|------|-------|---------|---------|----------------|
| **Fase 1** (Eficiência) | 6 | 2-3 dias | Redução 50% latência | Semana 1 |
| **Fase 2** (Qualidade Recuperação) | 7 | 3-4 dias | Personas mais precisas | Semana 2 |
| **Fase 3** (Novos Dados) | 9 | 5-7 dias | 3x mais dados cruzados | Semanas 3-4 |
| **Fase 4** (Arquitetura) | 4 | 2-3 dias | Manutenibilidade | Semana 5 |
| **Total** | **26** | **12-17 dias** | | **5 semanas** |

---

## Métricas de Sucesso

| Métrica | Antes | Depois (Meta) |
|---------|-------|---------------|
| Latência por deputado (batch) | ~15s | ~7s (-53%) |
| Throughput batch (50 dep.) | ~12 min | ~4 min (-67%) |
| Tipos de chunk indexados | 6 | 9 (+50%) |
| Fontes de dados cruzadas | 12 tabelas | 23 tabelas (+92%) |
| Qualidade dedup | 100-char prefix | Hash MD5 completo |
| Re-ranking | Ordem de inserção | RRF por score |
| Temas de votação | Não indexados | Indexados |
| Janela DOU | 30 dias | 90 dias |

---

## Riscos e Mitigações

| Risco | Probabilidade | Mitigação |
|-------|---------------|-----------|
| VRAM insuficiente para paralelismo | Média | Limitar workers a 2-3; usar `ensure_model_loaded()` |
| Qdrant collection cresce demais | Baixa | Monitorar tamanho;implementar TTL para chunks antigos |
| LLM hallucina com mais dados | Média | Adicionar validação pós-geração (Fase 2.7) |
| Matching por nome continua frágil | Alta | Implementar fuzzy match + CNPJ como fallback |
| SICONFI com atraso de 1-2 anos | Baixa | Documentar limitação;usar dados disponíveis como proxy |

---

## Conclusão

O pipeline RAG v3 tem uma base sólida mas desperdiça ~50% do processamento em chamadas duplicadas e não aproveita 11 fontes de dados já disponíveis no banco. As melhorias das Fases 1 e 2 são quick-wins de alto impacto. A Fase 3 transforma radicalmente a riqueza das personas ao cruzar emendas com compras, saúde, educação, processos judiciais e FNDE.
