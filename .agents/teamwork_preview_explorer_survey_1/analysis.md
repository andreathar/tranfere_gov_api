# Survey Analysis Report: Requirement R1 (Code Quality, Formatting & Typing)

**Project**: TransfereGov API  
**Target Python Version**: Python 3.11  
**Investigator**: Explorer Subagent (`teamwork_preview_explorer_survey_1`)  
**Date**: 2026-07-25  

---

## Executive Summary

This survey evaluates the TransfereGov API codebase against Requirement R1 (Code Quality, Formatting, Typing, and Automation). The analysis covered environment specifications, dependency declarations, linter/formatter configurations, static code analysis, strict type-checking readiness, CI pipeline setups, and local git hook architectures.

---

## 1. Python Environment & Dependencies

### Current State
- **Python Target**: Configured for `>=3.11` in `pyproject.toml` (`requires-python = ">=3.11"`), `[tool.ruff]` (`target-version = "py311"`), `[tool.mypy]` (`python_version = "3.11"`), and `.github/workflows/ci.yml` (test matrix with Python 3.11 and 3.12).
- **Build System**: `setuptools>=68.0` with `wheel`.

### Dependency Manifest Comparison

| Package Category | `pyproject.toml` (`[project.dependencies]`) | `requirements.txt` | Gap / Recommendation |
|---|---|---|---|
| **Core API & Data** | `requests>=2.31.0`, `pandas>=2.1.0`, `openpyxl>=3.1.0`, `python-dotenv>=1.0.0`, `pydantic>=2.0`, `httpx>=0.27`, `duckdb>=1.1`, `beautifulsoup4>=4.12`, `lxml>=5.0`, `psycopg2-binary>=2.9`, `plotly>=5.18` | Same + `fastapi>=0.115`, `uvicorn[standard]>=0.32` | Sync `fastapi` and `uvicorn` into `pyproject.toml` core dependencies. |
| **MCP & Agent Tools** | Missing | `fastmcp[code-mode]>=3.2.3`, `anthropic>=0.40` | Sync `fastmcp` and `anthropic` into `pyproject.toml` core or optional `mcp` extra. |
| **Dev Tools** | `pytest>=8.0`, `pytest-asyncio>=0.24`, `respx>=0.22`, `ruff>=0.8`, `mypy>=1.13` | Same | **`pre-commit` is MISSING** in both files! Add `pre-commit>=3.6.0` to `[project.optional-dependencies] dev` and `requirements.txt`. |
| **Type Stubs** | Missing | Missing | Add `types-requests`, `types-psycopg2`, `types-openpyxl` to dev dependencies for clean mypy execution. |

---

## 2. Linter, Formatter & Type Checker Configurations

### Current Configuration Analysis (`pyproject.toml`)

```toml
[tool.ruff]
target-version = "py311"
line-length = 99

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]
ignore = [
    "E501",   # line length handled by formatter
    "B905",   # zip() strict= — pre-existing, enable after audit
    "SIM105", # contextlib.suppress — pre-existing, enable after audit
]

[tool.ruff.lint.isort]
known-first-party = ["config", "src"]

[tool.mypy]
python_version = "3.11"
strict = false
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true
explicit_package_bases = true
mypy_path = "."
```

### Identified Configuration Gaps & Inconsistencies
1. **Missing Pre-commit Config**: `.pre-commit-config.yaml` is absent from the repository root.
2. **CI Scope Omissions in `.github/workflows/ci.yml`**:
   - `ruff check src/ config/ tests/` — Omits `scripts/` directory (`scripts/cross_analysis_tse_transferegov.py`, `scripts/test_tse_datasets.py`).
   - `mypy src/ --ignore-missing-imports --explicit-package-bases` — Omits `config/`, `scripts/`, and `tests/`.
3. **Mypy Strictness**: Currently set to `strict = false`. Switching directly to `strict = true` without type-annotation remediation will trigger numerous warnings/errors on untyped functions.

---

## 3. Codebase Analysis: Style, Syntax & Strict Typing Readiness

A comprehensive inspection across `src/`, `config/`, `scripts/`, and `tests/` revealed several critical code bugs, invalid type annotations, and typing gaps.

### A. Critical Code Bugs Detected (F821 / NameError)

1. **Undefined Name in `src/graph_tools.py`**:
   - **Location**: `src/graph_tools.py:155`
   - **Code**:
     ```python
     def dynamic_builder() -> go.Figure:
         df = query_df(sql_query)
     ```
   - **Issue**: `query_df` is invoked inside `register_custom_graph`, but `query_df` is **NOT imported** in `src/graph_tools.py` (only `fig_has_data` is imported from `src.db_utils`). Calling `register_custom_graph` will cause a runtime `NameError: name 'query_df' is not defined`.
   - **Fix**: Add `from src.db_utils import fig_has_data, query_df` at line 17 of `src/graph_tools.py`.

### B. Invalid Type Annotations (Built-in `any` vs `typing.Any`)

