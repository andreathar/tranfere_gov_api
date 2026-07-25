# Handoff Report: Formulate Fix Specifications for `run.sh` Argument Forwarding

## 1. Observation
Direct inspection of `/mnt/data/Projects_SSD/tranfere_gov_api/run.sh` using `view_file` revealed the following case block definitions:

1. **`cemiterios)` block (lines 68–70)**:
   ```bash
   cemiterios)
       $PYTHON "$SRC/transferegov_extract.py" --objeto 301 --ano 2026 "$@"
       ;;
   ```
2. **`negados)` block (lines 71–73)**:
   ```bash
   negados)
       $PYTHON "$SRC/transferegov_extract.py" --objeto 301 --ano 2026 --negados "$@"
       ;;
   ```
3. **`all)` block (lines 99–101)**:
   ```bash
   all)
       $PYTHON "$SRC/transferegov_extract.py" --objeto all --ano 2026 --csv
       ;;
   ```
4. **Other case blocks (`import`, `report`, `dashboard`, `enrich`, `validate`, `ibge`, `camara`)**:
   All use `"${@:2}"` to slice positional arguments starting from index 2, omitting `$1` (the subcommand name).

## 2. Logic Chain
1. *From Observation 1 & 2*: Using `"$@"` passes all positional parameters including `$1` (`"cemiterios"` or `"negados"`). When a user executes `./run.sh cemiterios --db`, `$1` is `"cemiterios"` and `$2` is `"--db"`. Passing `"$@"` results in executing `python3 src/transferegov_extract.py --objeto 301 --ano 2026 cemiterios --db`, which passes the string `"cemiterios"` as an unintended argument to `transferegov_extract.py`.
2. *From Observation 3*: The `all)` block executes `$PYTHON "$SRC/transferegov_extract.py" --objeto all --ano 2026 --csv` without forwarding any additional CLI arguments. If a user runs `./run.sh all --db`, the `--db` flag is discarded completely.
3. *From Observation 4*: Standardizing `cemiterios)`, `negados)`, and `all)` to use `"${@:2}"` will correctly skip `$1` and forward all subsequent arguments (`$2`, `$3`, ...) to `transferegov_extract.py`, matching the existing behavior of `import)`, `report)`, `enrich)`, etc.

## 3. Caveats
- No caveats. The bash parameter expansion syntax `"${@:2}"` is standard in POSIX bash and already used consistently across all other case blocks in `run.sh`.

## 4. Conclusion
The worker must update `run.sh` to replace `"$@"` with `"${@:2}"` in `cemiterios)` and `negados)`, and append `"${@:2}"` to `all)`.

### Concrete Instructions for Implementation Worker:
- **File**: `run.sh`
- **Change 1 (lines 68–73)**:
  - Replace:
    ```bash
        cemiterios)
            $PYTHON "$SRC/transferegov_extract.py" --objeto 301 --ano 2026 "$@"
            ;;
        negados)
            $PYTHON "$SRC/transferegov_extract.py" --objeto 301 --ano 2026 --negados "$@"
            ;;
    ```
  - With:
    ```bash
        cemiterios)
            $PYTHON "$SRC/transferegov_extract.py" --objeto 301 --ano 2026 "${@:2}"
            ;;
        negados)
            $PYTHON "$SRC/transferegov_extract.py" --objeto 301 --ano 2026 --negados "${@:2}"
            ;;
    ```
- **Change 2 (lines 99–101)**:
  - Replace:
    ```bash
        all)
            $PYTHON "$SRC/transferegov_extract.py" --objeto all --ano 2026 --csv
            ;;
    ```
  - With:
    ```bash
        all)
            $PYTHON "$SRC/transferegov_extract.py" --objeto all --ano 2026 --csv "${@:2}"
            ;;
    ```

## 5. Verification Method
1. Run bash syntax check: `bash -n run.sh`
2. Test CLI argument parsing dry-run (e.g. `./run.sh cemiterios --help`, `./run.sh negados --help`, `./run.sh all --help`).
3. Run `pre-commit run --all-files` to confirm code style and linting compliance.
