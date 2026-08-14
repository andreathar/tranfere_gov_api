# AGENTS.md — src/api

Aplicação FastAPI — Painel de Inteligência Parlamentar & Municipal. API REST com 43 endpoints
distribuídos em 9 routers, suportada por 4 serviços e uma SPA vanilla com Plotly.js.

---

## Início Rápido

```bash
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **Frontend**: `http://localhost:8000/` (SPA vanilla)

---

## Estrutura

```
src/api/
├── app.py                  App FastAPI principal (CORS, GZip, 13 routers, static files)
├── routes/
│   ├── deputados.py        /api/v1/deputados/*     (13 endpoints: +discursos, +alertas, +emendas-discricionarias)
│   ├── prefeitos.py        /api/v1/prefeitos/*     (6 endpoints)
│   ├── vereadores.py       /api/v1/vereadores/*    (6 endpoints)
│   ├── analytics.py        /api/v1/analytics/*     (5 endpoints: +votacoes-recentes)
│   ├── auditoria.py        /api/v1/auditoria/*     (3 endpoints)
│   ├── compras.py          /api/v1/compras/*       (2 endpoints)
│   ├── diario.py           /api/v1/diario/*        (2 endpoints)
│   ├── fnde.py             /api/v1/fnde/*          (5 endpoints)
│   ├── governadores.py     /api/v1/governadores/*  (5 endpoints)
│   ├── senadores.py        /api/v1/senadores/*     (4 endpoints)
│   ├── financeiro.py       /api/v1/financeiro/*    (4 endpoints)
│   ├── rag_efficiency.py   /api/v1/rag-efficiency/* (2 endpoints)
│   ├── localai.py          /api/v1/localai/*       (4 endpoints: observabilidade LocalAI)
│   └── municipios.py       /api/v1/municipios/*    (2 endpoints)
├── services/
│   ├── db_service.py       Consultas PostgreSQL (psycopg2, 45+ funcoes, TTLCache 300s em agregados)
│   ├── cache_utils.py      ANALYTICS_CACHE (TTLCache 300s) + invalidação
│   ├── camara_service.py   HTTP client assincrono para API Camara dos Deputados
│   ├── analytics_service.py Agregacoes analiticas (party-efficiency, deputy-roi, etc.)
│   └── mcp_service.py      Cliente MCPBrasilClient singleton (mcp-brasil)
└── static/
    ├── index.html          Frontend SPA (vanilla JS, Plotly lazy-load)
    ├── app.js              Logica JS core + loader de modulos (carregarAbasNovas)
    ├── js/tabs-novas.js    Abas novas (Senadores, Governadores, Financeiro, FNDE, sub-tabs deputado)
    └── style.css           Estilos (dark theme)
```

---

## Endpoints — 70 totais

### Deputados (13)

| Metodo | Rota | Descricao | Fonte |
|--------|------|-----------|-------|
| GET | `/api/v1/deputados/search?q=` | Busca por nome (ILIKE) | DB + API Camara (fallback) |
| GET | `/{deputado_id}/perfil` | Perfil completo do deputado | DB -> API Camara fallback |
| GET | `/{deputado_id}/emendas` | Emendas PIX do deputado | DB |
| GET | `/{deputado_id}/emendas/resumo` | Resumo agregado de emendas | DB |
| GET | `/{deputado_id}/despesas?ano=` | Despesas CEAP (paginado, max 500) | API Camara |
| GET | `/{deputado_id}/comissoes` | Orgaos/comissoes que integra | API Camara |
| GET | `/{deputado_id}/votacoes?limit=` | Ultimas votacoes nominais | DB (tabela votos_camara) |
| GET | `/{deputado_id}/proposicoes` | Proposicoes legislativas | API Camara |
| GET | `/{deputado_id}/full_report?ano=` | Relatorio completo via executar_lote | MCP-Brasil (lote paralelo) |
| GET | `/{deputado_id}/dossie` | Dossie comportamental RAG | DB (parlamentares_personas_v2) |
| GET | `/{deputado_id}/discursos?limit=&tipo=` | Discursos em plenario/comissoes | DB (parlamentar_discursos, idx novo) |
| GET | `/{deputado_id}/alertas` | Alertas automaticos do pipeline | DB (parlamentar_alertas) |
| GET | `/{deputado_id}/emendas-discricionarias?limit=` | Emendas discricionarias sincronizadas | DB (emendas_discricionarias, idx novo) |

