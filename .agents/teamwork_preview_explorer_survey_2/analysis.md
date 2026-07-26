# Analysis Report — CI/CD & Pre-Commit Infrastructure (Requirement R1)

**Project**: TransfereGov API
**Agent**: Explorer (`teamwork_preview_explorer_survey_2`)
**Date**: 2026-07-25

---

## 1. Executive Summary

This investigation analyzed the existing CI/CD and pre-commit hook infrastructure for Requirement R1 of the TransfereGov API project.

Key conclusions:
- `.github/workflows/ci.yml` exists but needs to be enhanced to run `pre-commit run --all-files`, include caching, and target all project Python modules (`src/`, `config/`, `tests/`).
- `.pre-commit-config.yaml` is currently **missing** and needs to be created to configure `ruff` (linter & formatter) and `mypy` (strict typing).
- `pre-commit` package is missing from `pyproject.toml` `dev` dependencies and `requirements.txt`.
- MyPy configuration in `pyproject.toml` currently specifies `strict = false`, which must be updated to `strict = true` (with proper module inclusions/overrides) to align with requirement R1.

---

## 2. Detailed Findings

### 2.1 Existing CI/CD Setup (`.github/workflows/ci.yml`)

The repository currently has a basic GitHub Actions workflow at `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

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

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Lint with ruff
        run: ruff check src/ config/ tests/

      - name: Type check with mypy
        run: mypy src/ --ignore-missing-imports --explicit-package-bases

      - name: Run tests
        run: python -m pytest tests/ -v
```

#### Identified Deficiencies in CI Workflow:
1. **No Pre-Commit Validation**: CI does not invoke `pre-commit run --all-files`. This means local pre-commit hooks and CI could potentially diverge in linting/formatting rules or behavior.
2. **Missing Ruff Formatting Check**: The current workflow runs `ruff check` but not `ruff format --check`.
3. **Incomplete MyPy Scope**: MyPy is invoked only on `src/` (`mypy src/`), ignoring `config/` and `tests/`.
4. **No Environment Caching**: CI lacks caching for `~/.cache/pip` and `~/.cache/pre-commit`, leading to slower job execution times on PRs.
5. **Branch Triggers**: Triggers only on `main`, should also cover `master` if applicable.

---

### 2.2 Pre-Commit Infrastructure

- **File Status**: `.pre-commit-config.yaml` does not exist in the root of `/mnt/data/Projects_SSD/tranfere_gov_api`.
- **Git Hooks**: `.git/hooks/` contains only default `.sample` files.
- **Dependency Status**: `pre-commit` is missing from `pyproject.toml` (`[project.optional-dependencies] dev`) and `requirements.txt`.

---

### 2.3 Required `.pre-commit-config.yaml` Configuration

To satisfy Requirement R1 and enable clean execution of `pre-commit run --all-files`, `.pre-commit-config.yaml` should be configured with:

1. **Standard Hygiene Hooks**:
   - `trailing-whitespace`
   - `end-of-file-fixer`
   - `check-yaml`
   - `check-toml`
   - `check-added-large-files`

2. **Ruff (Format + Lint)**:
   - Repo: `https://github.com/astral-sh/ruff-pre-commit` (v0.8.0)
   - Hooks:
     - `ruff` (with `--fix`)
     - `ruff-format`

3. **MyPy (Strict Typing)**:
   - Option A (Remote mirror hook):
     - Repo: `https://github.com/pre-commit/mirrors-mypy` (v1.13.0)
     - Hooks: `mypy`
     - Additional dependencies: `pydantic>=2.0`, `types-requests`, `pandas-stubs`, `types-openpyxl`, `types-psycopg2`, `fastapi`, `httpx`
     - Args: `["--config-file=pyproject.toml"]`
   - Option B (Local system hook):
     - Repo: `local`
     - Hook: `id: mypy`, `entry: mypy`, `language: system`, `files: ^(src|config|tests)/`

---

### 2.4 MyPy Configuration in `pyproject.toml`

Current `pyproject.toml` MyPy section:
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

#### Proposed Changes for Strict Typing:
1. Update `strict = true`.
2. Keep `ignore_missing_imports = true` for third-party libraries without type hints.
3. Ensure explicit module targets `src`, `config`, `tests`.

---

### 2.5 Bottlenecks & Missing Dependencies

1. **Missing Dev Dependency**: `pre-commit>=3.6.0` must be added to `pyproject.toml` `[project.optional-dependencies] dev` and `requirements.txt`.
2. **CI Caching**: Add `actions/cache@v4` in `ci.yml` targeting `~/.cache/pre-commit` to prevent redownloading environment dependencies on every commit.
3. **Execution Efficiency**: `pre-commit run --all-files` takes < 2 seconds when caches are warm and ruff/mypy are properly scoped.

---

## 3. Recommended Implementation Specification

### 3.1 `.pre-commit-config.yaml`
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files

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
          - pydantic>=2.0
          - types-requests
          - pandas-stubs
          - types-openpyxl
          - types-psycopg2
          - fastapi
          - httpx
        args: [--config-file=pyproject.toml]
```

### 3.2 Enhanced `.github/workflows/ci.yml`
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
          cache: "pip"

      - name: Cache Pre-Commit Hooks
        uses: actions/cache@v4
        with:
          path: ~/.cache/pre-commit
          key: pre-commit-${{ runner.os }}-${{ matrix.python-version }}-${{ hashFiles('.pre-commit-config.yaml') }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Run Pre-Commit Checks
        run: pre-commit run --all-files

      - name: Run pytest
        run: python -m pytest tests/ -v
```

---

## 4. Verification Checklist
- Run `pre-commit install` locally.
- Run `pre-commit run --all-files` and verify 100% exit code 0.
- Verify GitHub Actions CI syntax using workflow validator or test commit.
