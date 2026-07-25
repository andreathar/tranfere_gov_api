# Manual de Padrões de Desenvolvimento e Revisão Automatizada de Código — TransfereGov API

Este documento estabelece as diretrizes de desenvolvimento, padrões de estilo de código, tipagem estrita, configuração de hooks locais de `pre-commit`, workflows de Integração Contínua (CI/CD) e procedimentos de testes para o projeto **TransfereGov API**.

---

## 1. Padrões de Estilo e Qualidade de Código (Ruff)

O projeto adota o **Ruff** como linter e formatador de código padronizado para Python 3.11+.

### 1.1. Configuração do Ruff (`pyproject.toml`)
As regras ativas do Ruff estão definidas em `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py311"
line-length = 99

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]
ignore = [
    "E501",   # Comprimento de linha gerenciado pelo formatador
    "B905",   # zip() strict= (ignorado temporariamente para loops legados)
    "SIM105", # contextlib.suppress (ignorado temporariamente para compatibilidade)
]

[tool.ruff.lint.isort]
known-first-party = ["config", "src"]
```

### 1.2. Regras Aplicadas
- **`E` / `W` (Pycodestyle)**: Erros e avisos de formatação PEP 8.
- **`F` (Pyflakes)**: Detecção de variáveis não utilizadas, imports duplicados ou ausentes e erros de sintaxe.
- **`I` (isort)**: Ordenação automática de imports, separando pacotes de terceiros dos módulos locais (`config`, `src`).
- **`UP` (pyupgrade)**: Modernização automática de sintaxe Python 3.11+ (ex: sintaxe generativa `list[str]` em vez de `typing.List[str]`).
- **`B` (flake8-bugbear)**: Prevenção de falhas de design, valores padrão mutáveis e bugs comuns.
- **`SIM` (flake8-simplify)**: Simplificação de expressões booleanas e estruturas de controle redundantes.

### 1.3. Comandos do Ruff
```bash
# Verificar problemas de código e linters
ruff check .

# Corrigir automaticamente problemas identificados pelo linter
ruff check . --fix

# Formatar todos os arquivos Python
ruff format .

# Verificar formatação sem alterar arquivos
ruff format . --check
```

---

## 2. Tipagem Estrita e Verificação Estática (MyPy)

Todos os módulos Python na pasta `src/`, `config/` e `tests/` devem possuir anotações de tipo válidas.

### 2.1. Configuração do MyPy (`pyproject.toml`)
```toml
[tool.mypy]
python_version = "3.11"
strict = false
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true
explicit_package_bases = true
mypy_path = "."
```

### 2.2. Pacotes de Tipos (Stubs) Instalados
Para garantir validação estrita com bibliotecas de terceiros, as seguintes stubs estão configuradas em `pyproject.toml` / `requirements.txt`:
- `types-requests`: Tipagem para chamadas HTTP da API Transferegov, BrasilAPI e Câmara.
- `types-psycopg2`: Tipagem para conexões e cursores do PostgreSQL.
- `pandas-stubs`: Tipagem para DataFrames e Series do pandas.

### 2.3. Boas Práticas de Tipagem
1. **Anotação PEP 484 Obrigatória**: Todas as funções devem anotar tipos de argumentos e retorno.
   ```python
   def obter_resumo_parlamentar(deputado_id: int) -> dict[str, Any]:
   ```
2. **Generics Nativos (Python 3.11+)**: Use `list[...]`, `dict[...]`, `tuple[...]`, `set[...]` diretamente sem importar `List`, `Dict`, etc. de `typing`.
3. **Uso de `Any` Explícito**: Sempre importe `Any` explicitamente de `typing` (`from typing import Any`).

### 2.4. Comandos do MyPy
```bash
# Executar verificação de tipos no código-fonte
mypy src/

# Executar verificação de tipos nas configurações e testes
mypy config/ tests/
```

---

## 3. Configuração e Execução de Pre-commit Hooks Locais

O projeto utiliza `pre-commit` para interceptar commits locais e garantir que todo código atenda às exigências antes de ser salvo no histórico do Git.

