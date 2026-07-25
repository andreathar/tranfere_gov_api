# Handoff Report — Explorer (M2 Iteration 2)

## 1. Observation
- `docs/ONBOARDING.md` line 79 contains:
  `Conforme especificado em `docs/MIGRATIONS.md`, aplique todas as migrações SQL na sequência numérica:`
- `docs/ONBOARDING.md` line 152 contains:
  `./run.sh report parlamentar  # Totais por autor de emenda`
- `src/db_report.py` lines 22-62 and 167-174 define supported `report` commands as `resumo`, `estado`, `objeto`, `negados`, `emenda`, `municipio`, `top`, `sql`. Invoking `./run.sh report parlamentar` results in `Comando desconhecido: parlamentar`.
- The relative path `docs/MIGRATIONS.md` inside `docs/ONBOARDING.md` is redundant because `ONBOARDING.md` is already in the `docs/` directory.

## 2. Logic Chain
- **Step 1**: Observation of `src/db_report.py` shows `emenda` is the valid subcommand for reports by amendment author / totals.
- **Step 2**: Replacing `./run.sh report parlamentar` with `./run.sh report emenda` in line 152 of `docs/ONBOARDING.md` makes the documentation accurate and executable.
- **Step 3**: Observation of file structure shows `docs/ONBOARDING.md` and `docs/MIGRATIONS.md` are co-located in `docs/`.
- **Step 4**: Referencing `docs/MIGRATIONS.md` from `docs/ONBOARDING.md` creates a broken relative path `docs/docs/MIGRATIONS.md`.
- **Step 5**: Changing `` `docs/MIGRATIONS.md` `` to `` `MIGRATIONS.md` `` in line 79 corrects the relative link.

## 3. Caveats
No caveats. The required fixes are isolated to `docs/ONBOARDING.md` lines 79 and 152.

## 4. Conclusion
Exact instructions formulated for Worker:
1. In `docs/ONBOARDING.md` line 79, replace `` `docs/MIGRATIONS.md` `` with `` `MIGRATIONS.md` ``.
2. In `docs/ONBOARDING.md` line 152, replace `./run.sh report parlamentar` with `./run.sh report emenda`.

See `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_m2_r2_2/analysis.md` for full step-by-step specifications.

## 5. Verification Method
1. Inspect `docs/ONBOARDING.md` lines 79 and 152 via `view_file` or `grep_search`.
2. Run `pre-commit run --all-files` to ensure all pre-commit hooks pass.
