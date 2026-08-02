# AGENTS.md — src/enrichers

Pipeline de enriquecimento de dados do TransfereGov. Cada script roda como módulo independente via `python3 -m src.enrichers.<script>`.

---

## Arquitetura

```
pipeline.py  ← orquestrador, executa fases via subprocess (1-9)
    │
    ├── Fase 1: validacao.py → ibge.py → mapear_municipios.py → ibge_agregados.py
    ├── Fase 1e: siconfi.py (dados financeiros municipais)
    ├── Fase 2: camara.py (perfil deputados)
    ├── Fase 3: SQL JOIN direto no pipeline.py
    ├── Fase 4: datajud.py (processos judiciais via MCP)
    ├── Fase 5: compras.py (licitacoes PNCP)
    ├── Fase 6: saude_educacao.py (CNES/INEP)
    ├── Fase 7: tse_prefeitos.py + tse_vereadors.py
    ├── Fase 8: senado.py (perfil senadores)
    └── Fase 9: camara_discursos.py (discursos plenários)
```

Scripts auxiliares rodam fora do pipeline: `completar_deputados.py`, `discricionarias_sync.py`, `sync_proposicoes.py`, `votacoes_camara.py`, `votacoes_temas.py`, `fnde.py`, `diario_oficial_worker.py`, `tse_deputados.py`, `tcu_compras.py`, `rag_qdrant_indexer.py`, `rag_persona.py`.

**Requisito**: banco `transferegov_db` populado via extração (`transferegov_extract.py --db`) antes de rodar qualquer enricher.

---

## Scripts por Fase (Pipeline)

| Fase | Script | Fonte Externa | Tabela Destino | O que faz |
|------|--------|---------------|----------------|-----------|
| 1a | `validacao.py` | BrasilAPI (CNPJ) | `validacao_cnpj` | Valida situação cadastral dos CNPJs |
| 1b | `ibge.py` | IBGE API (localidades) | `municipios_ibge` | Lista municipios por UF (nomes, codigos, geo) |
| 1c | `mapear_municipios.py` | Match fuzzy (normalize) | `beneficiario_ibge_map` | Liga beneficiarios a codigos IBGE |
| 1d | `ibge_agregados.py` | IBGE API (agregados v3) | `municipios_ibge` (colunas extras) | Populacao, PIB, area territorial |
| 1e | `siconfi.py` | SICONFI/Tesouro Nacional (DCA + RREO A03) | `municipios_financeiro` | Dados financeiros + arrecadacao de impostos (IPTU/ISS/ICMS/FPM) |
| 1e2 | `estados_financeiro.py` | SICONFI esfera estadual (DCA + RREO A03) | `estados_financeiro` | Dados financeiros dos governos de estado (ICMS/IPVA/ITCD/FPE/FUNDEB/RCL) |
| 2 | `camara.py` | Camara dos Deputados | `parlamentares_dados` | Perfil completo dos deputados autores |
| 3 | `pipeline.py` (--fase 3) | SQL JOIN | `parlamentar_beneficiario` | Agrega valor total por parlamentar x municipio x emenda |
| 4 | `datajud.py` | DataJud CNJ (via mcp-brasil) | `beneficiario_processos` | Processos judiciais vinculados a CNPJs de beneficiarios |
| 5 | `compras.py` | PNCP + Dados Abertos Compras.gov.br | `compras_municipios` | Licitacoes e contratos publicos por municipio beneficiario |
| 6 | `saude_educacao.py` | CNES/DATASUS + INEP/MEC | `saude_municipios`, `educacao_municipios` | Estabelecimentos de saude, leitos, IDEB por municipio |
| 7 | `tse_prefeitos.py` | TSE (DuckDB local) | `prefeitos_dados` | Prefeitos eleitos (2020/2024) |
| 7 | `tse_vereadors.py` | TSE (DuckDB local) | `vereadores_dados` | Vereadores candidatos (2020/2024) |
| 8 | `senado.py` | Senado API REST | `senadores_dados` | Perfil completo senadores em exercicio |
| 9 | `camara_discursos.py` | Câmara Dados Abertos | `parlamentar_discursos` | Discursos de deputados em plenário (transcrições) |

### Scripts auxiliares

