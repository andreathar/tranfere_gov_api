# Handoff Report — Explorer M2-1 (README.md Blueprint)

## 1. Observation
- **Root `README.md` (`README.md:1-66`)**: Currently contains obsolete node/React 18/Express/Firebase instructions (`npm install`, `npm run dev`, `server.ts`, Vite).
- **`pyproject.toml:5-36`**: Project setup defines `transferegov-api` v2.0.0 for Python `>=3.11`, core dependencies (`requests`, `pandas`, `pydantic`, `psycopg2-binary`, `plotly`, `httpx`), dev dependencies (`pytest`, `ruff`, `mypy`, `pre-commit`, `types-requests`, `types-psycopg2`, `pandas-stubs`), `ruff` target `py311`, and `mypy` python version `3.11`.
- **`run.sh:1-112`**: Shell shortcuts script for `discover`, `cemiterios`, `negados`, `import`, `report`, `dashboard`, `web`, `enrich`, `validate`, `ibge`, `camara`, `all`.
- **`config/settings.py:108-128`**: PostgreSQL configuration defaults (`PGHOST=127.0.0.1`, `PGPORT=5432`, `PGDATABASE=transferegov_db`, `PGUSER=cognee`), external API bases (BrasilAPI, IBGE, Câmara).
- **`src/dash_app.py:8-33`**: Dash 4.3+ app with built-in MCP server at `http://localhost:8050/_mcp` and 31 Plotly analytics graphs.
- **`src/api/app.py:9-32`**: FastAPI web app serving REST endpoints on port 8000 for parliamentary intelligence.
- **`.pre-commit-config.yaml:1-26`**: Pre-commit configuration executing `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `ruff` (`--fix` & format), and `mypy` with type stubs.
- **`.github/workflows/ci.yml:1-43`**: GitHub Actions CI workflow running on Python 3.11/3.12 matrix, executing `pip install -e ".[dev]"`, `pre-commit run --all-files`, and `pytest`.

## 2. Logic Chain
1. **Observation 1** shows that the current `README.md` describes an obsolete Node.js/React scaffold that does not reflect the actual Python codebase.
2. **Observations 2 & 3** reveal that the actual core execution model relies on Python 3.11, `pyproject.toml`, and the `./run.sh` CLI wrapper script for data extraction, SQL reports, and multi-source enrichment.
3. **Observations 4, 5 & 6** establish the web and analysis layer: FastAPI (port 8000), Plotly Dash & MCP Server Hub (port 8050), and PostgreSQL persistence (`transferegov_db`).
4. **Observations 7 & 8** prove that M1 established automated code quality controls via `.pre-commit-config.yaml` and `.github/workflows/ci.yml`.
5. Therefore, a complete rewrite of `README.md` is required. The detailed content blueprint written in `analysis.md` provides an exact markdown template covering Project Title & Badges, Overview & Architecture, Directory Structure, Quickstart & DB Setup, CLI Execution, Web Applications & MCP Server, Code Quality & CI/CD, and Documentation Links.

## 3. Caveats
- `docs/ONBOARDING.md` and `docs/DEVELOPMENT.md` are linked in the blueprint as part of requirement R2; they are being created/updated in parallel M2 subtasks.
- The default port for `./run.sh web` in `run.sh:85` is 8080 while direct uvicorn in `src/api/app.py:9` notes 8000; the blueprint documents both local options clearly.

## 4. Conclusion
The comprehensive blueprint in `analysis.md` provides a complete, copy-paste ready blueprint for replacing `README.md`. The implementer agent can directly overwrite `README.md` using the exact content structure specified in `analysis.md`.

## 5. Verification Method
1. Inspect `analysis.md` at `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_m2_1/analysis.md`.
2. Verify all sections (Title, Architecture, Directory Tree, Quickstart, CLI, Web Apps/MCP, Code Quality/CI, Docs Links) match the exact specifications of `pyproject.toml`, `run.sh`, `.pre-commit-config.yaml`, and `.github/workflows/ci.yml`.
3. After `README.md` is updated by the implementer, verify formatting and links via `pre-commit run --all-files` and `markdownlint` (or manually rendering markdown).
