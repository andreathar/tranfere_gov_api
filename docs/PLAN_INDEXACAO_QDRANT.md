# Plano: Indexação Qdrant Completa + Personas com Modelo Rápido

## Estado Atual

### DB (tabelas com dados)
| Tabela | Linhas | Indexada no Qdrant? |
|--------|--------|---------------------|
| planos_acao | 9.598 | ✅ (via emendas) |
| parlamentares_dados | 512 | ✅ (perfil) |
| parlamentar_proposicoes | 27.553 | ✅ |
| votos_camara | 35.436 | ✅ (voto) |
| municipios_financeiro | 16.542 | ❌ |
| municipios_ibge | 5.570 | ⚠️ parcial (demografia) |
| prefeitos_dados | 5.545 | ⚠️ parcial (conexao_politica) |
| beneficiarios | 4.120 | ❌ |
| beneficiario_ibge_map | 4.048 | ❌ |
| saude_municipios | 4.045 | ⚠️ parcial |
| educacao_municipios | 4.045 | ⚠️ parcial |
| parlamentar_beneficiario | 8.408 | ❌ |
| vereadores_dados | 430.827 | ⚠️ parcial |
| emendas | 703 | ✅ |
| compras_municipios | 398 | ⚠️ parcial |
| fnde_repasses | 190 | ❌ |
| diario_oficial_atos | 63 | ✅ |
| parlamentar_alertas | 58 | ❌ |
| beneficiario_processos | 66 | ⚠️ parcial |
| senadores_dados | 81 | ❌ |
| emendas_discricionarias | 0 | (vazio) |
| votacoes_camara | 100 | ✅ (tema do voto) |

### Qdrant
- Collection: `deputados_perfis` — 39.703 vetores, 768d, cosine
- Chunk types: 11 (perfil, proposicao, emenda, voto, diario_oficial, conexao_politica, emenda_discricionaria, compras_municipio, indicadores_sociais, risco_judicial, demografia_municipio)

### Modelos Disponíveis (LocalAI)
| Modelo | Params | Velocidade | Uso |
|--------|--------|-----------|-----|
| gemma-4-e2b-it | 2B | ~37 tok/s | Atual (personas) |
| qwen2.5-1.5b-instruct-q4-k-m | 1.5B | ~89 tok/s | Rápido |
| llama-3.2-3b-instruct:q4_k_m | 3B | ~50 tok/s | Equilibrado |
| llama-3.1-8b-q4-k-m | 8B | ~8 tok/s | LENTO (atual persona lote) |
| qwen3.5-9b-dossie | 9B | ~10 tok/s | Dossiê (lento) |
| nomic-embed-text-v1.5 | -- | -- | Embeddings |

---

## Fase 1: Expandir Indexação Qdrant (novos chunk types)

### 1.1 Enriquecer chunk `municipio_financeiro`
**Fonte:** `municipios_financeiro` (16.542 linhas)
**Chunk text:** Resumo financeiro do município: arrecadação IPTU/ISS/ICMS/FPM, despesas, superávit/déficit.
**Payload:** `{type: "municipio_financeiro", municipio_ibge_id, uf, ano, arrecadacao_total, despesas_total}`
**Ganho:** Permite perguntas como "Quais municípios receptores têm melhor arrecadação?"

### 1.2 Enriquecer chunk `parlamentar_resumo`
**Fonte:** JOIN `parlamentar_beneficiario` + `parlamentares_dados`
**Chunk text:** Resumo consolidado: total emendas, municípios atendidos, valores, partidos aliados.
**Payload:** `{type: "parlamentar_resumo", deputado_id, uf, partido}`
**Ganho:** Visão holística do deputado (não só proposições isoladas)

### 1.3 Enriquecer chunk `beneficiario`
**Fonte:** `beneficiarios` + `validacao_cnpj` + `beneficiario_ibge_map`
**Chunk text:** Perfil do beneficiário: CNPJ, razão social, município, UF, situação cadastral.
**Payload:** `{type: "beneficiario", beneficiario_id, uf, municipio_ibge_id}`
**Ganho:** Busca por beneficiário específico, cruzamento com emendas

### 1.4 Enriquecer chunk `prefeito`
**Fonte:** `prefeitos_dados`
**Chunk text:** Perfil do prefeito: nome, município, partido, ano eleição, coligação.
**Payload:** `{type: "prefeito", municipio_ibge_id, uf, partido, ano}`
**Ganho:** Cruzamento deputado × prefeito (fisiologismo eleitoral)

### 1.5 Enriquecer chunk `senador`
**Fonte:** `senadores_dados`
**Chunk text:** Perfil do senador: nome, partido, UF, comissões, mandato.
**Payload:** `{type: "senador", senador_id, uf, partido}`
**Ganho:** Conexões federais (Senado ↔ Câmara ↔ Emendas)

