# Analysis Report: Remediation of CLI Argument Forwarding in `run.sh`

## Executive Summary
In `run.sh`, the case blocks `cemiterios)`, `negados)`, and `all)` currently do not forward extra CLI flags (such as `--db`, `--csv`, `-v`, `--uf SP`) correctly to `src/transferegov_extract.py`:
- `cemiterios)` and `negados)` pass `"$@"`, which includes `$1` (the sub-command string `"cemiterios"` or `"negados"`), causing `transferegov_extract.py` to receive an unparsed positional argument.
- `all)` does not pass any trailing CLI arguments, ignoring flags like `--db` when running `./run.sh all --db`.

Updating these three case blocks to use `"${@:2}"` ensures that all arguments starting from position 2 are passed cleanly to the underlying Python script, matching the convention already used by `import)`, `report)`, `dashboard)`, `enrich)`, `validate)`, `ibge)`, and `camara)`.

---

## Direct Observations & Code Audit

### File: `run.sh` (lines 64–111)

```bash
64: case "${1:-help}" in
65:     discover)
66:         $PYTHON "$SRC/transferegov_extract.py" --discover --ano 2026
67:         ;;
68:     cemiterios)
69:         $PYTHON "$SRC/transferegov_extract.py" --objeto 301 --ano 2026 "$@"
70:         ;;
71:     negados)
72:         $PYTHON "$SRC/transferegov_extract.py" --objeto 301 --ano 2026 --negados "$@"
73:         ;;
74:     import)
75:         $PYTHON "$SRC/db_import.py" "${@:2}"
76:         ;;
...
99:     all)
100:         $PYTHON "$SRC/transferegov_extract.py" --objeto all --ano 2026 --csv
101:         ;;
```

### Analysis of Current Behavior

1. **`cemiterios` Case Block (lines 68–70)**:
   - Current: `$PYTHON "$SRC/transferegov_extract.py" --objeto 301 --ano 2026 "$@"`
   - When executing `./run.sh cemiterios --db`:
     - `$1` = `"cemiterios"`
     - `$2` = `"--db"`
     - `"$@"` expands to `"cemiterios"` `"--db"`
   - Executed Command: `python3 src/transferegov_extract.py --objeto 301 --ano 2026 cemiterios --db`
   - **Fault**: The string `"cemiterios"` is passed as a positional argument to `transferegov_extract.py`.

2. **`negados` Case Block (lines 71–73)**:
   - Current: `$PYTHON "$SRC/transferegov_extract.py" --objeto 301 --ano 2026 --negados "$@"`
   - When executing `./run.sh negados --db`:
     - `$1` = `"negados"`
     - `$2` = `"--db"`
     - `"$@"` expands to `"negados"` `"--db"`
   - Executed Command: `python3 src/transferegov_extract.py --objeto 301 --ano 2026 --negados negados --db`
   - **Fault**: The string `"negados"` is passed as a positional argument to `transferegov_extract.py`.

3. **`all` Case Block (lines 99–101)**:
   - Current: `$PYTHON "$SRC/transferegov_extract.py" --objeto all --ano 2026 --csv`
   - When executing `./run.sh all --db`:
     - `$1` = `"all"`
     - `$2` = `"--db"`
     - `"${@:2}"` is omitted entirely.
   - Executed Command: `python3 src/transferegov_extract.py --objeto all --ano 2026 --csv`
   - **Fault**: `--db` flag is dropped, so data is not saved to PostgreSQL despite `./run.sh all --db` being documented in `AGENTS.md`.

---

## Step-by-Step Fix Specification for Worker

### Target File
`/mnt/data/Projects_SSD/tranfere_gov_api/run.sh`

### Edit 1: Fix `cemiterios)` and `negados)` case blocks
- **Lines**: 68–73
- **Target Content**:
```bash
    cemiterios)
        $PYTHON "$SRC/transferegov_extract.py" --objeto 301 --ano 2026 "$@"
        ;;
    negados)
        $PYTHON "$SRC/transferegov_extract.py" --objeto 301 --ano 2026 --negados "$@"
        ;;
```
- **Replacement Content**:
```bash
    cemiterios)
        $PYTHON "$SRC/transferegov_extract.py" --objeto 301 --ano 2026 "${@:2}"
        ;;
    negados)
        $PYTHON "$SRC/transferegov_extract.py" --objeto 301 --ano 2026 --negados "${@:2}"
        ;;
```

### Edit 2: Fix `all)` case block
- **Lines**: 99–101
- **Target Content**:
```bash
    all)
        $PYTHON "$SRC/transferegov_extract.py" --objeto all --ano 2026 --csv
        ;;
```
- **Replacement Content**:
```bash
    all)
        $PYTHON "$SRC/transferegov_extract.py" --objeto all --ano 2026 --csv "${@:2}"
        ;;
```

---

## Verification Plan

After applying the edits, the Worker or Reviewer can verify the fix by running:
1. Syntax check: `bash -n run.sh`
2. Test commands with extra CLI flags:
   - `./run.sh cemiterios --help`
   - `./run.sh negados --help`
   - `./run.sh all --help`
3. Verify pre-commit check: `pre-commit run --all-files`
