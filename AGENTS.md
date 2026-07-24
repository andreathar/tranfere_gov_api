# AGENTS.md — TransfereGov API

Projeto Python para extração, validação, enriquecimento e análise de Planos de Ação do
sistema Transferegov (Transferências Especiais / Emendas Pix) do Governo Federal.

## Status: PRODUÇÃO

Pipeline completo: **Extração → Validação (Pydantic) → PostgreSQL (upsert idempotente) → Enriquecimento (IBGE, BrasilAPI, Câmara) → Relatórios SQL + Views**

---

## Comandos Essenciais

```bash
# Ativar venv
source .venv/bin/activate

# ============================================================
# EXTRAÇÃO (src/transferegov_extract.py)
# ============================================================
./run.sh discover                          # listar objetos disponíveis (2026)
./run.sh cemiterios                        # extrair objeto 301 (cemitérios)
./run.sh negados                           # extrair negados/perdidos (objeto 301)
./run.sh cemiterios --db                   # extrair + salvar no PostgreSQL
./run.sh negados --csv --db               # extrair + CSV + banco
./run.sh all --db                          # todos os objetos + banco

# Extração por programa + situação (API server-side)
python3 src/transferegov_extract.py --objeto all --ano 2026 --programa 25 --situacao-api IMPEDIDO --db --csv

# Flags extras (funcionam em qualquer extração)
  --db                 Salvar no PostgreSQL (upsert idempotente)
  --csv                Exportar CSV além de Excel
  --programa N         Filtrar por programaId (25 = Transferências Especiais)
  --uf UF              Filtrar por UF (ex: SP, AL, PI)
  --situacao-api S     Filtrar por situação na API (ex: IMPEDIDO)
  -v                   Logging verboso

# ============================================================
# IMPORTAÇÃO MANUAL
# ============================================================
./run.sh import                            # importa todos os JSONs de output/json/

# ============================================================
# RELATÓRIOS (src/db_report.py) — via banco
# ============================================================
./run.sh report resumo                     # resumo geral
./run.sh report estado                     # por estado (UF)
./run.sh report negados                    # planos negados
./run.sh report top 10                     # top 10 valores
./run.sh report municipio SP               # planos de um estado
./run.sh report emenda                     # por parlamentar/emenda
./run.sh report sql "SELECT ..."           # query customizada

# ============================================================
# ENRIQUECIMENTO (src/enrichers/) — pós-extração, requer DB populado
# ============================================================
# Fase 1: Validação CNPJ + IBGE
python3 -m src.enrichers.validacao [--dry-run] [--limit N]
python3 -m src.enrichers.ibge [--dry-run] [--uf UF]
python3 -m src.enrichers.mapear_municipios [--dry-run]

# Fase 2: Perfil parlamentares (Câmara)
python3 -m src.enrichers.camara [--dry-run] [--limit N]

# Fase 3: Vinculação parlamentar-beneficiário
python3 -m src.enrichers.pipeline --fase 3

# Pipeline completo (fases 1+2+3)
python3 -m src.enrichers.pipeline --fase all [--dry-run] [--limit N]

# ============================================================
# BANCO
# ============================================================
psql -U cognee -h 127.0.0.1 -d transferegov_db
```

---

## Estrutura do Projeto

```
tranfere_gov_api/
├── src/                          Scripts Python ativos
│   ├── transferegov_extract.py     ← CLI PRINCIPAL (extração + DB)
│   ├── db_import.py                Importação JSON → PostgreSQL
│   ├── db_report.py                Relatórios SQL formatados
│   ├── schemas.py                  Pydantic schemas (PlanoAcaoSchema)
│   ├── http_cache.py               Cache TTL para requests HTTP
│   │
│   └── enrichers/                  Pipeline de enriquecimento
│       ├── __init__.py
│       ├── pipeline.py             Orquestrador (fases 1-3)
│       ├── validacao.py            Fase 1a: Validação CNPJ (BrasilAPI)
│       ├── ibge.py                 Fase 1b: Dados IBGE (municípios)
│       ├── camara.py               Fase 2: Perfil parlamentares (Câmara)
│       ├── mapear_municipios.py    Mapeamento fuzzy beneficiário → IBGE
│       └── validacao.py            Validação cruzada
│
├── config/                         Config centralizada
│   ├── settings.py                 ← API, DB, paths, ENRICH_*
│   └── .env.example
│
├── data/                           Dados de referência
│   ├── swagger.yaml                Spec OpenAPI 3.0 (engenharia reversa)
│   ├── schema.sql                  Schema PostgreSQL completo (core)
│   └── migration_002_relatorios.sql  Migration: tabelas enriquecimento + views
│
├── output/                         Gitignored (xlsx, csv, json, logs)
│   ├── xlsx/
│   ├── csv/
│   ├── json/
│   └── logs/
│
├── archive/                        Scripts obsoletos (referência)
├── docs/                           Documentação
├── app/                            App React (AI Studio scaffold)
├── run.sh                          Atalhos CLI
├── requirements.txt
└── MCP_BRASIL_INTEGRATION_PLAN.md  Plano integração mcp-brasil
```

---

