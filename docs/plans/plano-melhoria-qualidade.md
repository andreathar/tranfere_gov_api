# Plano de Melhoria — Qualidade de Código e Fluxo de Dados

> **Data**: 2026-07-29
> **Baseado em**: Análise de 102 arquivos fonte, 13 integrações externas, 646 funções, 141 testes

---

## FASE 0: Mapeamento do Fluxo de Dados (Entendimento)

### 0.1 Diagrama de Fluxo Atual

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        EXTRAÇÃO (transferegov_extract.py)                │
│  API TransfereGov ──(requests, pagination, retry 3x, backoff 2.0)──►    │
│  JSON response → parse_page() → PlanoAcaoSchema (Pydantic)               │
└────────────────────────┬─────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    PERSISTÊNCIA (db_import.py)                           │
│  JSON files (output/json/) ou streaming → upsert_plano_acao()           │
│  → PostgreSQL: planos_acao, beneficiarios, parlamentares, emendas        │
└────────────────────────┬─────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────────────┐
│              ENRIQUECIMENTO (pipeline.py → subprocess → 25 módulos)     │
│                                                                          │
│  Fase 1a: validacao.py     ──(requests)──► BrasilAPI (CNPJ)             │
│  Fase 1b: ibge.py          ──(requests)──► IBGE API                     │
│  Fase 1c: mapear_municipios.py  ──(fuzzy match)──► beneficiario_ibge_map│
│  Fase 1d: ibge_agregados.py──(requests)──► IBGE Agregados               │
│  Fase 1e: siconfi.py       ──(requests)──► SICONFI (DCA+RREO)           │
│  Fase 2:  camara.py        ──(requests)──► Câmara Deputados             │
│  Fase 3:  SQL JOIN direto (pipeline.py)                                  │
│  Fase 4:  datajud.py       ──(MCP/async)──► DataJud CNJ                 │
│  Fase 5:  compras.py       ──(requests)──► Compras Gov                  │
│  Fase 6:  saude_educacao.py──(requests)──► CNES/INEP                    │
│  Fase 7a: tse_prefeitos.py ──(DuckDB local)──► TSE                      │
│  Fase 7b: tse_vereadors.py ──(DuckDB local)──► TSE                      │
│  Fase 8:  senado.py        ──(requests)──► Senado API                   │
│                                                                          │
│  Auxiliares: sync_proposicoes.py, votacoes_camara.py, fnde.py,          │
│              diario_oficial_worker.py, discricionarias_sync.py, etc.     │
└────────────────────────┬─────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────────────┐
│          CONSUMO (3 saídas independentes)                                │
│                                                                          │
│  ┌─────────────────────┐  ┌─────────────────┐  ┌──────────────────────┐ │
│  │ Dash (dash_app.py)  │  │ API (src/api/)  │  │ RAG (Qdrant+LocalAI) │ │
│  │                     │  │                 │  │                      │ │
│  │ 68 gráficos Plotly  │  │ 38 endpoints    │  │ 19 tipos de chunk   │ │
│  │ 17 módulos graphs/  │  │ 8 routers       │  │ Multi-Query RAG v6  │ │
│  │ MCP Hub /_mcp       │  │ 4 services      │  │ Personas analíticas │ │
│  │ Porta 8050          │  │ Porta 8000      │  │ Qdrant + LocalAI    │ │
│  └─────────────────────┘  └─────────────────┘  └──────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

### 0.2 Formatos de Dados em Cada Estágio

| Estágio | Formato de Entrada | Transformação | Formato de Saída |
|---------|-------------------|---------------|------------------|
| Extração | HTTP JSON (API Gov) | Pydantic PlanoAcaoSchema | JSON files + DB rows |
| Importação | JSON files | upsert_plano_acao() | PostgreSQL (5 tabelas) |
| Enriquecimento | DB rows | HTTP requests + parsing | Tabelas de enriquecimento |
| Dashboard | DB queries | SQL → Plotly Figure | HTML/Plotly.js |
| API | DB queries | JSON serialization | REST JSON |
| RAG | DB queries | Embeddings → Qdrant → LLM | Personas textuais |

