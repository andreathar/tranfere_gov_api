# Project: TransfereGov API Code Quality & Documentation

## Architecture
- Python 3.11 / PostgreSQL / FastAPI / Plotly Dash / MCP project structure.
- Pre-commit hooks (`.pre-commit-config.yaml`) running `ruff` (linter & formatter), `mypy` (type checking), standard formatting checks (`trailing-whitespace`, `end-of-file-fixer`, `check-yaml`).
- GitHub Actions CI workflow (`.github/workflows/ci.yml`) validating commits and PRs using python setup, dependency installation, pre-commit caching, `pre-commit run --all-files`, and `pytest`.
- Comprehensive 2-tier documentation (`README.md`, `docs/ONBOARDING.md`, `docs/DEVELOPMENT.md`).

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Code Defect Remediation | Fix `src/graph_tools.py` missing import (`query_df`) and `src/api/services/camara_service.py` type annotation (`any` -> `typing.Any`) | M1 | survey |
| 2 | Dev Dependencies Update | Add `pre-commit>=3.6.0`, `types-requests`, `types-psycopg2`, `pandas-stubs` to `pyproject.toml` and `requirements.txt` | M1 | survey |
| 3 | Pre-commit Configuration | Create `.pre-commit-config.yaml` with `ruff` (linter + formatter), `mypy`, `check-yaml`, `trailing-whitespace` | M1 | survey |
| 4 | GitHub Actions CI Workflow | Update `.github/workflows/ci.yml` with pre-commit caching and `pre-commit run --all-files` execution | M1 | survey |
| 5 | Local Code Quality Verification | Ensure `pre-commit run --all-files` passes cleanly with exit code 0 | M1 | survey |
| 6 | Central README Rewrite | Rewrite `README.md` replacing legacy React/Vite template with Python/PostgreSQL/FastAPI/Dash/Pre-commit guide | M2 | survey |
| 7 | Developer Onboarding Guide | Create `docs/ONBOARDING.md` with step-by-step environment, database, pipeline, and app setup instructions | M2 | survey |
| 8 | Development Workflows Guide | Create `docs/DEVELOPMENT.md` covering pre-commit hook setup, ruff/mypy rules, PR process, and CI workflows | M2 | survey |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Pre-commit & CI/CD Setup | Implement `.pre-commit-config.yaml`, update `pyproject.toml`, `requirements.txt`, `.github/workflows/ci.yml`, and fix codebase linting/typing defects | none | DONE |
| M2 | Project Documentation & Onboarding | Rewrite `README.md`, create `docs/ONBOARDING.md` and `docs/DEVELOPMENT.md` | M1 | DONE |

## Interface & Configuration Contracts
### Pre-Commit Hooks Contract (`.pre-commit-config.yaml`)
- `ruff`: `ruff check --fix` and `ruff format`
- `mypy`: `mypy` running with `types-requests`, `types-psycopg2`, `pandas-stubs`
- `check-yaml`, `end-of-file-fixer`, `trailing-whitespace`

### CI/CD Workflow Contract (`.github/workflows/ci.yml`)
- Triggers: `push` on `main`/`master`, `pull_request` on `main`/`master`
- Python versions: `3.11`, `3.12`
- Steps: `checkout`, `setup-python`, cache `pre-commit`, `pip install -e ".[dev]"`, `pre-commit run --all-files`, `pytest`

### Documentation Structure Contract
- `README.md`: Project summary, architecture, quickstart, setup overview, CLI usage, web apps, pre-commit & CI badge/usage.
- `docs/ONBOARDING.md`: Step-by-step setup guide for new developers (python venv, postgresql, migrations, run.sh).
- `docs/DEVELOPMENT.md`: Code quality rules, pre-commit installation & execution, mypy rules, PR guidelines.

## Code Layout
- `.pre-commit-config.yaml`: Root pre-commit hooks file
- `.github/workflows/ci.yml`: Root GitHub Actions workflow
- `pyproject.toml` & `requirements.txt`: Root dependency configs
- `src/`: Core Python application code
- `README.md`: Root central project documentation
- `docs/ONBOARDING.md`: Developer onboarding manual
- `docs/DEVELOPMENT.md`: Developer standards and workflows manual
