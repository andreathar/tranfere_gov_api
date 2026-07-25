# Analysis & Onboarding Blueprint — TransfereGov API

**Milestone**: M2 (Requirement R2: Project Documentation & Onboarding)  
**Target Document**: `docs/ONBOARDING.md`  
**Author**: Explorer Subagent M2.2  
**Date**: 2026-07-25  

---

## Executive Summary

This report contains a complete, verified, step-by-step blueprint for `docs/ONBOARDING.md`. It covers everything required for a new developer to set up the environment, provision the PostgreSQL database, execute the extraction and enrichment data pipeline, launch the local FastAPI backend and Dash/MCP servers, and perform verification and troubleshooting.

All commands, file paths, configurations, environment variables, schema definitions, and migration sequences have been audited against the actual codebase files (`pyproject.toml`, `requirements.txt`, `config/settings.py`, `data/schema.sql`, `data/migration_*.sql`, `docs/MIGRATIONS.md`, `run.sh`, `src/api/app.py`, `src/dash_app.py`, `src/verify_graphs.py`, `AGENTS.md`).

---

## Onboarding Blueprint (`docs/ONBOARDING.md` Proposed Content)

```markdown
# Guia de Onboarding de Desenvolvimento — TransfereGov API

Este documento fornece um passo a passo completo para configuração do ambiente de desenvolvimento, provisionamento do banco de dados PostgreSQL, execução do pipeline de dados e enriquecimento, e inicialização dos serviços web locais (FastAPI e Plotly Dash MCP).

---

## 1. Pré-requisitos

Antes de iniciar a instalação, certifique-se de que as ferramentas abaixo estão instaladas no seu ambiente operacional Linux / macOS:

- **Python**: versão 3.11 ou superior (recomendado `python3.11`)
- **PostgreSQL**: versão 14 ou superior (com utilitários de CLI `createdb` e `psql`)
- **Git**: para controle de versão e instalação dos hooks de pre-commit
- **virtualenv / venv**: módulo nativo do Python para ambientes virtuais

---

## 2. Configuração do Ambiente

Siga as etapas abaixo para clonar o repositório, criar e ativar o ambiente virtual, e instalar as dependências do projeto.

### 2.1. Clonar o Repositório
```bash
git clone https://github.com/seu-usuario/tranfere_gov_api.git
cd tranfere_gov_api
```

### 2.2. Criar e Ativar o Ambiente Virtual
```bash
# Criar o ambiente virtual na pasta .venv
python3.11 -m venv .venv

# Ativar o ambiente virtual
source .venv/bin/activate
```

### 2.3. Instalar Dependências (Modo Editável + Dev)
```bash
# Instalar o pacote local com suporte a dependências de desenvolvimento
pip install -e ".[dev]"
```

### 2.4. (Recomendado) Configurar Pre-Commit Hooks
Para garantir a aderência às regras de qualidade de código (linter `ruff` e checagem de tipos `mypy`), instale os hooks no repositório local:
```bash
pre-commit install
```

---

## 3. Provisionamento do Banco de Dados PostgreSQL

O projeto exige o PostgreSQL em execução com a base de dados `transferegov_db`.

### 3.1. Configuração do Usuário e Banco de Dados
Por padrão, o sistema utiliza as seguintes credenciais de desenvolvimento (definidas em `config/settings.py`):
- **Host**: `127.0.0.1` (variável `PGHOST`)
- **Porta**: `5432` (variável `PGPORT`)
- **Banco**: `transferegov_db` (variável `PGDATABASE`)
- **Usuário**: `cognee` (variável `PGUSER`)
- **Senha**: `cognee` (variável `PGPASSWORD`)

Se o usuário e o banco ainda não existirem no PostgreSQL local, crie-os com o comando:
```bash
# Criar usuário cognee (caso não exista)
sudo -u postgres psql -c "CREATE USER cognee WITH PASSWORD 'cognee' SUPERUSER;"

# Criar o banco de dados transferegov_db
createdb -h 127.0.0.1 -U cognee transferegov_db
```

### 3.2. Aplicação do Schema Base
Execute o script de schema base (`data/schema.sql`):
```bash
psql -U cognee -h 127.0.0.1 -d transferegov_db -f data/schema.sql
```

### 3.3. Execução das Migrações SQL em Ordem
Conforme especificado em `docs/MIGRATIONS.md`, aplique todas as migrações SQL na sequência numérica:
```bash
# Aplicar todas as migrações na ordem correta
for f in data/migration_*.sql; do
    echo "Aplicando migração: $f..."
    psql -U cognee -h 127.0.0.1 -d transferegov_db -f "$f"
