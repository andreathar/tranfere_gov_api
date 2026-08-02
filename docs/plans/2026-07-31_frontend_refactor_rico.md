# Plano — Refatoração do Frontend: Painel Rico de Inteligência + Performance

> **Para Hermes:** executar fase a fase com `subagent-driven-development`, um subagente por tarefa, com revisão de spec + qualidade.
>
> **Objetivo:** transformar a SPA vanilla (src/api/static) em um painel que expõe TODOS os dados enriquecidos já disponíveis no PostgreSQL (senadores, governadores, financeiro SICONFI, FNDE, discursos, alertas), com abas faltantes e performance de carregamento/UI significativamente melhor.
>
> **Arquitetura:** manter vanilla JS (convenção do projeto — proibido React), separar app.js monolítico em módulos carregados sob demanda, lazy-load do Plotly (~4,5 MB), paginação/windowing para tabelas grandes, cache TTL + GZip no backend.
>
> **Stack:** FastAPI + psycopg2 (pool existente em src/db_utils.py) + vanilla JS + Plotly.js + PostgreSQL.

---

## 1. Contexto atual

### 1.1 Dados disponíveis (row counts reais, 2026-07-31)

| Tabela | Linhas | Exposto na API? | Aba no frontend? |
|--------|-------:|-----------------|------------------|
| planos_acao | 50.350 | Sim (deputados, prefeitos) | Parcial |
| vereadores_dados | 430.827 | Sim (6 endpoints) | Sim (sem paginação!) |
| parlamentar_proposicoes | 27.553 | Sim | Sim |
| parlamentar_discursos | 24.040 | **NÃO** | **NÃO** |
| municipios_financeiro | 16.546 | **NÃO** (só via governadores/{uf}) | **NÃO** |
| emendas_discricionarias | 10.517 | **NÃO** | **NÃO** |
| parlamentar_beneficiario | 8.408 | Parcial (via prefeitos) | Parcial |
| municipios_ibge | 5.570 | Parcial | Parcial |
| prefeitos_dados | 5.545 | Sim | Sim |
| beneficiarios | 4.910 | Parcial | Parcial |
| saude/educacao_municipios | 4.045 cada | **NÃO** (via MCP externo) | Parcial |
| municipios_financeiro | 16.546 | **NÃO** | **NÃO** |
| parlamentares_dados | 565 | Sim | Sim |
| votos_camara | 35.436 | Sim (por deputado) | Sim |
| votacoes_camara | 100 | **NÃO** (função existe) | **NÃO** |
| governadores_dados | 27 | Sim (9 endpoints!) | **NÃO** |
| estados_financeiro | 27 | Parcial (1 endpoint) | **NÃO** |
| senadores_dados | 81 | **NÃO** | **NÃO** |
| parlamentar_alertas | 58 | **NÃO** | **NÃO** |
| fnde_repasses | 190 | Sim (5 endpoints) | **NÃO** |
| diario_oficial_atos | 63 | Sim | Sim |
| violencia_municipios | 400 | **NÃO** | **NÃO** |
| beneficiario_processos | 192 | Sim (MCP cache) | Sim (modal) |
| validacao_cnpj | 0 (vazia) | — | — |

### 1.2 Lacunas identificadas (o que o plano fecha)

1. **Senadores**: tabela completa (81) — sem router, sem service, sem aba.
2. **Governadores**: router de 9 endpoints pronto — **zero** uso no frontend.
3. **Financeiro**: estados_financeiro (27) + municipios_financeiro (16.546) — só 1 endpoint, sem aba.
4. **FNDE**: 5 endpoints prontos — **zero** uso no frontend.
5. **Discursos**: 24.040 registros — sem endpoint nem aba.
6. **Alertas**: 58 registros — sem endpoint nem aba.
7. **Votações recentes (nacionais)**: `get_votacoes_recentes()` existe em db_service — sem rota.
8. **Emendas discricionárias** (10.517): sem exposição dedicada.
9. **Performance**: app.js monolítico 1.422 linhas; Plotly 4,5 MB carregado sempre; tabelas grandes renderizadas inteiras (430k vereadores); sem GZip; sem cache HTTP; sem cache de resposta no backend.