### Prefeitos (6)

| Metodo | Rota | Descricao | Fonte |
|--------|------|-----------|-------|
| GET | `/api/v1/prefeitos/search?q=` | Busca por nome, municipio ou UF | DB |
| GET | `/api/v1/prefeitos/ranking?limit=` | Ranking de prefeituras por captacao | DB |
| GET | `/{municipio_id}/perfil` | Perfil do prefeito + indicadores | DB |
| GET | `/{municipio_id}/emendas?ano=&limit=` | Emendas recebidas pelo municipio | DB |
| GET | `/{municipio_id}/licitacoes?limit=` | Licitacoes e processos de compra | DB |
| GET | `/{municipio_id}/licitacoes/ganhadores?limit=` | Ranking de fornecedores vencedores | DB |

### Vereadores (6)

| Metodo | Rota | Descricao | Fonte |
|--------|------|-----------|-------|
| GET | `/api/v1/vereadores/search?q=` | Busca por nome, municipio, partido ou UF | DB |
| GET | `/api/v1/vereadores/ranking?limit=&partido=&uf=` | Ranking por votos | DB |
| GET | `/api/v1/vereadores/resumo` | KPIs agregados de vereadores | DB |
| GET | `/api/v1/vereadores/por-partido?uf=` | Contagem por partido | DB |
| GET | `/api/v1/vereadores/municipio/{municipio_id}` | Vereadores de um municipio | DB |
| GET | `/api/v1/vereadores/uf/{uf}` | Vereadores de uma UF | DB |

### Analytics (5)

| Metodo | Rota | Descricao | Fonte |
|--------|------|-----------|-------|
| GET | `/api/v1/analytics/party-efficiency` | Eficiencia de execucao por partido | DB (view v_emendas_unificadas) |
| GET | `/api/v1/analytics/socioeconomic` | Emendas vs IDHM e PIB per capita | DB (JOIN com municipios_ibge) |
| GET | `/api/v1/analytics/deputy-roi` | Comparativo CEAP vs Emendas | DB + API Camara (despesas) |
| GET | `/api/v1/analytics/top-municipios` | Top municipios por valor total | DB (JOIN com municipios_ibge) |
| GET | `/api/v1/analytics/votacoes-recentes?ano=&limit=` | Ultimas votacoes registradas | DB (votacoes_camara, TTLCache) |

### Auditoria (3)

| Metodo | Rota | Descricao | Fonte |
|--------|------|-----------|-------|
| GET | `/api/v1/auditoria/saude/{codigo_ibge}` | Rede municipal de saude | MCP-Brasil (farmacia_popular) |
| GET | `/api/v1/auditoria/justica?query=` | Processos judiciais por CNPJ | MCP-Brasil (DataJud, cache 30d) |
| GET | `/api/v1/auditoria/tcu?cnpj=` | Sancoes TCU (inidoneos + inabilitados) | MCP-Brasil (executar_lote) |

### Compras (2)

| Metodo | Rota | Descricao | Fonte |
|--------|------|-----------|-------|
| GET | `/api/v1/compras/fornecedor?cnpj=` | Dados do fornecedor no PNCP | MCP-Brasil (compras_pncp) |
| GET | `/api/v1/compras/bps?termo=` | Precos de saude no BPS | MCP-Brasil (bps_buscar) |

### Diario Oficial (2)