| Script | Fonte | Tabela Destino | O que faz |
|--------|-------|----------------|-----------|
| `completar_deputados.py` | API Camara | `parlamentares_dados` | Busca partido/sigla para deputados que faltam |
| `discricionarias_sync.py` | Portal Transparencia API | `emendas_discricionarias` | Sincroniza emendas discricionarias com a API gov.br |
| `sync_proposicoes.py` | API Camara | `parlamentar_proposicoes` | Sincroniza PLs e proposicoes dos deputados (para RAG) |
| `votacoes_camara.py` | API Camara | `votacoes_camara`, `votos_camara` | Busca votacoes nominais e votos individuais por ano |
| `votacoes_temas.py` | LocalAI (LLaMA) | `votacoes_camara` (campo tema) | Classifica tema de votacoes via LLM (ex: "Saude", "Orcamento") |
| `fnde.py` | FNDE/MEC (OData v4) | `fnde_repasses` | Repasses FUNDEB, PNAE, PNLD, PNATE por municipio |
| `diario_oficial_worker.py` | DOU (web) + LocalAI | `diario_oficial_atos` | Busca atos no Diario Oficial e extrai dados via NER com LLM |
| `tse_deputados.py` | TSE (DuckDB local) | `parlamentares_dados` (campos extras) | Enriquece perfil eleitoral de deputados federais |
| `tcu_compras.py` | TCU + Compras.gov + INEP | Audit/consulta | Audita parlamentares contra sancoes TCU e rastreia contratos |
| `governadores.py` | TSE 2022 (mapeamento manual) | `governadores_dados` | Governadores eleitos: votos 1º/2º turno, partido, coligação (27 UFs) |
| `violencia.py` | ISP-RJ (DuckDB) + Atlas da Violência (IPEA) | `violencia_municipios` | Indicadores criminais por município (RJ + demais UFs) |
| `rag_qdrant_indexer.py` | PostgreSQL -> Qdrant | Qdrant (colecao vetorial) | Indexa dados de deputados no Qdrant para busca semantica (RAG) |
| `rag_persona.py` | Qdrant + LocalAI | `parlamentares_personas_v2` | Gera dossies/ personas analiticas de deputados via RAG v7 (multi-analista) |

---

## Pipeline RAG

O pipeline RAG (Retrieval-Augmented Generation) indexa dados de deputados no Qdrant e gera dossies analiticos via LLM local.

### Indexador (`rag_qdrant_indexer.py`)

Modelo de embeddings: `embeddinggemma-300m` (768d) | Metrica: Cosine | Checkpoint: tabela `qdrant_index_checkpoint`

**23 tipos de chunks indexados** (exemplos): `perfil`, `parlamentar_resumo`, `emenda`, `emenda_discricionaria`, `beneficiario`, `voto`, `proposicao`, `discurso_plenario`, `conexao_politica`, `risco_judicial`, `compras_municipio`, `demografia_municipio`, `municipio_financeiro`, `estado_financeiro`, `indicadores_sociais`, `indicadores_municipal`, `fnde_repasses`, `diario_oficial`, `senador`, `prefeito`, `vereadores_resumo`, `parlamentar_alertas`, `persona_existente`.

Modos: `--limit N`, `--nome "NOME"`, `--diff` (incremental por hash), `--types voto,emenda`, `--rebuild`, `--checkpoint`. Cada chunk type é isolado em try/except — falha em um não aborta os demais.

### Gerador de Personas (`rag_persona.py`) — RAG v7 Multi-Analista

**15 queries tematicas** (batch embedding, cobrindo todos os 23 chunk types) + Reciprocal Rank Fusion (k=60):

1. Padrão de votos, dissenso partidário e obstrução
2. Proposições legislativas (PLs, PECs, PDLs)
3. Emendas Pix por município e situação dos planos
4. Emendas discricionárias (Portal Transparência)
5. Resumo consolidado do deputado
6. Dados financeiros SICONFI dos municípios
7. Dados demográficos IBGE (população, PIB, IDHM)
8. Indicadores de saúde e educação
9. Repasses FNDE
10. Conexão política local (apadrinhamento/fisiologismo)
11. Risco judicial (DataJud)
12. Compras públicas municipais
13. Ideologia nos discursos de plenário
14. Tópicos recorrentes e bandeiras públicas

**7 analistas especialistas** (`src/analysts/`): `classificador`, `perfil`, `tematicas`, `cruzamento`, `alinhamento`, `discursos`, `anomalias` — cada um com prompt focado, subconjunto de chunks (`router.py`) e quality check próprio. Ativação adaptativa (`get_active_analysts()`): analistas sem dados suficientes são pulados. Falha de um analista não aborta os demais.

