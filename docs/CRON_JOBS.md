# CRON_JOBS.md — Jobs Agendados do TransfereGov

Documentacao dos tres jobs agendados do projeto. Cada job roda como modulo
independente via `./run.sh` ou diretamente via `python3 -m`.

Todos os jobs dependem do banco `transferegov_db` populado via extracao
(`transferegov_extract.py --db`) e enriquecimento basico (fases 1-3 do pipeline).

---

## cron-diario — Worker do Diario Oficial

### Comando

```bash
./run.sh cron-diario
# Equivalente a:
python3 -m src.enrichers.diario_oficial_worker
```

### O que faz

1. Busca publicacoes recentes no Diario Oficial da Uniao (DOU) via MCP server
   (`mcp-brasil`).
2. Envia o texto extraido para o LLM local (Gemma/Qwen) com um prompt de
   Reconhecimento de Entidades Nomeadas (NER) juridico-politico.
3. Extrai dados estruturados: tipo de ato, orgao, valor financeiro, entidades
   citadas, resumo e data de publicacao.
4. Salva os atos extraidos no PostgreSQL, com deduphash para evitar duplicatas.

### Dependencias

| Componente | Descricao |
|------------|-----------|
| PostgreSQL | Tabela `diario_oficial_atos` (requer migration correspondente) |
| MCP server | `mcp-brasil` ativo para busca no DOU |
| LocalAI | Modelo `gemma` ou `fast` carregado para NER |

### Tabela de saida

**`diario_oficial_atos`** — Atos publicados no Diario Oficial da Uniao

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| deduphash | TEXT | Hash de deduplicacao (chave primaria) |
| tipo_ato | TEXT | Portaria, Licitacao, Nomeacao, Repasse, etc. |
| orgao | TEXT | Orgao que assinou ou publicou |
| valor_financeiro | NUMERIC | Valor financeiro (quando aplicavel) |
| entidades_citadas | JSONB | Lista de entidades mencionadas |
| resumo | TEXT | Resumo do conteudo do ato |
| data_publicacao | DATE | Data de publicacao no DOU |
| link | TEXT | Link para a edicao original |

### Flags

Nenhuma flag adicional disponivel. O script roda com configuracoes padrao
definidas em `config/settings.py`.

---

## cron-qdrant — Indexador Vetorial Qdrant

### Comando

```bash
./run.sh cron-qdrant [flags]
# Equivalente a:
python3 -m src.enrichers.rag_qdrant_indexer [flags]
```

### O que faz

1. Conecta ao Qdrant (via `QDRANT_URL`) e assegura que a colecao
   `deputados_perfis` existe.
2. Para cada deputado, coleta dados de 6 fontes distintas no PostgreSQL.
3. Gera embeddings usando `nomic-embed-text-v1.5` (768 dimensoes, metrica Cosine)
   via LocalAI.
4. Insere os chunks vetoriais no Qdrant com metadados (tipo, deputado_id, etc.).
5. O `LocalAIManager` garante exclusividade de VRAM — descarrega modelos inativos
   antes de invocar o modelo de embeddings.

### 6 tipos de chunks indexados

| Tipo | Conteudo | Fonte no DB |
|------|----------|-------------|
| `perfil` | Nome, partido, UF do deputado | `parlamentares_dados` |
| `proposicao` | PLs e proposicoes legislativas | `parlamentar_proposicoes` |
| `emenda` | Emendas Pix com dados financeiros do municipio | `planos_acao` + `municipios_financeiro` |
| `voto` | Padrao de voto em votacoes nominais | `votacoes_camara` + `votos_camara` |
| `diario_oficial` | Atos do Diario Oficial da Uniao | `diario_oficial_atos` |
| `conexao_politica` | Partido do prefeito beneficiado x partido do deputado | `prefeitos_dados` + `parlamentares_dados` |

### Dependencias

