# Plano de Melhoria: RAG Persona de Deputados

**Data:** 2026-07-26
**Status:** Proposta
**Escopo:** Performance do workflow + Qualidade da avaliação IA

---

## 1. Diagnóstico do Estado Atual

### Dados Disponíveis vs. Indexados

| Fonte | Registros | Indexados no Qdrant? | Impacto na Análise |
|-------|----------:|:--------------------:|-------------------:|
| `parlamentares_dados` | 564 deputados | ✅ 1 chunk/deputado | Base do perfil |
| `parlamentar_proposicoes` | 12.923 | ✅ 1 chunk/proposição | Alto — PLs do deputado |
| `planos_acao` (emendas) | 9.598 | ✅ 1 chunk/emenda (max 20) | Alto — verba transferida |
| `diario_oficial_atos` | 60 | ✅ 1 chunk/ato | Baixo — dados muito escassos |
| `parlamentar_alertas` | 55 | ❌ Não indexado diretamente | Médio — alertas de fiscalização |
| **`votos_camara`** | **35.436** | **❌ NÃO INDEXADO** | **ALTO — padrão de voto do deputado** |
| `votacoes_camara` | 100 (nominais) | ❌ Não indexado | Médio — contexto das votações |
| `parlamentares_dados` (TSE) | 564 | Parcial (nome/partido/UF) | Médio — patrimônio, votos eleitorais |
| `municipios_financeiro` | ~5.500 | ❌ Não indexado | Médio — dados financeiros dos municípios |
| `prefeitos_dados` | N/A | ❌ Não indexado | Baixo — contexto municipal |

### Persona Atual — Números

| Métrica | Valor |
|---------|-------|
| Personas geradas | 325 |
| Tamanho médio | 512 caracteres (~80 palavras) |
| Tamanho máximo | 3.688 caracteres |
| Duração média | 9.3 segundos |
| Prompt usado | Genérico (1 fixo) |
| Dados de votação | ❌ Ausente |

### ⚠️ Problemas Críticos Identificados

1. **Votos não indexados** — 35.436 votos nominais ignorados. O LLM não sabe como o deputado vota.
2. **Persona muito curta** — 512 chars é uma nota de rodapé, não um dossiê. Deputados com dados ricos (props + emendas + votos) poderiam gerar 3.000-5.000 chars.
3. **Prompt genérico** — Um único prompt "sirva para todos". Não adapta a profundidade ao volume de dados disponível.
4. **Sem cross-referencing** — O LLM analisa emendas OU votos, nunca ambos juntos. Ex: "Deputado X votou contra PEC da saúde mas destinou R$ 2M em emendas para hospitais."
5. **Sem re-ranking** — Top-15 chunks são todos tratados igual. Chunks irrelevantes diluem a qualidade.
6. **Tabela `parlamentares_personas` sem migration** — Criada via `CREATE TABLE IF NOT EXISTS` no script Python. Sem índices, sem constraint de unicidade.
7. **`embed_text()` bypassa `LocalAIClient`** — Não usa retry nem cache do client.

---

## 2. Plano de Melhorias — Priorizado

### Fase 1: Dados (Impacto ALTO, Esforço MÉDIO)

#### 1.1 Indexar votos nominais no Qdrant
**Arquivo:** `src/enrichers/rag_qdrant_indexer.py`

Adicionar fonte de dados `votos_camara` + `votacoes_camara`:

```python
# Chunk de votos: agregar por deputado → tipo de voto + contexto
cur.execute("""
    SELECT vc.descricao, v.tipo_voto, COUNT(*) as n
    FROM votos_camara v
    JOIN votacoes_camara vc ON v.votacao_id = vc.votacao_id
    WHERE v.deputado_id = %s
    GROUP BY vc.descricao, v.tipo_voto
    ORDER BY n DESC
    LIMIT 50
""", (deputado_id,))
```

**Chunks gerados:**
- "O deputado votou 'Sim' 45 vezes, 'Não' 8 vezes, 'Abstenção' 2 vezes em 2026."
- "Votou 'Não' na PEC da reforma administrativa (PLP 77/2026)."
- "Votou 'Sim' na PL 6359/2025 (orçamento)."
- "Padrão: alinhado com bancada do governo em 83% das votações."

