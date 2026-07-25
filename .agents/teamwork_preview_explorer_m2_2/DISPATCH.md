## 2026-07-25T22:22:28Z
You are an Explorer subagent for Milestone M2 (Requirement R2: Project Documentation & Onboarding).
Your working directory is /mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_m2_2

MANDATORY FIRST STEP: Read the original user request at /mnt/data/Projects_SSD/tranfere_gov_api/ORIGINAL_REQUEST.md and project roadmap at /mnt/data/Projects_SSD/tranfere_gov_api/.agents/orchestrator/PROJECT.md

Your Mission:
Investigate and produce an exact blueprint for `docs/ONBOARDING.md`:
1. Step-by-step developer onboarding manual.
2. Section 1: Prerequisites (Python 3.11+, PostgreSQL 14+, git, virtualenv).
3. Section 2: Environment Setup (`git clone`, `python3.11 -m venv .venv`, `source .venv/bin/activate`, `pip install -e ".[dev]"`).
4. Section 3: Database Provisioning (`createdb transferegov_db`, `psql -U cognee -d transferegov_db -f data/schema.sql`, running migrations in order per `docs/MIGRATIONS.md`).
5. Section 4: Data Pipeline & Enrichment Execution (`./run.sh discover`, `./run.sh all --db`, `python3 -m src.enrichers.pipeline --fase all`).
6. Section 5: Running Local Web Services (FastAPI backend at localhost:8000, Dash & MCP server at localhost:8050).
7. Section 6: Verification & Troubleshooting.

Write your findings to `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_m2_2/analysis.md` and handoff report to `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_m2_2/handoff.md`.
Update progress.md and send a message back to parent.
