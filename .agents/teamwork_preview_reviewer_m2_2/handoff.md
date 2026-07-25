# Handoff Report — Milestone M2 Documentation & Onboarding Review

**Reviewer**: Reviewer Subagent (`teamwork_preview_reviewer_m2_2`)  
**Target Milestone**: Milestone M2 — Project Documentation & Onboarding (Requirement R2)  
**Verdict**: **REQUEST_CHANGES**

---

## 1. Review Summary

The documentation created for Milestone M2 (`README.md`, `docs/ONBOARDING.md`, and `docs/DEVELOPMENT.md`) is structurally rich, professional, and well-aligned with the project's technical architecture (Python 3.11+, PostgreSQL, FastAPI, Plotly Dash, MCP Server, Ruff, MyPy, pre-commit, and GitHub Actions).

However, during verification against the actual codebase and scripts, **3 Major findings** and **2 Minor findings** were discovered. Specifically, `docs/ONBOARDING.md` contains an invalid CLI command that fails upon execution (`./run.sh report parlamentar`), `README.md` documents an incorrect port for `./run.sh web` (`8000` instead of `8080`), and `README.md` links to a non-existent `LICENSE` file.

---

## 2. Findings

### Major Finding 1: Non-Existent CLI Subcommand in `docs/ONBOARDING.md`

- **What**: `docs/ONBOARDING.md` instructs developers to run `./run.sh report parlamentar`, but `src/db_report.py` does not have a `parlamentar` subcommand.
- **Where**: `docs/ONBOARDING.md`, line 152:
  ```bash
  ./run.sh report parlamentar  # Totais por autor de emenda
  ```
  Code location: `src/db_report.py`, line 173:
  `print("Comandos: resumo, estado, objeto, negados, emenda, municipio, top, sql")`
- **Why**: Executing `./run.sh report parlamentar` results in `Comando desconhecido: parlamentar` and exits with error code 1.
- **Suggestion**: Update `docs/ONBOARDING.md` line 152 to use `./run.sh report emenda` (or update `src/db_report.py` to add `parlamentar` as an alias for `emenda`).

### Major Finding 2: Port Discrepancy for `./run.sh web` in `README.md`

- **What**: `README.md` states that `./run.sh web` runs on port `8000`, whereas `run.sh` launches uvicorn on port `8080`.
- **Where**: `README.md`, lines 184–188:
  ```bash
  ./run.sh web
  # Ou diretamente:
  # uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
  ```
  `- **Interface Web**: http://localhost:8000`  
  Code location: `run.sh`, lines 84–85:
  ```bash
  echo "🌐 Iniciando Painel Web do Deputado em http://localhost:8080 ..."
  $PYTHON -m uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8080
  ```
- **Why**: A developer running `./run.sh web` as instructed by `README.md` will attempt to open `http://localhost:8000` and fail to connect because the server is listening on port `8080`.
- **Suggestion**: Clarify in `README.md` that `./run.sh web` launches on port `8080` (or update `run.sh` to use port `8000` to match direct uvicorn execution). Note that `docs/ONBOARDING.md` line 168 already correctly documents that `./run.sh web` uses port `8080`.

### Major Finding 3: Missing `LICENSE` File Reference in `README.md`

- **What**: `README.md` refers to a `LICENSE` file in the root directory, but no such file exists in the repository.
- **Where**: `README.md`, line 250:
  ```markdown
  Distribuído sob a licença MIT. Veja `LICENSE` para mais informações.
  ```
- **Why**: Following the link/reference leads to a non-existent file.
- **Suggestion**: Either create the root `LICENSE` file containing the MIT License text or remove the "Veja `LICENSE` para mais informações" clause from `README.md`.

### Minor Finding 1: Script Argument Forwarding in `./run.sh all`

- **What**: `README.md` (line 149) and `docs/ONBOARDING.md` (line 114) suggest running `./run.sh all --db`, but `run.sh`'s `all)` block does not forward additional arguments (`"${@:2}"`).
- **Where**: `run.sh`, lines 99–101:
  ```bash
  all)
      $PYTHON "$SRC/transferegov_extract.py" --objeto all --ano 2026 --csv
      ;;
  ```
- **Why**: Running `./run.sh all --db` does not pass `--db` to `transferegov_extract.py`.
- **Suggestion**: Update `run.sh` line 100 to `$PYTHON "$SRC/transferegov_extract.py" --objeto all --ano 2026 --csv "${@:2}"`.

### Minor Finding 2: Relative File Reference inside `docs/ONBOARDING.md`

- **What**: `docs/ONBOARDING.md` references `docs/MIGRATIONS.md` rather than `MIGRATIONS.md`.
- **Where**: `docs/ONBOARDING.md`, line 79:
  `Conforme especificado em docs/MIGRATIONS.md...`
