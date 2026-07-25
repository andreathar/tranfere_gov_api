## 2026-07-25T22:29:29Z
<USER_REQUEST>
You are the Worker subagent for Milestone M2 (Iteration 2 Remediation).
Your working directory is /mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_worker_m2_r2

MANDATORY FIRST STEP: Read the original user request at /mnt/data/Projects_SSD/tranfere_gov_api/ORIGINAL_REQUEST.md, project roadmap at /mnt/data/Projects_SSD/tranfere_gov_api/.agents/orchestrator/PROJECT.md, and gate status at /mnt/data/Projects_SSD/tranfere_gov_api/.agents/orchestrator/GATE_STATUS.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

File Write Ownership:
You have exclusive write ownership of the following target files:
- `README.md`
- `LICENSE`
- `docs/ONBOARDING.md`
- `run.sh`

Read the Explorer blueprints before modifying files:
- `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_m2_r2_1/analysis.md` & `handoff.md`
- `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_m2_r2_2/analysis.md` & `handoff.md`
- `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_m2_r2_3/analysis.md` & `handoff.md`

Your Execution Tasks:
1. `README.md`: Update `./run.sh web` port documentation to port 8080 (`http://localhost:8080`), preserving direct uvicorn port 8000 notes. Update line 250 to link `[LICENSE](LICENSE)`.
2. `LICENSE`: Create `/mnt/data/Projects_SSD/tranfere_gov_api/LICENSE` containing standard 2026 MIT License text.
3. `docs/ONBOARDING.md`: Update line 152 from `./run.sh report parlamentar` to `./run.sh report emenda`. Update line 79 relative link from `docs/MIGRATIONS.md` to `MIGRATIONS.md`.
4. `run.sh`: Update case blocks `cemiterios)`, `negados)`, and `all)` to forward extra arguments using `"${@:2}"`.
5. Verify your work:
   - Run compilation and pre-commit check (`pre-commit run --all-files` or script verification).
   - Document all verification commands and outputs in your handoff report.

Write your changes report to `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_worker_m2_r2/changes.md` and handoff report to `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_worker_m2_r2/handoff.md`.
Update progress.md when finished and send a message back to parent.
</USER_REQUEST>