## Convenções

- **Language**: Português (comentários, logs, CLI help em PT-BR)
- **Style**: ruff (line-length 99, target py311)
- **Types**: mypy strict
- **Tests**: pytest + pytest-asyncio
- **Config**: tudo em `config/settings.py`, importar via `from config.settings import X`
- **Paths**: usar `config.settings.OUTPUT_*` para saídas, nunca hardcodar
- **Schema**: validar com Pydantic antes de processar
- **DB**: usar `upsert_plano_acao()` para import idempotente
- **Commit**: mensagens em PT-BR, sem emoji

---

## API TransfereGov

- **Endpoint**: `GET https://especiais.transferegov.sistema.gov.br/maisbrasil-transferencia-especial-backend/api/public/plano-acao/listagem`
- **Response key**: `listaPlanosAcao` (NÃO `data`/`content`/`items`)
- **Pagination**: `pageSize=100`, `pageNumber=1..N`, break when empty
- **Auth**: NENHUMA (público)
- **IP restriction**: pode bloquear IPs fora do Brasil (TCP timeout)
- **Timeout**: 60s, retries 3 com backoff exponencial

### Parâmetros de Query (descobertos via URL real)

| Param | Descrição | Exemplo |
|-------|-----------|---------|
| `objetoExecucao` | Código do objeto (vazio = todos) | `301`, `662`, `` |
| `objetoExecucaoAno` | Ano exercício | `2026` |
| `programaId` | ID do programa (25 = Transf. Especiais) | `25` |
| `planoAcaoSituacao` | Situação do plano (underscores) | `IMPEDIDO` |
| `planoTrabalhoSituacao` | Situação do plano de trabalho | `ENVIADO_PARA_ANALISE` |
| `politicasPublicas` | Código da política pública | `4` |
| `uf` | UF do beneficiário | `AL`, `SP` |
| `beneficiario` | ID do beneficiário | `9858` |
| `parlamentar` | ID do parlamentar | `4291` |
| `emenda` | ID da emenda | `11228` |
| `pageSize` | Itens por página (máx: 100) | `100` |
| `pageNumber` | Página atual (1-indexed) | `1` |

### Mapeamento Situação (display site → valor API)

| Display no Site | Valor API |
|-----------------|-----------|
| Aguardando Ciência | `AGUARDANDO_CIENCIA` |
| Plano de Trabalho em Elaboração/... | `PLANO_TRABALHO_EM_ELABORACAO` |
| Ciente | `CIENTE` |
| Impedido por Restrição Técnica | `IMPEDIDO` |
| Impedido por Rejeição do Plano de Trabalho | `IMPEDIDO_REJEICAO_PLANO_TRABALHO` |
| Aprovado | `APROVADO` |
| Reprovado | `REPROVADO` |
| Cancelado | `CANCELADO` |
| Em Execução | `EM_EXECUCAO` |
| Concluído | `CONCLUIDO` |
| Não Cumpriu | `NAO_CUMPROU` |

---

## PostgreSQL

- **Banco**: `transferegov_db` em `127.0.0.1:5432`
- **User**: `cognee` / **Pass**: `cognee`

### Schema Core (9 tabelas + 5 views)

**Tabelas dimensão**: `objetos`, `programas`, `beneficiarios`, `parlamentares`, `emendas`, `politicas_publicas`, `situacoes_map`
**Tabela fato**: `planos_acao` (22 colunas + 3 parseadas: `emenda_codigo`, `parlamentar_nome`, `emenda_ano`)
**Controle**: `extract_log`

**Views**:
- `v_planos_completo` — join completo com parlamentar + situação display
- `v_negados` — só negados (IMPEDIDO, REPROVADO, CANCELADO, NAO_CUMPROU)
- `v_resumo_por_estado` — por UF + situação
- `v_resumo_por_objeto` — por objeto + total parlamentares
- `v_resumo_por_parlamentar` — totais por parlamentar/ano

**Funções**:
- `upsert_plano_acao()` — importação idempotente
- `parse_emenda()` — extrai emenda, parlamentar e ano do código

### Tabelas de Enriquecimento (migration_002_relatorios.sql)

