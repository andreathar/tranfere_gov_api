# Handoff Report — Project Documentation & Onboarding Survey (Requirement R2)

**Agent**: Explorer Subagent
**Working Directory**: `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_survey_3`
**Date**: 2026-07-25

---

## 1. Observation

1. **Original Request**: `ORIGINAL_REQUEST.md` (lines 13-29) defines Requirement R1 (Code Quality Hooks & CI/CD) and Requirement R2 (Project Documentation & Onboarding), with acceptance criteria requiring `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `pre-commit run --all-files` clean execution, and updated central documentation.
2. **Existing README**: `README.md` (lines 1-66) describes an obsolete Vite/React 18 frontend and Express server (`npm install`, `npm run dev`, `server.ts`, `App.tsx`) with only brief mentions of Plotly Dash / MCP server in section 4. It contains zero references to Python 3.11 extractions, PostgreSQL, FastAPI, Pydantic, enrichers, `run.sh`, pre-commit hooks, or CI workflows.
3. **Internal Documentation**: `AGENTS.md` (lines 1-250) provides extensive Python pipeline instructions, `run.sh` commands, PostgreSQL schema, enrichment pipeline phases, FastAPI endpoints, Dash 4.3+ MCP server details, and pitfalls.
4. **Docs Directory**: `docs/` contains `MIGRATIONS.md` (migration order 002-009), `manual.txt` (Transferegov spec v1.3), `strategy.md` (data strategy & LGPD), `plans/MCP_BRASIL_INTEGRATION_PLAN.md` (mcp-brasil integration), and `diagrams/schemas.mmd`.
5. **CLI Helper**: `run.sh` (lines 1-112) wraps CLI extractions, database imports, SQL reports, Dash server, FastAPI web app (`./run.sh web`), and enrichment phases (`./run.sh enrich`).
6. **Project Config & CI**: `pyproject.toml` configures `ruff` (py311, line length 99, rule selection `E,F,W,I,UP,B,SIM`) and `mypy`. `.github/workflows/ci.yml` (lines 1-37) runs matrix tests on Python 3.11/3.12 with `ruff check`, `mypy src/`, and `pytest tests/`. `.pre-commit-config.yaml` is currently absent from the root directory.

---

## 2. Logic Chain

1. **Premise**: `README.md` is currently out of sync with the codebase because it describes a legacy React/npm setup instead of the production Python 3.11 / PostgreSQL / FastAPI / Dash project.
2. **Observation reference**: Observations 2 and 3. `AGENTS.md` contains accurate details of the Python system, while `README.md` references Vite and Express.
3. **Premise**: Developer onboarding requires clear, step-by-step instructions for environment setup, database creation, migration execution, pipeline running, and running applications.
4. **Observation reference**: Observations 4 and 5. `docs/MIGRATIONS.md` and `run.sh` provide the technical steps, but they must be unified into user-facing developer documentation.
5. **Premise**: Automated code quality workflows (`pre-commit`, `ruff`, `mypy`, `pytest`, GitHub Actions CI) must be clearly documented so developers can run local checks before pushing PRs.
6. **Observation reference**: Observations 1 and 6. `ci.yml` runs `ruff check`, `mypy src/`, and `pytest`, while `pre-commit` local hooks must be documented alongside `.pre-commit-config.yaml`.
7. **Deduction**: A complete rewrite of `README.md` supported by dedicated guides (`docs/ONBOARDING.md` and `docs/DEVELOPMENT.md`) is necessary and sufficient to satisfy Requirement R2 and its acceptance criteria.

---

## 3. Caveats

- **Implementation Scope**: This survey is read-only. File changes to `README.md`, `docs/ONBOARDING.md`, `docs/DEVELOPMENT.md`, or `.pre-commit-config.yaml` will be executed by Implementer agents based on these recommendations.
- **Pre-commit Config Dependency**: `.pre-commit-config.yaml` creation is handled under Requirement R1. Documentation under R2 should accurately reference `.pre-commit-config.yaml` once created.

---

## 4. Conclusion

Requirement R2 should be implemented by:
1. **Completely rewriting `README.md`** to cover Project Overview, Architecture, Quickstart, Prerequisites, Environment Setup, Database Setup & Migrations, Pipeline Execution (`run.sh`), Web/Dash Applications, Automated Code Review (`pre-commit`, `ruff`, `mypy`), and Testing (`pytest`, `verify_graphs.py`).
2. **Creating `docs/ONBOARDING.md`** as a step-by-step developer onboarding manual.
3. **Creating `docs/DEVELOPMENT.md`** detailing code quality standards, pre-commit configuration, mypy typing guidelines, adding new endpoints/enrichers/charts, and CI/CD workflow details.

Detailed analysis and outline are provided in `analysis.md` in the working directory.

---

## 5. Verification Method

To verify these findings and recommendations independently:
1. Inspect existing documentation files:
   - `view_file /mnt/data/Projects_SSD/tranfere_gov_api/README.md`
   - `view_file /mnt/data/Projects_SSD/tranfere_gov_api/AGENTS.md`
   - `view_file /mnt/data/Projects_SSD/tranfere_gov_api/docs/MIGRATIONS.md`
   - `view_file /mnt/data/Projects_SSD/tranfere_gov_api/.github/workflows/ci.yml`
2. Inspect analysis report:
   - `view_file /mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_survey_3/analysis.md`
3. Invalidation condition: If `README.md` already accurately described the Python system and pre-commit workflows, or if `docs/` already contained developer onboarding guides. (Verified false: `README.md` currently describes React/npm).