done
```

#### Relação Sequencial de Migrações:
1. `data/migration_002_relatorios.sql` — Tabelas core de relatórios
2. `data/migration_003_enrichment.sql` — Tabelas de enriquecimento (CNPJ, IBGE, Câmara)
3. `data/migration_004_ibge_agregados.sql` — Colunas agregadas do IBGE (população, PIB, área)
4. `data/migration_005_unificacao.sql` — Emendas discricionárias e views unificadas
5. `data/migration_006_datajud.sql` — Cache de processos judiciais DataJud
6. `data/migration_007_siconfi.sql` — Dados financeiros municipais (SICONFI / Tesouro Nacional)
7. `data/migration_008_enriched_views.sql` — Views cruzadas de dados enriquecidos
8. `data/migration_009_novas_fontes.sql` — Compras públicas, saúde, educação e segurança
9. `data/migration_010_prefeitos.sql` — Tabelas e views de inteligência municipal / prefeituras
10. `data/migration_011_tse_deputados.sql` — Cruzamento de dados de deputados com o TSE

---

## 4. Pipeline de Dados & Enriquecimento

O pipeline de dados opera em duas etapas: extração/ingestão e enriquecimento de dados multi-fonte.

### 4.1. Descobrimento e Extração de Planos de Ação (API Transferegov)
Você pode utilizar o script wrapper `./run.sh` ou invocar diretamente o CLI de extração:

```bash
# 1. Descobrir os objetos de execução disponíveis para o exercício atual (2026)
./run.sh discover

# 2. Extrair TODOS os objetos de 2026 e persistir no PostgreSQL
./run.sh all --db

# Extração customizada por programa e situação (exemplo: Transferências Especiais + IMPEDIDO)
python3 src/transferegov_extract.py --objeto all --ano 2026 --programa 25 --situacao-api IMPEDIDO --db --csv
```

### 4.2. Importação Manual de Arquivos JSON (Opcional)
Se houver arquivos JSON pré-existentes na pasta `output/json/`:
```bash
./run.sh import
```

### 4.3. Pipeline de Enriquecimento Multi-Fase
Após popular o PostgreSQL com os planos de ação base, execute o pipeline de enriquecimento (BrasilAPI + IBGE + Câmara dos Deputados):

```bash
# Execução completa de todas as fases de enriquecimento (Fases 1 a 3)
python3 -m src.enrichers.pipeline --fase all

# (Opcional) Teste sem alterações em banco com limite de registros:
python3 -m src.enrichers.pipeline --fase all --dry-run --limit 100
```

#### Fases Individuais do Pipeline:
- **Fase 1 (Validação & IBGE)**:
  `python3 -m src.enrichers.validacao` (CNPJs via BrasilAPI)  
  `python3 -m src.enrichers.ibge` (Dados de municípios IBGE)  
  `python3 -m src.enrichers.mapear_municipios` (Mapeamento beneficiário → IBGE)  
- **Fase 2 (Câmara dos Deputados)**:
  `python3 -m src.enrichers.camara` (Perfil dos parlamentares)  
- **Fase 3 (Agregação & Vinculação)**:
  `python3 -m src.enrichers.pipeline --fase 3` (Cruzamento parlamentar × beneficiário × emenda)

### 4.4. Emissão de Relatórios SQL via CLI
```bash
./run.sh report resumo       # Resumo estatístico geral
./run.sh report estado       # Resumo por Estado (UF)
./run.sh report negados      # Planos impedidos/negados
./run.sh report parlamentar  # Totais por autor de emenda
```

---

## 5. Execução dos Serviços Web Locais

O sistema possui duas aplicações web independentes que podem ser executadas concorrentemente.

### 5.1. Backend API REST & Painel Web (FastAPI)
Painel de Inteligência Parlamentar & Municipal e API REST.

- **Comando**:
  ```bash
  uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
  ```
  *(Alternativamente, via wrapper: `./run.sh web` no port 8080)*
- **Endereço da Interface Web**: `http://localhost:8000`
- **Documentação Swagger (OpenAPI)**: `http://localhost:8000/docs`
- **Documentação ReDoc**: `http://localhost:8000/redoc`