| Componente | Descricao |
|------------|-----------|
| PostgreSQL | Tabelas: `parlamentares_dados`, `parlamentar_proposicoes`, `planos_acao`, `municipios_financeiro`, `votacoes_camara`, `votos_camara`, `diario_oficial_atos`, `prefeitos_dados` |
| Qdrant | Servidor ativo em `QDRANT_URL` |
| LocalAI | Modelo `nomic-embed-text-v1.5` carregado para geracao de embeddings |

### Tabela de saida

**Qdrant `deputados_perfis`** — Colecao vetorial (nao PostgreSQL)

Cada ponto vetorial contem:
- `vector`: embedding de 768d
- `payload`: tipo_chunk, deputado_id, deputado_nome, texto_original, metadados

### Flags

| Flag | Descricao |
|------|-----------|
| `--rebuild` | Limpa a colecao e reindexa tudo do zero |
| `--limit N` | Processa no maximo N deputados |
| `--nome NOME` | Indexa apenas o deputado com o nome informado |

---

## cron-dossie — Gerador de Personas Analiticas

### Comando

```bash
./run.sh cron-dossie [flags]
# Equivalente a:
python3 -m src.enrichers.rag_persona [flags]
```

### O que faz

1. Para cada deputado, executa 5 queries tematicas no Qdrant (Multi-Query RAG).
2. Coleta os chunks mais relevantes (top-k por query) com seus metadados.
3. Monta um prompt adaptativo: a complexidade do prompt varia conforme o volume
   de dados disponiveis para o deputado.
4. Envia ao LLM local (Gemma/Qwen) para gerar um dossier analitico completo.
5. Salva o resultado no PostgreSQL com contexto_rag (trechos recuperados) e
   fontes_usadas (auditoria rastreavel).

### 5 queries tematicas do Multi-Query RAG

| # | Perspectiva | O que busca |
|---|-------------|-------------|
| 1 | Voto e alinhamento | Padrao de voto em votacoes nominais e posicao politica |
| 2 | Emendas PIX | Emendas parlamentares, municipios beneficiarios e valores |
| 3 | Proposicoes | PLs apresentadas e areas tematicas de foco |
| 4 | Diario Oficial | Atos, fiscalizacao, decretos e movimentacoes relevantes |
| 5 | Conexao politica | Partido do prefeito beneficiado x partido do deputado (fisiologismo) |

### Dependencias

| Componente | Descricao |
|------------|-----------|
| Qdrant | Colecao `deputados_perfis` indexada (requer `cron-qdrant` antes) |
| LocalAI | Modelo `gemma` (ou `RAG_LLM_MODEL`) carregado para geracao do dossier |
| PostgreSQL | Tabela `parlamentares_dados` (leitura) + `parlamentares_personas_v2` (escrita) |

### Tabela de saida

**`parlamentares_personas_v2`** — Personas/dossies analiticos gerados por IA

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| deputado_id | INTEGER | ID do deputado na Camara |
| deputado_nome | TEXT | Nome completo do deputado |
| persona_texto | TEXT | Dossier analitico gerado pelo LLM |
| contexto_rag | JSONB | Trechos recuperados do Qdrant (auditoria) |
| fontes_usadas | JSONB | Fontes consultadas por tipo de chunk |
| versao_prompt | TEXT | Versao do prompt utilizado |
| criado_em | TIMESTAMP | Data/hora de geracao |

### Flags

| Flag | Descricao |
|------|-----------|
| `--nome NOME` | Gera persona para um deputado especifico |
| `--regerar` | Sobrescreve persona existente (regera do zero) |
| `--lote N` | Processa no maximo N deputados em sequencia |

---

## Ordem de Execucao Recomendada

Os tres jobs possuem dependencia em cascata. A ordem correta e:

```
1. cron-diario    -->  Enriquece diario_oficial_atos (DB)
2. cron-qdrant    -->  Indexa tudo no Qdrant (inclui dados do DOU)
3. cron-dossie    -->  Gera personas a partir do Qdrant
```

**Por que essa ordem:**