---

## 2. Decisões de arquitetura (com justificativa)

| Decisão | Escolha | Por quê |
|---------|---------|---------|
| Framework frontend | **Vanilla JS (manter)** | Convenção explícita no AGENTS.md: "Frontend: vanilla JS, não React". Adicionar bundler/React seria refactor massivo sem retorno proporcional. |
| Estrutura JS | Módulos: `js/core.js` + `js/tabs/*.js` carregados **sob demanda** (script injection) | Sem bundler, múltiplos arquivos pequenos são a forma nativa de code-splitting. Cada aba só baixa o código dela. |
| Plotly | **Lazy-load** via `charts.js` (injeção dinâmica do script CDN na 1ª renderização de gráfico) | 4,5 MB → ~0 até o usuário ver um gráfico. CDN com cache imutável. |
| Tabelas grandes | **Paginação server-side** (limit/offset já suportado) + **windowing client-side** (100 linhas + IntersectionObserver) | 430.827 vereadores não podem ser renderizados de uma vez. |
| Backend cache | `cachetools.TTLCache` por função cara (analytics, financeiro, resumos) — TTL 300s | Queries agregadas de 16k+ linhas não precisam rodar a cada F5. |
| Compressão | `GZipMiddleware` (min_size=1000) | JSON repetitivo comprime 5-10x. |
| Cache estático | Header `Cache-Control: public, max-age=31536000, immutable` + `?v=` no cache-busting | SPA estática é imutável entre deploys. |
| Deep links | Hash routing `#/deputados/4291/emendas` | Recarregar página não perde contexto; compartilhável. |

**Excluído (com rationale):** React/Vue (convenção proíbe), bundler (Vite/Webpack exigiria toolchain Node nova no projeto Python puro), HTMX (não resolve as tabelas de 430k linhas melhor que windowing), SQLite (não se aplica — já temos Postgres), Redis (overkill para single-node; TTLCache resolve).

---

## 3. Fases e tarefas

---

### FASE 0 — Fundação de performance (backend)

#### Tarefa 0.1: GZip + cache headers no app.py

**Arquivo:** `src/api/app.py`

**Passo 1 — adicionar middleware GZip e headers de estático:**

```python
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
```

No `app.mount("/static", ...)` atual, adicionar após a definição da rota raiz um handler de cache:

```python
@app.middleware("http")
async def cache_static(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response
```

**Passo 2 — validar:**

```bash
curl -s -o /dev/null -w '%{size_download} %{header_json}' http://localhost:8000/api/v1/analytics/top-municipios
# esperado: size_download menor que antes (gzip), header content-encoding: gzip
```

#### Tarefa 0.2: Cache TTL no db_service para queries caras

**Arquivo:** `src/api/services/db_service.py`

Adicionar no topo:

```python
from cachetools import TTLCache, cached
```

Decorar as funções agregadas caras (resultados mudam só com re-enriquecimento):

```python
_cache_analytics = TTLCache(maxsize=32, ttl=300)

@cached(_cache_analytics)
def get_resumo_emendas_por_parlamentar_id(parlamentar_id: int) -> dict: ...
@cached(_cache_analytics)
def get_ranking_prefeitos(limit: int = 20) -> list[dict]: ...
@cached(_cache_analytics)
def get_resumo_vereadores() -> dict: ...
@cached(_cache_analytics)
def get_ranking_governadores_emendas(limit: int = 27) -> list[dict]: ...
@cached(_cache_analytics)
def get_ranking_alinhamento_governador(limit: int = 27) -> list[dict]: ...
```

Criar `src/api/services/cache_utils.py` com `invalidate_analytics_cache()` (chama `.clear()`) para os enrichers usarem pós-import. **Atenção:** `cached` exige argumentos hashable — `limit` é int, ok. NÃO decorar funções que retornam conexões/objetos mutáveis.