### 0.3 Pontos de Handoff (com arquivos e linhas)

| Handoff | Arquivo | Linha | Risco |
|---------|---------|-------|-------|
| API JSON → Pydantic | `src/transferegov_extract.py` | ~120 | Baixo (Pydantic valida) |
| Pydantic → DB | `src/db_import.py` | ~50 | Baixo (upsert idempotente) |
| DB → Enrichers | `src/enrichers/*.py` | vários | **Médio** (cada um faz próprio SQL) |
| DB → Dashboard | `src/graphs/*.py` | vários | **Médio** (SQL inline nos builders) |
| DB → API | `src/api/services/db_service.py` | ~1076 | **Médio** (1076 LOC gigante) |
| DB → RAG | `src/enrichers/rag_qdrant_indexer.py` | ~1465 | **Alto** (19 extractors repetidos) |

---

## FASE 1: Quick Wins (1-2 dias)

### 1.1 Remover Código Morto (~4.500 LOC)

**Arquivos para remover** (confirmados como não importados por nenhum código ativo):

| Arquivo | LOC | Motivo |
|---------|-----|--------|
| `src/dashboard.py` | 517 | Substituído por `dash_app.py` + `src/graphs/` |
| `src/dashboard_deputados.py` | 1334 | Substituído por `dash_app.py` + `src/graphs/` |
| `src/dashboard_emendas.py` | 967 | Substituído por `dash_app.py` + `src/graphs/` |
| `src/dashboard_cross_analysis.py` | 1000 | Substituído por `dash_app.py` + `src/graphs/` |
| `src/dashboard_cross_fiscal.py` | 766 | Substituído por `dash_app.py` + `src/graphs/` |
| `src/graph_generator.py` | 322 | Substituído por `src/graphs/registry.py` |
| `src/redator/` (dir) | - | Apenas outputs, código está em `redator_transferegov.py` |

**Ação**: Criar branch, remover arquivos, verificar se `dash_app.py` cobre todos os casos de uso.

### 1.2 Corrigir Erros de Lint (17 erros)

**6 auto-fixáveis** via `ruff check --fix`:
- `I001` (2): imports desordenados em `config/settings.py` e outro
- `W293` (4): whitespace em linhas em branco

**11 manuais**:
- `F821` (2): undefined-name — verificar variáveis
- `SIM102` (3): collapsible-if — aninhamentos desnecessários
- `F841` (1): unused-variable
- `B007` (1): unused-loop-control-variable
- `W291` (2): trailing-whitespace
- `SIM108` (1): if-else-block-instead-of-if-exp
- `SIM110` (1): reimplemented-builtin

### 1.3 Remover Chave de API no AGENTS.md

**Arquivo**: `AGENTS.md` (linha referenciando `TRANSPARENCIA_API_KEY = 5b81984fd0892eb1bf6408876fd0c7ab`)

**Ação**: Remover a chave do AGENTS.md (está exposta em documentação pública do repositório). A chave deve estar apenas no `.env`.

---

## FASE 2: Infraestrutura de Testes (3-5 dias)

### 2.1 Adicionar pytest-cov ao CI

**Arquivos**: `.github/workflows/ci.yml`, `pyproject.toml`

```toml
[tool.pytest.ini_options]
addopts = "-v --tb=short --cov=src --cov-report=term-missing --cov-fail-under=30"
```

**Dependência**: `pytest-cov>=5.0` em `[project.optional-dependencies.dev]`

### 2.2 Criar conftest.py com Fixtures Compartilhadas

**Arquivo novo**: `tests/conftest.py`

Fixtures a incluir:
- `mock_db_connection` — mock de `get_connection()` usando `MagicMock`
- `mock_http_client` — mock de `requests.get` / `httpx.get` usando `respx`
- `sample_planos` — fixture com dados realistas de `PlanoAcaoSchema`
- `sample_deputado` — fixture com perfil de deputado
- `db_session` — (opcional) conexão real com banco de testes