```sql
-- Validação CNPJ (BrasilAPI)
CREATE TABLE validacao_cnpj (
    cnpj TEXT PRIMARY KEY,
    razao_social TEXT, nome_fantasia TEXT, situacao_cadastral TEXT,
    data_situacao DATE, porte TEXT, natureza_juridica TEXT,
    cep TEXT, telefone TEXT, email TEXT,
    valido BOOLEAN, erro TEXT, checked_at TIMESTAMPTZ
);

-- Municípios IBGE
CREATE TABLE municipios_ibge (
    municipio_id INTEGER PRIMARY KEY,  -- código IBGE 7 dígitos
    nome TEXT, uf CHAR(2), regiao TEXT,
    mesorregiao TEXT, microrregiao TEXT
);

-- Mapeamento beneficiário → IBGE (fuzzy match)
CREATE TABLE beneficiario_ibge_map (
    beneficiario_id INTEGER PRIMARY KEY REFERENCES beneficiarios(beneficiario_id),
    municipio_id INTEGER REFERENCES municipios_ibge(municipio_id)
);

-- Perfil parlamentares (Câmara dos Deputados)
CREATE TABLE parlamentares_dados (
    deputado_id INTEGER PRIMARY KEY,
    nome TEXT, nome_urna TEXT, sigla_partido TEXT, uf CHAR(2),
    situacao TEXT, gabinete_numero TEXT, gabinete_predio TEXT,
    gabinete_telefone TEXT, gabinete_email TEXT, url_foto TEXT,
    ultimo_status TEXT, data_nascimento DATE, municipio_nascimento TEXT,
    uf_nascimento CHAR(2), escolaridade TEXT
);

-- Vinculação parlamentar ↔ beneficiário (agregado)
CREATE TABLE parlamentar_beneficiario (
    parlamentar_nome TEXT,
    beneficiario_id INTEGER REFERENCES beneficiarios(beneficiario_id),
    emenda_codigo TEXT,
    valor_total NUMERIC(15,2),
    plano_acao_situacao TEXT,
    PRIMARY KEY (parlamentar_nome, beneficiario_id, emenda_codigo)
);
```

---

## Pipeline de Enriquecimento

| Fase | Script | Fonte | Tabelas Destino | Descrição |
|------|--------|-------|-----------------|-----------|
| 1a | `validacao.py` | BrasilAPI (CNPJ) | `validacao_cnpj` | Valida CNPJs dos beneficiários |
| 1b | `ibge.py` | IBGE API (localidades) | `municipios_ibge` | Dados demográficos/econômicos dos municípios |
| 1c | `mapear_municipios.py` | Match fuzzy (normalize) | `beneficiario_ibge_map` | Liga beneficiários a códigos IBGE |
| 2 | `camara.py` | Câmara dos Deputados | `parlamentares_dados` | Perfil completo dos deputados autores |
| 3 | `pipeline.py` (fase3) | SQL join | `parlamentar_beneficiario` | Agrega valor total por parlamentar×município×emenda |

**Execução**:
```bash
# Dry-run (só mostra, não salva)
python3 -m src.enrichers.pipeline --fase all --dry-run

# Produção com limite
python3 -m src.enrichers.pipeline --fase all --limit 100
```

---

## Configuração (config/settings.py)

```python
# API TransfereGov
API_URL_LISTAGEM = "https://especiais.transferegov.sistema.gov.br/..."
HEADERS = {"Accept": "application/json", "User-Agent": "TransfereGov-Extractor/1.0"}
DEFAULT_PAGE_SIZE = 100
DEFAULT_TIMEOUT = 60
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0
SLEEP_BETWEEN_PAGES = 1.0

# Situações
SITUACOES_NEGADAS = {"REPROVADO", "IMPEDIDO", "CANCELADO", "NAO_CUMPROU"}
SITUACOES_CONHECIDAS = {"CIENTE", "APROVADO", "REPROVADO", "IMPEDIDO", ...}

# Enriquecimento
ENRICH_ENABLED = True
ENRICH_CACHE_TTL = 3600
ENRICH_RATE_LIMIT = 0.2      # 5s entre requests
ENRICH_BATCH_SIZE = 50

# APIs externas
BRASILAPI_BASE = "https://brasilapi.com.br/api"
IBGE_API_BASE = "https://servicodados.ibge.gov.br/api/v1"
CAMARA_API_BASE = "https://dadosabertos.camara.leg.br/api/v2"

# PostgreSQL (via env vars)
PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASS
```

---

## Pitfalls

1. Chave do response é `listaPlanosAcao`, não `data`/`content`/`items`
2. `planoTrabalhoSituacao` pode ser `None`
3. `total` no response indica o total real — sempre comparar com acumulado
4. Arrow backend do pandas: usar `.fillna("").astype(str).str.len()` não `.map(len)`
5. Valores monetários vêm como float — usar `pd.to_numeric` antes de exportar
6. IP pode ser bloqueado fora do Brasil — TCP timeout = rede gov.br restrita
7. `--db` é idempotente (upsert) — seguro rodar múltiplas vezes
8. Scripts especializados (`extract_cemiterios_*`) são **DEPRECATED**
9. Cache TTL em `output/.http_cache/` — limpar com `cache_clear()`
10. Config centralizada: **NUNCA** hardcodar URLs/paths nos scripts
11. `IMPEDIDO` = Restrição Técnica, `IMPEDIDO_REJEICAO_PLANO_TRABALHO` = Rejeição
12. Parse de emenda é automático no import (`emenda_codigo` + `parlamentar_nome`)

---

## Referência

- `references/mcp-brasil/` — MCP server gov.br (533 tools, 70 features)
  - Patterns: Pydantic schemas, retry, TTL cache, `format_brl()`
  - Feature `transferegov` usa API PostgREST antiga (diferente da nossa)
  - Worth studying: `_shared/http_client.py`, `schemas.py`, `formatting.py`
- `MCP_BRASIL_INTEGRATION_PLAN.md` — Plano detalhado de integração mcp-brasil
- `data/schema.sql` + `data/migration_002_relatorios.sql` — Schema completo do banco
