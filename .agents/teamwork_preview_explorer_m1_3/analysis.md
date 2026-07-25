# GitHub Actions CI Workflow Blueprint (`.github/workflows/ci.yml`)

## 1. Executive Summary
This document provides the exact file specification and implementation blueprint for `.github/workflows/ci.yml`. The workflow automates Continuous Integration (CI) for the TransfereGov API project, ensuring code quality, formatting, static type checking, and unit test validity on Python 3.11 and 3.12.

---

## 2. Specification & Version Standards

### GitHub Actions Dependencies
- `actions/checkout@v4`: Latest major version for repository checkout.
- `actions/setup-python@v5`: Latest major version for Python environment setup with built-in pip caching.
- `actions/cache@v4`: Latest major version for pre-commit environment caching.

### Strategy Matrix
- Python versions: `3.11`, `3.12`
- `fail-fast: false` (ensures both versions finish execution even if one encounters an error).

### Event Triggers
- `push` on `main` and `master` branches.
- `pull_request` on `main` and `master` branches.

### Pre-commit Cache Configuration
- **Path**: `~/.cache/pre-commit`
- **Key**: `pre-commit-${{ runner.os }}-${{ matrix.python-version }}-${{ hashFiles('.pre-commit-config.yaml') }}`
- **Restore Keys**: `pre-commit-${{ runner.os }}-${{ matrix.python-version }}-`

---

## 3. Exact Workflow File Specification (`.github/workflows/ci.yml`)

Target Path: `/mnt/data/Projects_SSD/tranfere_gov_api/.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

permissions:
  contents: read

jobs:
  ci:
    name: Build & Test (Python ${{ matrix.python-version }})
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: 'pip'

      - name: Cache pre-commit environment
        uses: actions/cache@v4
        with:
          path: ~/.cache/pre-commit
          key: pre-commit-${{ runner.os }}-${{ matrix.python-version }}-${{ hashFiles('.pre-commit-config.yaml') }}
          restore-keys: |
            pre-commit-${{ runner.os }}-${{ matrix.python-version }}-

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Install pre-commit hooks
        run: pre-commit install

      - name: Run pre-commit checks
        run: pre-commit run --all-files

      - name: Run test suite
        run: pytest
```

---

## 4. Verification Plan for Worker / Implementer

1. **File Creation**:
   Create directory `.github/workflows/` if it does not exist and write `.github/workflows/ci.yml` with the exact contents above.

2. **YAML Syntax Validation**:
   Validate that the YAML file is syntactically valid using pre-commit check (`check-yaml`).

3. **Workflow Execution Criteria**:
   - On `git push` or PR creation targeting `main` or `master`, GitHub Actions will trigger `ci.yml`.
   - Matrix runs 2 jobs in parallel: Python 3.11 and Python 3.12.
   - Pre-commit cache speeds up execution by persisting pre-commit environments across workflow runs.
   - `pre-commit run --all-files` runs ruff linting, formatting, mypy, check-yaml, end-of-file-fixer, and trailing-whitespace checks.
   - `pytest` executes unit tests in `tests/`.