**Validação:** `pytest tests/test_api_routes.py -x` + smoke: duas chamadas seguidas ao mesmo endpoint, segunda em <10ms.

#### Tarefa 0.3: Index composto para ranking de vereadores

**Arquivo:** `data/migration_026_frontend_perf.sql` (novo, seguir padrão de `data/migration_*.sql`)

```sql
-- Ranking por partido/UF (filtros mais usados no frontend)
CREATE INDEX IF NOT EXISTS idx_vereadors_uf_partido_situacao
    ON vereadores_dados (uf, partido, situacao);
-- Discursos por ordem cronológica por deputado
CREATE INDEX IF NOT EXISTS idx_discursos_parlamentar_data
    ON parlamentar_discursos (parlamentar_id, data_hora_inicio DESC);
```

Registrar em `docs/MIGRATIONS.md`.

**Validação:** `PGPASSWORD=cognee psql -U cognee -h 127.0.0.1 -d transferegov_db -f data/migration_026_frontend_perf.sql`

---

### FASE 1 — Novos endpoints de API (dados que já existem no banco)

#### Tarefa 1.1: Router Senadores (novo)

**Criar:** `src/api/routes/senadores.py` · `src/api/services/db_service.py` (funções) · registrar em `src/api/app.py`

```python
"""Rotas REST de Senadores (FastAPI)."""
from fastapi import APIRouter, HTTPException
from src.api.services import db_service

router = APIRouter()

@router.get("/search")
async def search_senadores(q: str = Query(..., min_length=2)):
    return db_service.search_senadores(q)

@router.get("/ranking")
async def ranking_senadores(limit: int = 30, partido: str | None = None, uf: str | None = None):
    return db_service.get_ranking_senadores(limit=limit, partido=partido, uf=uf)

@router.get("/por-partido")
async def senadores_por_partido():
    return db_service.get_senadores_por_partido()

@router.get("/{senador_codigo}/perfil")
async def perfil_senador(senador_codigo: int):
    perfil = db_service.get_perfil_senador(senador_codigo)
    if not perfil:
        raise HTTPException(404, "Senador não encontrado")
    return perfil
```

Em `db_service.py`:

```python
def search_senadores(query: str) -> list[dict]:
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT senador_codigo, nome_parlamentar, nome_completo, sigla_partido,
                       uf, situacao, foto_url, legislatura
                FROM senadores_dados
                WHERE nome_parlamentar ILIKE %s OR nome_completo ILIKE %s
                ORDER BY nome_parlamentar LIMIT 50
            """, (f"%{query}%", f"%{query}%"))
            return _rows_to_list(cur.fetchall())
    finally:
        conn.close()

def get_ranking_senadores(limit: int = 30, partido: str | None = None, uf: str | None = None) -> list[dict]:
    # ranking por total_votacoes (atividade legislativa) com filtros opcionais
    ...

def get_perfil_senador(senador_codigo: int) -> dict | None:
    # SELECT * FROM senadores_dados WHERE senador_codigo = %s
    ...
```

**Registrar em `app.py`:**

```python
from src.api.routes import senadores
app.include_router(senadores.router, prefix="/api/v1/senadores", tags=["senadores"])
```

#### Tarefa 1.2: Discursos + Alertas do deputado

**Arquivo:** `src/api/routes/deputados.py`

```python
@router.get("/{deputado_id}/discursos")
async def get_discursos(deputado_id: int, limit: int = 50, tipo: str | None = None):
    """Discursos em plenário/comissões do deputado (tabela parlamentar_discursos)."""
    return db_service.get_discursos_deputado(deputado_id, limit=limit, tipo=tipo)

@router.get("/{deputado_id}/alertas")
async def get_alertas(deputado_id: int):
    """Alertas automáticos do pipeline (parlamentar_alertas)."""
    return db_service.get_alertas_deputado(deputado_id)
```

Em `db_service.py`:

