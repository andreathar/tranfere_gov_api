# AGENTS.md — src/api

FastAPI web app — Painel de Inteligência Parlamentar. Consulta deputados, emendas Pix, despesas CEAP, comissões, votações e proposições legislativas.

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
├── app.py                  App FastAPI principal (CORS, routers, static files)
├── routes/
│   └── deputados.py        Rotas REST de deputados (/api/v1/deputados/*)
├── services/
│   ├── db_service.py       Consultas PostgreSQL (psycopg2, sem ORM)
│   └── camara_service.py   HTTP client assíncrono para API Câmara dos Deputados
└── static/
    ├── index.html          Frontend SPA
    ├── app.js              Lógica JS
    └── style.css           Estilos
```

---

## Endpoints

| Método | Rota | Descrição | Fonte |
|--------|------|-----------|-------|
| GET | `/api/v1/deputados/search?q=` | Busca por nome | DB + API Câmara |
| GET | `/{id}/perfil` | Perfil completo | DB → API Câmara fallback |
| GET | `/{id}/emendas` | Emendas do deputado | DB |
| GET | `/{id}/emendas/resumo` | Resumo agregado | DB |
| GET | `/{id}/despesas?ano=` | Despesas CEAP | API Câmara |
| GET | `/{id}/comissoes` | Comissões | API Câmara |
| GET | `/{id}/votacoes?limit=` | Últimas votações | API Câmara |
| GET | `/{id}/proposicoes` | Proposições legislativas | API Câmara |

---

## Padrão de Fallback

```
Requisição → Busca local (PostgreSQL)
                  │
                  ├── ≥5 resultados → retorna
                  └── <5 resultados → enriquece com API Câmara
                                         │
                                         ├── sucesso → merge + retorna
                                         └── falha   → degrade graceful (retorna local)
```

**Regra**: Nunca quebrar por falha de API externa. Sempre retornar dados parciais quando a Câmara falhar.

---

## Serviços

### db_service.py

- Consultas SQL diretas via `psycopg2` (sem ORM)
- `RealDictCursor` para retorno como dicts
- Conversão automática `Decimal → float` para serialização JSON
- Conexão recriada a cada chamada (sem pool — sync driver)

### camara_service.py

- HTTP client assíncrono (`httpx.AsyncClient`)
- Endpoints da API Câmara: `/api/v2/deputados`, `/deputados/{id}/despesas`, etc.
- Rate limit: respeitar `ENRICH_RATE_LIMIT` entre chamadas
- Erros de rede → eleva exceção (handler do route faz degrade)

---

## Convenções

- **Rotas**: Prefixo `/api/v1/deputados` — versionamento explícito
- **Erro handling**: `try/except Exception` no route → `HTTPException(502)` se API externa falhar
- **Logging**: `logging.getLogger(__name__)` nos serviços
- **DB**: `config.settings.PG_*` — nunca hardcodar credenciais
- **Frontend**: SPA vanilla (React não usado) — index.html + app.js + style.css
- **CORS**: Permissivo para dev (`allow_origins=["*"]`) — restringir em produção

---

## Pitfalls

1. `db_service.py` recria conexão a cada chamada — não usar em loops (performance)
2. `camara_service.py` é async mas `db_service.py` é sync — não misturar sem cuidado
3. Frontend é vanilla JS, não React — não criar componentes React
4. `Decimal` do PostgreSQL não serializa JSON — sempre converter via `_rows_to_list()`
5. Rotas usam `/{deputado_id}/` — ID numérico, não slug
6. `search` retorna merge de DB + API — pode haver duplicatas se IDs coincidem
7. API Câmara tem rate limit — não fazer batch requests sem delay

---

## Configuração

Variáveis relevantes em `config/settings.py`:

```python
# PostgreSQL
PG_HOST = "127.0.0.1"
PG_PORT = 5432
PG_DB = "transferegov_db"
PG_USER = "cognee"
PG_PASS = "cognee"

# API Câmara
CAMARA_API_BASE = "https://dadosabertos.camara.leg.br/api/v2"

# Enriquecimento
ENRICH_RATE_LIMIT = 0.2  # 5s entre requests (compartilhado com enrichers)
```

Para a app completa, ver `AGENTS.md` na raiz do projeto.