### 1.6 Enriquecer chunk `fnde_repasses`
**Fonte:** `fnde_repasses`
**Chunk text:** Repasse FNDE: programa, município, valor, ano, situação.
**Payload:** `{type: "fnde_repasses", municipio_ibge_id, uf, programa, ano}`
**Ganho:** Educação municipal vinculada a emendas

### 1.7 Enriquecer chunk `indicadores_municipal`
**Fonte:** JOIN `saude_municipios` + `educacao_municipios` + `municipios_ibge`
**Chunk text:** Painel municipal:.IDEB, taxas de escolaridade, IDHM, mortalidade, leitos.
**Payload:** `{type: "indicadores_municipal", municipio_ibge_id, uf}`
**Ganho:** Análise de impacto social por município receptor

### 1.8 Enriquecer chunk `vereadores_resumo`
**Fonte:** `vereadores_dados` (agregados por município)
**Chunk text:** Resumo: N vereadores, partido dominante, coligações no município.
**Payload:** `{type: "vereadores_resumo", municipio_ibge_id, uf, ano}`
**Ganho:** Rede política local do deputado

---

## Fase 2: Otimizar Indexador

### 2.1 Paginação incremental
- Flag `--incremental`: só indexa dados novos desde último `extract_log`
- Flag `--force`: reindexa tudo
- Evita reprocessar 430k vereadores toda vez

### 2.2 Batch embedding
- Acumula textos e chama `embed_text_batch()` em lotes de 50
- Reduz chamadas HTTP ao LocalAI de N para N/50

### 2.3 Dedup por hash
- MD5 do texto embeddings → evita re-embedding se conteúdo não mudou
- Persiste hash no payload Qdrant

---

## Fase 3: Personas com Modelo Rápido

### 3.1 Trocar modelo padrão de persona
**Atual:** `gemma-4-e2b-it` (2B, ~37 tok/s) — qualidade OK mas lentidão
**Novo:** `qwen2.5-1.5b-instruct-q4-k-m` (1.5B, ~89 tok/s) — 2.4x mais rápido

**Alternativa (melhor qualidade):** `llama-3.2-3b-instruct:q4_k_m` (3B, ~50 tok/s)
- Melhor que gemma em português
- 2x mais rápido que gemma
- Boa razão qualidade/velocidade

**Decisão:** Usar `llama-3.2-3b-instruct:q4_k_m` como padrão de persona
- `gemma-4-e2b-it` para queries simples de RAG
- `llama-3.1-8b-q4-k-m` para análise investigativa profunda (raro)

### 3.2 Atualizar `rag_persona.py`
- Trocar `RAG_LLM_MODEL` default para `llama-3.2-3b-instruct:q4_k_m`
- Adicionar flag `--modelo` para override
- Reduzir `max_tokens` de 2048 para 1500 (personas não precisam de textão)
- Adicionar flag `--reindexar` para re-gerar apenas personas com dados novos

### 3.3 Estimativa de tempo
- 512 deputados × ~30s por persona (llama-3.2-3B) = ~4.3 horas
- vs 512 × ~180s (llama-3.1-8B) = ~25.6 horas (6x mais lento)
- vs 512 × ~40s (gemma-2B) = ~5.6 horas

---

## Fase 4: Schema Qdrant Otimizado

### 4.1 Payload indexes expandidos
Adicionar indexes para novos campos:
- `municipio_ibge_id` (INTEGER) — busca por município
- `ano` (INTEGER) — filtro temporal
- `partido` (KEYWORD) — busca por partido
- `programa` (KEYWORD) — filtro por programa

### 4.2 HNSW tuning
- `m=32` (aumentar de 16) para coleção maior
- `ef_construct=200` (manter)
- `ef_search=128` (aumentar recall)

---

## Fase 5: Execução

### Ordem recomendada:
1. `sync_proposicoes --ano-inicio 2023` (completar proposições)
2. `rag_qdrant_indexer --rebuild` (reindexar tudo com novos chunks)
3. `rag_persona --lote 512 --modelo llama-3.2-3b-instruct:q4_k_m`

### Comandos:
```bash
# 1. Completar proposições 2023+
python3 -m src.enrichers.sync_proposicoes --ano-inicio 2023 --itens 200

# 2. Reindexar Qdrant (com novos chunks)
python3 -m src.enrichers.rag_qdrant_indexer --rebuild

# 3. Gerar personas (modelo rápido)
python3 -m src.enrichers.rag_persona --lote 512 --modelo llama-3.2-3b-instruct:q4_k_m
```

---

## Impacto Esperado

| Métrica | Antes | Depois |
|---------|-------|--------|
| Vetores Qdrant | 39.703 | ~80.000+ |
| Chunk types | 11 | 18 |
| Tabelas indexadas | 8 | 16 |
| Velocidade persona | ~180s/deputado | ~30s/deputado |
| Tempo total personas | ~25h | ~4h |
| Cobertura deputados | 335/512 | 512/512 |
