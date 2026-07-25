# Detailed Analysis & Blueprint for Pre-commit & Dev Dependencies (R1 / M1)

## Executive Summary
This analysis details the exact blueprint for configuring `.pre-commit-config.yaml`, updating `pyproject.toml`, and updating `requirements.txt` for the TransfereGov API project.

---

## 1. `.pre-commit-config.yaml` Blueprint

### Objective
Create `.pre-commit-config.yaml` at the root of `/mnt/data/Projects_SSD/tranfere_gov_api/` to enforce automated linting, formatting, syntax checking, and type checking before code is committed.

### File Blueprint (`.pre-commit-config.yaml`)

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

### Rationale & Mechanism
1. **`pre-commit-hooks` (v4.6.0)**:
   - `trailing-whitespace`: Strips unnecessary whitespace at the end of lines.
   - `end-of-file-fixer`: Ensures files end with a newline.
   - `check-yaml`: Validates syntax of YAML files (including `.pre-commit-config.yaml` and `.github/workflows/ci.yml`).
   - `check-added-large-files`: Prevents accidental commits of large binary/data outputs (especially important given `output/` directories).
   - `check-merge-conflict`: Rejects unresolved merge conflict markers.
2. **`astral-sh/ruff-pre-commit` (v0.8.0)**:
   - `ruff`: Executes fast linting with `--fix` to auto-fix safe lint rules. Respects `[tool.ruff]` in `pyproject.toml`.
   - `ruff-format`: Formats Python code consistent with `line-length = 99`.
3. **`pre-commit/mirrors-mypy` (v1.13.0)**:
   - `mypy`: Runs static type checking using Python 3.11 mode.
   - `additional_dependencies`: Includes `types-requests`, `types-psycopg2`, and `pandas-stubs` in the isolated mypy environment so type annotations for third-party libraries pass without error.

---

## 2. `pyproject.toml` Blueprint

### Objective
Update `[project.optional-dependencies] dev` in `pyproject.toml` to include `pre-commit` and type stubs required for development.

### Target Section in `pyproject.toml`

**Before:**
```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "respx>=0.22",
    "ruff>=0.8",
    "mypy>=1.13",
]
```

**After (Blueprint):**
```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "respx>=0.22",
    "ruff>=0.8",
    "mypy>=1.13",
    "pre-commit>=3.6.0",
    "types-requests",
    "types-psycopg2",
    "pandas-stubs",
]
```

### Full Context Preserved
- `[build-system]`: setuptools backend preserved.
- `[project]`: metadata and core dependencies preserved.
- `[tool.setuptools.packages.find]`: package discovery preserved.
- `[tool.ruff]`: line-length=99, target-version=py311 preserved.
- `[tool.mypy]`: strict=false, ignore_missing_imports=true preserved.
- `[tool.pytest.ini_options]`: pytest setup preserved.

---

## 3. `requirements.txt` Blueprint

### Objective
Update the `# Dev` section of `requirements.txt` so `pip install -r requirements.txt` includes pre-commit and type stubs.

### Target Section in `requirements.txt`

**Before:**
```text
# Dev
pytest>=8.0
pytest-asyncio>=0.24
respx>=0.22
ruff>=0.8
mypy>=1.13
```

**After (Blueprint):**
```text
# Dev
pytest>=8.0
pytest-asyncio>=0.24
respx>=0.22
ruff>=0.8
mypy>=1.13
pre-commit>=3.6.0
types-requests
types-psycopg2
pandas-stubs
```

---

## 4. Instructions for Implementer / Worker

1. **Create `.pre-commit-config.yaml`**:
   Write the exact blueprint contents shown in Section 1 to `/mnt/data/Projects_SSD/tranfere_gov_api/.pre-commit-config.yaml`.

2. **Update `pyproject.toml`**:
   Replace the `[project.optional-dependencies] dev` array with the expanded array shown in Section 2. Do not modify other sections (`[tool.ruff]`, `[tool.mypy]`, etc.).

3. **Update `requirements.txt`**:
   Append `pre-commit>=3.6.0`, `types-requests`, `types-psycopg2`, `pandas-stubs` under `# Dev` in `/mnt/data/Projects_SSD/tranfere_gov_api/requirements.txt`.

4. **Verification**:
   Run `pre-commit install` (optional) and test execution with `pre-commit run --all-files`.