```python
def get_discursos_deputado(deputado_id: int, limit: int = 50, tipo: str | None = None) -> list[dict]:
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            sql = """
                SELECT id, data_hora_inicio, fase_evento, tipo_discurso, keywords,
                       sumario, url_texto
                FROM parlamentar_discursos
                WHERE deputado_id = %s
            """
            params: list = [deputado_id]
            if tipo:
                sql += " AND tipo_discurso ILIKE %s"
                params.append(f"%{tipo}%")
            sql += " ORDER BY data_hora_inicio DESC LIMIT %s"
            params.append(limit)
            cur.execute(sql, params)
            return _rows_to_list(cur.fetchall())
    finally:
        conn.close()

def get_alertas_deputado(deputado_id: int) -> list[dict]:
    # JOIN parlamentar_alertas a ON a.parlamentar_id = get_parlamentar_id(deputado_id)
    ...
```

#### Tarefa 1.3: Router Financeiro (novo)

**Criar:** `src/api/routes/financeiro.py`

```python
"""Rotas REST de Financeiro SICONFI (estados + municípios)."""
from fastapi import APIRouter, Query
from src.api.services import db_service

router = APIRouter()

@router.get("/estados")
async def financeiro_estados(exercicio: int | None = None):
    """Resumo financeiro das 27 UFs (DCA + arrecadação RREO)."""
    return db_service.get_financeiro_estados(exercicio=exercicio)

@router.get("/estado/{uf}")
async def financeiro_estado(uf: str):
    """Detalhe financeiro de um estado (reutiliza get_financeiro_estado)."""
    return db_service.get_financeiro_estado(uf.upper())

@router.get("/municipios")
async def financeiro_municipios(uf: str | None = None, exercicio: int | None = None,
                                order_by: str = "despesas_totais", limit: int = 100):
    """Ranking de municípios por receita/despesa/arrecadação."""
    return db_service.get_financeiro_municipios(uf=uf, exercicio=exercicio,
                                                 order_by=order_by, limit=limit)

@router.get("/municipio/{municipio_id}")
async def financeiro_municipio(municipio_id: int):
    """Financeiro + indicadores IBGE + emendas recebidas do município."""
    return db_service.get_financeiro_municipio(municipio_id)

@router.get("/comparativo")
async def comparativo(uf: str | None = None):
    """Emendas Pix recebidas × arrecadação própria (ICMS/IPTU/ISS/FPM) por UF."""
    return db_service.get_comparativo_emendas_financeiro(uf=uf)
```

Em `db_service.py` — função principal (JOIN para municípios com UF):

```python
def get_financeiro_municipios(uf: str | None = None, exercicio: int | None = None,
                              order_by: str = "despesas_totais", limit: int = 100) -> list[dict]:
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            order_col = order_by if order_by in {
                "despesas_totais", "receitas_orcamentarias", "arrec_iss",
                "arrec_iptu", "arrec_cota_icms", "arrec_cota_fpm", "resultado_orcamentario"
            } else "despesas_totais"
            sql = f"""
                SELECT mf.municipio_id, mi.nome, mi.uf, mf.exercicio,
                       mf.receitas_orcamentarias, mf.despesas_totais,
                       mf.resultado_orcamentario, mf.arrec_iss, mf.arrec_iptu,
                       mf.arrec_cota_icms, mf.arrec_cota_fpm
                FROM municipios_financeiro mf
                JOIN municipios_ibge mi ON mi.codigo_ibge = mf.municipio_id
                WHERE 1=1
            """
            params: list = []
            if uf:
                sql += " AND mi.uf = %s"
                params.append(uf.upper())
            if exercicio:
                sql += " AND mf.exercicio = %s"
                params.append(exercicio)
            sql += f" ORDER BY mf.{order_col} DESC NULLS LAST LIMIT %s"
            params.append(limit)
            cur.execute(sql, params)
            return _rows_to_list(cur.fetchall())
    finally:
        conn.close()
```

#### Tarefa 1.4: Votações recentes (nacionais) + endpoint emendas discricionárias

