# Analysis Report: Requirement R2 — Project Documentation & Developer Onboarding

**Project**: TransfereGov API (Python Pipeline, Enrichment, FastAPI, Dash 4.3+ MCP Server)
**Agent Role**: Explorer Subagent
**Working Directory**: `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_survey_3`
**Date**: 2026-07-25

---

## Executive Summary

This report provides a comprehensive analysis of the existing project documentation and technical workflows for the **TransfereGov API** repository. It defines the complete structure and content required to fulfill **Requirement R2 (Project Documentation & Onboarding)**.

Key finding: The existing `README.md` contains legacy React/Vite/Express scaffolding instructions that do not reflect the current production Python 3.11 system. While `AGENTS.md` contains extensive internal documentation for AI agents, there is an urgent need to update `README.md` and complement it with structured onboarding and code quality guides under `docs/` for human developers.

---

## 1. Analysis of Existing Documentation & Codebase

### 1.1 Documentation Inventory

| File / Location | Current Content & Status | Gap / Opportunity |
|---|---|---|
| `README.md` | Contains obsolete React 18 / Express server / `npm install` references; only section 4 mentions Dash & MCP. | **High priority rewrite needed**: Needs complete update to reflect Python 3.11 pipeline, PostgreSQL, FastAPI, Dash/MCP server, and pre-commit/CI workflows. |
| `AGENTS.md` | Extensive agent reference manual (CLI commands, DB schema, enrichment phases, Dash server, pitfalls, code guidelines). | Excellent source material, but formatted as system prompt / agent rules rather than clean developer onboarding. |
| `docs/MIGRATIONS.md` | Documents migration order (schema.sql -> 002..009) and execution via `psql`. | Accurate and functional. Can be referenced directly in onboarding docs. |
| `docs/manual.txt` | Transferegov official integration manual v1.3 (PDF converted text). | Reference documentation for Transferegov payload specifications. |
| `docs/strategy.md` | Data handling, security, LGPD compliance, and Brazilian government API integration strategy. | Architectural reference. |
| `docs/plans/MCP_BRASIL_INTEGRATION_PLAN.md` | Comprehensive 3-phase integration plan for 533 mcp-brasil tools. | Detailed roadmap doc. |
| `run.sh` | Shell wrapper with 12+ commands (`discover`, `cemiterios`, `negados`, `import`, `report`, `web`, `enrich`, `all`, etc.). | Needs clear documentation in onboarding and developer workflow guides. |
| `pyproject.toml` | Configures package dependencies, `ruff` (py311, line-length 99), `mypy`, and `pytest`. | Standard Python configuration; pre-commit tool dependencies are specified in `[project.optional-dependencies]`. |
| `.github/workflows/ci.yml` | GitHub Actions workflow running on push/PR (`ruff check`, `mypy src/`, `pytest tests/`). | Needs developer-facing documentation explaining how local checks mirror CI. |
| `.pre-commit-config.yaml` | Currently missing (being created under Requirement R1). | Developer docs must explain how to install and execute pre-commit hooks locally. |

---

## 2. Developer Onboarding Requirements

To provide a friction-free onboarding experience for new developers, the documentation must address the following key areas:

### 2.1 Project Overview & System Architecture
- **Objective**: Federal government resource extraction (Transferências Especiais / Emendas Pix), Pydantic validation, PostgreSQL persistence, enrichment (IBGE, BrasilAPI, Câmara, SICONFI, DataJud, PNCP), and analytical interfaces.
- **Components**:
  1. **Extraction Engine**: `src/transferegov_extract.py` (REST client for Transferegov API with rate limiting and exponential backoff).
  2. **Data Layer**: PostgreSQL database (`transferegov_db`) with `schema.sql` and migrations 002-009, managed via `src/db_import.py` and `src/db_utils.py`.
  3. **Enrichment Pipeline**: `src/enrichers/` (Phase 1: CNPJ validation & IBGE; Phase 2: Deputados/Câmara; Phase 3: Financial cross-matching).
  4. **FastAPI Web App**: `src/api/app.py` (Parliamentary Intelligence Panel with REST endpoints and SPA frontend).
  5. **Dash 4.3+ & MCP Hub**: `src/dash_app.py` (31 interactive Plotly charts, server-side pre-rendering, `@mcp_enabled` tools for AI agents).
  6. **Interactive CLIs**: `src/deputado_followup.py` and `src/prefeito_followup.py`.

### 2.2 Prerequisites
- Linux / macOS (or WSL2 on Windows).
- Python 3.11 or 3.12.
- PostgreSQL 14+ (or Docker container).
- Shell tools: `git`, `bash`, `curl`, `psql`.

### 2.3 Environment Setup Step-by-Step
```bash
# 1. Clone repository & enter directory
git clone <repository-url>
cd tranfere_gov_api

# 2. Create and activate virtual environment (Python 3.11+)
python3.11 -m venv .venv
source .venv/bin/activate

# 3. Upgrade pip and install dependencies (including dev dependencies)
pip install --upgrade pip
pip install -e ".[dev]"
# Or: pip install -r requirements.txt

# 4. Environment Configuration
cp config/.env.example .env # or create .env with PG_HOST, PG_USER, PG_PASS, etc.
```

