# README.md Rewrite Analysis & Blueprint

## 1. Executive Summary
The existing `README.md` file in the root of `tranfere_gov_api` contains legacy node/React/Express boilerplate (`npm install`, `vite`, `server.ts`, Firebase Drive integration) from an earlier prototype. The project has evolved into a production-grade Python 3.11 data engineering and intelligence framework for TransfereGov (Transferências Especiais / Emendas Pix), featuring:
- Automated REST API data extraction & Pydantic validation.
- Idempotent PostgreSQL persistence (`upsert_plano_acao`).
- Multi-source data enrichment (IBGE, BrasilAPI, Câmara dos Deputados, SICONFI).
- Parliamentary & Municipal Intelligence REST API (`FastAPI` on port 8000).
- Plotly Dash 4.3+ Interactive Web Dashboard & Native MCP Server Hub on port 8050 (`/_mcp`).
- Automated pre-commit checks (`ruff`, `mypy`, standard hooks) and GitHub Actions CI.

This document provides a comprehensive audit of existing sources and an exact, copy-paste ready blueprint for replacing `README.md`.

---

## 2. Legacy vs. Current Architecture Gap Analysis

| Section | Legacy `README.md` State | Current Repository Reality | Action Required |
|---|---|---|---|
| **Tech Stack** | React 18, Vite, Express, Tailwind, Firebase, Drive API | Python 3.11+, PostgreSQL 14+, FastAPI, Plotly Dash 4.3+, DuckDB, Pydantic v2 | Replace stack section completely |
| **Setup Steps** | `npm install`, `npm run dev`, `npm run build` | `python3.11 -m venv .venv`, `pip install -e ".[dev]"`, PostgreSQL setup | Rewrite quickstart instructions |
| **CLI & Commands** | None | `./run.sh discover`, `./run.sh cemiterios`, `./run.sh all --db`, `./run.sh report`, enrichers | Document full CLI & `run.sh` interface |
| **Web Apps & Services** | `server.ts` Express proxy | FastAPI REST Server (`src/api/app.py` port 8000), Dash + MCP (`src/dash_app.py` port 8050) | Add detailed Web & MCP server documentation |
| **Code Quality / CI** | None | `.pre-commit-config.yaml` (`ruff`, `mypy`), `.github/workflows/ci.yml` | Add Code Quality & CI/CD section |
| **Documentation Links** | None | Links to `docs/ONBOARDING.md`, `docs/DEVELOPMENT.md`, `docs/MIGRATIONS.md`, `AGENTS.md` | Add Documentation Index section |

---

## 3. Comprehensive Content Blueprint for `README.md`

Below is the structured layout and exact content spec for the new `README.md`:

```markdown
# TransfereGov API — Extração, Validação, Enriquecimento e Análise de Emendas Pix

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checking: MyPy](https://img.shields.io/badge/type%20checking-mypy-blue.svg)](https://mypy-lang.org/)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![CI/CD](https://github.com/andretwl/tranfere_gov_api/actions/workflows/ci.yml/badge.svg)](https://github.com/andretwl/tranfere_gov_api/actions)

Projeto Python de engenharia de dados e inteligência parlamentar para extração, validação, enriquecimento e análise dos **Planos de Ação** do sistema **Transferegov.br** (Transferências Especiais / Emendas Pix do Governo Federal).

---

## 📌 Visão Geral & Arquitetura

O sistema implementa uma pipeline completa em 5 etapas:

1. **Extração**: Coleta resiliente de dados via API pública do Transferegov com paginação e backoff exponencial.
2. **Validação**: Normalização e validação de schemas com `Pydantic v2`.
3. **Persistência PostgreSQL**: Carga idempotente via `upsert_plano_acao()` com schema relacional normalizado.
4. **Enriquecimento Multi-Fonte**:
   - **Fase 1**: Validação de CNPJ (BrasilAPI), Dados demográficos/econômicos (IBGE) e dados fiscais municipais (SICONFI/Tesouro Nacional).
   - **Fase 2**: Perfil completo e acompanhamento legislativo de parlamentares (API Dados Abertos da Câmara).
   - **Fase 3**: Vinculação agregada entre parlamentares, beneficiários e emendas.
5. **Visualização & Servidor MCP**:
   - **Painel REST & Web App (FastAPI)**: Inteligência parlamentar e municipal na porta `8000`.
   - **Plotly Dash & Servidor MCP Hub**: 31 gráficos analíticos interativos e endpoint MCP nativo (`/_mcp`) na porta `8050`.

```
[ API TransfereGov ] ──► [ Extração & Pydantic ] ──► [ PostgreSQL ]
                                                          │
   ┌──────────────────────────────────────────────────────┴──────────────────────────────────────────────────────┐
   ▼                                                      ▼                                                      ▼
