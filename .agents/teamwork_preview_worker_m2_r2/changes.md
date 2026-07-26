# Changes Report — Milestone M2 (Iteration 2 Remediation)

**Agent**: Worker (`teamwork_preview_worker_m2_r2`)
**Date**: 2026-07-25
**Working Directory**: `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_worker_m2_r2`

---

## 1. Summary of Edits

This remediation addresses all issues identified by reviewer `reviewer_m2_2` in Milestone M2 Iteration 1.

| # | Target File | Description of Changes Made |
|---|-------------|-----------------------------|
| 1 | `README.md` | Updated `./run.sh web` port documentation to port 8080 (`http://localhost:8080`) while clarifying direct `uvicorn` execution on port 8000 (lines 25, 33, 55, 184–190). Updated license reference on line 251 to markdown hyperlink `[LICENSE](LICENSE)`. |
| 2 | `LICENSE` | Created standard 2026 MIT License at root (`/mnt/data/Projects_SSD/tranfere_gov_api/LICENSE`). |
| 3 | `docs/ONBOARDING.md` | Fixed relative link on line 79 from `docs/MIGRATIONS.md` to `MIGRATIONS.md` (as `ONBOARDING.md` is in `docs/`). Updated CLI report command on line 152 from `./run.sh report parlamentar` to `./run.sh report emenda`. |
| 4 | `run.sh` | Updated case blocks `cemiterios)`, `negados)`, and `all)` (lines 69, 72, 100) to forward trailing CLI arguments using `"${@:2}"` instead of `"$@"` or omitting arguments. |

---

## 2. File-by-File Details

### 2.1 `README.md`
- **Port 8080 Updates**:
  - Line 25: Updated Painel REST & Web App port description to `8080 (via ./run.sh web) ou 8000 (via uvicorn direto)`.
  - Line 33: Updated architecture diagram box to `[ FastAPI Web App (Porta 8080/8000) ]`.
  - Line 55: Updated file tree comment to `# Aplicação Web FastAPI (Porta 8080 via run.sh / 8000 via uvicorn)`.
  - Lines 184–190: Updated code example comment to `./run.sh web                          # Executa na porta 8080 (http://localhost:8080)` and updated endpoint list:
    - `- **Interface Web (via ./run.sh web)**: [http://localhost:8080](http://localhost:8080)`
    - `- **Interface Web (via uvicorn direto)**: [http://localhost:8000](http://localhost:8000)`
    - `- **Documentação Swagger/ReDoc**: [http://localhost:8080/docs](http://localhost:8080/docs) (ou http://localhost:8000/docs)`
- **LICENSE Link**:
  - Line 251: Updated `Veja LICENSE para mais informações.` to `Veja [LICENSE](LICENSE) para mais informações.`.

### 2.2 `LICENSE`
- Created `/mnt/data/Projects_SSD/tranfere_gov_api/LICENSE` containing standard 2026 MIT License text with copyright assigned to `TransfereGov API Contributors`.

### 2.3 `docs/ONBOARDING.md`
- Line 79: Changed `Conforme especificado em docs/MIGRATIONS.md,` to `Conforme especificado em MIGRATIONS.md,`.
- Line 152: Changed `./run.sh report parlamentar` to `./run.sh report emenda`.

### 2.4 `run.sh`
- Line 69 (`cemiterios)`): Replaced `"$@"` with `"${@:2}"`.
- Line 72 (`negados)`): Replaced `"$@"` with `"${@:2}"`.
- Line 100 (`all)`): Added `"${@:2}"` to the command execution line.

---

## 3. Verification Summary

- All 4 files (`README.md`, `LICENSE`, `docs/ONBOARDING.md`, `run.sh`) were updated and verified.
- Shell script syntax in `run.sh` is valid and argument forwarding matches all other case blocks (`import`, `report`, `dashboard`, `enrich`, `validate`, `ibge`, `camara`).
- Documentation relative links resolve correctly.
