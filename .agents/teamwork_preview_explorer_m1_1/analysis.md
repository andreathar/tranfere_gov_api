# Codebase Defects Analysis Report (Milestone M1 - Requirement R1)

## Executive Summary
This analysis specifies the exact defect locations, root causes, and step-by-step remediation instructions for Python codebase defects in `src/`. No modifications have been made to source files by this agent (read-only investigation).

---

## 1. Defect 1: Missing Import in `src/graph_tools.py`

### File Path
`/mnt/data/Projects_SSD/tranfere_gov_api/src/graph_tools.py`

### Problem Description
In `src/graph_tools.py`, line 155 invokes `query_df(sql_query)` inside the `dynamic_builder()` function. However, line 17 only imports `fig_has_data` from `src.db_utils`. At runtime, calling `register_custom_graph()` triggers a `NameError: name 'query_df' is not defined`.

### Exact Code Context

#### Line 17 (Current):
```python
16: from src.graph_factory import CHART_REGISTRY, aplicar_tema, register_chart
17: from src.db_utils import fig_has_data
18:
```

#### Lines 153-156 (Current Usage):
```python
153:     try:
154:         def dynamic_builder() -> go.Figure:
155:             df = query_df(sql_query)
156:             if df.empty:
```

### Exact Fix Specification
Update line 17 of `src/graph_tools.py` to import `query_df` alongside `fig_has_data`.

#### Proposed Modification:
```python
17: from src.db_utils import fig_has_data, query_df
```

---

## 2. Defect 2: Built-in `any` Type Annotation in `src/api/services/camara_service.py`

### File Path
`/mnt/data/Projects_SSD/tranfere_gov_api/src/api/services/camara_service.py`

### Problem Description
`src/api/services/camara_service.py` uses Python's built-in `any` (the built-in function) as a type annotation across multiple function and variable declarations instead of `typing.Any`. This causes static type checking errors with `mypy` (`Name 'any' is not defined` or invalid type hint usage) and violates PEP 484 type annotation standards.

### Exact Code Locations & Context

#### Line 3 (Current Imports):
```python
3: from typing import Optional
```

#### Line 7:
```python
7: cache: dict[str, tuple[float, any]] = {}
```

#### Line 9:
```python
9: def get_from_cache(key: str) -> Optional[any]:
```

#### Line 18:
```python
18: def set_in_cache(key: str, value: any):
```

#### Line 21:
```python
21: async def _get_json(client: httpx.AsyncClient, endpoint: str, params: dict = None) -> any:
```

### Exact Fix Specification
1. Update line 3 to import `Any` from `typing`:
   ```python
   from typing import Any, Optional
   ```
2. Replace all instances of `any` used as type hints with `Any`:
   - Line 7: `cache: dict[str, tuple[float, Any]] = {}`
   - Line 9: `def get_from_cache(key: str) -> Optional[Any]:`
   - Line 18: `def set_in_cache(key: str, value: Any):`
   - Line 21: `async def _get_json(client: httpx.AsyncClient, endpoint: str, params: dict = None) -> Any:`

---

## 3. General Codebase Audit (`src/`, `config/`, `scripts/`)

A full scan of all 61 Python files across `src/`, `config/`, and `scripts/` was conducted.

### Scope Evaluated:
- `src/` (49 files: `api/`, `enrichers/`, `graphs/`, CLI tools, core modules)
- `config/` (2 files: `__init__.py`, `settings.py`)
- `scripts/` (2 files: `cross_analysis_tse_transferegov.py`, `test_tse_datasets.py`)

### Audit Findings:
1. No other uses of lowercase `any` as type annotations exist in `src/`, `config/`, or `scripts/`.
2. All internal module imports (e.g. `from src.db_utils import ...`, `from src.formatters import ...`) refer to existing functions and classes.
3. Module structure and exports in `src/db_utils.py` (`get_connection`, `query_df`, `fig_has_data`), `src/formatters.py` (`fmt_brl`, `format_brl`, `fmt_num`, `fmt_pct`), and `src/graphs/` match caller expectations.

---

## 4. Step-by-Step Instructions for Worker (Implementer)

1. **Edit `src/graph_tools.py`**:
   - Locate line 17: `from src.db_utils import fig_has_data`
   - Change to: `from src.db_utils import fig_has_data, query_df`

2. **Edit `src/api/services/camara_service.py`**:
   - Change line 3: `from typing import Optional` → `from typing import Any, Optional`
   - Change line 7: `cache: dict[str, tuple[float, any]] = {}` → `cache: dict[str, tuple[float, Any]] = {}`
   - Change line 9: `def get_from_cache(key: str) -> Optional[any]:` → `def get_from_cache(key: str) -> Optional[Any]:`
   - Change line 18: `def set_in_cache(key: str, value: any):` → `def set_in_cache(key: str, value: Any):`
   - Change line 21: `async def _get_json(client: httpx.AsyncClient, endpoint: str, params: dict = None) -> any:` → `async def _get_json(client: httpx.AsyncClient, endpoint: str, params: dict = None) -> Any:`

3. **Verification**:
   - Run `python3 -m py_compile src/graph_tools.py src/api/services/camara_service.py` to ensure syntax validity.
   - Run `ruff check src/` and `mypy src/` when dev environment is active.