### 5.2. Dashboard Analítico Interativo & Servidor MCP (Plotly Dash 4.3+)
Dashboard com 31 gráficos Plotly e servidor MCP (Model Context Protocol) integrado para agentes autônomos de IA.

- **Comando**:
  ```bash
  python3 src/dash_app.py
  ```
- **Endereço da Interface Web (Dash)**: `http://localhost:8050`
- **Endpoint do Servidor MCP**: `http://localhost:8050/_mcp`

---

## 6. Verificação & Solução de Problemas (Troubleshooting)

### 6.1. Verificação da Instalação e Testes Automatizados

#### Executar a Suíte de Testes com Pytest:
```bash
pytest
```

#### Validar Estilo, Linting e Tipagem Estrita:
```bash
# Executar pre-commit em todos os arquivos
pre-commit run --all-files

# Executar ruff e mypy individualmente
ruff check .
mypy src config tests
```

#### Auditar a Integridade dos 31 Gráficos do Dashboard:
```bash
python3 src/verify_graphs.py
```

#### Testar Ferramentas CLI Interativas:
```bash
python3 src/deputado_followup.py --ranking
python3 src/prefeito_followup.py --ranking
```

---

### 6.2. Solução de Problemas Comuns (Troubleshooting)

| Sintoma / Erro | Causa Provável | Solução Recomendada |
|----------------|----------------|---------------------|
| `psycopg2.OperationalError: could not connect to server` | O serviço do PostgreSQL não está rodando localmente ou as variáveis de ambiente apontam para host/porta incorretos. | Verifique se o daemon do PostgreSQL está ativo (`sudo systemctl status postgresql`). Confirme as variáveis `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`. |
| `FATAL: database "transferegov_db" does not exist` | O banco de dados ainda não foi criado. | Execute `createdb -h 127.0.0.1 -U cognee transferegov_db` e aplique `data/schema.sql` e as migrações. |
| Timeout HTTP ao consultar a API do Transferegov | Restrição de IP / Geoblocking ou lentidão nos servidores do Governo Federal (`transferegov.sistema.gov.br`). | Verifique sua conexão à internet (IPs fora do Brasil podem sofrer bloqueio TCP). O sistema possui retry automático com exponencial backoff. |
| Gráfico exibe aviso "Dados em sincronização ou insuficientes" no Dash | O banco PostgreSQL não possui dados suficientes para a consulta do gráfico selecionado. | Execute `./run.sh all --db` e `python3 -m src.enrichers.pipeline --fase all` para popular o banco de dados. |
| `ModuleNotFoundError: No module named 'src'` | O pacote não foi instalado em modo editável ou o `PYTHONPATH` não inclui a raiz do projeto. | Execute `pip install -e ".[dev]"` na raiz do repositório ou execute com `PYTHONPATH=. python3 <script>`. |
```

---

## Validation & Evidence Chain

1. **Prerequisites & Python Version**:
   - `pyproject.toml` explicitly specifies `requires-python = ">=3.11"`.
   - `pyproject.toml` uses `target-version = "py311"` for `ruff` and `python_version = "3.11"` for `mypy`.
2. **Setup Commands**:
   - Package setup uses `pip install -e ".[dev]"` with `pyproject.toml` defining optional dependencies under `[project.optional-dependencies] dev = [...]`.
   - `pre-commit` is included in dev dependencies and configured via `.pre-commit-config.yaml`.
3. **Database Setup**:
   - `config/settings.py` sets defaults: host `127.0.0.1`, port `5432`, db `transferegov_db`, user `cognee`, pass `cognee`.
   - Base schema is `data/schema.sql`.
   - Migrations in `data/` range from `migration_002_relatorios.sql` through `migration_011_tse_deputados.sql`.
4. **Pipeline & Enrichers**:
   - Extractions use `./run.sh` wrappers around `src/transferegov_extract.py`.
   - Enrichers use `src.enrichers.pipeline`, `src.enrichers.validacao`, `src.enrichers.ibge`, `src.enrichers.camara`.
5. **Web Services**:
   - FastAPI server: `uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000`.
   - Dash & MCP server: `python3 src/dash_app.py` listening on port `8050` with endpoint `/_mcp`.
6. **Verification & Auditing**:
   - `pytest` for unit/integration tests.
   - `pre-commit run --all-files` for linting/formatting/types.
   - `python3 src/verify_graphs.py` for health audit of all 31 Plotly graphs.