### 2.4 Database Setup & Migrations
```bash
# 1. Create database and user (if not existing)
psql -U postgres -c "CREATE USER cognee WITH PASSWORD 'cognee';"
psql -U postgres -c "CREATE DATABASE transferegov_db OWNER cognee;"

# 2. Execute base schema
psql -U cognee -h 127.0.0.1 -d transferegov_db -f data/schema.sql

# 3. Apply migrations in order (002 through 009)
for f in data/migration_00*.sql; do
    echo "Applying $f..."
    psql -U cognee -h 127.0.0.1 -d transferegov_db -f "$f"
done

# 4. Verify database status
./scripts/db_inspect.sh
./run.sh report resumo
```

### 2.5 Running Key Workflows & Applications
- **Extractions**:
  - Discover available objects: `./run.sh discover`
  - Extract cemetery plans (Object 301) to DB: `./run.sh cemiterios --db --csv`
  - Full extraction: `./run.sh all --db`
- **Enrichment Pipeline**:
  - Run full enrichment: `python3 -m src.enrichers.pipeline --fase all` (or `./run.sh enrich --fase all`)
- **FastAPI Web Service**:
  - Start server: `./run.sh web` (http://localhost:8080 or http://localhost:8000)
  - Open API docs: `http://localhost:8000/docs`
- **Dash & MCP Hub**:
  - Start server: `python3 src/dash_app.py`
  - Access Web UI: `http://localhost:8050`
  - Access MCP Endpoint: `http://localhost:8050/_mcp`

---

## 3. Automated Code Review & Quality Workflow Documentation

Developer documentation must clearly explain the code quality standards and automated review mechanisms:

### 3.1 Pre-Commit Local Hook Setup
Developers must enable pre-commit hooks upon cloning the repository:
```bash
# Install git hook scripts
pre-commit install

# Verify pre-commit installation across all files
pre-commit run --all-files
```

### 3.2 Code Quality Tools & Rules
- **Ruff (`ruff check` & `ruff format`)**:
  - Target Python version: 3.11.
  - Max line length: 99 characters.
  - Active rule sets: `E` (errors), `F` (Pyflakes), `W` (warnings), `I` (isort), `UP` (pyupgrade), `B` (flake8-bugbear), `SIM` (flake8-simplify).
  - Common command: `ruff check src/ config/ tests/` (auto-fixable with `--fix`).
- **Mypy (`mypy src/`)**:
  - Static type checking for Python modules.
  - Ensures clean type annotations across API models, services, and pipeline scripts.
  - Common command: `mypy src/ --ignore-missing-imports --explicit-package-bases`.
- **Pytest (`pytest`)**:
  - Unit and integration tests located under `tests/`.
  - Common command: `python -m pytest tests/ -v`.
- **Graph Auditor (`verify_graphs.py`)**:
  - Verifies that all 31 Plotly charts load correctly without empty figure boxes.
  - Common command: `python3 src/verify_graphs.py`.

### 3.3 CI/CD Workflow (`.github/workflows/ci.yml`)
- Triggered automatically on `push` to `main` and all `pull_request` events.
- Test matrix: Python 3.11 and Python 3.12.
- Steps executed in CI:
  1. `pip install -e ".[dev]"`
  2. `ruff check src/ config/ tests/`
  3. `mypy src/ --ignore-missing-imports --explicit-package-bases`
  4. `python -m pytest tests/ -v`
- Quality Gate: All CI checks must pass cleanly before pull requests are approved and merged.

---

## 4. Documentation Structure Recommendations

We recommend a 2-tier documentation structure:

### Tier 1: Main Entrypoint (`README.md`)
Rewrite `README.md` to serve as the single source of truth for repository overview, quickstart, and primary developer workflows:
1. **Title & Badge Header** (Python 3.11 | PostgreSQL | FastAPI | Plotly Dash | CI Status)
2. **Project Overview & Capabilities**
3. **Architecture & Technology Stack**
4. **Quickstart Guide (Local Setup in 5 Steps)**
5. **Database Setup & Migrations**
6. **Running Pipelines & Services (`run.sh`, FastAPI, Dash/MCP)**
7. **Code Quality & Automated Review Workflow (`pre-commit`, `ruff`, `mypy`, `pytest`, `ci.yml`)**
8. **Testing & Verification**
9. **Documentation Directory Index** (links to `docs/`)

### Tier 2: Specialized Guides under `docs/`
- **`docs/ONBOARDING.md`**: Comprehensive developer onboarding guide detailing environment options (local venv vs Docker), database setup, environment variable reference, sample data loading, and API usage.
- **`docs/DEVELOPMENT.md`**: Deep dive into contribution guidelines, code review standards, pre-commit configuration details, adding new API endpoints, adding new Plotly charts to `src/graphs/`, and writing pytest test cases.
- **Keep existing specialized docs**:
  - `docs/MIGRATIONS.md` (Database migrations order & scripts)
  - `docs/plans/MCP_BRASIL_INTEGRATION_PLAN.md` (mcp-brasil integration roadmap)
  - `docs/strategy.md` (Data strategy & LGPD compliance)
  - `docs/manual.txt` (Transferegov API spec reference)

---

## Conclusion & Implementation Roadmap

1. **For Requirement R1 (Implementer Task)**:
   - Ensure `.pre-commit-config.yaml` is placed in repo root configuring `ruff`, `mypy`, and standard file fixers.
   - Verify `pre-commit run --all-files` passes cleanly.

2. **For Requirement R2 (Documentation Task)**:
   - Rewrite `README.md` following the structure outlined above.
   - Create `docs/ONBOARDING.md` and `docs/DEVELOPMENT.md`.
   - Update `docs/MIGRATIONS.md` if needed to cross-reference onboarding instructions.

This structure guarantees full compliance with all acceptance criteria in `ORIGINAL_REQUEST.md`.