**PromptPreparer** (`src/analysts/preparer.py`): sintetiza até 8 chunks → Briefing + Fact Table + Insights com `PREPARER_MODEL` (zero-gemma4-e4b-openzero-q5-k-m), com validação de fidelidade numérica R$ pós-geração.

Fluxo: busca Qdrant (15 queries x top-k) -> PromptPreparer (briefing) -> 7 analistas (paralelo opcional) -> `assemble_dossier()` -> `calculate_global_score()` (≥ 70 aprova) -> salva no DB com contexto_rag, fontes_usadas e versao_prompt.

Uso:
```bash
./run.sh cron-qdrant --limit 10          # indexar no Qdrant
./run.sh cron-qdrant --nome "AFONSO FLORENCE"  # indexar um deputado
./run.sh cron-qdrant --diff --limit 50   # incremental
./run.sh qdrant-status                   # status da indexação
./run.sh qdrant-staleness                # deputados desatualizados
./run.sh cron-dossie --nome "AFONSO FLORENCE"   # gerar persona
./run.sh cron-dossie --lote 50                    # gerar personas em lote
python3 -m src.enrichers.rag_qdrant_indexer --rebuild  # limpa e reindexa tudo
python3 -m src.enrichers.rag_persona --nome "AFONSO FLORENCE" --regerar
```

---

## Comandos

```bash
# Pipeline completo (fases 1-9)
python3 -m src.enrichers.pipeline --fase all [--dry-run] [--limit N]

# Fases individuais
python3 -m src.enrichers.pipeline --fase 1 [--dry-run]  # Validacao + IBGE
python3 -m src.enrichers.pipeline --fase 2 [--dry-run]  # Camara
python3 -m src.enrichers.pipeline --fase 3 [--dry-run]  # Vinculacao
python3 -m src.enrichers.pipeline --fase 4 [--dry-run]  # DataJud
python3 -m src.enrichers.pipeline --fase 5 [--dry-run] [--ano 2026]  # Compras
python3 -m src.enrichers.pipeline --fase 6 [--dry-run]  # Saude + Educacao
python3 -m src.enrichers.pipeline --fase 7 [--dry-run]  # TSE
python3 -m src.enrichers.pipeline --fase 8 [--dry-run]  # Senado
python3 -m src.enrichers.pipeline --fase 9 [--dry-run] [--ano 2026]  # Discursos

# Scripts avulsos - Fases principais
python3 -m src.enrichers.validacao [--dry-run] [--limit N]
python3 -m src.enrichers.camara_discursos [--ano ANO] [--limit N] [--resumo]
python3 -m src.enrichers.governadores [--dry-run] [--limit N]
python3 -m src.enrichers.violencia [--dry-run] [--uf UF] [--ano ANO]
python3 -m src.enrichers.ibge [--dry-run] [--uf UF]
python3 -m src.enrichers.ibge_agregados [--dry-run] [--uf UF] [--limit N]
python3 -m src.enrichers.siconfi [--dry-run] [--uf UF] [--limit N] [--ano ANO] [--rreo]
python3 -m src.enrichers.mapear_municipios [--dry-run]
python3 -m src.enrichers.camara [--dry-run] [--limit N]
python3 -m src.enrichers.datajud [--limit N]
python3 -m src.enrichers.compras [--dry-run] [--limit N] [--ano YYYY]
python3 -m src.enrichers.saude_educacao [--dry-run] [--limit N]
python3 -m src.enrichers.tse_prefeitos [--dry-run] [--uf UF] [--ano ANO]
python3 -m src.enrichers.tse_vereadors [--dry-run] [--uf UF] [--ano ANO]
python3 -m src.enrichers.tse_deputados [--dry-run] [--ano 2022]
python3 -m src.enrichers.senado [--dry-run] [--limit N]

# Scripts auxiliares
python3 -m src.enrichers.completar_deputados
python3 -m src.enrichers.discricionarias_sync
python3 -m src.enrichers.sync_proposicoes [--limit N]
python3 -m src.enrichers.votacoes_camara [--ano ANO] [--dry-run] [--limit N]
python3 -m src.enrichers.votacoes_temas [--limit N]
python3 -m src.enrichers.fnde [--dry-run] [--limit N] [--programa PROGRAMA]
python3 -m src.enrichers.diario_oficial_worker
python3 -m src.enrichers.tcu_compras --auditar-tcu
python3 -m src.enrichers.tcu_compras --contratos --uf SP

# RAG
python3 -m src.enrichers.rag_qdrant_indexer [--rebuild] [--limit N] [--nome NOME]
python3 -m src.enrichers.rag_persona [--nome NOME] [--regerar] [--lote N]
```

