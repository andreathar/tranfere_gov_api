# Analysis & Exact Blueprint for `docs/DEVELOPMENT.md`

## Executive Summary
This document provides the complete, production-ready blueprint for `docs/DEVELOPMENT.md` (Developer Standards & Automated Code Review Manual) for the **TransfereGov API** project. The blueprint aligns 100% with the existing project configuration files (`pyproject.toml`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `requirements.txt`, `src/verify_graphs.py`, and `AGENTS.md`).

---

## Blueprint Overview & Table of Contents

The document `docs/DEVELOPMENT.md` is structured into 6 comprehensive sections:

1. **Section 1: Code Style & Quality Standards (Ruff)**
2. **Section 2: Strict Typing & MyPy Standards (MyPy)**
3. **Section 3: Local Pre-commit Hooks Setup & Execution**
4. **Section 4: Continuous Integration (GitHub Actions CI)**
5. **Section 5: Testing & Graph Verification (`pytest` & `verify_graphs.py`)**
6. **Section 6: Pull Request & Contribution Workflow**

---

## Detailed Section Specifications

### Header & Introduction
- **Title**: `# Manual de Padrões de Desenvolvimento e Revisão Automatizada de Código`
- **Target Audience**: Core developers, open-source contributors, and automated CI pipelines.
- **Goal**: Maintain zero technical debt, enforce Python 3.11+ modern idioms, guarantee robust typing, prevent invalid code commits, and automate graph health checks.

---

### Section 1: Code Style & Quality Standards (Ruff)

#### Configuration Reference (`pyproject.toml`)
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
```

#### Rule Sets Explanation
- **`E` / `W` (Pycodestyle Errors and Warnings)**: Standard PEP 8 formatting, spacing, and syntax rules.
- **`F` (Pyflakes)**: Detection of undefined variables, unused imports, duplicate arguments, and logic flaws.
- **`I` (isort)**: Automatic import sorting and grouping (`known-first-party = ["config", "src"]`).
- **`UP` (pyupgrade)**: Enforces Python 3.11+ modern syntax (e.g., `list[str]` instead of `typing.List[str]`, `f-strings`, union types `X | Y`).
- **`B` (flake8-bugbear)**: Catching design flaws, dangerous defaults (mutable default arguments), and potential bugs.
- **`SIM` (flake8-simplify)**: Simplifying boolean expressions, unnecessary `if/else` clauses, and redundant constructs.

#### Ignored Rules Rationale
- `E501`: Line length soft-capped at 99 characters by `ruff-format`; hard breaking is managed by formatter.
- `B905`: `zip(..., strict=True)` — temporarily ignored for legacy loops, slated for future audit.
- `SIM105`: `try-except-pass` vs `contextlib.suppress` — temporarily ignored for compatibility.

#### Execution Commands
```bash
# Verify code quality and view issues
ruff check

# Automatically fix fixable linter issues
ruff check --fix

# Format all Python files
ruff format

# Verify formatting without modifying files
ruff format --check
```

---

### Section 2: Strict Typing & MyPy Standards (MyPy)

#### Configuration Reference (`pyproject.toml` & `.pre-commit-config.yaml`)
```toml
[tool.mypy]
python_version = "3.11"
strict = false
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true
explicit_package_bases = true
mypy_path = "."
```

#### Type Stubs & Packages
- `types-requests`: Type annotations for `requests` HTTP calls.
- `types-psycopg2`: Type definitions for PostgreSQL `psycopg2` connections and cursors.
- `pandas-stubs`: Type hints for pandas DataFrames and Series operations.

#### Typing Rules & Best Practices
1. **PEP 484 Annotations**: Every function must annotate arguments and return types:
   ```python
   def consultar_plano(plano_id: int) -> dict[str, Any]:
   ```
2. **Built-in Generics (PEP 585 / Python 3.11+)**: Use `list[...]`, `dict[...]`, `tuple[...]`, `set[...]` directly without importing `List`, `Dict`, `Tuple` from `typing`.
3. **Explicit `Any`**: Always import `Any` explicitly (`from typing import Any`). Raw `any` as a type hint is strictly invalid.
4. **DataFrame Typing**: Utilize `pandas.DataFrame` or `pd.DataFrame` hints for database query returns.

#### Execution Commands
```bash
# Run MyPy static type checking on source code
mypy src/