### 3.1. Pipeline de Hooks (`.pre-commit-config.yaml`)
O arquivo `.pre-commit-config.yaml` configura as seguintes etapas automatizadas:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-merge-conflict

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        additional_dependencies:
          - types-requests
          - types-psycopg2
          - pandas-stubs
```

### 3.2. Instalação e Uso
```bash
# 1. Ativar ambiente virtual
source .venv/bin/activate

# 2. Instalar dependências em modo editável com dev extras
pip install -e ".[dev]"

# 3. Instalar os ganchos do git
pre-commit install

# 4. Executar verificação manual em todos os arquivos
pre-commit run --all-files
```

### 3.3. Resolução de Falhas de Pre-commit
- Se o `ruff` ou os fixers de arquivo (`trailing-whitespace`, `end-of-file-fixer`) alterarem arquivos automaticamente, revise as mudanças com `git diff`, adicione os arquivos com `git add .` e re-execute `pre-commit run --all-files`.
- Se o `mypy` indicar falhas de tipagem, corrija as anotações no código antes de prosseguir.

---

## 4. Integração Contínua (GitHub Actions CI/CD)

Toda alteração submetida via Pull Request ou Push para as branches `main` ou `master` é validada pelo GitHub Actions (`.github/workflows/ci.yml`).

### 4.1. Estrutura do Workflow CI (`.github/workflows/ci.yml`)
```yaml
name: CI

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

jobs:
  quality:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Cache Pre-Commit
        uses: actions/cache@v4
        with:
          path: ~/.cache/pre-commit
          key: pre-commit-${{ runner.os }}-${{ matrix.python-version }}-${{ hashFiles('.pre-commit-config.yaml') }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Install pre-commit
        run: pre-commit install

      - name: Run pre-commit checks
        run: pre-commit run --all-files

      - name: Run tests
        run: pytest
```

### 4.2. Recursos da Pipeline de CI
- **Matriz de Execução Multi-Versão**: Executa testes em ambientes Python 3.11 e Python 3.12.
- **Cache de Dependências**: Armazena em cache o diretório `~/.cache/pre-commit` para otimizar o tempo de execução dos trabalhos.
- **Bloqueio de PRs (Gatekeeper)**: PRs não podem ser consolidados caso ocorra qualquer erro no `pre-commit` ou no `pytest`.

---

## 5. Suíte de Testes & Verificação de Gráficos

O projeto possui duas suítes de teste automatizadas para validação funcional e visual.

### 5.1. Testes Unitários e de Integração (`pytest`)
- Configurado em `pyproject.toml` sob a seção `[tool.pytest.ini_options]`.
- Execução:
  ```bash
  pytest
  ```

### 5.2. Suíte de Auditoria de Gráficos (`src/verify_graphs.py`)
Valida a integridade, resiliência e ausência de telas brancas em todos os 31 gráficos registrados no dashboard Dash (`CHART_REGISTRY`).

- Checa a contagem de pontos de dados (`x`, `y`, `values`, `z`, `locations`, `link.value`).
- Garante o funcionamento do wrapper anti-falha `safe_build_chart`.
- Execução:
  ```bash
  python3 src/verify_graphs.py
  ```

---

## 6. Fluxo de Trabalho de Contribuição e Pull Requests

1. **Nomenclatura de Branches**:
   - `feature/<nome>`: Novas funcionalidades ou novos gráficos.
   - `fix/<descricao>`: Correções de bugs ou rotas.
   - `docs/<topico>`: Atualizações de documentação.
   - `refactor/<modulo>`: Refatoração de código sem alteração funcional.
2. **Mensagens de Commit**: Mensagens em Português (PT-BR), concisas e sem emojis.
3. **Checklist Pré-Submissão de PR**:
   - [ ] Executou `pre-commit run --all-files` com 100% de aprovação.
   - [ ] Executou `pytest` com sucesso.
   - [ ] Executou `python3 src/verify_graphs.py` com sucesso.
   - [ ] Garantia de que a pipeline do GitHub Actions passou em Python 3.11 e 3.12.
