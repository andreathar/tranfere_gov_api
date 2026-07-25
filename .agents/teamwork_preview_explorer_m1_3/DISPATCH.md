## 2026-07-25T22:15:18Z

You are an Explorer subagent for Milestone M1 (Pre-commit & CI/CD Setup - Requirement R1).
Your working directory is /mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_m1_3

MANDATORY FIRST STEP: Read the original user request at /mnt/data/Projects_SSD/tranfere_gov_api/ORIGINAL_REQUEST.md and project roadmap at /mnt/data/Projects_SSD/tranfere_gov_api/.agents/orchestrator/PROJECT.md

Your Mission:
Investigate and produce an exact workflow blueprint for `.github/workflows/ci.yml`:
1. Check GitHub Actions version standards (checkout@v4, setup-python@v5, cache@v4).
2. Configure matrix for Python 3.11 and 3.12.
3. Configure caching for `~/.cache/pre-commit` based on `.pre-commit-config.yaml` hash.
4. Configure environment setup, dependency installation (`pip install -e ".[dev]"`), pre-commit installation (`pre-commit install`), pre-commit execution (`pre-commit run --all-files`), and `pytest` test suite execution.
5. Provide exact file specifications for the Worker. Do NOT edit files directly.

Write your findings to `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_m1_3/analysis.md` and handoff report to `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_m1_3/handoff.md`.
When done, update progress.md and send a message to parent.