**Arquivo:** `src/api/routes/` — nova rota em `analytics.py` ou novo `votacoes.py`:

```python
@router.get("/recentes")
async def votacoes_recentes(ano: int | None = None, limit: int = 20):
    """Últimas votações nominais da Câmara (tabela votacoes_camara)."""
    return db_service.get_votacoes_recentes(ano=ano, limit=limit)
```

Emendas discricionárias (10.517 linhas) — expor como sub-recurso do deputado:

```python
@router.get("/{deputado_id}/emendas-discricionarias")
async def get_emendas_discricionarias(deputado_id: int, ano: int | None = None, limit: int = 100):
    return db_service.get_emendas_discricionarias_deputado(deputado_id, ano=ano, limit=limit)
```

#### Tarefa 1.5: Testes dos novos endpoints

**Arquivo:** `tests/test_api_routes.py` (estender) + `tests/test_api_senadores.py` (novo)

Cobrir: search senadores, perfil 404, ranking vereadores paginado, discursos deputado, financeiro municipios com UF, comparativo. Rodar:

```bash
source .venv/bin/activate && pytest tests/test_api_routes.py tests/test_api_senadores.py -v
```

---

### FASE 2 — Frontend: nova arquitetura (performance)

#### Tarefa 2.1: Split do app.js em módulos

**Criar estrutura:**

```
src/api/static/
├── index.html              (modificado: <script defer src="/static/js/core.js">)
├── style.css               (mantém + tokens novos)
└── js/
    ├── core.js             (estado global, formatadores, fetchWrapper com timeout+abort, hash router)
    ├── charts.js           (lazy Plotly loader + plotlyDarkLayout + renderChart helper)
    └── tabs/
        ├── deputado.js     (perfil, sidebar, sub-tabs: emendas, despesas, comissões, votações, proposições, discursos, alertas, dossiê)
        ├── prefeitos.js
        ├── vereadores.js
        ├── senadores.js    (NOVO)
        ├── governadores.js (NOVO)
        ├── financeiro.js   (NOVO)
        ├── fnde.js         (NOVO)
        ├── inteligencia.js
        ├── saude.js
        └── diario.js
```

**Padrão de carregamento lazy** (em `core.js`):

```javascript
const tabLoaders = {
  senadores: () => loadScript('/static/js/tabs/senadores.js').then(() => window.TabsSenadores.init()),
  governadores: () => loadScript('/static/js/tabs/governadores.js').then(() => window.TabsGovernadores.init()),
  financeiro: () => loadScript('/static/js/tabs/financeiro.js').then(() => window.TabsFinanceiro.init()),
  // ... demais abas
};

async function loadScript(src) {
  if (document.querySelector(`script[src="${src}"]`)) return;
  return new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = src; s.defer = true;
    s.onload = resolve; s.onerror = () => reject(new Error(`Falha ao carregar ${src}`));
    document.head.appendChild(s);
  });
}

// fetch wrapper com timeout + abort + cache em memória
const apiFetch = (() => {
  const memCache = new Map();
  const TTL = 5 * 60 * 1000;
  return async function apiFetch(path, { force = false } = {}) {
    const key = path;
    const hit = memCache.get(key);
    if (!force && hit && Date.now() - hit.t > TTL) memCache.delete(key);
    if (!force && memCache.has(key)) return memCache.get(key).data;
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 15000);
    try {
      const res = await fetch(`/api/v1${path}`, { signal: ctrl.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      memCache.set(key, { t: Date.now(), data });
      return data;
    } finally {
      clearTimeout(timer);
    }
  };
})();
```

#### Tarefa 2.2: Lazy-load do Plotly

**Arquivo:** `src/api/static/js/charts.js`

