# Analysis Report: Documentation Fixes for `docs/ONBOARDING.md`

**Milestone**: M2 (Iteration 2 - Remediation of Reviewer Feedback)  
**Agent**: Explorer (`teamwork_preview_explorer_m2_r2_2`)  
**Target File**: `docs/ONBOARDING.md`  

---

## Executive Summary

During the review phase of Milestone M2 (Iteration 1), `reviewer_m2_2` requested changes regarding two documentation defects in `docs/ONBOARDING.md`:
1. **Invalid subcommand reference**: `docs/ONBOARDING.md` line 152 refers to `./run.sh report parlamentar`, but `src/db_report.py` and `run.sh` define the valid subcommand as `emenda` (or `resumo`, `estado`, `objeto`, `negados`, `municipio`, `top`, `sql`), not `parlamentar`.
2. **Redundant/broken relative path reference**: `docs/ONBOARDING.md` line 79 references `docs/MIGRATIONS.md`. Because `ONBOARDING.md` is already located inside the `docs/` directory (`docs/ONBOARDING.md`), referring to `docs/MIGRATIONS.md` resolves relatively to `docs/docs/MIGRATIONS.md`, which does not exist. The correct relative path reference from within `docs/ONBOARDING.md` is `MIGRATIONS.md`.

This report provides the detailed analysis, evidence chain, and step-by-step fix specifications for the Worker subagent.

---

## Detailed Findings & Evidence Chain

### Finding 1: Invalid CLI Subcommand in `docs/ONBOARDING.md:152`

- **Observation 1.1**: In `docs/ONBOARDING.md` line 152:
  ```markdown
  ./run.sh report parlamentar  # Totais por autor de emenda
  ```
- **Observation 1.2**: In `src/db_report.py` (lines 22-62 and 167-174):
  ```python
  QUERIES = {
      "resumo": "...",
      "estado": "SELECT * FROM v_resumo_por_estado",
      "objeto": "SELECT * FROM v_resumo_por_objeto",
      "negados": "...",
      "emenda": """
          SELECT
              codigo_emenda_formatado,
              COUNT(*) AS planos,
              SUM(valor_total) AS valor_total,
              STRING_AGG(DISTINCT beneficiario_uf, ', ') AS ufs
          FROM v_planos_completo
          WHERE codigo_emenda_formatado IS NOT NULL AND codigo_emenda_formatado != ''
          GROUP BY codigo_emenda_formatado
          ORDER BY valor_total DESC
      """,
  }
  ```
  If an invalid command like `parlamentar` is passed to `src/db_report.py`, it executes line 172:
  `Comando desconhecido: parlamentar`  
  `Comandos: resumo, estado, objeto, negados, emenda, municipio, top, sql`
- **Logic**: The subcommand for querying totals by amendment / parliamentarian in `src/db_report.py` is `emenda`. Updating line 152 of `docs/ONBOARDING.md` to `./run.sh report emenda       # Totais por autor de emenda` aligns the documentation with the executable CLI contract.

---

### Finding 2: Incorrect Relative Path Reference in `docs/ONBOARDING.md:79`

- **Observation 2.1**: In `docs/ONBOARDING.md` line 79:
  ```markdown
  Conforme especificado em `docs/MIGRATIONS.md`, aplique todas as migrações SQL na sequência numérica:
  ```
- **Observation 2.2**: The file structure is:
  ```
  docs/
  ├── DEVELOPMENT.md
  ├── MIGRATIONS.md
  └── ONBOARDING.md
  ```
  Since `ONBOARDING.md` resides inside the `docs/` folder, referencing `docs/MIGRATIONS.md` inside `docs/ONBOARDING.md` is incorrect because it points relative to `docs/` (i.e. `docs/docs/MIGRATIONS.md`).
- **Logic**: The reference within `docs/ONBOARDING.md` must be updated from `` `docs/MIGRATIONS.md` `` to `` `MIGRATIONS.md` ``.

---

## Step-by-Step Specifications for Worker Implementation

The Worker agent should execute the following modifications on `/mnt/data/Projects_SSD/tranfere_gov_api/docs/ONBOARDING.md`:

### Step 1: Fix Relative Migration Path Reference
- **File**: `docs/ONBOARDING.md`
- **Line Range**: 78–80
- **Target Content**:
  ```markdown
  Conforme especificado em `docs/MIGRATIONS.md`, aplique todas as migrações SQL na sequência numérica:
  ```
- **Replacement Content**:
  ```markdown
  Conforme especificado em `MIGRATIONS.md`, aplique todas as migrações SQL na sequência numérica:
  ```

### Step 2: Fix Report Subcommand Reference
- **File**: `docs/ONBOARDING.md`
- **Line Range**: 151–153
- **Target Content**:
  ```markdown
  ./run.sh report parlamentar  # Totais por autor de emenda
  ```
- **Replacement Content**:
  ```markdown
  ./run.sh report emenda       # Totais por autor de emenda
  ```

---

## Verification Plan

After applying the edits, verify using:
1. `grep -n "MIGRATIONS.md" docs/ONBOARDING.md` -> confirms `MIGRATIONS.md` without leading `docs/`.
2. `grep -n "report" docs/ONBOARDING.md` -> confirms `./run.sh report emenda`.
3. `pre-commit run --all-files` -> verifies markdown formatting / linting and ensures repository checks pass cleanly.