- `cron-qdrant` indexa chunks do tipo `diario_oficial` a partir da tabela
  `diario_oficial_atos`. Se `cron-diario` nao rodou antes, esses chunks ficam
  vazios no Qdrant.
- `cron-dossie` depende de chunks indexados no Qdrant. Sem `cron-qdrant` rodado
  anteriormente, a consulta Multi-Query retorna poucos ou nenhum resultado, e as
  personas sao geradas com dados insuficientes (abaixo de `RAG_MIN_CHUNKS`).
- Executar na ordem inversa resulta em personas incompletas ou falha no
  processamento.

---

## Frequencia Recomendada

| Job | Frequencia | Justificativa |
|-----|------------|---------------|
| `cron-diario` | Diaria | O DOU publica de segunda a sexta. Rodar uma vez por dia, preferencialmente apos as 20h (edicao do dia encerrada), captura todos os atos. |
| `cron-qdrant` | Semanal | A indexacao vetorial e custosa (embeddings em todos os deputados). Uma vez por semana e suficiente, pois os dados de votacoes, emendas e proposicoes nao mudam com frequencia critica. |
| `cron-dossie` | Sob demanda ou quinzenal | A geracao de personas via LLM e a operacao mais lenta e depende de VRAM dedicada. Rodar sob demanda (quando necessario) ou em intervalos quinzenais para manter os dossies atualizados. |

### Exemplo de cron (crontab)

```cron
# Diario Oficial: todos os dias as 21h00
0 21 * * 1-5  cd /caminho/para/tranfere_gov_api && ./run.sh cron-diario >> output/logs/cron-diario.log 2>&1

# Qdrant Indexer: toda segunda-feira as 02h00
0 2 * * 1     cd /caminho/para/tranfere_gov_api && ./run.sh cron-qdrant >> output/logs/cron-qdrant.log 2>&1

# Dossie Persona: a cada 15 dias (dia 1 e 16) as 04h00
0 4 1,16 * *  cd /caminho/para/tranfere_gov_api && ./run.sh cron-dossie --lote 50 >> output/logs/cron-dossie.log 2>&1
```

**Nota:** Ajuste os horarios conforme a carga do servidor e a disponibilidade de
GPU para o LocalAI. Jobs que dependem de LLM local (`cron-diario` e `cron-dossie`)
nao devem rodar simultaneamente, pois compartilham a VRAM da GPU.

---

## Gerenciamento de VRAM (LocalAI)

O `LocalAIManager` (`src/localai_manager.py`) e responsavel por garantir que
apenas um modelo esteja carregado por vez na GPU. Antes de cada operacao que
requer LLM:

1. Verifica quais modelos estao carregados (`is_model_loaded`).
2. Descarrega modelos inativos (`unload_model` via `/backend/shutdown`).
3. Carrega o modelo necessario (`ensure_model_loaded`).

Isso impede erros de estouro de memoria (OOM) e falhas de conexao (RPC EOF).

---

## Troubleshooting

| Problema | Causa provavel | Solucao |
|----------|---------------|---------|
| `cron-diario` nao salva atos | MCP server `mcp-brasil` offline | Verificar se o MCP server esta ativo |
| `cron-qdrant` falha com "connection refused" | Qdrant nao esta rodando | Iniciar Qdrant em `QDRANT_URL` |
| `cron-dossie` gera persona vazia | Poucos chunks no Qdrant | Rodar `cron-qdrant` antes; verificar `RAG_MIN_CHUNKS` |
| OOM / RPC erro na GPU | Dois modelos carregados ao mesmo tempo | Verificar `localai_manager`; descarregar modelos manualmente |
| Dedup duplicado no DOU | `deduphash` nao esta sendo gerado corretamente | Verificar se o hash inclui tipo_ato + orgao + data_publicacao |
| Rate limit APIs governamentais | Muitas requests em curto periodo | Respeitar `ENRICH_RATE_LIMIT` (0.2s entre requests) |
