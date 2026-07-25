## 2026-07-25T19:22:27Z
Investigate and produce an exact content blueprint for completely rewriting `README.md`:
1. Analyze existing `README.md` (legacy React/Vite/Express scaffolding) and project sources (`AGENTS.md`, `run.sh`, `pyproject.toml`, `config/settings.py`, `src/dash_app.py`, `src/api/app.py`).
2. Structure the new `README.md` with:
   - Project Title & Overview (TransfereGov API: Python 3.11 extraction, validation, PostgreSQL persistence, enrichment, FastAPI web app, Plotly Dash dashboard & MCP server).
   - Architecture & Directory Structure.
   - Quickstart & Environment Setup (Python 3.11, venv, PostgreSQL).
   - CLI Execution (`./run.sh discover`, `./run.sh cemiterios`, `./run.sh all --db`, `./run.sh report`, etc.).
   - Web Application & MCP Server (`./run.sh web` on port 8000, `python3 src/dash_app.py` on port 8050, `http://localhost:8050/_mcp`).
   - Code Quality & CI/CD (`pre-commit install`, `pre-commit run --all-files`, ruff, mypy, GitHub Actions CI).
   - Link to `docs/ONBOARDING.md` and `docs/DEVELOPMENT.md`.

Write your findings to `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_m2_1/analysis.md` and handoff report to `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_m2_1/handoff.md`.
Update progress.md and send a message back to parent.