```javascript
let plotlyPromise = null;
function loadPlotly() {
  if (window.Plotly) return Promise.resolve(window.Plotly);
  if (plotlyPromise) return plotlyPromise;
  plotlyPromise = new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = 'https://cdn.plot.ly/plotly-2.35.2.min.js';
    s.onload = () => resolve(window.Plotly);
    s.onerror = () => { plotlyPromise = null; reject(new Error('CDN Plotly indisponível')); };
    document.head.appendChild(s);
  });
  return plotlyPromise;
}

async function renderChart(elId, data, layout, config = { displayModeBar: false, responsive: true }) {
  const el = document.getElementById(elId);
  if (!el) return;
  try {
    const Plotly = await loadPlotly();
    await Plotly.react(el, data, { ...plotlyDarkLayout(), ...layout }, config);
  } catch (e) {
    el.innerHTML = '<p class="chart-fallback">Gráfico indisponível (CDN offline).</p>';
  }
}
```

**Remover** o `<script src="plotly...">` do `index.html` — só carrega quando a primeira aba com gráfico abre. Adicionar `preconnect` para `https://cdn.plot.ly` no head.

#### Tarefa 2.3: Paginação/windowing para tabelas grandes

**Arquivo:** `src/api/static/js/core.js` — componente `PaginatedTable`:

```javascript
function createPaginatedTable(containerId, columns, fetchPage, pageSize = 100) {
  // renderiza cabeçalho + <tbody> + controles (⏮ ◀ pág X/N ▶ ⏭)
  // usa IntersectionObserver no último <tr> para "carregar mais" (infinite scroll)
  // estado: page, hasMore, loading — chama fetchPage(page, pageSize) → {rows, total}
}
```

Aplicar em: vereadores (430k), emendas deputado (50k), proposições, discursos, ranking financeiro. **Nunca** `innerHTML` com 430k linhas.

#### Tarefa 2.4: Hash routing (deep links)

**Arquivo:** `src/api/static/js/core.js`:

```javascript
window.addEventListener('hashchange', handleRoute);
function handleRoute() {
  // #/deputados/4291/emendas | #/senadores | #/governadores/SP | #/financeiro | #/fnde
  const [_, section, id, subtab] = location.hash.split('/');
  // mapeia para switchNavMode + selectDeputado + switchTab
}
```

`switchNavMode()` e `selectDeputado()` passam a setar `location.hash` (sem re-trigger de loop — guard flag).

#### Tarefa 2.5: Skeleton loaders + estados vazios/erro padronizados

**Arquivo:** `src/api/static/style.css` + `core.js`

- Classe `.skeleton` (gradiente animado) para substituir spinners em tabelas/cards.
- Helpers `renderEmpty(container, msg)` e `renderError(container, err, retryFn)` — todo `try/catch` de aba usa esses helpers (padrão atual repete HTML solto em 15 lugares).
- Badge/skeleton de perfil enquanto carrega.

---

### FASE 3 — Novas abas no frontend

#### Tarefa 3.1: Aba SENADORES

**Arquivos:** `index.html` (botão nav + `#tab-senadores`), `js/tabs/senadores.js`

Conteúdo:
- Header: busca + filtro partido/UF + botão Ranking.
- KPIs: total senadores, partidos, UFs, média de votações (endpoint `/senadores/ranking` + `/senadores/por-partido`).
- Gráfico: senadores por partido (Plotly bar — lazy).
- Tabela paginada: nome, partido, UF, situação, votações, relatorias.
- Clique → **modal perfil**: foto, mandato (início/fim), contato, email, total votações/relatorias.

#### Tarefa 3.2: Aba GOVERNADORES

**Arquivos:** `index.html`, `js/tabs/governadores.js`

Conteúdo (usa os 9 endpoints prontos):
- KPIs: 27 UFs, partido mais frequente, maior % votos 1º turno, maior captação de emendas.
- Gráficos: 1) Ranking emendas por UF (bar), 2) Alinhamento partidário bancada (bar horizontal), 3) Mapa de triângulo político por UF (tabela heat ou scatter).
- Tabela: UF, governador, vice, partido, votos T1/T2 %, situação.
- Clique → **perfil UF**: dados eleitorais + financeiro SICONFI (`/governadores/{uf}/perfil` já traz) + bancada aliada + emendas por município.

