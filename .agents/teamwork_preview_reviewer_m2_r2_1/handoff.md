# Handoff Report — Milestone M2 Iteration 2 Review

## 1. Observation
- **`README.md`**:
  - Line 25: `- **Painel REST & Web App (FastAPI)**: Inteligência parlamentar e municipal na porta 8080 (via ./run.sh web) ou 8000 (via uvicorn direto).`
  - Line 33: `[ FastAPI Web App (Porta 8080/8000) ]`
  - Line 55: `├── api/                      # Aplicação Web FastAPI (Porta 8080 via run.sh / 8000 via uvicorn)`
  - Line 184: `./run.sh web                          # Executa na porta 8080 (http://localhost:8080)`
  - Line 188: `- **Interface Web (via ./run.sh web)**: http://localhost:8080`
  - Line 190: `- **Documentação Swagger/ReDoc**: http://localhost:8080/docs (ou http://localhost:8000/docs)`
  - Line 251: `Distribuído sob a licença MIT. Veja [LICENSE](LICENSE) para mais informações.`
- **`LICENSE`**:
  - Lines 1-21: Contains standard, complete MIT License text copyright 2026 TransfereGov API Contributors.
- **`docs/ONBOARDING.md`**:
  - Line 79: `Conforme especificado em `MIGRATIONS.md`, aplique todas as migrações SQL na sequência numérica:`
  - Line 152: `./run.sh report emenda       # Totais por autor de emenda`
- **`src/db_report.py`**:
  - Line 51: `"emenda": """ SELECT ... FROM v_planos_completo ... """`
- **`run.sh`**:
  - Line 69: `$PYTHON "$SRC/transferegov_extract.py" --objeto 301 --ano 2026 "${@:2}"`
  - Line 72: `$PYTHON "$SRC/transferegov_extract.py" --objeto 301 --ano 2026 --negados "${@:2}"`
  - Line 85: `$PYTHON -m uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8080`
  - Line 100: `$PYTHON "$SRC/transferegov_extract.py" --objeto all --ano 2026 --csv "${@:2}"`

## 2. Logic Chain
1. **Port 8080 & License link in `README.md`**:
   - Observations show `README.md` consistently documents `http://localhost:8080` for `./run.sh web` in lines 25, 33, 55, 184, 188, and 190, matching `run.sh` line 85 (`--port 8080`).
   - Line 251 in `README.md` contains the valid Markdown link `[LICENSE](LICENSE)`.
2. **Valid MIT License text in `LICENSE`**:
   - `LICENSE` exists at project root and contains the standard open-source MIT License text with copyright 2026.
3. **Onboarding guide fixes in `docs/ONBOARDING.md`**:
   - Line 152 in `docs/ONBOARDING.md` references `./run.sh report emenda`, which matches `src/db_report.py` line 51 (`"emenda"` key in `QUERIES`).
   - Line 79 references `MIGRATIONS.md`, matching the migration guide location in `docs/MIGRATIONS.md`.
4. **Argument forwarding in `run.sh`**:
   - Lines 69, 72, 100 (as well as lines 75, 78, 81, 88, 91, 94, 97) use `"${@:2}"` to forward all positional parameters starting from the second parameter to Python CLI tools.
   - Example: `./run.sh cemiterios --db --csv` passes `--db --csv` directly to `transferegov_extract.py`, working cleanly without dropping flags.

## 3. Caveats
- Direct shell execution of `run.sh` in this environment was restricted by subagent non-interactive CLI timeout, but full static code analysis and AST/syntax inspections were performed on all targets.
- No integrity violations, hardcoded test facades, or bypassed logic were found.

## 4. Conclusion
**Verdict**: **APPROVE**
The remediation work implemented in Milestone M2 Iteration 2 is complete, accurate, robust, and fully satisfies all documentation and CLI forwarding requirements.

## 5. Verification Method
1. Inspect `README.md` lines 25, 184, 251 to confirm port 8080 and license link.
2. Inspect `LICENSE` root file for standard MIT license text.
3. Inspect `docs/ONBOARDING.md` lines 79 and 152 for `./run.sh report emenda` and `MIGRATIONS.md`.
4. Inspect `run.sh` lines 69, 72, 100 for `"${@:2}"` argument forwarding.