- **Why**: Since `ONBOARDING.md` is inside the `docs/` folder, referencing `docs/MIGRATIONS.md` resolves to `docs/docs/MIGRATIONS.md`.
- **Suggestion**: Update the relative reference inside `docs/ONBOARDING.md` to `MIGRATIONS.md` (or `../docs/MIGRATIONS.md`).

---

## 3. Verified Claims

- **Architecture Representation**: `README.md` accurately describes the 5-phase pipeline, ASCII system diagram, module layout (`src/`, `config/`, `data/`, `docs/`, `src/api/`, `src/enrichers/`, `src/graphs/`), and technologies (`Python 3.11`, `PostgreSQL`, `FastAPI`, `Plotly Dash`, `MCP Server`). Verified via `view_file` on `README.md`.
- **Developer Onboarding Instructions**: `docs/ONBOARDING.md` covers Python environment creation (`python3.11 -m venv .venv`), editable installation (`pip install -e ".[dev]"`), pre-commit installation (`pre-commit install`), PostgreSQL setup, and schema + migration script application (`schema.sql` and `migration_002` through `migration_011`). Verified via `view_file` on `docs/ONBOARDING.md`, `data/schema.sql`, and `data/migration_*.sql`.
- **Development Standards & Quality Workflow**: `docs/DEVELOPMENT.md` accurately details Ruff configuration (target-version `py311`, line-length `99`, select rules, ignore rules), MyPy strict typing stubs (`types-requests`, `types-psycopg2`, `pandas-stubs`), local pre-commit hook executions (`pre-commit run --all-files`), GitHub Actions CI matrix (`.github/workflows/ci.yml`), unit testing (`pytest`), graph audit (`python3 src/verify_graphs.py`), and PR contribution guidelines. Verified via `view_file` on `pyproject.toml`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, and `tests/`.
- **No Integrity Violations**: Verified test suite in `tests/` (`test_config.py`, `test_extract.py`, `test_schemas.py`, `test_deputado_followup.py`, `test_mcp_brasil_integration.py`). Code implementations are genuine; no hardcoded test results, facade shortcuts, or self-certifying stubs were detected.

---

## 4. Coverage Gaps & Unverified Items

- **Live External API Connectivity**: Live requests to external Government APIs (`transferegov.sistema.gov.br`, `brasilapi.com.br`, `dadosabertos.camara.leg.br`) were not executed during review (out of scope for doc review).

---

## 5. Handoff 5-Component Protocol

### 1. Observation
- **Observation 1**: `docs/ONBOARDING.md` Line 152 contains `./run.sh report parlamentar`. `src/db_report.py` Line 173 lists valid subcommands as `resumo, estado, objeto, negados, emenda, municipio, top, sql`. `src/db_report.py` has no `parlamentar` command.
- **Observation 2**: `README.md` Line 184–188 documents `./run.sh web` running on port `8000`. `run.sh` Line 85 contains `$PYTHON -m uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8080`.
- **Observation 3**: `README.md` Line 250 states `Veja LICENSE para mais informações.`. `find_by_name` search in project root `/mnt/data/Projects_SSD/tranfere_gov_api/` confirms no `LICENSE` file exists.
- **Observation 4**: `run.sh` Lines 99–101 does not include `${@:2}` in the `all)` case block.
- **Observation 5**: `pyproject.toml`, `.pre-commit-config.yaml`, and `.github/workflows/ci.yml` match `docs/DEVELOPMENT.md` definitions verbatim.

### 2. Logic Chain
- Step 1: Comparing documented commands in `ONBOARDING.md` with CLI script `src/db_report.py` reveals that `parlamentar` is not a handled command, causing CLI failure.
- Step 2: Comparing documented web ports in `README.md` with `run.sh` reveals a port discrepancy (`8000` vs `8080`).
- Step 3: Checking repository files against `README.md` references reveals a missing `LICENSE` file.
- Step 4: Therefore, while the documentation structure and depth are excellent, these actionable defects require resolution before milestone sign-off.

### 3. Caveats
- No live PostgreSQL database instance or live web server was bound during doc review; verification was performed by static code inspection and file mapping.

### 4. Conclusion
The M2 documentation is high quality overall, but requires minor updates (`REQUEST_CHANGES`) to resolve the 3 Major documentation findings prior to approval.

### 5. Verification Method
- Inspect `docs/ONBOARDING.md` line 152 and `src/db_report.py` line 173.
- Inspect `README.md` lines 184-188 and `run.sh` line 85.
- Check existence of `/mnt/data/Projects_SSD/tranfere_gov_api/LICENSE`.
- Re-run verification after implementer resolves the findings.
