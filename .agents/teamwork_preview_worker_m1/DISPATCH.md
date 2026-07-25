## 2026-07-25T22:17:19Z

You are the Worker subagent for Milestone M1 (Requirement R1: Pre-commit & CI/CD Setup).
Your working directory is /mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_worker_m1

MANDATORY FIRST STEP: Read the original user request at /mnt/data/Projects_SSD/tranfere_gov_api/ORIGINAL_REQUEST.md and project roadmap at /mnt/data/Projects_SSD/tranfere_gov_api/.agents/orchestrator/PROJECT.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

File Write Ownership:
You have exclusive write ownership of the following target files:
- `src/graph_tools.py`
- `src/api/services/camara_service.py`
- `pyproject.toml`
- `requirements.txt`
- `.pre-commit-config.yaml`
- `.github/workflows/ci.yml`

Read the Explorer blueprints and handoff reports before modifying files:
- `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_m1_1/handoff.md`
- `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_m1_2/handoff.md`
- `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_m1_3/handoff.md`

Your Execution Tasks:
1. Fix `src/graph_tools.py`: Update line 17 import to `from src.db_utils import fig_has_data, query_df`.
2. Fix `src/api/services/camara_service.py`: Import `Any` from `typing` (`from typing import Any, Optional`) and replace lowercase `any` with `Any` across lines 7, 9, 18, 21.
3. Update `pyproject.toml`: Add `"pre-commit>=3.6.0"`, `"types-requests"`, `"types-psycopg2"`, `"pandas-stubs"` to `[project.optional-dependencies] dev`.
4. Update `requirements.txt`: Add `pre-commit>=3.6.0`, `types-requests`, `types-psycopg2`, `pandas-stubs` under `# Dev`.
5. Create `.pre-commit-config.yaml`:
   - `pre-commit/pre-commit-hooks` (v4.6.0): `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-added-large-files`, `check-merge-conflict`.
   - `astral-sh/ruff-pre-commit` (v0.8.0): `ruff` with `--fix` arg and `ruff-format`.
   - `pre-commit/mirrors-mypy` (v1.13.0): `mypy` with `additional_dependencies: [types-requests, types-psycopg2, pandas-stubs]`.
6. Create/Update `.github/workflows/ci.yml`:
   - GitHub Actions: `checkout@v4`, `setup-python@v5`, `cache@v4` for `~/.cache/pre-commit` keyed by OS, python version, `.pre-commit-config.yaml` hash.
   - Matrix: Python `3.11` and `3.12`.
   - Steps: checkout, setup python, cache pre-commit, `pip install -e ".[dev]"`, `pre-commit install`, `pre-commit run --all-files`, `pytest`.
7. Verify your work:
   - Run compilation checks, `ruff check`, `mypy src/`, `pre-commit run --all-files` (or equivalent test runner commands).
   - Document all verification commands and execution outputs in your handoff report.

Write your changes report to `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_worker_m1/changes.md` and handoff report to `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_worker_m1/handoff.md`.
Update progress.md when finished and send a message back to parent.
