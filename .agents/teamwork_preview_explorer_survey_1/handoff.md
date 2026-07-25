# Handoff Report — Requirement R1 (Code Quality, Formatting & Typing Survey)

**Agent**: Explorer Subagent (`teamwork_preview_explorer_survey_1`)  
**Target Milestone**: Survey Phase for Requirement R1  
**Working Directory**: `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_survey_1`  

---

## 1. Observation

Direct observations from examining the codebase, dependencies, configurations, and source code:

1. **Python Environment & Dependencies**:
   - Python target: `3.11` configured across `pyproject.toml:9`, `pyproject.toml:39`, `pyproject.toml:54`, and `.github/workflows/ci.yml:14`.
   - `pyproject.toml` contains `[project.dependencies]` and `[project.optional-dependencies] dev`.
   - `requirements.txt` includes additional runtime dependencies (`fastapi`, `uvicorn`, `fastmcp`, `anthropic`).
   - `pre-commit` dependency is **absent** from both `pyproject.toml` and `requirements.txt`.
2. **Configurations**:
   - `.pre-commit-config.yaml` is **missing** from repository root.
   - `pyproject.toml` specifies `[tool.ruff]` (line-length 99, target py311) and `[tool.mypy]` (`strict = false`, `ignore_missing_imports = true`).
   - `.github/workflows/ci.yml` runs `ruff check src/ config/ tests/` and `mypy src/`, omitting `scripts/`.
3. **Source Code Defects & Typing Readiness**:
   - **NameError / F821 in `src/graph_tools.py:155`**: `query_df(sql_query)` is called inside `register_custom_graph`, but `query_df` is **not imported** (only `fig_has_data` is imported from `src.db_utils`).
   - **Invalid type annotation in `src/api/services/camara_service.py`**: Lines 7, 9, 18, 21 use standard built-in `any` instead of `typing.Any` (`cache: dict[str, tuple[float, any]]`, `def get_from_cache(...) -> Optional[any]:`).
   - **Missing return annotations**: Function signatures across `src/api/routes/` (`analytics.py`, `deputados.py`, `auditoria.py`, `prefeitos.py`), `src/dash_app.py`, `src/graphs/registry.py`, `src/db_utils.py` lack return type hints (`-> None`, `-> dict[str, Any]`, etc.).

---

## 2. Logic Chain

1. **Premise**: Requirement R1 requires setting up local pre-commit hooks (`.pre-commit-config.yaml`) and CI workflows (`.github/workflows/ci.yml`) enforcing strict ruff linting, formatting, and mypy type checking.
2. **Step 1 (Dependencies)**: Pre-commit cannot be executed locally or installed cleanly without declaring `pre-commit` in `pyproject.toml` `dev` dependencies and `requirements.txt`.
3. **Step 2 (Code Defects)**: Pre-commit or CI run of `ruff check` will immediately fail on `src/graph_tools.py` due to `F821` (undefined name `query_df`). Fixing this import is mandatory for pre-commit / CI to pass.
4. **Step 3 (Type Checker Errors)**: Pre-commit or CI run of `mypy` will fail on `src/api/services/camara_service.py` due to lower-case `any` used as a type annotation. Replacing `any` with `typing.Any` resolves this syntax error.
5. **Step 4 (Hook Architecture)**: Creating `.pre-commit-config.yaml` using `ruff` (linter + formatter) and `mypy` (with `types-requests`, `types-psycopg2`, `pandas-stubs`) guarantees pre-commit compliance across `src/`, `config/`, `scripts/`, and `tests/`.
6. **Step 5 (CI Alignment)**: Updating `.github/workflows/ci.yml` to check `src/`, `config/`, `scripts/`, and `tests/` ensures parity between local git hooks and remote CI.

---

## 3. Caveats

- Interactive terminal command execution (`run_command`) timed out due to environment permission rules. Static code analysis was performed using read-only filesystem search (`find_by_name`, `grep_search`, `view_file`).
- Mypy `strict = true` should be enabled in a phased manner after adding explicit return type annotations to all untyped API routes and graph registry functions. Currently `strict = false` is safe while basic mypy type checking runs cleanly once `any` is fixed and type stubs are installed.

---

## 4. Conclusion

The survey for Requirement R1 is complete. The exact root causes for potential linting and type-checking failures have been pinpointed, and concrete configuration blueprints for `.pre-commit-config.yaml`, `pyproject.toml`, and `.github/workflows/ci.yml` have been delivered in `analysis.md`.

---

## 5. Verification Method

1. Inspect `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_survey_1/analysis.md` for full survey details and recommended configurations.
2. Verify missing imports and type syntax issues in files:
   - `src/graph_tools.py`: Search line 17 (`from src.db_utils import fig_has_data`) and line 155 (`query_df`).
   - `src/api/services/camara_service.py`: Search lines 7, 9, 18, 21 for `any`.
3. Test proposed pre-commit setup after implementation by running:
   ```bash
   pip install -e ".[dev]"
   pre-commit install
   pre-commit run --all-files
   ```