#### Tarefa 3.3: Aba FINANCEIRO (SICONFI)

**Arquivos:** `index.html`, `js/tabs/financeiro.js`

Conteúdo:
- Seletor: esfera (Estados/Municípios) + UF + exercício.
- KPIs (estados): maior receita, maior RCL, maior arrecadação ICMS, resultado primário agregado.
- Gráficos: 1) Receita vs Despesa por UF (bar agrupada), 2) Composição arrecadação (ICMS/IPVA/ITCD/FPE/FUNDEB — donut), 3) Comparativo emendas Pix recebidas × arrecadação própria (scatter, do endpoint `/financeiro/comparativo`).
- Tabela paginada de municípios: nome/UF, receitas, despesas, resultado, ISS/ICMS/FPM, ordenável (order_by do backend).
- Clique município → modal com financeiro + IBGE + emendas recebidas.

#### Tarefa 3.4: Aba FNDE

**Arquivos:** `index.html`, `js/tabs/fnde.js`

Conteúdo (usa 5 endpoints prontos):
- KPIs: total repasses, municípios, programas.
- Gráfico: repasses por UF (bar) + por programa (donut).
- Tabela: município, programa, valor, UF.
- Busca por município.

#### Tarefa 3.5: Sub-tabs novas do deputado — Discursos + Alertas + Discricionárias

**Arquivos:** `index.html` (botões `data-tab="discursos"`, `"alertas"`), `js/tabs/deputado.js`

- **Discursos**: timeline (data, fase, tipo, keywords chips, sumário colapsável com link para transcrição) — paginada.
- **Alertas**: cards por nível de relevância (cores), com data e referência ao ato.
- **Emendas Discricionárias**: tabela paginada com ano, valor, situação.
- Adicionar ao `loadTabData()` correspondente no novo módulo.

---

### FASE 4 — Inteligência rica (cross-data)

#### Tarefa 4.1: Inteligência — novos gráficos

**Arquivos:** `js/tabs/inteligencia.js`

Adicionar ao grid existente (party-efficiency, socioeconomic, deputy-roi):
1. **Triângulo político por UF** (`/governadores/triangulo-politico`) — scatter: deputados × prefeitos do mesmo partido do governador vs outros, anotado por UF.
2. **Ranking governadores × emendas** (`/governadores/ranking/emendas`) — bar horizontal.
3. **Alinhamento bancada federal** (`/governadores/ranking/alinhamento`) — bar com % de deputados alinhados.
4. **Emendas × Arrecadação municipal** (`/financeiro/comparativo`) — scatter com eixo log.

#### Tarefa 4.2: Perfil município rico (modal prefeito v2)

**Arquivo:** `js/tabs/prefeitos.js` (modal `openPrefeitoModal` atual)

Enriquecer o modal com abas internas:
- **Gestão**: dados TSE do prefeito (já existe).
- **Finanças**: `municipios_financeiro` do município (novo endpoint) — receitas, despesas, arrecadação.
- **Saúde/Educação**: `saude_municipios` + `educacao_municipios` (novos endpoints de leitura — hoje só via MCP externo).
- **Violência**: `violencia_municipios`.
- **Compras**: licitações + ganhadores (já existe).

Adicionar endpoints de leitura local em `routes/auditoria.py` ou novo `routes/municipios.py`:

```python
@router.get("/{municipio_id}/indicadores")
async def indicadores_municipio(municipio_id: int):
    """Indicadores locais: saúde, educação, violência, financeiro (JOIN com IBGE)."""
    return db_service.get_indicadores_municipio(municipio_id)
```

---

### FASE 5 — UI/UX polish

#### Tarefa 5.1: Design tokens + responsividade

**Arquivo:** `src/api/static/style.css`

- Consolidar CSS vars (já existem `--bg-card`, `--accent-blue`...) em `:root` completo: espaçamento, radius, sombra, breakpoints.
- Grid responsivo: `.kpi-grid` e `.charts-row` com `grid-template-columns: repeat(auto-fit, minmax(280px, 1fr))` — hoje há grids fixos de 3-4 colunas que quebram em mobile.
- Navbar colapsável (hamburger < 768px), tabelas com scroll horizontal (já usam `.table-responsive`).
- Scrollbar customizada fina (dark).