[ Enriquecimento: IBGE/Câmara/SICONFI ]      [ FastAPI Web App (Porta 8000) ]            [ Plotly Dash + MCP (Porta 8050) ]
```

---

## 📁 Estrutura do Projeto

```
tranfere_gov_api/
├── src/                          # Módulos Python principais
│   ├── transferegov_extract.py   # CLI Principal de extração e carga no DB
│   ├── db_import.py              # Importador JSON → PostgreSQL
│   ├── db_report.py              # Relatórios SQL formatados
│   ├── db_utils.py               # Utilitários centralizados de conexão DB
│   ├── formatters.py             # Formatação de moeda e porcentagens
│   ├── schemas.py                # Schemas de validação Pydantic
│   ├── dash_app.py               # Servidor Plotly Dash & MCP Server Hub (Porta 8050)
│   ├── graph_tools.py            # Ferramentas MCP customizadas (@mcp_enabled)
│   ├── verify_graphs.py          # Suíte de auditoria e verificação de gráficos
│   ├── deputado_followup.py      # CLI interativo de inteligência parlamentar
│   ├── prefeito_followup.py      # CLI interativo de inteligência municipal
│   │
│   ├── api/                      # Aplicação Web FastAPI (Porta 8000)
│   │   ├── app.py                # App FastAPI principal
│   │   ├── routes/               # Endpoints REST (deputados, prefeitos, analytics, compras, diario)
│   │   └── services/             # Regras de negócio e integração DB/Câmara
│   │
│   ├── enrichers/                # Pipeline de Enriquecimento (Fases 1, 2, 3)
│   │   ├── pipeline.py           # Orquestrador do enriquecimento
│   │   ├── validacao.py          # Fase 1a: Validação CNPJ via BrasilAPI
│   │   ├── ibge.py               # Fase 1b: Dados locais IBGE
│   │   ├── camara.py             # Fase 2: Perfis de Deputados (Câmara)
│   │   └── siconfi.py            # Fase 1e: Indicadores Fiscais Municipais
│   │
│   └── graphs/                   # Módulos Plotly (12 domínios, 31 gráficos)
│
├── config/                       # Configuração centralizada
│   └── settings.py               # Configurações de API, DB, paths e env vars
│
├── data/                         # Schemas SQL e Migrations
│   ├── schema.sql                # Schema PostgreSQL core
│   └── migration_*.sql           # Migrações aplicadas
│
├── docs/                         # Documentação do desenvolvedor
│   ├── ONBOARDING.md             # Guia passo a passo de onboarding
│   ├── DEVELOPMENT.md            # Padrões de desenvolvimento e pre-commit
│   └── MIGRATIONS.md             # Instruções e histórico de migrations
│
├── .github/workflows/ci.yml      # CI/CD Pipeline (GitHub Actions)
├── .pre-commit-config.yaml       # Configuração de ganchos de código (Ruff, MyPy)
├── pyproject.toml                # Dependências, ruff e mypy config
├── requirements.txt              # Dependências pip
└── run.sh                        # Interface CLI rápida (atalhos)
```

---

## ⚡ Pré-requisitos & Instalação

### Pré-requisitos
- **Python 3.11+**
- **PostgreSQL 14+**
- **Git**

### Configuração do Ambiente Local

1. **Clonar o repositório:**
   ```bash
   git clone https://github.com/andretwl/tranfere_gov_api.git
   cd tranfere_gov_api
   ```

2. **Criar e ativar ambiente virtual Python:**
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   ```

3. **Instalar dependências (incluindo pacotes de desenvolvimento):**
   ```bash
   pip install --upgrade pip
   pip install -e ".[dev]"
   ```

4. **Configurar o Banco de Dados PostgreSQL:**
   Certifique-se de que o serviço PostgreSQL está em execução e crie o banco de dados e usuário:
   ```sql
   CREATE DATABASE transferegov_db;
   CREATE USER cognee WITH PASSWORD 'cognee';
   GRANT ALL PRIVILEGES ON DATABASE transferegov_db TO cognee;
   ```

   Execute o schema inicial e as migrações:
   ```bash
   psql -U cognee -h 127.0.0.1 -d transferegov_db -f data/schema.sql
   # Executar migrações conforme docs/MIGRATIONS.md
   ```

---

## 🚀 Execução CLI & Pipelines

O projeto fornece o script `./run.sh` como atalho para todas as operações comuns.