| Metodo | Rota | Descricao | Fonte |
|--------|------|-----------|-------|
| GET | `/api/v1/diario/buscar?q=&escopo=` | Busca no DOU + Diarios municipais | MCP-Brasil (diario_oficial_unificado) |
| POST | `/api/v1/diario/buscar-perfil` | Citacoes de politico no DOU (body: q, escopo, uf_municipio, data_inicio, data_fim) | MCP-Brasil (DOU + Querido Diario) |

### FNDE — Verbas Educacionais (5)

| Metodo | Rota | Descricao | Fonte |
|--------|------|-----------|-------|
| GET | `/api/v1/fnde/resumo?uf=` | Resumo FNDE por estado | DB (fnde_repasses) |
| GET | `/api/v1/fnde/municipios?municipio_id=&uf=&limit=` | Resumo FNDE por municipio | DB |
| GET | `/api/v1/fnde/municipio/{municipio_id}?programa=` | Programas FNDE de um municipio | DB |
| GET | `/api/v1/fnde/programas` | Lista de programas disponiveis | DB |
| GET | `/api/v1/fnde/search?q=&limit=` | Busca municipios com dados FNDE | DB |

### Governadores (5)

| Metodo | Rota | Descricao | Fonte |
|--------|------|-----------|-------|
| GET | `/api/v1/governadores?partido=&regiao=` | Lista governadores (filtros opcionais) | DB (governadores_dados) |
| GET | `/api/v1/governadores/ranking/emendas?limit=` | Ranking por emendas Pix captadas na UF | DB (JOIN planos_acao) |
| GET | `/api/v1/governadores/ranking/alinhamento?limit=` | Alinhamento partidario com bancada federal | DB |
| GET | `/api/v1/governadores/triangulo-politico?uf=&limit=` | Triangulo politico deputado x prefeito x governador | DB (v_triangulo_politico) |
| GET | `/api/v1/governadores/{uf}/perfil` | Perfil: dados eleitorais + SICONFI + bancada aliada | DB |

### Senadores (4)

| Metodo | Rota | Descricao | Fonte |
|--------|------|-----------|-------|
| GET | `/api/v1/senadores/ranking?limit=&partido=&uf=` | Ranking por atividade legislativa | DB (senadores_dados) |
| GET | `/api/v1/senadores/search?q=` | Busca por nome | DB |
| GET | `/api/v1/senadores/por-partido` | Contagem por partido + UFs cobertas | DB |
| GET | `/api/v1/senadores/{senador_codigo}/perfil` | Perfil completo do senador | DB |

### Financeiro SICONFI (4)

| Metodo | Rota | Descricao | Fonte |
|--------|------|-----------|-------|
| GET | `/api/v1/financeiro/estados?ano=&limit=` | Ranking financeiro dos 27 estados | DB (estados_financeiro) |
| GET | `/api/v1/financeiro/municipios?uf=&order_by=&limit=` | Ranking financeiro municipal | DB (municipios_financeiro JOIN IBGE) |
| GET | `/api/v1/financeiro/comparativo?uf=` | Emendas Pix x arrecadacao propria por UF | DB (JOIN planos_acao + SICONFI) |
| GET | `/api/v1/financeiro/municipio/{municipio_id}` | Financeiro detalhado de um municipio | DB |

### Municipios (2)

| Metodo | Rota | Descricao | Fonte |
|--------|------|-----------|-------|
| GET | `/api/v1/municipios/{municipio_id}/financeiro` | Financeiro SICONFI do municipio | DB |

### RAG Efficiency (2)

| Metodo | Rota | Descricao | Fonte |
|--------|------|-----------|-------|
| GET | `/api/v1/rag-efficiency/runs` | Historico de execucoes de eficiencia do RAG | DB (rag_efficiency_runs) |
| GET | `/api/v1/rag-efficiency/runs/{run_id}/metrics` | Detalhamento das metricas por pergunta | DB (rag_efficiency_metrics) |