### 2.3 Testes para Camada Crítica (prioridade)

**Lote 1 — Enrichers Core** (maior risco de quebra):
| Módulo | Abordagem | Tabela |
|--------|-----------|--------|
| `validacao.py` | Mock `requests.get(BRASILAPI_BASE)`, testar parsing/resilience | `validacao_cnpj` |
| `camara.py` | Mock requests, testar parsing de JSON da Câmara | `parlamentares_dados` |
| `siconfi.py` | Mock requests, testar parsing DCA + RREO | `municipios_financeiro` |
| `ibge.py` | Mock requests, testar parsing IBGE | `municipios_ibge` |

**Lote 2 — API Routes** (38 endpoints sem teste):
- Testar cada router com `TestClient` do FastAPI + mock de `db_service`
- Verificar status codes, formato de resposta, fallback

**Lote 3 — Gráficos**:
- Testar que cada `@register_chart` retorna `go.Figure` sem erro
- Usar `safe_build_chart()` como entry point (já tem try/except)

### 2.4 Testes de Integração (end-to-end crítico)

- **Extração → Validação**: Mockar API TransfereGov, testar pipeline completo de `parse_page()` → `PlanoAcaoSchema` → `upsert_plano_acao()`
- **Enriquecimento → API**: Testar que dados enriquecidos aparecem nos endpoints da API

---

## FASE 3: Refatoração Core (5-8 dias)

### 3.1 Refatorar rag_qdrant_indexer.py (1.465 LOC → ~600 LOC)

**Problema**: 19 funções `_extract_*` com assinatura idêntica `(cur: Any, deputado_id: int, nome: str)` e estrutura copiada.

**Solução**: Padrão Registry + Strategy

```python
# Novo: extractor_registry.py
from dataclasses import dataclass
from collections.abc import Callable

@dataclass
class ExtractorSpec:
    name: str
    description: str
    fn: Callable

EXTRACTOR_REGISTRY: dict[str, ExtractorSpec] = {}

def register_extractor(name: str, description: str):
    def decorator(fn):
        EXTRACTOR_REGISTRY[name] = ExtractorSpec(name, description, fn)
        return fn
    return decorator

# Cada extractor vira um módulo separado ou funções registradas:

@register_extractor("perfil", "Perfil enriquecido do deputado")
def extract_perfil(cur, deputado_id: int, nome: str) -> list[dict]:
    ...

# No indexador principal:
for name, spec in EXTRACTOR_REGISTRY.items():
    try:
        chunks = spec.fn(cur, deputado_id, nome)
        ...
    except Exception as e:
        log.error("Extractor %s falhou: %s", name, e)
        continue  # resiliência — falha de um não aborta os demais
```

**Benefícios**:
- Elimina 19× repetição de try/except
- Cada extractor pode ser testado isoladamente
- Novo extractor = 1 registro, não 1 cópia
- Remove 21 ocorrências de `Any`

### 3.2 Unificar Cliente HTTP (14 módulos → 1)

**Problema**: `requests` em 14 módulos + `httpx` em 6 módulos, cada um com timeout/retry próprio.

**Solução**: `src/http_client.py` — cliente unificado baseado em `httpx` (já é a lib mais nova):

```python
import httpx
from httpx import HTTPError, TimeoutException
import time
from typing import Any

class ApiClient:
    def __init__(self, base_url: str, timeout: int = 30, max_retries: int = 3):
        self.client = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
        self.max_retries = max_retries

    def get(self, path: str, params: dict | None = None) -> dict[str, Any] | list:
        for attempt in range(self.max_retries):
            try:
                resp = self.client.get(path, params=params)
                resp.raise_for_status()
                return resp.json()
            except HTTPError as e:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2 ** attempt)  # backoff exponencial
        return {}
```

**Benefícios**:
- Retry + backoff centralizado
- Timeout consistente
- Pool de conexões reutilizável
- Rate limit configurável

**Migração**: Criar `ApiClient` e refatorar enrichers um por um, começando pelos mais críticos.

### 3.3 Refatorar db_service.py (1.076 LOC → módulos por domínio)

