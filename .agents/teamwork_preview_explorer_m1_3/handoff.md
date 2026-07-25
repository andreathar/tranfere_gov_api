# Handoff Report: GitHub Actions CI Workflow Blueprint (R1 / M1)

## 1. Observation
- Target CI file `.github/workflows/ci.yml` currently does not exist in the repository root `/mnt/data/Projects_SSD/tranfere_gov_api/` (confirmed via `find_by_name`).
- Project configuration (`pyproject.toml` lines 25-32 & `requirements.txt` lines 29-35) defines Python `>=3.11` compatibility and `dev` dependencies (`pytest`, `pytest-asyncio`, `respx`, `ruff`, `mypy`).
- Peer explorer `teamwork_preview_explorer_m1_2` established the `.pre-commit-config.yaml` blueprint with `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-added-large-files`, `check-merge-conflict`, `ruff`, `ruff-format`, and `mypy` with type stubs (`types-requests`, `types-psycopg2`, `pandas-stubs`).
- Unit test suite is located in `/mnt/data/Projects_SSD/tranfere_gov_api/tests/` (configured in `pyproject.toml` lines 62-66: `testpaths = ["tests"]`, `python_files = ["test_*.py"]`).
- Latest GitHub Actions standards: `actions/checkout@v4`, `actions/setup-python@v5`, `actions/cache@v4`.

## 2. Logic Chain
1. *Observation*: Requirement R1 and PROJECT.md contract specify automated CI execution via GitHub Actions for Python 3.11 and 3.12.
2. *Inference*: The CI workflow must include a matrix strategy for `python-version: ["3.11", "3.12"]` on `ubuntu-latest`.
3. *Observation*: The project relies on `.pre-commit-config.yaml` for formatting, linting, YAML validation, and type checking.
4. *Inference*: Caching `~/.cache/pre-commit` using `actions/cache@v4` with key `pre-commit-${{ runner.os }}-${{ matrix.python-version }}-${{ hashFiles('.pre-commit-config.yaml') }}` ensures fast pre-commit execution without re-downloading environment hooks on every run.
5. *Observation*: The python dependencies require `pip install -e ".[dev]"` for proper package installation and CLI entry points.
6. *Inference*: Step execution order must be: Checkout repo -> Setup Python -> Cache pre-commit -> Install editable package with dev dependencies -> Install pre-commit hooks -> Run pre-commit checks (`pre-commit run --all-files`) -> Run unit test suite (`pytest`).

## 3. Caveats
- GitHub Actions execution can only run when committed to a GitHub repository with GitHub Actions runner enabled.
- Pre-commit cache will miss initially on the first CI run, but populate for subsequent commits/PRs.

## 4. Conclusion
The exact blueprint for `.github/workflows/ci.yml` has been designed and documented in `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_m1_3/analysis.md`. The Worker can implement this file directly to satisfy requirement R1 and milestone M1.

## 5. Verification Method
- **File Inspection**: Verify existence and exact content of `.github/workflows/ci.yml`.
- **Pre-commit YAML Validation**: Run `pre-commit run check-yaml --all-files` locally to verify valid YAML syntax.
- **CI Trigger Verification**: Push a branch or open a PR to `main`/`master` and verify GitHub Actions runs jobs for Python 3.11 and 3.12, executing pre-commit checks and pytest successfully.