### LocalAI Observabilidade (4)

| Metodo | Rota | Descricao | Fonte |
|--------|------|-----------|-------|
| GET | `/api/v1/localai/events` | Listar eventos do LocalAI (cadeia de traces) | DB (localai_event_log) |
| GET | `/api/v1/localai/snapshots` | Listar snapshots da cadeia de eventos | DB (localai_chain_snapshot) |
| GET | `/api/v1/localai/snapshot/{id}` | Snapshot completo com cadeia de eventos | DB (localai_chain_snapshot) |
| GET | `/api/v1/localai/stats` | Estatísticas resumidas (total, errors, models, avg_duration) | DB (localai_event_log) |

---

## Padrao de Fallback

```
Requisicao -> Busca local (PostgreSQL)
                  |
                  |-> >=5 resultados -> retorna
                  |-> <5 resultados  -> enriquece com API Camara
                                          |
                                          |-> sucesso -> merge + retorna
                                          |-> falha   -> degrade graceful (retorna local)
```

**Regra**: Nunca quebrar por falha de API externa. Sempre retornar dados parciais quando a Camara falhar.

---

## Servicos

### db_service.py — Acesso ao PostgreSQL

- **Driver**: `psycopg2` com `RealDictCursor` (sincrono, sem ORM)
- **Conexao**: `get_real_dict_connection()` de `src.db_utils` (recriada a cada chamada)
- **30+ funcoes publicas** organizadas por dominio:
  - Deputados: `search_deputados`, `get_perfil_deputado`, `get_nome_by_id`, `get_emendas_deputado`, `get_resumo_emendas`, `get_municipios_deputado`, `get_dossie_deputado`
  - Prefeitos: `search_prefeitos`, `get_perfil_prefeito`, `get_ranking_prefeitos`, `get_emendas_municipio`, `get_licitacoes_prefeitura`, `get_ganhadores_licitacoes_prefeitura`
  - Vereadores: `search_vereadores`, `get_ranking_vereadores`, `get_resumo_vereadores`, `get_vereadores_por_partido`, `get_vereadores_por_municipio`, `get_vereadores_por_uf`
  - Votacoes: `get_votacoes_deputado`, `get_resumo_votos_deputado`, `get_resumo_votacao`, `get_votacoes_recentes`, `get_votos_por_votacao`
  - FNDE: `get_fnde_resumo_estado`, `get_fnde_resumo_municipio`, `get_fnde_programas_municipio`, `get_fnde_programas_disponiveis`, `search_fnde_municipios`
  - Governadores: `get_all_governadores`, `get_ranking_governadores_emendas`, `get_ranking_alinhamento_governador`, `get_triangulo_politico`, `get_perfil_governador`
- **Conversao**: `_rows_to_list()` e `_row_to_dict()` convertem `Decimal -> float` automaticamente

### camara_service.py — API Camara dos Deputados

- **Driver**: `httpx.AsyncClient` (assincrono)
- **Cache em memoria**: dict com TTL de 3600s
- **Funcoes**: `buscar_deputado`, `search_deputados_api`, `listar_despesas` (paginado, max 500), `listar_orgaos`, `listar_votacoes` (delega ao DB local), `listar_proposicoes`
- **Rate limit**: respeitar `ENRICH_RATE_LIMIT` entre chamadas externas

### analytics_service.py — Agregacoes Analiticas

- **Execucao**: queries SQL síncronas envoltas em `asyncio.run_in_executor()` para nao bloquear o event loop
- **Funcoes**: `get_party_efficiency`, `get_socioeconomic_data`, `get_deputy_roi` (cruza DB + API Camara), `get_top_municipios`
- **View principal**: `v_emendas_unificadas` (JOIN parlamentares_dados + emendas)

### mcp_service.py — Cliente MCP-Brasil