**Problema**: 30+ funções em 1 arquivo, 3 erros mypy ativos, lida com 5 domínios diferentes.

**Solução**: Extrair para `src/api/services/db/`:

```
src/api/services/db/
├── __init__.py          # Re-exports
├── base.py             # Conexão, _rows_to_list, _row_to_dict
├── deputados.py        # search_deputados, get_perfil_deputado, get_emendas_deputado
├── prefeitos.py        # search_prefeitos, get_perfil_prefeito, get_ranking
├── vereadores.py       # search_vereadores, get_ranking_vereadores
├── votacoes.py         # get_votacoes_deputado, get_resumo_votos
└── fnde.py             # get_fnde_resumo_estado, get_fnde_programas
```

**Benefícios**:
- Cada domínio com <200 LOC
- Testável isoladamente
- Elimina 3 erros mypy

---

## FASE 4: Integrações e Resiliência (3-5 dias)

### 4.1 Retry + Circuit Breaker para Todos os Enrichers

**Problema**: Apenas `transferegov_extract.py` e `datajud.py` têm retry. Demais 11 integrações não têm.

**Implementação**: Decorator `@retry_api` no novo `http_client.py`:

```python
import functools
import time
import logging

log = logging.getLogger(__name__)

def retry_api(max_retries: int = 3, backoff: float = 2.0, retry_on: tuple = ()):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return fn(*args, **kwargs)
                except retry_on as e:
                    last_error = e
                    wait = backoff ** attempt
                    log.warning("Tentativa %d/%d falhou para %s: %s. Retrying em %.1fs...",
                                attempt + 1, max_retries, fn.__name__, e, wait)
                    time.sleep(wait)
            log.error("Todas as %d tentativas falharam para %s: %s",
                      max_retries, fn.__name__, last_error)
            raise last_error
        return wrapper
    return decorator
```

### 4.2 Cache Unificado (substituir http_cache.py)

**Problema**: `http_cache.py` existe mas poucos enrichers o usam. Cache é file-based com race conditions.

**Solução**: Estender `ApiClient` com cache em memória + fallback file:

```python
from functools import lru_cache
from datetime import datetime, timedelta

class CachedApiClient(ApiClient):
    def __init__(self, *args, cache_ttl: int = 3600, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache: dict[str, tuple[float, Any]] = {}
        self.cache_ttl = cache_ttl

    def get(self, path, params=None):
        key = f"{path}?{json.dumps(params or {}, sort_keys=True)}"
        now = time.time()

        if key in self._cache:
            ts, data = self._cache[key]
            if now - ts < self.cache_ttl:
                return data

        data = super().get(path, params)
        self._cache[key] = (now, data)
        return data

    def invalidate(self, path_pattern: str):
        """Invalida entradas cujo path contém o padrão."""
        keys = [k for k in self._cache if path_pattern in k]
        for k in keys:
            del self._cache[k]
```

### 4.3 Health Checks Pre-Processamento

**Problema**: Enrichers só descobrem que API está fora após processar N registros.

**Solução**: Adicionar `ApiClient.health_check()` em cada enricher:

```python
def enrich():
    client = ApiClient(BRASILAPI_BASE)
    if not client.health_check("/cnpj/v1/00000000000191"):
        log.error("BrasilAPI indisponível. Abortando.")
        return
    # ...processamento normal...
```

### 4.4 Data Lineage (Rastreabilidade)

**Problema**: Não há registro de qual enricher populou qual tabela, quando, com quais parâmetros.

**Solução**: Criar tabela `enrichment_log` no PostgreSQL:

```sql
CREATE TABLE enrichment_log (
    id SERIAL PRIMARY KEY,
    enricher_name TEXT NOT NULL,
    table_name TEXT NOT NULL,
    records_processed INT,
    records_inserted INT,
    records_updated INT,
    errors INT,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    params JSONB,
    status TEXT CHECK (status IN ('success', 'partial', 'failed'))
);
```

Cada enricher registra ao final: `INSERT INTO enrichment_log (...) VALUES (...)`

