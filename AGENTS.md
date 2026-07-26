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
# REDATOR OFICIAL (src/redator_transferegov.py)
# ============================================================
./run.sh redator nota-tecnica --parlamentar "AFONSO FLORENCE" --ano 2026
./run.sh redator oficio --dest "Governador" --cargo "Governador do Estado" --assunto "Relatório" --corpo "..."
./run.sh redator parecer --processo "001/2026" --consulta "Análise de emendas impedidas"
./run.sh redator despacho --assunto "Encaminhamento" --texto "Encaminho..."
./run.sh redator validar --arquivo "docs/nota.txt" --tipo nota_tecnica
./run.sh redator listar-tipos                     # listar tipos de documento suportados
./run.sh redator --data                           # data por extenso (Brasília, 25 de julho de 2026.)
./run.sh redator --pronomes "governador"          # pronome de tratamento
./run.sh redator --numeracao oficio 142 SAA/SE/MT # numeração oficial

# ============================================================
# BANCO
# ============================================================
psql -U cognee -h 127.0.0.1 -d transferegov_db

# ============================================================
# DASHBOARD INTERATIVO & SERVIDOR MCP (Dash 4.3+)
# ============================================================
python3 src/dash_app.py                    # Servidor Web (http://localhost:8050) & MCP (http://localhost:8050/_mcp)
python3 src/verify_graphs.py              # Suíte de verificação/auditoria automática dos 31 gráficos
```

---

## Estrutura do Projeto

```
tranfere_gov_api/
├── src/                          Scripts Python ativos
│   ├── transferegov_extract.py     ← CLI PRINCIPAL (extração + DB)
│   ├── db_utils.py                ← NOVO: get_connection(), query_df() centralizados
│   ├── formatters.py              ← NOVO: fmt_brl(), fmt_num(), fmt_pct() centralizados
│   ├── db_import.py                Importação JSON → PostgreSQL
│   ├── db_report.py                Relatórios SQL formatados
│   ├── schemas.py                  Pydantic schemas (PlanoAcaoSchema)
│   ├── http_cache.py               Cache TTL para requests HTTP
│   ├── dash_app.py                 ← Servidor Web Plotly Dash + MCP Hub (http://localhost:8050)
│   ├── graphs/                     ← Pacote de gráficos Plotly (12 módulos, 31 gráficos)
│   │   ├── __init__.py               Re-exports CHART_REGISTRY, aplicar_tema, etc.
│   │   ├── registry.py               CHART_REGISTRY dict + @register_chart decorator + dataclasses
│   │   ├── theme.py                  Theme tokens (THEME_CARD_BG, CORES_SITUACAO, TODAS_UFS)
│   │   ├── parlamentar.py            Charts: eficiencia_partidos, top_parlamentares_valores, impedimentos_por_partido
│   │   ├── socioeconomico.py         Charts: socioeconomico_idhm, investimento_per_capita_idhm, vulnerabilidade_social
│   │   ├── fiscal.py                 Charts: custeio_vs_investimento, taxa_impedimento_objeto, emendas_vs_compras
│   │   ├── siconfi.py                Charts: 10 gráficos SICONFI (dependência, resultado, autonomia, etc.)
│   │   ├── geoespacial.py            Charts: choropleth_emendas, choropleth_valor_total_uf, choropleth_taxa_impedimento_uf
│   │   ├── impacto_social.py         Charts: impacto_saude, ideb_vs_emendas
│   │   ├── analitico.py              Charts: tendencia_temporal, eleicao_emendas
│   │   ├── hierarquico.py            Charts: sunburst_drilldown_recursos, treemap_investimentos_objetos, sankey_fluxo_financeiro
│   │   └── prefeitos.py              Charts: ranking_prefeituras_emendas_per_capita, prefeitos_emendas_por_partido
│   ├── graph_factory.py            ← Shim backward-compat (26 linhas) → importa de src.graphs
│   ├── graph_tools.py              ← Ferramentas MCP customizadas (@mcp_enabled) para agentes
│   ├── verify_graphs.py            ← Suíte de auditoria e verificação automatizada dos 31 gráficos
│   ├── dashboard.py                Dashboard geral (Plotly HTML) — DEPRECATED, usar dash_app.py
│   ├── dashboard_deputados.py      Dashboard parlamentar — DEPRECATED, usar dash_app.py
│   ├── dashboard_cross_analysis.py Análise cruzada — DEPRECATED, usar dash_app.py
│   ├── dashboard_cross_fiscal.py   Análise fiscal — DEPRECATED, usar dash_app.py
│   ├── graph_generator.py          Gerador modular de gráficos — DEPRECATED, usar src/graphs/
│   ├── deputado_followup.py        CLI interativo de followup por deputado
│   ├── redator_transferegov.py     ← Redator oficial de documentos (nota-técnica, ofício, parecer, despacho)
│   │
│   ├── api/                        ← FastAPI Web App (ver src/api/AGENTS.md)
│   │   ├── app.py                  App FastAPI principal
│   │   ├── routes/                 Rotas REST (deputados, analytics, auditoria, compras, diario)
│   │   ├── services/               Serviços (db_service, camara_service, mcp_service, analytics_service)
│   │   └── static/                 Frontend (index.html, app.js, style.css)
│   │
│   └── enrichers/                  ← Pipeline de enriquecimento (ver src/enrichers/AGENTS.md)
│       ├── __init__.py
│       ├── pipeline.py             Orquestrador (fases 1-3)
│       ├── validacao.py            Fase 1a: Validação CNPJ (BrasilAPI)
│       ├── ibge.py                 Fase 1b: Dados IBGE (municípios)
│       ├── ibge_agregados.py       Fase 1d: Dados IBGE agregados (pop, PIB, área)
│       ├── siconfi.py              Fase 1e: Dados financeiros (SICONFI/Tesouro)
│       ├── camara.py               Fase 2: Perfil parlamentares (Câmara)
│       ├── mapear_municipios.py    Mapeamento fuzzy beneficiário → IBGE
│       ├── compras.py              Licitações/contratos (PNCP/Compras.gov.br)
│       ├── saude_educacao.py       Saúde e educação (CNES/DataSUS + INEP/IDEB)
│       ├── datajud.py              Processos judiciais (DataJud/CNJ)
│       ├── completar_deputados.py  Completar dados de deputados incompletos
│       └── discricionarias_sync.py Sync emendas discricionárias (Portal Transparência)
│
├── config/                         Config centralizada
│   ├── settings.py                 ← API, DB, paths, ENRICH_*
│   └── .env.example
│
├── data/                           Dados de referência
│   ├── swagger.yaml                Spec OpenAPI 3.0 (engenharia reversa)
│   ├── schema.sql                  Schema PostgreSQL completo (core)
│   ├── brazil_states.json          Dados dos estados brasileiros
│   └── migration_002-009*.sql      Migrations (ver docs/MIGRATIONS.md)
│
├── scripts/                        CLI utilities e helpers
│   ├── db_inspect.sh               Inspeção rápida do banco
│   ├── run_siconfi_batch.sh        Batch SICONFI parallel (tmux)
│   └── cross_analysis_tse_transferegov.py  Análise cruzada TSE
│
├── docs/                           Documentação
│   ├── MIGRATIONS.md               ← Ordem correta de execução das migrations
│   ├── manual.txt                  Manual detalhado
│   └── plans/                      Planos e roadmap
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

## Web App (FastAPI)

Aplicação web em `src/api/` — Painel de Inteligência Parlamentar.

```bash
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

- **Rotas**: `src/api/routes/deputados.py` — `/api/v1/deputados/*`
- **Serviços**: `src/api/services/` — `db_service.py` (PostgreSQL), `camara_service.py` (API Câmara)
- **Frontend**: `src/api/static/` — SPA vanilla (index.html + app.js + style.css)
- **Docs**: Swagger em `/docs`, ReDoc em `/redoc`
- **CORS**: Permissivo para dev local (`allow_origins=["*"]`)

**Endpoints**:
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/deputados/search?q=` | Busca por nome (DB + API Câmara) |
| GET | `/{id}/perfil` | Perfil do deputado |
| GET | `/{id}/emendas` | Emendas do deputado |
| GET | `/{id}/emendas/resumo` | Resumo agregado de emendas |
| GET | `/{id}/despesas?ano=` | Despesas CEAP (API Câmara) |
| GET | `/{id}/comissoes` | Comissões que participa |
| GET | `/{id}/votacoes` | Últimas votações |
| GET | `/{id}/proposicoes` | Proposições legislativas |

**Padrão de fallback**: Busca local primeiro → se <5 resultados, enriquece com API Câmara → degrade graceful se API externa falhar.

Para detalhes completos, ver `src/api/AGENTS.md`.

---

## Dashboards, Servidor MCP e Gestão de Gráficos (Plotly + Dash 4.3+)

O projeto possui um hub interativo completo em `src/dash_app.py` integrando a biblioteca **Dash 4.3+ com Servidor MCP nativo**.

- **URL Web UI**: `http://localhost:8050`
- **Endpoint MCP Server**: `http://localhost:8050/_mcp`

### Módulos Principais

| Módulo | Descrição | Uso |
|--------|-----------|-----|
| `dash_app.py` | Aplicação Web Dash interativa + Servidor MCP com pré-renderização server-side resiliente | `python3 src/dash_app.py` |
| `src/graphs/` | Pacote de gráficos: `registry.py` (CHART_REGISTRY + decorator), `theme.py` (tokens), 9 módulos de domínio com 31 gráficos | `from src.graphs import CHART_REGISTRY` |
| `graph_factory.py` | Shim backward-compat (26 linhas) que re-exporta de `src.graphs` | `from src.graph_factory import CHART_REGISTRY` |
| `graph_tools.py` | Custom MCP Tools decoradas com `@mcp_enabled` para controle autônomo por Agentes | `from src.graph_tools import *` |
| `verify_graphs.py` | Suíte de auditoria e verificação automatizada dos 31 gráficos | `python3 src/verify_graphs.py` |

### Resiliência & Prevenção de Gráficos em Branco

1. **Pré-renderização Server-Side**: O layout `dcc.Graph(id=..., figure=initial_figure)` inicializa todos os gráficos 100% preenchidos no HTML server-side, garantindo carregamento instantâneo sem depender unicamente de callbacks JS do cliente.
2. **Wrapper Anti-Falha (`safe_build_chart`)**: Caso um filtro retorne 0 resultados ou ocorra erro de sincronização, o gráfico exibe um card Dark Slate informativo em vez de uma caixa branca vazia.

### Ferramentas MCP Customizadas (@mcp_enabled em `src/graph_tools.py`)

- **`list_registered_charts()`**: Retorna lista com todos os gráficos, categorias e opções de filtro.
- **`inspect_chart_health(chart_id)`**: Audita e retorna a integridade e número de pontos de dados dos gráficos.
- **`get_chart_data_summary(chart_id, **kwargs)`**: Retorna resumo estatístico em JSON dos dados do gráfico.
- **`register_custom_graph(id, title, description, category, sql_query, chart_type)`**: Permite que Agentes de IA **criem e registrem novos gráficos SQL dinamicamente no dashboard em tempo real!**

---

## Followup por Deputado & Prefeito (CLIs)

```bash
# Followup de Deputados
python3 src/deputado_followup.py AFONSO FLORENCE     # busca por nome
python3 src/deputado_followup.py --buscar "ULYSSES"   # busca fuzzy
python3 src/deputado_followup.py --emenda 202642740010 # por código emenda
python3 src/deputado_followup.py --ranking              # ranking de deputados
python3 src/deputado_followup.py --partido PT           # por partido

# Followup de Prefeitos & Inteligência Municipal
python3 src/prefeito_followup.py "Amapá"             # busca por município/prefeito
python3 src/prefeito_followup.py --buscar "DAYMO"    # busca por nome do prefeito
python3 src/prefeito_followup.py --ranking           # ranking top prefeituras por emendas
```


CLI interativo que consulta o PostgreSQL e mostra: perfil do deputado, trail de emendas, municípios beneficiários, comparação com outros deputados do mesmo partido/UF.

---

## Redator Oficial de Documentos (src/redator_transferegov.py)

CLI standalone que gera documentos oficiais seguindo o Manual de Redação da Presidência da República, 3ª edição (2018).

```bash
# Nota técnica com dados reais do PostgreSQL
./run.sh redator nota-tecnica --parlamentar "AFONSO FLORENCE" --ano 2026
./run.sh redator nota-tecnica --ano 2026 --output docs/nota_impedidos.txt

# Ofício
./run.sh redator oficio --dest "Governador" --cargo "Governador do Estado" \
  --assunto "Relatório de Emendas" --corpo "Segue em anexo..." --numero 142

# Parecer técnico/jurídico
./run.sh redator parecer --processo "001/2026" --consulta "Análise de emendas impedidas"

# Despacho administrativo
./run.sh redator despacho --assunto "Encaminhamento" --texto "Encaminho..."

# Validação de documento existente
./run.sh redator validar --arquivo "docs/nota.txt" --tipo nota_tecnica

# Utilitários rápidos
./run.sh redator --data                           # data por extenso (Brasília, 25 de julho de 2026.)
./run.sh redator --pronomes "governador"          # pronome de tratamento correto
./run.sh redator --numeracao oficio 142 SAA/SE/MT # numeração oficial
./run.sh redator listar-tipos                     # tipos de documento suportados
```

### Regras Implementadas (Manual 3ª edição)
- **Data por extenso**: `"Brasília, 25 de julho de 2026."` — ordinal para 1º, cardinal para o resto
- **Pronomes de tratamento**: 27 entradas em 4 tiers — Excelentíssimo (3 chefes de estado), Vossa Excelência (ministros, senadores, governadores), Vossa Senhoria (diretores, coordenadores), Vossa Magnificência (reitores)
- **Numeração**: `"OFÍCIO Nº 142/2026/SAA/SE/MT"` — siglas da menor para maior hierarquia
- **Fechos**: APENAS "Respeitosamente," (superior) ou "Atenciosamente," (igual) — DD e Ilmo./Ilustríssimo foram ABOLIDOS
- **Legado**: memorando/aviso → automaticamente convertido para OFÍCIO

### Validação
O comando `validar` verifica:
- Uso de datas numéricas (DD/MM/AAAA) em vez de extenso
- Presença de pronomes abolidos (Digníssimo, Ilmo., Ilustríssimo, DD)
- Gerúndio excessivo (>3 ocorrências)
- Uso de memorando/aviso (abolidos)

### Tipos de Documento Suportados
| Tipo | Prefixo | Uso |
|------|---------|-----|
| `oficio` | OFÍCIO | Comunicação entre órgãos |
| `nota_tecnica` | NOTA TÉCNICA | Análise técnica com dados |
| `parecer` | Parecer | Opinião técnica/jurídica |
| `despacho` | Despacho | Decisão administrativa |
| `portaria` | PORTARIA | Norma interna |
| `ata` | ATA | Registro de reunião |

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
11. Módulos compartilhados: `src/db_utils.py` (get_connection/query_df) e `src/formatters.py` (fmt_brl/fmt_num/fmt_pct) — NÃO redefinir localmente
11. `IMPEDIDO` = Restrição Técnica, `IMPEDIDO_REJEICAO_PLANO_TRABALHO` = Rejeição
12. Parse de emenda é automático no import (`emenda_codigo` + `parlamentar_nome`)
13. **Dash Server-Side Initial Rendering**: Todo `dcc.Graph` deve ser instanciado com `figure=safe_build_chart(...)` no layout inicial para pré-carregamento server-side instantâneo, prevenindo caixas brancas sem dados.
14. **Wrapper Anti-Falha (`safe_build_chart`)**: Toda geração de gráfico deve ser envelopada em `try/except` com verificação de `has_data`. Em caso de erro/sem dados, retornar figura estilizada com aviso amigável no tema Dark Slate (`#1e293b`).
15. **Custom MCP Tools (`@mcp_enabled`)**: Usar `from dash.mcp import mcp_enabled` com `@mcp_enabled(name="...", expose_docstring=True)` para expor ferramentas de inspeção, auditoria e criação de gráficos para Agentes de IA.
16. **Verificação Integrada por Tipo de Gráfico**: Ao validar pontos de dados em suítes de teste:
    - Gráficos padrão (Bar, Scatter, Pie): checar `trace.x`, `trace.y`, `trace.values`.
    - Mapas Coropléticos (`px.choropleth`): checar `trace.z` ou `trace.locations`.
    - Diagramas de Fluxo (`go.Sankey`): checar `trace.link.value`.
17. **Adicionar novos gráficos**: Crie um módulo em `src/graphs/` com o decorator `@register_chart` — ele será importado automaticamente via `src/graphs/__init__.py`. O shim `graph_factory.py` re-exporta tudo para backward compat.
18. **Decomposição de `main()`**: `transferegov_extract.py` foi decomposto em funções auxiliares (`parse_args`, `setup_logging`, `run_discover`, `run_extraction`). Novas flags CLI vão para `parse_args()`.
19. **Connection Pooling**: `db_utils.py` usa `psycopg2.pool.ThreadedConnectionPool` (min=2, max=10). `__exit__` patched com `_released` flag para prevenir double-return ao pool.


---

## Referência

- `references/mcp-brasil/` — MCP server gov.br (533 tools, 70 features)
  - Patterns: Pydantic schemas, retry, TTL cache
  - Feature `transferegov` usa API PostgREST antiga (diferente da nossa)
- `docs/MIGRATIONS.md` — Ordem de execução das migrations (002-009)
- `docs/plans/` — Planos antigos de integração mcp-brasil
- `data/schema.sql` — Schema completo do banco (core)