- **Classe**: `MCPBrasilClient` (singleton via `_mcp_client`)
- **Transporte**: MCP sobre stdio (`uvx mcp-brasil`)
- **Cache**: dict com TTL configuravel (default 3600s), com double-check por lock
- **Funcoes expostas**: `get_saude_resumo`, `buscar_processos_datajud` (retry com backoff), `executar_lote` (lote paralelo), `buscar_diario_perfil` (DOU + Querido Diario)
- **Uso nos routes**: directly por auditoria, compras, diario e deputados (full_report)

---

## Frontend SPA

- **Stack**: vanilla JavaScript (sem framework), Plotly.js para graficos
- **Arquivos**: `index.html` (450+ linhas), `app.js` (1400+ linhas), `style.css` (dark theme)
- **6 secoes de navegacao**: Deputados, Prefeitos, Vereadores, Inteligencia, Saude, Diario Oficial
- **Subtabs do deputado**: Emendas, Despesas, Comissoes, Votacoes, Proposicoes, Dossie IA
- **4 modais**: Saude Municipal, Justica/TCU (integridade), Perfil Prefeito, Diario Oficial Perfil
- **Features**:
  - Autocomplete de busca com debounce
  - Cache em memoria por deputado/secao
  - Graficos Plotly com dark theme (layout padronizado `plotlyDarkLayout`)
  - KPIs agregados na sidebar (total emendas, valor, municipios)
  - Status colors mapeados por situacao do plano de acao

---

## Convencoes

- **Rotas**: prefixo `/api/v1/{recurso}` — versionamento explicito
- **Error handling**: `try/except Exception` no route -> `HTTPException(502)` se API externa falhar
- **Logging**: `logging.getLogger(__name__)` nos servicos
- **DB**: `config.settings.PG_*` — nunca hardcodar credenciais
- **Frontend**: vanilla JS, nao React — nao criar componentes React
- **CORS**: configuravel via env var `CORS_ORIGINS` (default local dev) — restringir em producao
- **Diario buscar-perfil**: unico endpoint POST (body JSON), todos os demais sao GET

---

## Pitfalls

1. `db_service.py` recria conexao a cada chamada — nao usar em loops (performance)
2. `camara_service.py` e async mas `db_service.py` e sync — nao misturar sem cuidado
3. Frontend e vanilla JS, nao React — nao criar componentes React
4. `Decimal` do PostgreSQL nao serializa JSON — sempre converter via `_rows_to_list()`
5. Rotas usam `/{deputado_id}/` ou `/{municipio_id}/` — IDs numericos, nao slug
6. `search` de deputados retorna merge de DB + API — pode haver duplicatas se IDs coincidirem
7. API Camara tem rate limit — nao fazer batch requests sem delay
8. `mcp_service.py` inicia conexao MCP sob demanda (lazy connect) — primeira chamada tem latencia
9. `analytics_service.py` usa `run_in_executor` para queries sync — nao e verdadeiramente paralelo
10. `diario/buscar-perfil` aceita POST com body JSON — nao e GET como os demais
11. `auditoria/justica` tem cache de 30 dias no DB (`beneficiario_processos`) — dados podem ficar stale
12. `listar_votacoes` delega ao `db_service` (tabela local `votos_camara`), nao a API Camara

---

## Configuracao

Variaveis relevantes em `config/settings.py`:

```python
# PostgreSQL
PG_HOST = "127.0.0.1"
PG_PORT = 5432
PG_DB = "transferegov_db"
PG_USER = "cognee"
PG_PASS = "cognee"

# API Camara
CAMARA_API_BASE = "https://dadosabertos.camara.leg.br/api/v2"

# Enriquecimento
ENRICH_RATE_LIMIT = 0.2  # 5s entre requests (compartilhado com enrichers)

# CORS (env var)
CORS_ORIGINS = "http://localhost:8000,http://127.0.0.1:8000"
```

Para a app completa, ver `AGENTS.md` na raiz do projeto.