**Impacto estimado:** +40% de riqueza na análise comportamental.

#### 1.2 Indexar dados financeiros dos municípios beneficiários
**Arquivo:** `src/enrichers/rag_qdrant_indexer.py`

Para cada emenda, enriquecer com dados SICONFI:

```python
# Para cada emenda, buscar dados financeiros do município
cur.execute("""
    SELECT b.nome, b.uf, pa.valor_total, o.descricao,
           mf.receita_total, mf.despesa_total, mf.divida_total
    FROM planos_acao pa
    JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
    JOIN objetos o ON pa.objeto_id = o.objeto_id
    LEFT JOIN municipios_financeiro mf ON b.cnpj = mf.cnpj
    WHERE pa.parlamentar_nome = %s
""", (nome,))
```

**Chunk:** "Emenda de R$ 500k para o município de X-UF (receita municipal: R$ 12M, despesa: R$ 11M, dívida: R$ 8M)."

**Impacto estimado:** +25% de capacidade de cruzamento financeiro.

#### 1.3 Migration正规 para `parlamentares_personas`
**Arquivo:** `data/migration_017_rag_personas.sql`

```sql
CREATE TABLE IF NOT EXISTS parlamentares_personas (
    id SERIAL PRIMARY KEY,
    deputado_id INTEGER REFERENCES parlamentares_dados(deputado_id),
    query_text TEXT,
    contexto_rag TEXT,           -- NOVO: chunks recuperados do Qdrant
    analise_gerada TEXT,
    versao_prompt INTEGER DEFAULT 1,  -- NOVO: versionamento
    fontes_usadas TEXT[],        -- NOVO: ['emendas', 'votos', 'proposicoes']
    data_analise TIMESTAMPTZ DEFAULT NOW(),
    duracao_segundos NUMERIC,
    UNIQUE (deputado_id, versao_prompt)  -- NOVO: 1 persona por versão
);

CREATE INDEX IF NOT EXISTS idx_personas_deputado ON parlamentares_personas(deputado_id);
CREATE INDEX IF NOT EXISTS idx_personas_versao ON parlamentares_personas(versao_prompt);
```

---

### Fase 2: Qualidade da Análise (Impacto ALTO, Esforço MÉDIO)

#### 2.1 Multi-Query RAG
**Arquivo:** `src/enrichers/rag_persona.py`

Em vez de 1 query genérica, usar 3-4 queries temáticas:

```python
QUERIES_TEMATICAS = [
    "Padrão de voto e alinhamento político do deputado em votações nominais",
    "Emendas parlamentares, municípios beneficiários e valores transferidos",
    "Proposições legislativas apresentadas e áreas temáticas de foco",
    "Atos no diário oficial, fiscalização e movimentações relevantes",
]

def search_context_multiquery(deputado_id: int, top_k_per_query: int = 8) -> list[str]:
    """Executa múltiplas queries e faz merge + dedup dos resultados."""
    all_chunks = []
    for q in QUERIES_TEMATICAS:
        chunks = search_context_qdrant(deputado_id, q, limit=top_k_per_query)
        all_chunks.extend(chunks)
    # Dedup por texto
    seen = set()
    unique = []
    for c in all_chunks:
        key = c[:100]
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique[:25]  # top-25 únicos
```

**Impacto estimado:** +60% de cobertura temática (votos + emendas + props + DO).

#### 2.2 Prompt Adaptativo por Volume de Dados
**Arquivo:** `src/enrichers/rag_persona.py`

