## 2026-07-25T22:22:28Z
You are an Explorer subagent for Milestone M2 (Requirement R2: Project Documentation & Onboarding).
Your working directory is /mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_m2_3

MANDATORY FIRST STEP: Read the original user request at /mnt/data/Projects_SSD/tranfere_gov_api/ORIGINAL_REQUEST.md and project roadmap at /mnt/data/Projects_SSD/tranfere_gov_api/.agents/orchestrator/PROJECT.md

Your Mission:
Investigate and produce an exact blueprint for `docs/DEVELOPMENT.md`:
1. Developer Standards & Automated Code Review manual.
2. Section 1: Code Style & Quality Standards (Ruff linter rules `E,F,W,I,UP,B,SIM`, line length 99, target Python 3.11).
3. Section 2: Strict Typing & MyPy Standards (`mypy src/`, PEP 484 annotations, type stubs `types-requests`, `types-psycopg2`, `pandas-stubs`).
4. Section 3: Local Pre-commit Hooks Setup & Execution (`pip install -e ".[dev]"`, `pre-commit install`, `pre-commit run --all-files`, handling pre-commit failures).
5. Section 4: Continuous Integration (`.github/workflows/ci.yml`, matrix builds, caching, PR checks).
6. Section 5: Testing & Graph Verification (`pytest`, `python3 src/verify_graphs.py`).
7. Section 6: Pull Request & Contribution Workflow.

Write your findings to `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_m2_3/analysis.md` and handoff report to `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_m2_3/handoff.md`.
Update progress.md and send a message back to parent.