# Run MyPy static type checking on tests
mypy tests/
```

---

### Section 3: Local Pre-commit Hooks Setup & Execution

#### Pre-commit Pipeline (`.pre-commit-config.yaml`)
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-merge-conflict

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        additional_dependencies:
          - types-requests
          - types-psycopg2
          - pandas-stubs
```

#### Setup & Workflow Instructions
```bash
# 1. Activate environment
source .venv/bin/activate

# 2. Install editable package with dev dependencies
pip install -e ".[dev]"

# 3. Install pre-commit hooks into git repository
pre-commit install

# 4. Execute checks manually across all files
pre-commit run --all-files
```

#### Pre-commit Failure Resolution Strategy
1. **Auto-fixes by Ruff & file fixers**: If `trailing-whitespace`, `end-of-file-fixer`, `ruff`, or `ruff-format` fail, they automatically format your code.
2. **Review & Stage**: Run `git diff` to inspect auto-formatted changes, then stage them with `git add .`.
3. **Manual Type Fixes**: If `mypy` fails, fix missing or incorrect type annotations in your source files.
4. **Re-test**: Run `pre-commit run --all-files` again until all hooks display `Passed`.

---

### Section 4: Continuous Integration (`.github/workflows/ci.yml`)

#### CI Workflow Blueprint
```yaml
name: CI

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

jobs:
  quality:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Cache Pre-Commit
        uses: actions/cache@v4
        with:
          path: ~/.cache/pre-commit
          key: pre-commit-${{ runner.os }}-${{ matrix.python-version }}-${{ hashFiles('.pre-commit-config.yaml') }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Install pre-commit
        run: pre-commit install

      - name: Run pre-commit checks
        run: pre-commit run --all-files

      - name: Run tests
        run: pytest
```

#### Key Architecture Features
- **Matrix Testing**: Validates build integrity across Python 3.11 and Python 3.12.
- **Pre-commit Cache**: Caches environment dependencies at `~/.cache/pre-commit` to speed up CI runs.
- **Merge Gate**: Pull Requests cannot be merged if any job in the matrix fails pre-commit or pytest.

---

### Section 5: Testing & Graph Verification

#### 1. Unit & Integration Testing (`pytest`)
- Configuration in `pyproject.toml`:
  ```toml
  [tool.pytest.ini_options]
  testpaths = ["tests"]
  python_files = ["test_*.py"]
  python_functions = ["test_*"]
  addopts = "-v --tb=short"
  ```
- Command:
  ```bash
  pytest
  ```

#### 2. Graph Verification Suite (`src/verify_graphs.py`)
- Audits all 31 registered Dash/Plotly charts in `CHART_REGISTRY`.
- Verifies figure instantiation, trace counts, non-empty data points (`x`, `y`, `values`, `z`, `locations`, `link.value`), execution latency, and zero blank graph states.
- Command:
  ```bash
  python3 src/verify_graphs.py
  ```

---

### Section 6: Pull Request & Contribution Workflow

1. **Branch Naming Conventions**:
   - `feature/<nome>`: New feature or analytical route
   - `fix/<descricao>`: Bug resolution
   - `docs/<topico>`: Documentation update
   - `refactor/<modulo>`: Code refactoring
2. **Commit Convention**: Commit messages in Portuguese (PT-BR), concise, no emojis.
3. **PR Checklist**:
   - [ ] Local `pre-commit run --all-files` passed cleanly.
   - [ ] Unit tests (`pytest`) passed cleanly.
   - [ ] Graph verification (`python3 src/verify_graphs.py`) passed cleanly.
   - [ ] GitHub Actions CI workflow passed on Python 3.11 & 3.12.

---

## Verification & Alignment Confirmation
- `pyproject.toml` settings (ruff rules `E,F,W,I,UP,B,SIM`, line length 99, target Python 3.11) match Section 1 & 2 specs.
- `.pre-commit-config.yaml` hooks (`trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `ruff`, `ruff-format`, `mypy` with stubs) match Section 3 specs.
- `.github/workflows/ci.yml` matrix (`3.11`, `3.12`), pre-commit caching, and pytest steps match Section 4 specs.
- `src/verify_graphs.py` and `tests/` match Section 5 specs.