```python
def build_analysis_prompt(context_list: list[str], perfil: dict) -> str:
    """Monta prompt adaptativo baseado na quantidade e tipo de dados."""
    n_votos = sum(1 for c in context_list if "[VOTO]" in c)
    n_emendas = sum(1 for c in context_list if "[EMENDA]" in c)
    n_props = sum(1 for c in context_list if "[PROPOSICAO]" in c)

    # Seção de votos (só aparece se houver dados)
    secao_votos = ""
    if n_votos > 0:
        secao_votos = """
        6. **PADRÃO DE VOTO**: Analise o alinhamento político do deputado.
           Identifique: votos com o governo vs. oposição, temas onde divergiu
           da bancada, e consistência do discurso vs. voto real.
        """

    # Seção de emendas (só aparece se houver dados)
    secao_emendas = ""
    if n_emendas > 0:
        secao_emendas = """
        7. **EMENDAS PIX**: Mapeie concentração de verbas por município/estado.
           Identifique: municípios pequenos com valores altos, entidades
           recorrentes, e eventual favorecimento.
        """

    return f"""
    Você é um Analista Investigativo especializado em Contas Públicas.

    CONTEXTO ({len(context_list)} fontes: {n_votos} votos, {n_emendas} emendas, {n_props} proposições):
    {chr(10).join(f'- {c}' for c in context_list)}

    ANÁLISE REQUERIDA:
    1. **PERFIL**: Nome, partido, UF, exercício
    2. **ÁREAS TEMÁTICAS**: Concentração de atuação (saúde, segurança, etc.)
    3. **CRUZAMENTO DE DADOS**: Conecte votos com emendas.
       Ex: "Votou contra aPEC da saúde mas destinou R$ 2M para hospitais"
    4. **ALINHAMENTO POLÍTICO**: Situação vs. oposição, fisiologismo
    5. **ANOMALIAS**: Valores atípicos, entidades obscuras, padrões suspeitos
    {secao_votos}
    {secao_emendas}

    Formato: Markdown, tom firme, fundamentado em dados reais.
    NÃO invente informações ausentes do contexto.
    """
```

**Impacto estimado:** +50% de profundidade analítica (análise contextualizada, não genérica).

#### 2.3 Salvar Contexto Rastreável
**Arquivo:** `src/enrichers/rag_persona.py`

```python
# Após gerar, salvar os chunks que o LLM viu
cur.execute("""
    INSERT INTO parlamentares_personas
        (deputado_id, query_text, contexto_rag, analise_gerada,
         fontes_usadas, versao_prompt, duracao_segundos)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (deputado_id, versao_prompt) DO UPDATE SET
        analise_gerada = EXCLUDED.analise_gerada,
        contexto_rag = EXCLUDED.contexto_rag,
        data_analise = NOW()
""", (dep_id, query, "\n".join(context_list), analise,
      fontes_list, VERSAO_PROMPT, duracao))
```

---

### Fase 3: Performance do Workflow (Impacto MÉDIO, Esforço BAIXO)

#### 3.1 Batch Embedding
**Arquivo:** `src/enrichers/rag_qdrant_indexer.py`

Atualmente: 1 request HTTP por chunk. Para 20 emendas + 10 props + 1 voto = 31 requests.

```python
# DEPOIS: 1 request batch com todos os textos
texts = [doc["text"] for doc in docs]
vectors = embed_text_batch(texts)  # POST com input=[...] array

def embed_text_batch(texts: list[str]) -> list[list[float]]:
    """Embedding em batch via LocalAI."""
    url = f"{LOCALAI_BASE_URL}/embeddings"
    payload = {"input": texts, "model": EMBEDDER_MODEL}
    resp = requests.post(url, json=payload, timeout=60)
    if resp.status_code == 200:
        return [d["embedding"] for d in resp.json()["data"]]
    return []
```

**Impacto estimado:** 30x mais rápido no indexing (31 requests → 1 request).

#### 3.2 Evitar Reload de Modelo entre Batch
**Arquivo:** `src/enrichers/rag_persona.py`

Atualmente: `ensure_model_loaded` descarrega e recarrega o modelo para cada lote.

```python
# DEPOIS: Manter modelo carregado durante todo o lote
def generate_batch(deputados: list[tuple], query: str = None):
    llm_model = LOCALAI_MODELS["general"]
    localai_manager.ensure_model_loaded(llm_model)  # 1x só
    ai_client = LocalAIClient(model=llm_model)

    for dep_id, nome in deputados:
        # Usa o mesmo client, sem reload
        analise, duracao = _generate_with_client(ai_client, dep_id, nome, query)
        _save_persona(dep_id, query, analise, duracao)
```

**Impacto estimado:** -50% de tempo em lotes (evita unload/load循环).

#### 3.3 Cache de Embeddings
**Arquivo:** `src/enrichers/rag_qdrant_indexer.py`

Atualmente: `embed_text()` faz request HTTP direto, sem cache.