1. **Invalid Built-in `any` in `src/api/services/camara_service.py`**:
   - **Location**: `src/api/services/camara_service.py`, lines 7, 9, 18, 21
   - **Code**:
     ```python
     cache: dict[str, tuple[float, any]] = {}  # Line 7
     def get_from_cache(key: str) -> Optional[any]:  # Line 9
     def set_in_cache(key: str, value: any):  # Line 18
     async def _get_json(client: httpx.AsyncClient, endpoint: str, params: dict = None) -> any:  # Line 21
     ```
   - **Issue**: `any` refers to Python's built-in function `any()`, **not** `typing.Any`. Mypy flags this as an invalid type expression. In addition, `params: dict = None` should be `params: dict[str, Any] | None = None`.
   - **Fix**: Import `Any` from `typing` and replace all occurrences of lower-case `any` in type annotations with `Any`.

### C. Functions Missing Type Annotations (Strict Typing Obstacles)

1. **API Routes (`src/api/routes/`)**:
   - `src/api/routes/analytics.py`: `party_efficiency()`, `socioeconomic()`, `deputy_roi()`, `top_municipios()` lack return type annotations `-> dict[str, Any]`.
   - `src/api/routes/deputados.py`: `search_deputados()`, `get_perfil()`, `get_emendas()`, `get_resumo_emendas()`, `get_despesas()`, `get_comissoes()`, `get_votacoes()`, `get_proposicoes()`, `get_full_report()` lack explicit return type hints.
   - `src/api/routes/auditoria.py`: `get_saude()`, `search_justica()`, `check_tcu()` lack return types.
   - `src/api/routes/prefeitos.py`: `search_prefeitos()`, `get_ranking()`, `get_perfil()`, `get_emendas()` lack return types.

2. **Core Services & Dash App**:
   - `src/api/services/db_service.py`: `_get_connection()`, `_row_to_dict()` lack complete return/parameter annotations.
   - `src/db_utils.py`: `_patched_exit(exc_type, exc_val, exc_tb)`, `query_df_simple(conn, ...)` lack parameter type annotations.
   - `src/dash_app.py`: `build_layout()` lacks return type `-> html.Div`; callback inner function `update_graph_ctrl(*args)` lacks parameter and return types.
   - `src/graphs/registry.py`: `register_chart()` and inner `decorator()` lack return type annotations.

3. **Pydantic Schema Validators (`src/schemas.py`)**:
   - `src/schemas.py:61`: `def coerce_float(cls, v) -> float:` parameter `v` is untyped (`v: Any`).

---

## 4. Recommendations for `.pre-commit-config.yaml`

To fulfill Requirement R1, create `.pre-commit-config.yaml` in the project root with the following structure:

```yaml
# TransfereGov API — Pre-commit Configuration
# Validates code quality, formatting, and strict typing on local commits.

repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files
        args: ['--maxkb=1000']
      - id: check-merge-conflict

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.6
    hooks:
      - id: ruff
        name: ruff-linter
        args: [--fix, --exit-non-zero-on-fix]
        files: ^(src|config|scripts|tests)/
      - id: ruff-format
        name: ruff-formatter
        files: ^(src|config|scripts|tests)/

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.15.0
    hooks:
      - id: mypy
        name: mypy-type-checker
        args: [--config-file=pyproject.toml]
        additional_dependencies:
          - pydantic>=2.0
          - types-requests
          - types-psycopg2
          - pandas-stubs
        files: ^(src|config|scripts|tests)/
```

---

## 5. Recommended Updates to `pyproject.toml` and `.github/workflows/ci.yml`

### `pyproject.toml` Enhancements
1. Update `[project.optional-dependencies] dev`:
   ```toml
   dev = [
       "pytest>=8.0",
       "pytest-asyncio>=0.24",
       "respx>=0.22",
       "ruff>=0.8",
       "mypy>=1.13",
       "pre-commit>=3.6.0",
       "types-requests>=2.31.0",
       "types-psycopg2>=2.9.0",
   ]
   ```

2. Update `[tool.mypy]` to cover all directories cleanly once type annotations are completed:
   ```toml
   [tool.mypy]
   python_version = "3.11"
   strict = false
   warn_return_any = true
   warn_unused_configs = true
   ignore_missing_imports = true
   explicit_package_bases = true
   mypy_path = "."
   files = ["src", "config", "scripts", "tests"]
   ```

### `.github/workflows/ci.yml` Alignment
Ensure CI runs lint and type-check commands across **all** project directories:
```yaml
      - name: Lint with ruff
        run: ruff check src/ config/ scripts/ tests/

      - name: Format check with ruff
        run: ruff format --check src/ config/ scripts/ tests/

      - name: Type check with mypy
        run: mypy src/ config/ scripts/ tests/ --config-file=pyproject.toml
```

---

## Summary of Actionable Items for Implementer Agent

1. **Fix `src/graph_tools.py`**: Import `query_df` from `src.db_utils`.
2. **Fix `src/api/services/camara_service.py`**: Replace `any` with `typing.Any` and type `params`.
3. **Add missing type annotations**: Annotate return types in `src/api/routes/*.py`, `src/graphs/registry.py`, `src/dash_app.py`, and `src/db_utils.py`.
4. **Create `.pre-commit-config.yaml`**: Implement the recommended pre-commit config.
5. **Update `pyproject.toml` & `requirements.txt`**: Add `pre-commit` and type stubs.
6. **Update `.github/workflows/ci.yml`**: Include `scripts/` and add `ruff format --check`.