#### Tarefa 5.2: Exportação CSV

**Arquivo:** `js/core.js` — helper:

```javascript
function exportCSV(filename, headers, rows) {
  const csv = [headers, ...rows].map(r => r.map(c => `"${String(c ?? '').replace(/"/g, '""')}"`).join(';')).join('\n');
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}
```

Botão "Exportar CSV" em todas as tabelas paginadas.

#### Tarefa 5.3: Acessibilidade + micro UX

- `aria-label` nos botões de nav/tab, `role="tablist"`, `aria-selected`.
- Foco visível (`:focus-visible`) consistente.
- `prefers-reduced-motion` desativa animações de skeleton/spinner.
- Toast de erro global (`core.js`) em vez de só console.error.

---

## 4. Validação final

```bash
# Backend
source .venv/bin/activate
ruff check src/api/ tests/test_api_routes.py tests/test_api_senadores.py
pytest tests/test_api_routes.py tests/test_api_senadores.py -v

# Smoke manual (uvicorn)
uvicorn src.api.app:app --port 8000 &
curl -s http://localhost:8000/api/v1/senadores/ranking | head -c 400
curl -s http://localhost:8000/api/v1/financeiro/municipios?uf=SP\&limit=5
curl -s http://localhost:8000/api/v1/deputados/4291/discursos | head -c 400

# Frontend
# 1) Abrir http://localhost:8000/#/senadores — sem Plotly no Network até abrir gráfico
# 2) #/governadores/SP — perfil carrega sem reload
# 3) Aba Vereadores — tabela paginada (contador de linhas, scroll infinito, sem freeze)
# 4) Lighthouse/DevTools Performance: < 2.5s LCP, Plotly só após interação
# 5) Testar com CDN offline (block plot.ly) — gráficos mostram fallback, app não quebra
```

## 5. Riscos e mitigações

| Risco | Mitigação |
|-------|-----------|
| Split do app.js (1.422 linhas) introduz regressões | Fase 2 é a ÚLTIMA a tocar no JS existente; antes dela, Fase 1 adiciona endpoints sem mexer no frontend. Migrar aba por aba, validando cada uma. `git commit` por tarefa. |
| Plotly CDN offline | `renderChart` com try/catch → fallback textual; `preconnect` + retry 1x. |
| cachetools `cached` com kwargs não-hashable | Só decorar funções com args int/str/None; testar com 2 chamadas. |
| Tabela de 430k vereadores trava UI | Paginação server-side (limit/offset já suportado) + windowing 100 linhas — nunca renderizar tudo. |
| `get_financeiro_estado` retorna dict grande | Manter payload ≤ 50 campos; adicionar `?resumo=1` se preciso. |
| SICONFI multi-exercício | Filtro `exercicio` com default = último ano presente no banco. |
| Cache TTL fica stale após re-enriquecimento | `invalidate_analytics_cache()` chamado no fim dos enrichers (pipeline.py). |

## 6. Ordem de execução recomendada

1. **Fase 0** (perf backend) — 3 tarefas, ~30 min.
2. **Fase 1** (endpoints novos) — 5 tarefas, ~2-3 h. API pronta antes de tocar UI.
3. **Fase 5.1/5.2/5.3** (CSS tokens, export, a11y) — independente, pode rodar em paralelo com Fase 2.
4. **Fase 2** (arquitetura JS) — 5 tarefas, ~3-4 h. Migrar abas existentes 1 a 1.
5. **Fase 3** (abas novas: Senadores → Governadores → Financeiro → FNDE → sub-tabs deputado) — 5 tarefas, ~4 h.
6. **Fase 4** (inteligência rica + modal município) — 2 tarefas, ~2 h.
7. **Validação final** + commit.

**Estimativa total: ~12-15 h de trabalho efetivo.**