---

## FASE 5: Type Safety e Manutenibilidade (2-3 dias)

### 5.1 Aumentar Cobertura de Type Hints (58% → 80%+)

| Ação | Alvo |
|------|------|
| Adicionar return types em funções sem `->` | +269 funções |
| Substituir `Any` por tipos concretos | 21 em `rag_qdrant_indexer.py` |
| Habilitar `warn_return_any = true` no mypy | `pyproject.toml` |
| Habilitar `disallow_untyped_defs = true` gradualmente | módulo por módulo |

### 5.2 Endurecer Configuração mypy

```toml
[tool.mypy]
python_version = "3.11"
strict = false                         # manter por enquanto
warn_return_any = true                 # ATIVAR — pega Any vazando
warn_unused_configs = true
ignore_missing_imports = true          # manter para libs sem stubs
explicit_package_bases = true
mypy_path = "."
disallow_untyped_defs = false          # ativar por módulo depois
```

### 5.3 Modularizar Arquivos Grandes

| Arquivo | LOC Atual | Ação | LOC Alvo |
|---------|-----------|------|----------|
| `arrecadacao.py` | 1.321 | Dividir por subcategoria (iptu, iss, icms, fpm) | ~300 cada |
| `rag_qdrant_indexer.py` | 1.465 | Registry pattern (Fase 3.1) | ~600 |
| `db_service.py` | 1.076 | Dividir por domínio (Fase 3.3) | ~200 cada |
| `rag_persona.py` | 1.122 | Extrair queries temáticas para módulo separado | ~500 |
| `redator_transferegov.py` | 902 | Extrair cada tipo de documento | ~200 cada |

---

## PRIORIZAÇÃO

| Prioridade | Fase | Esforço | Impacto | Depende de |
|------------|------|---------|---------|------------|
| P0 | 1.1 Remover dead code | 1h | 🟢 Reduz 4.500 LOC | Nenhuma |
| P0 | 1.3 Remover chave API do AGENTS.md | 5min | 🟢 Segurança | Nenhuma |
| P0 | 2.2 conftest.py | 4h | 🟢 Habilita testes | Nenhuma |
| P1 | 3.1 Refatorar rag_qdrant_indexer.py | 8h | 🟢 -800 LOC, 21 Any | Nenhuma |
| P1 | 2.1 pytest-cov no CI | 2h | 🟢 Qualidade | Nenhuma |
| P1 | 2.3 Testes enrichers core | 16h | 🟢 Cobertura | 2.2 |
| P2 | 3.2 Cliente HTTP unificado | 12h | 🟢 Resiliência | Nenhuma |
| P2 | 3.3 Refatorar db_service.py | 8h | 🟢 Manutenibilidade | Nenhuma |
| P2 | 4.1 Retry para todos enrichers | 8h | 🟢 Resiliência | 3.2 |
| P3 | 4.4 Data lineage | 4h | 🟡 Rastreabilidade | Nenhuma |
| P3 | 5.1 Type hints coverage | 16h | 🟡 Type safety | Nenhuma |
| P4 | 5.3 Modularizar arquivos grandes | 24h | 🟡 Manutenibilidade | 3.1, 3.3 |

---

## CRONOGRAMA SUGERIDO

```
Semana 1:  Fase 1 (quick wins) + Fase 2 (test infra)
Semana 2:  Fase 3 (refatoração core)
Semana 3:  Fase 4 (resiliência) + Fase 5 (type safety)
Semana 4:  Testes de regressão, validação, deploy
```

---

## MÉTRICAS DE SUCESSO

| Métrica | Atual | Alvo |
|---------|-------|------|
| Erros ruff | 17 | 0 |
| `type: ignore` | 24 | <10 |
| `Any` annotations | 28 | <5 |
| Cobertura de testes | ~3% | >30% |
| Funções com type hints | 58% | >80% |
| Arquivos >300 LOC | 31 | <20 |
| Clientes HTTP diferentes | 2 (requests+httpx) | 1 |
| Erros mypy ativos | 3 | 0 |