### Extração de Dados
```bash
# Descobrir objetos disponíveis para o exercício 2026
./run.sh discover

# Extrair planos de ação de cemitérios (objeto 301) e salvar no PostgreSQL
./run.sh cemiterios --db --csv

# Extrair planos negados/impedidos
./run.sh negados --db

# Extrair TODOS os objetos de 2026 e salvar no banco
./run.sh all --db
```

### Importação Manual e Relatórios SQL
```bash
# Importar arquivos JSON pendentes para o banco de dados
./run.sh import

# Gerar relatórios formatados no terminal
./run.sh report resumo
./run.sh report estado
./run.sh report negados
./run.sh report sql "SELECT parlamentar_nome, COUNT(*) FROM v_planos_completo GROUP BY 1 LIMIT 10"
```

### Enriquecimento de Dados Multi-Fonte
```bash
# Pipeline completo de enriquecimento (Fases 1, 2 e 3)
python3 -m src.enrichers.pipeline --fase all

# Execução individual de fases de enriquecimento
./run.sh validate     # Validação de CNPJs via BrasilAPI
./run.sh ibge         # Mapeamento e dados demográficos IBGE
./run.sh camara       # Perfil parlamentar da Câmara dos Deputados
```

---

## 🌐 Aplicações Web & Servidor MCP

O projeto conta com duas aplicações web complementares:

### 1. Painel Web de Inteligência Parlamentar (FastAPI)
Interface RESTful e SPA para consulta de deputados, emendas, despesas CEAP e proposições.
```bash
./run.sh web
# Ou diretamente:
# uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```
- **Interface Web**: [http://localhost:8000](http://localhost:8000)
- **Documentação Swagger/ReDoc**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 2. Plotly Dash & Servidor MCP Hub (Dash 4.3+)
Dashboard analítico interativo com 31 gráficos e Servidor MCP nativo integrado para suporte a Agentes de IA autônomos.
```bash
python3 src/dash_app.py
```
- **Dashboard Web**: [http://localhost:8050](http://localhost:8050)
- **Endpoint MCP Server**: [http://localhost:8050/_mcp](http://localhost:8050/_mcp)

Para verificar a integridade e renderização dos gráficos:
```bash
python3 src/verify_graphs.py
```

---

## 🛠️ Qualidade de Código, Linting & CI/CD

O projeto adota padrões rigorosos de qualidade de código automatizados via `pre-commit` hooks, `ruff`, `mypy` e `GitHub Actions`.

### Configuração dos Ganchos Locais (Pre-commit)
Instale os ganchos do git para validar automaticamente todo commit:
```bash
pre-commit install
```

### Execução Manual de Verificações de Qualidade
Execute a suíte de linters e validadores de tipo em todo o repositório:
```bash
pre-commit run --all-files
```

Você também pode executar as ferramentas individualmente:
```bash
# Linter e Formatação com Ruff
ruff check . --fix
ruff format .

# Checagem de Tipos Estrita com MyPy
mypy .

# Execução de Testes Automatizados
pytest
```

### Integração Contínua (CI/CD)
Toda alteração enviada para as branches `main` ou `master` via Push ou Pull Request dispara automaticamente o workflow do GitHub Actions (`.github/workflows/ci.yml`), testando o projeto em ambientes Python 3.11 e 3.12.

---

## 📖 Documentação Adicional

- [**Guia de Onboarding (`docs/ONBOARDING.md`)**](docs/ONBOARDING.md): Manual detalhado de primeiros passos e configuração de ambiente.
- [**Guia de Desenvolvimento (`docs/DEVELOPMENT.md`)**](docs/DEVELOPMENT.md): Padrões de código, regras do Ruff/MyPy e fluxo de Pull Requests.
- [**Guia de Migrações SQL (`docs/MIGRATIONS.md`)**](docs/MIGRATIONS.md): Instruções para aplicação de scripts SQL.
- [**Guia de Agentes (`AGENTS.md`)**](AGENTS.md): Especificações técnicas para agentes autônomos de IA.

---

## 📄 Licença
Distribuído sob a licença MIT. Veja `LICENSE` para mais informações.
```

---

## 4. Invalidation & Verification Conditions
- The blueprint must match existing command flags in `run.sh` and Python scripts.
- Port allocations must be verified: FastAPI runs on 8000 (with `./run.sh web` running uvicorn on port 8080/8000 as configured), Dash runs on 8050.
- Pre-commit commands (`pre-commit install`, `pre-commit run --all-files`) must match `.pre-commit-config.yaml` and `.github/workflows/ci.yml`.