```python
# Usar o LocalAIClient que já tem cache
from src.localai_client import LocalAIClient
_client = LocalAIClient(model=EMBEDDER_MODEL)

def embed_text_cached(text: str) -> list[float]:
    """Embedding com cache via LocalAIClient."""
    result = _client.embed(text)
    return result if result else []
```

**Impacto estimado:** -70% de requests em re-indexing (cache hit para textos idênticos).

---

### Fase 4: Infraestrutura (Impacto MÉDIO, Esforço BAIXO)

#### 4.1 Migration正规
Criar `data/migration_017_rag_personas.sql` com:
- Schema da tabela `parlamentares_personas`
- Constraint `UNIQUE(deputado_id, versao_prompt)`
- Índices em `deputado_id` e `versao_prompt`
- Coluna `contexto_rag` para auditoria

#### 4.2 Centralizar Constantes
**Arquivo:** `config/settings.py`

```python
# RAG Settings
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = "deputados_perfis"
EMBEDDER_MODEL = "nomic-embed-text-v1.5"
EMBEDDING_DIM = 768
RAG_LLM_MODEL = LOCALAI_MODELS["general"]
RAG_PERSONA_VERSION = 2  # Incrementar para regenerar todas as personas
```

**Arquivos:** `rag_qdrant_indexer.py` e `rag_persona.py` → importar de `config.settings`.

#### 4.3 Error Handling Melhorado
- `embed_text()` retornar `None` em vez de `[]` (semântica mais clara)
- Retry com backoff no indexer (atualmente falha silenciosamente)
- Log de progresso a cada 10 deputados no lote
- Skip de deputados com < 2 chunks disponíveis (análise pobre demais)

---

## 3. Roadmap de Implementação

| Fase | Item | Prioridade | Esforço | Impacto |
|------|------|-----------|---------|---------|
| 1.1 | Indexar votos nominais | 🔴 Alta | 2h | +40% riqueza |
| 1.3 | Migration parlamentares_personas | 🔴 Alta | 30min | Correção técnica |
| 2.1 | Multi-Query RAG | 🔴 Alta | 3h | +60% cobertura |
| 2.2 | Prompt adaptativo | 🔴 Alta | 2h | +50% profundidade |
| 4.2 | Centralizar constantes | 🟡 Média | 30min | Manutenção |
| 3.1 | Batch embedding | 🟡 Média | 1h | 30x mais rápido |
| 3.2 | Evitar reload em lote | 🟡 Média | 1h | -50% tempo lote |
| 1.2 | Indexar dados financeiros | 🟡 Média | 3h | +25% cruzamento |
| 2.3 | Salvar contexto rastreável | 🟢 Baixa | 1h | Auditoria |
| 3.3 | Cache de embeddings | 🟢 Baixa | 30min | -70% re-requests |
| 4.3 | Error handling | 🟢 Baixa | 1h | Robustez |

---

## 4. Resultado Esperado (pós-Fase 1+2)

| Métrica | Antes | Depois |
|---------|-------|--------|
| Tamanho médio da persona | 512 chars | ~2.500 chars |
| Fontes de dados usadas | 2 (emendas + props) | 5 (+votos, +votações, +financeiro) |
| Queries RAG | 1 genérica | 4 temáticas |
| Profundidade analítica | Superficial | Cruzamento voto × emenda |
| Dados de votação no LLM | ❌ Nenhum | ✅ Padrão de voto, alinhamento |
| Re-ranking | ❌ Nenhum | Parcial (dedup por query) |
| Contexto rastreável | ❌ Não | ✅ Salvo no DB |
| Tempo de geração (lote 50) | ~8 min | ~5 min |

---

## 5. Comandos para Validação

```bash
# Rodar migration
psql -U cognee -h 127.0.0.1 -d transferegov_db -f data/migration_017_rag_personas.sql

# Re-indexar Qdrant com novos dados (votos incluídos)
./run.sh cron-qdrant --limit 10 --nome "Afonso Florence"

# Regenerar persona com multi-query
./run.sh cron-dossie --nome "Afonso Florence"

# Comparar antes/depois
psql -U cognee -h 127.0.0.1 -d transferegov_db -c "
  SELECT versao_prompt, COUNT(*), AVG(LENGTH(analise_gerada))
  FROM parlamentares_personas GROUP BY versao_prompt
"

# Gerar em lote (com modelo já carregado)
./run.sh cron-dossie --lote 50
```