---

## Convencoes deste modulo

- **Idioma**: Portugues (comentarios, logs, output)
- **Dry-run**: Todo script aceita `--dry-run` -- mostra o que faria sem escrever no DB
- **Rate limit**: Respeitar `ENRICH_RATE_LIMIT` (0.2s entre requests) -- nao sobrecarregar APIs externas
- **Batch**: Processar em lotes de `ENRICH_BATCH_SIZE` (50 registros)
- **Cache**: Usar `http_cache.py` para requests HTTP -- TTL `ENRICH_CACHE_TTL` (3600s)
- **DB**: Usar `psycopg2` direto (sem ORM), imports de `config.settings`
- **Imports**: `sys.path.append` no `discricionarias_sync.py` (unico outlier -- considerar corrigir)
- **Fase 3**: SQL INSERT...ON CONFLICT (upsert) -- idempotente, seguro re-executar
- **Fase 4 (datajud)**: usa `asyncio` + MCP -- ignora `--dry-run` pois usa MCP diretamente
- **RAG**: requer Qdrant rodando em `QDRANT_URL` e LocalAI com modelos carregados

---

## Pitfalls

1. `mapear_municipios.py` usa normalizacao Unicode para fuzzy match -- funciona para acentos/abreviacoes, mas pode falhar para nomes muito diferentes
2. `camara.py` usa `requests` (sincrono) -- outros usam `httpx` ou `psycopg2`
3. `discricionarias_sync.py` usa `sys.path.append` para importar config -- nao e padrao do projeto
4. Rate limit entre requests: minimo 0.2s -- APIs do governo bloqueiam IP por excesso
5. `pipeline.py --fase 3` roda SQL direto (nao subprocesso) -- unico enricher que nao delega
6. Dry-run nao garante que APIs externas nao serao chamadas -- mostra output mas nao bloqueia HTTP
7. `ibge_agregados.py` requer migration_004 aplicada (colunas populacao, pib, area_km2) e `ibge.py` rodado antes (popula municipios_ibge com codigos)
8. `siconfi.py` requer migration_007 + migration_012 aplicadas (tabelas municipios_financeiro + colunas arrec_*) e `ibge.py` rodado antes (popula municipios_ibge com codigos)
9. `siconfi.py` tem rate limit proprio de 1 req/s -- SICONFI bloqueia IP por excesso de requests
10. DCA (Declaracao de Contas Anuais) costuma ter 1-2 anos de atraso -- o script tenta automaticamente 2025->2023 quando `--ano` nao e informado
11. RREO Anexo 03 (`--rreo`) contem arrecadacao de impostos por municipio -- usa `nr_periodo=6` (consolidacao anual, 6o bimestre)
12. RREO retorna texto com acentos (ex: 'Transferencias') -- o parser usa `unicodedata.normalize('NFKD')` para normalizar
13. `tse_vereadors.py` usa `qt_votos_nominais` (nao `qt_votos`) no dataset `tse_votacao` -- coluna e VARCHAR, requer `CAST(... AS BIGINT)`
14. `tse_vereadors.py` pode falhar silenciosamente nos votos se o dataset `tse_votacao` nao estiver ativo -- o enricher continua com votos zerados
15. `datajud.py` usa `asyncio` e MCP client — nao aceita `--dry-run` e requer que o MCP server `mcp-brasil` esteja ativo; rate limit proprio de 3s entre requests e retry de 15s em caso de 429
15a. `datajud_buscar_processos` (mcp-brasil) retorna STRING (tabela markdown/mensagem), NUNCA JSON — parse via `src/datajud_utils.parse_datajud_response()` (json.loads naive gravava total=0 falso e zerava o chunk `risco_judicial` no Qdrant); usar `--reprocess` para refazer CNPJs com falso-zero da versao antiga
16. `compras.py` extrai codigo IBGE do municipio a partir dos 7 primeiros digitos do CNPJ -- pode ser impreciso para municipios com mesmo codigo de-area
17. `saude_educacao.py` usa estimativas regionais como fallback quando APIs do CNES/DATASUS ou INEP estao indisponiveis -- valores sao aproximados, nao exatos
18. `votacoes_camara.py` usa paginacao da API da Camara com maximo de 200 paginas -- pode perder votacoes antigas se o ano tiver mais de 10.000 registros
19. `votacoes_temas.py` depende do LocalAI com modelo `llama` carregado -- se o modelo nao estiver disponivel, o script falha ao classificar temas
20. `fnde.py` depende de APIs OData v4 do FNDE (Olinda) -- se indisponiveis, nao ha fallback e a fase retorna vazio
21. `diario_oficial_worker.py` usa MCP para busca + LLM para NER -- dupla dependencia externa (MCP server + LocalAI)
22. `rag_qdrant_indexer.py` requer Qdrant ativo em `QDRANT_URL` e modelo `embeddinggemma-300m` carregado no LocalAI -- sem esses, indexacao falha (nomic-embed-text-v1.5 foi substituído)
23. `rag_persona.py` usa Multi-Query RAG v7 (15 queries + 7 analistas + PromptPreparer) -- se Qdrant retornar poucos chunks (< `RAG_MIN_CHUNKS`), a persona e gerada com dados insuficientes; analistas sem dados são pulados via `get_active_analysts()`
24. `tcu_compras.py` e auditoria/consulta (nao enriquecimento) -- nao escreve tabelas novas, usa MCP para consultas sob demanda
25. `tse_deputados.py` sincroniza dados eleitorais do TSE com `parlamentares_dados` -- requer que `camara.py` (fase 2) tenha rodado antes para popular a tabela base
26. `governadores.py` usa mapeamento manual (TSE 2022) -- atualizar dados exige editar a lista `GOVERNADORES_2022` no script
27. `violencia.py` depende dos datasets DuckDB do mcp-brasil (ISP-RJ) -- se o dataset nao estiver ativo, o enricher continua com Atlas da Violência ou pula

