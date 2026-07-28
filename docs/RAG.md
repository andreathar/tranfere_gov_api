# RAG — Sistema de Recuperação e Geracao de Dossies de Deputados

Documentacao tecnica do pipeline RAG v2/v3: indexacao vetorial, recuperacao multi-query,
geracao adaptativa via LLM local e persistencia de personas de parlamentares.

---

## Sumario

1. [Visao Geral](#1-visao-geral)
2. [Pre-requisitos](#2-pre-requisitos)
3. [Indexacao](#3-indexacao)
4. [Recuperacao Multi-Query](#4-recuperacao-multi-query)
5. [Geracao Adaptativa](#5-geracao-adaptativa)
6. [Persistencia](#6-persistencia)
7. [Comandos](#7-comandos)
8. [Dependencias](#8-dependencias)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Visao Geral

O sistema RAG (Retrieval-Augmented Generation) gera dossies comportamentais de deputados
federais combinando dois estagios:

1. **Indexacao vetorial** (`rag_qdrant_indexer.py`): extrai dados de 6 fontes do banco
   PostgreSQL, gera embeddings via modelo local e persiste vetores no Qdrant.

2. **Geracao de persona** (`rag_persona.py`): recupera chunks relevantes com 5 queries
   tematicas, monta um prompt adaptativo e envia a um LLM local para gerar o dossie.

### Arquitetura

```
PostgreSQL (banco transferegov_db)
    |
    v
rag_qdrant_indexer.py ──► nomic-embed-text-v1.5 (LocalAI) ──► Qdrant (colecao: deputados_perfis)
                                                                     |
                                                                     v
rag_persona.py ──► 5 queries tematicas + embed ──► Qdrant (busca filtrada)
        |
        v
    Prompt adaptativo ──► gemma-4-e2b-it (LocalAI) ──► Dossie em Markdown
        |
        v
    parlamentares_personas (PostgreSQL)
```

### Modelos Utilizados

| Modelo | Funcao | Dimensao | Velocidade |
|--------|--------|----------|------------|
| `nomic-embed-text-v1.5` | Embeddings | 768d | -- |
| `gemma-4-e2b-it` | Geracao de dossie (padrao) | -- | 36.8 tok/s |
| `llama-3.1-8b-q4-k-m` | Analise profunda (alternativo) | -- | 7.7 tok/s |

---

## 2. Pre-requisitos

### Qdrant

Servidor vetorial para armazenamento e busca por similaridade coseno.

| Parametro | Valor | Configuracao |
|-----------|-------|--------------|
| URL | `http://localhost:6333` | `QDRANT_URL` em `config/settings.py` |
| Colecao | `deputados_perfis` | `QDRANT_COLLECTION` |
| Dimensao | 768 | `EMBEDDING_DIM` |
| Metrica | Cosine | Configurada na criacao da colecao |

Configuracao HNSW da colecao:

- `m = 16` (conexoes por no)
- `ef_construct = 200` (precisao na insercao)
- `full_scan_threshold = 10000`

Payload indexes (para busca filtrada):

- `deputado_id`: INTEGER (filtro por deputado)
- `type`: KEYWORD (filtro por tipo de chunk)
- `uf`: KEYWORD (filtro por UF)

Instalacao do Qdrant:

```bash
# Via Docker (recomendado)
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage \
  qdrant/qdrant:latest
```

### LocalAI

Servidor de inferencia local com API compativel OpenAI.

| Parametro | Valor | Configuracao |
|-----------|-------|--------------|
| URL | `http://localhost:8080/v1` | `LOCALAI_BASE_URL` |
| Timeout | 300s | `LOCALAI_TIMEOUT` |
| Retries | 3 | `LOCALAI_MAX_RETRIES` |

O `LocalAIClient` (`src/localai_client.py`) fornece as primitivas:

- `embed(texts)` — batch embedding de listas de texto
- `chat(prompt, system)` — geracao de texto via LLM

### GPU

O gerenciador de VRAM (`src/localai_manager.py`) controla a exclusividade de GPU:

- Antes de cada operacao, `ensure_model_loaded(model)` descarrega modelos inativos
  via `/backend/shutdown` para liberar VRAM
- Evita erros OOM (OutOfMemory) e RPC EOF
- Apenas um modelo deve estar carregado por vez em GPUs com VRAM limitada

Recomendacoes de GPU:

- **Minimo**: 4 GB VRAM (cabe gemma-4-e2b-it ou nomic-embed-text)
- **Ideal**: 8 GB VRAM (permite rodar LLM + embedder sem descarregar)
- **Otimizado**: 16+ GB VRAM (permite carregar modelos maiores como llama-3.1-8b)

---

## 3. Indexacao

Modulo: `src/enrichers/rag_qdrant_indexer.py`

A indexacao extrai chunks de texto de 6 fontes distintas para cada deputado, gera
embeddings em batch via `nomic-embed-text-v1.5` e insere vetores no Qdrant com
upsert idempotente (UUID5 deterministico baseado em `deputado_id + texto`).

### Fontes de dados (6 tipos de chunk)

#### 3.1 perfil

- **Tabela**: `parlamentares_dados`
- **Funcao extratora**: `_extract_perfil()`
- **Quantidade**: 1 chunk por deputado
- **Campos**: nome completo, sigla_partido, uf
- **Formato do texto**:
  ```
  Deputado Federal: {nome}. Partido: {partido}. Estado: {uf}.
  Atuacao legislativa na Camara dos Deputados.
  ```
- **Metadados**: `type=perfil`, `deputado_id`

#### 3.2 proposicao

- **Tabela**: `parlamentar_proposicoes`
- **Funcao extratora**: `_extract_proposicoes()`
- **Quantidade**: 0 a N chunks (uma proposicao por chunk)
- **Campos**: sigla_tipo, numero, ano, ementa
- **Filtro**: apenas proposicoes com ementa nao nula
- **Formato do texto**:
  ```
  Proposicao do deputado {nome}: {sigla} {num}/{ano}. Ementa: {ementa}
  ```
- **Metadados**: `type=proposicao`, `deputado_id`, `ref="{sigla} {num}/{ano}"`

#### 3.3 emenda

- **Tabelas**: `planos_acao`, `beneficiarios`, `objetos`, `parlamentares_dados`,
  `beneficiario_ibge_map`, `municipios_financeiro` (enriquecimento SICONFI)
- **Funcao extratora**: `_extract_emendas()`
- **Quantidade**: ate 20 chunks (ordenados por `valor_total DESC`)
- **Campos**: municipio, UF, objeto, valor_total, receitas_orcamentarias,
  despesas_totais, divida_passiva
- **Formato do texto**:
  ```
  Emenda do deputado {nome} para {municipio}-{uf}. Objeto: {obj}. Valor: R$ {valor}.
  Dados financeiros do municipio: receita orcamentaria R$ {receita},
  despesas totais R$ {despesa}. Divida passiva R$ {divida}.
  ```
- **Metadados**: `type=emenda`, `deputado_id`, `ref="Emenda para {municipio}"`
- **Nota**: os dados financeiros (receita, despesa, divida) sao incluidos apenas
  quando disponiveis na tabela `municipios_financeiro`

#### 3.4 voto

- **Tabelas**: `votos_camara`, `votacoes_camara`
- **Funcao extratora**: `_extract_votos()`
- **Quantidade**: 1 chunk de resumo + ate 30 chunks individuais
- **Estrutura**:
  - **Resumo agregado**: contagem de votos SIM/NAO/ABSTENCAO com percentual
  - **Votos individuais**: as 30 votacoes mais recentes, com tag `[DISSENSO]`
    quando o voto do deputado contradiz o resultado da votacao
- **Formato do texto (resumo)**:
  ```
  Padrao de voto do deputado {nome} em {total} votacoes nominais em 2026:
  'Sim': {n} vezes ({pct}%), 'Nao': {n} vezes ({pct}%).
  ```
- **Formato do texto (individual)**:
  ```
  [DISSENSO] Deputado {nome} votou '{tipo}' em: {descricao}
  ```
- **Metadados**: `type=voto`, `deputado_id`
- **Deteccao de dissenso**: o voto e marcado como dissenso quando o deputado votou
  "Nao" ou "Obstrucao" em proposicoes aprovadas, ou "Sim" em reprovadas

#### 3.5 diario_oficial

- **Tabelas**: `parlamentar_alertas`, `diario_oficial_atos`
- **Funcao extratora**: `_extract_diario_oficial()`
- **Quantidade**: 0 a N chunks
- **Campos**: orgao, tipo_ato, resumo_ia, valor_financeiro, entidades_citadas
- **Formato do texto**:
  ```
  Ato Oficial ({tipo_ato}) em {orgao}. Resumo: {resumo}.
  Entidades citadas: {entidades}. Valor associado: R$ {valor}.
  ```
- **Metadados**: `type=diario_oficial`, `deputado_id`, `ref="Ato: {tipo_ato}"`

#### 3.6 conexao_politica

- **Tabelas**: `planos_acao`, `beneficiarios`, `parlamentares_dados`,
  `beneficiario_ibge_map`, `prefeitos_dados` (enriquecimento TSE)
- **Funcao extratora**: `_extract_prefeitos_aliados()`
- **Quantidade**: ate 15 chunks (ordenados por `valor_total DESC`)
- **Campos**: municipio, partido_deputado, prefeito_nome, partido_prefeito,
  coligacao, valor_total
- **Classificacao da relacao**:
  - `MESMO PARTIDO DO DEPUTADO` — partido do prefeito identico ao do deputado
  - `ALIANCA/COLIGACAO` — partido do prefeito presente na coligacao do deputado
  - `OPOSICAO/OUTRO PARTIDO` — nenhuma das anteriores
- **Formato do texto**:
  ```
  Conexao politica local em {municipio}: Prefeito {prefeito} ({partido}).
  Relacao com o deputado {nome} ({partido_dep}): {relacao}.
  Total emendas recebidas: R$ {valor}.
  ```
- **Metadados**: `type=conexao_politica`, `deputado_id`, `ref="Prefeito de {municipio}"`

### Ordem de extracao

A funcao `get_deputado_texts()` orquestra a extracao na seguinte ordem:

1. perfil
2. proposicoes
3. emendas
4. votos
5. diario_oficial
6. conexao_politica

### Processo de indexacao

1. Garantir/criar colecao Qdrant com payload indexes
2. Para cada deputado, extrair chunks das 6 fontes
3. Gerar embeddings em batch (1 request para todos os chunks do deputado)
4. Gerar UUID5 deterministico para cada point (idempotente)
5. Upsert no Qdrant

---

## 4. Recuperacao Multi-Query

Modulo: `src/enrichers/rag_persona.py`

A recuperacao utiliza 5 queries tematicas para cobrir todas as dimensoes do perfil
do deputado. Cada query e embedada e executada contra o Qdrant com filtro por
`deputado_id`.

### Queries Tematicas

As 5 queries exatas utilizadas no sistema:

1. `"Padrao de voto e alinhamento politico do deputado em votacoes nominais no plenario"`
2. `"Emendas parlamentares Pix, municipios beneficiarios e valores transferidos"`
3. `"Proposicoes legislativas apresentadas e areas tematicas de foco"`
4. `"Atos no diario oficial, fiscalizacao, decretos e movimentacoes relevantes"`
5. `"Conexao politica local, partido dos prefeitos beneficiados e alinhamento eleitoral municipal"`

### Fluxo de busca

```
Para cada uma das 5 queries:
    1. Embeddar query via nomic-embed-text-v1.5
    2. Buscar top-k chunks (padrao: 8) no Qdrant
       - Filtro: deputado_id = {id}
       - Parametro HNSW: ef=128
    3. Acumular resultados com prefixo [TIPO]

Merge + Dedup:
    1. Concatenar todos os chunks brutos
    2. Dedup por prefixo (primeiros 100 caracteres)
    3. Truncar para RAG_MAX_CHUNKS (30 chunks maximo)

Total bruto: 5 queries x 8 chunks = 40 candidates
Apos dedup e truncamento: ate 30 chunks unicos
```

### Funcao de busca individual

`search_context_qdrant(deputado_id, query_text, limit)`:

- Conecta ao Qdrant via `QDRANT_URL`
- Aplica filtro `must` por `deputado_id`
- Retorna lista de strings no formato `[TIPO] {texto}`

### Funcao de busca multi-query

`search_context_multiquery(deputado_id, top_k_per_query)`:

- Itera sobre `QUERIES_TEMATICAS`
- Chama `search_context_qdrant()` para cada uma
- Dedup por prefixo de 100 caracteres
- Trunca para `RAG_MAX_CHUNKS` (30)

---

## 5. Geracao Adaptativa

### Contagem de fontes

A funcao `_count_sources()` analisa os chunks recuperados e conta a quantidade
de cada tipo de fonte:

| Tipo | Tag no chunk | Chave no dict |
|------|-------------|---------------|
| Votos | `[VOTO]` | `votos` |
| Emendas | `[EMENDA]` | `emendas` |
| Proposicoes | `[PROPOSICAO]` | `proposicoes` |
| Diario Oficial | `[DIARIO_OFICIAL]` | `diario_oficial` |
| Perfil | `[PERFIL]` | `perfil` |
| Conexao Politica | `[CONEXAO_POLITICA]` | `conexao_politica` |

### Construcao do prompt

A funcao `build_analysis_prompt()` monta o prompt de forma adaptativa, incluindo
ou omitindo secoes com base na disponibilidade de dados:

**Scoes sempre presentes:**

1. **PERFIL** — Nome, partido, UF e contexto politico
2. **AREAS TEMATICAS** — Principais areas de atuacao por volume de emendas e proposicoes
3. **CRUZAMENTO DE DADOS** — Conexao entre votos, emendas e proposicoes
4. **ALINHAMENTO POLITICO** — Grau de alinhamento com base do governo
5. **ANOMALIAS E FISIOLOGISMO** — Valores atipicos e padroes suspeitos

**Scoes condicionais (incluidas apenas se houver dados):**

6. **PADRAO DE VOTO** (se `votos > 0`) — Analise de alinhamento politico, dissenso,
   consistencia entre discurso e voto
7. **EMENDAS PIX** (se `emendas > 0`) — Concentracao de verbas, entidades recorrentes,
   anomalias, cruzamento com dados financeiros municipais
8. **PROPOSICOES LEGISLATIVAS** (se `proposicoes > 0`) — Areas tematicas, produtividade,
   coerencia entre proposicoes e emendas
9. **FISIOLOGISMO E ALINHAMENTO MUNICIPAL** (se `conexao_politica > 0`) — Analise de
   favorecimento partidario em repasses de emendas PIX

### Versionamento

- `RAG_PERSONA_VERSION` (atualmente `3`) em `config/settings.py`
- Incrementar quando houver alteracao significativa no prompt
- Usado como `versao_prompt` no upsert da tabela `parlamentares_personas`
- A condicao `ON CONFLICT (deputado_id, versao_prompt)` garante que atualizacoes
  sobrescrevem a versao anterior do mesmo deputado

### System prompt

```
Voce e um assistente analitico focado em ciencia politica
e dados empiricos. Analise friamente os dados, sem viés ideologico.
```

### Minimo e maximo de chunks

| Parametro | Valor | Configuracao |
|-----------|-------|--------------|
| Minimo | 3 chunks | `RAG_MIN_CHUNKS` |
| Maximo | 30 chunks | `RAG_MAX_CHUNKS` |

Se o numero de chunks for menor que `RAG_MIN_CHUNKS`, a geracao e abortada com
mensagem de "Dados insuficientes".

---

## 6. Persistencia

### Tabela `parlamentares_personas`

Campos:

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| `deputado_id` | INTEGER | FK para parlamentares_dados |
| `query_text` | TEXT | Query utilizada (ou "Analise comportamental multi-query v2") |
| `contexto_rag` | TEXT | Chunks concatenados utilizados no prompt |
| `analise_gerada` | TEXT | Dossie gerado pelo LLM em Markdown |
| `fontes_usadas` | TEXT[] | Lista de fontes (ex: {votos,emendas,perfil}) |
| `versao_prompt` | INTEGER | Versao do prompt (RAG_PERSONA_VERSION) |
| `data_analise` | TIMESTAMP | Data/hora da geracao |
| `duracao_segundos` | FLOAT | Tempo de geracao pelo LLM |

### Constraints

- **Chave primaria composta**: `(deputado_id, versao_prompt)`
- **UPSERT**: `ON CONFLICT (deputado_id, versao_prompt) DO UPDATE` — reescreve
  analise, contexto e fontes mantendo a data de atualizacao

### Funcao de persistencia

`_save_persona()`:

1. Insere ou atualiza na tabela `parlamentares_personas`
2. Utiliza `conn.commit()` para confirmar
3. Em caso de erro, executa `conn.rollback()`
4. Aceita conexao externa (modo lote) ou cria/conecta internamente (modo single)

---

## 7. Comandos

### cron-qdrant (Indexacao)

```bash
# Via run.sh
./run.sh cron-qdrant --limit 10
./run.sh cron-qdrant --nome "Afonso Florence"

# Via modulo Python
python3 -m src.enrichers.rag_qdrant_indexer --limit 10
python3 -m src.enrichers.rag_qdrant_indexer --nome "Afonso Florence"
python3 -m src.enrichers.rag_qdrant_indexer --rebuild
```

| Flag | Tipo | Padrao | Descricao |
|------|------|--------|-----------|
| `--limit` | int | 10 | Numero de deputados a processar |
| `--nome` | str | -- | Nome do deputado (busca ILIKE, parcial) |
| `--rebuild` | flag | False | Recria a colecao do zero (apaga dados existentes) |

**Ordenacao padrao** (sem `--nome`): prioriza deputados com mais alertas do diario
oficial e mais votos registrados.

### cron-dossie (Geracao de Persona)

```bash
# Via run.sh
./run.sh cron-dossie --nome "Afonso Florence"
./run.sh cron-dossie --lote 50

# Via modulo Python
python3 -m src.enrichers.rag_persona --nome "Afonso Florence"
python3 -m src.enrichers.rag_persona --nome "Afonso Florence" --regerar
python3 -m src.enrichers.rag_persona --lote 50
python3 -m src.enrichers.rag_persona --lote 50 --regerar
python3 -m src.enrichers.rag_persona --nome "Afonso Florence" --query "Consulta customizada"
```

| Flag | Tipo | Padrao | Descricao |
|------|------|--------|-----------|
| `--nome` | str | -- | Nome do deputado (busca ILIKE, parcial) |
| `--query` | str | -- | Query customizada (substitui as 5 queries tematicas) |
| `--lote` | int | -- | Gerar para N deputados sem persona na versao atual |
| `--regerar` | flag | False | Regenerar mesmo se ja existir persona |

**Modo lote**:

- Sem `--regerar`: seleciona deputados que nao possuem persona na versao atual
  (`RAG_PERSONA_VERSION`)
- Com `--regerar`: seleciona os primeiros N deputados e regenera todas as personas
- O modelo LLM e carregado uma unica vez para todo o lote (otimizacao)

**Modo single**:

- Busca o deputado por nome (ILIKE parcial)
- Gera o dossie e salva no banco
- Exibe o resultado no terminal com cabecalho formatado

---

## 8. Dependencias

### Pacotes Python

| Pacote | Uso |
|--------|-----|
| `qdrant-client` | Conexao e operacoes com o Qdrant |
| `psycopg2` | Conexao com PostgreSQL (via `src.db_utils`) |

### Modulos internos

| Modulo | Dependencia |
|--------|------------|
| `config.settings` | `QDRANT_URL`, `QDRANT_COLLECTION`, `EMBEDDER_MODEL`, `EMBEDDING_DIM`, `RAG_LLM_MODEL`, `RAG_PERSONA_VERSION`, `RAG_MIN_CHUNKS`, `RAG_MAX_CHUNKS` |
| `src.db_utils` | `get_connection()` |
| `src.localai_client` | `LocalAIClient` (embed + chat) |
| `src.localai_manager` | `manager.ensure_model_loaded()` |
| `src.enrichers.rag_qdrant_indexer` | `embed_text()` (usado por `rag_persona.py`) |

### Tabelas PostgreSQL necessarias

**Leitura (indexacao):**

| Tabela | Chunk |
|--------|-------|
| `parlamentares_dados` | perfil, conexao_politica |
| `parlamentar_proposicoes` | proposicao |
| `planos_acao` | emenda, conexao_politica |
| `beneficiarios` | emenda, conexao_politica |
| `objetos` | emenda |
| `beneficiario_ibge_map` | emenda, conexao_politica |
| `municipios_financeiro` | emenda |
| `votos_camara` | voto |
| `votacoes_camara` | voto |
| `parlamentar_alertas` | diario_oficial |
| `diario_oficial_atos` | diario_oficial |
| `prefeitos_dados` | conexao_politica |

**Escrita (persistencia):**

| Tabela | Operacao |
|--------|----------|
| `parlamentares_personas` | INSERT/UPSERT |

---

## 9. Troubleshooting

### Erros comuns

| Erro | Causa | Solucao |
|------|-------|---------|
| `Dados insuficientes: N chunks (minimo 3)` | Deputado tem poucos dados indexados | Rodar `cron-qdrant` para indexar mais dados do deputado |
| `Falha ao embeddar query` | LocalAI indisponivel ou modelo nao carregado | Verificar se LocalAI esta rodando em `localhost:8080` e se o modelo `nomic-embed-text-v1.5` esta disponivel |
| `Erro ao verificar/criar colecao Qdrant` | Qdrant indisponivel ou erro de conexao | Verificar se Qdrant esta rodando em `localhost:6333` |
| `Erro LLM` na geracao | Timeout ou modelo sobrecarregado | Verificar VRAM disponivel; usar `localai_manager` para descarregar modelos inativos |
| `Nenhum deputado encontrado para indexar` | Tabela `parlamentares_dados` vazia | Rodar enriquecimento Fase 2 (`camara.py`) antes da indexacao |
| Persona nao e atualizada em lote | Versao do prompt nao mudou | Incrementar `RAG_PERSONA_VERSION` em `config/settings.py` e usar `--regerar` |

### Diagnostico

```bash
# Verificar se o Qdrant esta respondendo
curl http://localhost:6333/collections

# Verificar se o LocalAI esta respondendo
curl http://localhost:8080/v1/models

# Listar modelos carregados no LocalAI
curl http://localhost:8080/v1/models | python3 -m json.tool

# Verificar quantos deputados estao indexados
python3 -c "
from qdrant_client import QdrantClient
from config.settings import QDRANT_URL, QDRANT_COLLECTION
c = QdrantClient(url=QDRANT_URL)
info = c.get_collection(QDRANT_COLLECTION)
print(f'Vetores: {info.points_count}')
print(f'Dimensao: {info.config.params.vectors.size}')
"

# Verificar quantas personas existem
psql -U cognee -h 127.0.0.1 -d transferegov_db -c \
  "SELECT versao_prompt, COUNT(*) FROM parlamentares_personas GROUP BY versao_prompt;"

# Verificar chunks de um deputado especifico
psql -U cognee -h 127.0.0.1 -d transferegov_db -c \
  "SELECT deputado_id, nome FROM parlamentares_dados WHERE nome ILIKE '%Afonso Florence%';"
```

### Performance

- **Indexacao**: ~2-5s por deputado (6 fontes + batch embedding + upsert)
- **Geracao de dossie**: ~30s por deputado (5 queries + LLM com gemma-4-e2b-it)
- **Lote de 50 deputados**: ~25-30 min total (modelo LLM carregado uma vez)
- **Batch embedding**: 1 request HTTP para todos os chunks de um deputado
- **VRAM**: sempre invocar `localai_manager.ensure_model_loaded(model)` antes de
  operacoes pesadas para evitar crash de GPU
