# Changes Summary — Milestone M1 (Pre-commit & CI/CD Setup)

## Modified & Created Files

1. **`src/graph_tools.py`**:
   - Updated line 17 import from `from src.db_utils import fig_has_data` to `from src.db_utils import fig_has_data, query_df`.
   - Resolves runtime `NameError: name 'query_df' is not defined` inside `dynamic_builder()`.

2. **`src/api/services/camara_service.py`**:
   - Updated line 3 import to `from typing import Any, Optional`.
   - Replaced Python built-in `any` with `typing.Any` across type annotations on lines 7, 9, 18, and 21.
   - Resolves mypy type checker syntax errors and enforces standard PEP 484 type annotations.

3. **`pyproject.toml`**:
   - Added `"pre-commit>=3.6.0"`, `"types-requests"`, `"types-psycopg2"`, `"pandas-stubs"` to `[project.optional-dependencies] dev`.

4. **`requirements.txt`**:
   - Added `pre-commit>=3.6.0`, `types-requests`, `types-psycopg2`, and `pandas-stubs` under `# Dev`.

5. **`.pre-commit-config.yaml`**:
   - Created root pre-commit configuration file with 3 repository hooks:
     - `pre-commit/pre-commit-hooks` (v4.6.0): `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-added-large-files`, `check-merge-conflict`.
     - `astral-sh/ruff-pre-commit` (v0.8.0): `ruff` with `--fix` arg, `ruff-format`.
     - `pre-commit/mirrors-mypy` (v1.13.0): `mypy` with additional dependencies (`types-requests`, `types-psycopg2`, `pandas-stubs`).

6. **`.github/workflows/ci.yml`**:
   - Created GitHub Actions workflow triggered on push/pull_request to `main`/`master`.
   - Configured matrix strategy for Python versions `3.11` and `3.12` on `ubuntu-latest`.
   - Included steps: `checkout@v4`, `setup-python@v5`, `cache@v4` for `~/.cache/pre-commit` (keyed by OS, python version, `.pre-commit-config.yaml` hash), editable dependency install `pip install -e ".[dev]"`, `pre-commit install`, `pre-commit run --all-files`, and `pytest`.