---

## Tabelas de banco usadas

### Leitura

`planos_acao`, `beneficiarios`, `parlamentares`, `objetos`, `programas`, `municipios_ibge`, `beneficiario_ibge_map`, `parlamentares_dados`

### Escrita (enriquecimento principal)

| Tabela | Script(s) | Descricao |
|--------|-----------|-----------|
| `validacao_cnpj` | `validacao.py` | Validacao cadastral de CNPJs via BrasilAPI |
| `municipios_ibge` | `ibge.py`, `ibge_agregados.py` | Dados demograficos e economicos dos municipios |
| `beneficiario_ibge_map` | `mapear_municipios.py` | Mapeamento fuzzy beneficiario -> codigo IBGE |
| `municipios_financeiro` | `siconfi.py` | Dados financeiros + 15 colunas de arrecadacao |
| `parlamentares_dados` | `camara.py`, `tse_deputados.py` | Perfil completo dos deputados autores |
| `parlamentar_beneficiario` | `pipeline.py` (fase 3) | Agregacao parlamentar x municipio x emenda |
| `beneficiario_processos` | `datajud.py` | Processos judiciais vinculados a CNPJs |
| `compras_municipios` | `compras.py` | Licitacoes e contratos publicos por municipio |
| `saude_municipios` | `saude_educacao.py` | Estabelecimentos CNES, leitos, profissionais |
| `educacao_municipios` | `saude_educacao.py` | IDEB, escolas, matriculas por municipio |
| `prefeitos_dados` | `tse_prefeitos.py` | Prefeitos eleitos (2020/2024) |
| `vereadores_dados` | `tse_vereadors.py` | Vereadores candidatos (2020/2024) |
| `senadores_dados` | `senado.py` | Perfil completo dos senadores em exercicio |
| `emendas_discricionarias` | `discricionarias_sync.py` | Emendas discricionarias sincronizadas |
| `parlamentar_proposicoes` | `sync_proposicoes.py` | Proposicoes legislativas dos deputados |
| `votacoes_camara` | `votacoes_camara.py`, `votacoes_temas.py` | Votacoes na Camara + temas classificados |
| `votos_camara` | `votacoes_camara.py` | Votos nominais individuais por deputado |
| `fnde_repasses` | `fnde.py` | Repasses educacionais do FNDE |
| `diario_oficial_atos` | `diario_oficial_worker.py` | Atos publicados no Diario Oficial da Uniao |
| `parlamentar_discursos` | `camara_discursos.py` | Discursos de deputados em plenário/comissões |
| `governadores_dados` | `governadores.py` | Governadores eleitos (TSE 2022) |
| `violencia_municipios` | `violencia.py` | Indicadores criminais municipais |
| `parlamentares_personas_v2` | `rag_persona.py` | Personas/ dossies analiticos gerados por IA |

Schema completo em `data/schema.sql` + migrations 002-025 (ver `docs/MIGRATIONS.md`).
