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
- Cobertura: schemas Pydantic, utilitários de formatação (`fmt_brl`, `fmt_num`, `fmt_pct`), upsert idempotente, parsers de dados (SICONFI, IBGE, TSE) e endpoints FastAPI.
- Execução:
  ```bash
  pytest                          # Todos os testes
  pytest -v                       # Saída detalhada
  pytest tests/test_schemas.py    # Módulo específico
  ```

### 5.2. Suíte de Auditoria de Gráficos (`src/verify_graphs.py`)
Valida a integridade, resiliência e ausência de telas brancas em todos os 68 gráficos registrados no dashboard Dash (`CHART_REGISTRY`), distribuídos em 17 módulos (`src/graphs/`).

- Para cada gráfico: verifica retorno `go.Figure`, contagem de traces e pontos de dados (`x`, `y`, `values`, `z`, `locations`, `link.value`), tempo de resposta e ausência de erros.
- Garante o funcionamento do wrapper anti-falha `safe_build_chart` (captura exceções SQL, dados ausentes e erros inesperados).
- Execução:
  ```bash
  python3 src/verify_graphs.py
  ```
- A saída gera um relatório consolidado com contagem de gráficos OK, com aviso, com erro e tempo total.

---

## 6. Padrões de Código LocalAI

O projeto integra modelos de linguagem locais via API compatível OpenAI. Três módulos formam a camada de integração: gerenciamento de VRAM, cliente HTTP e configuração centralizada de modelos.

### 6.1. Gerenciamento de VRAM (`src/localai_manager.py`)

Antes de invocar qualquer modelo, **sempre** chamar `ensure_model_loaded()` para garantir exclusividade de VRAM na GPU. Esta função descarrega todos os modelos inativos antes de carregar o modelo alvo, eliminando erros de estouro de memória (OOM / RPC EOF).

```python
from src.localai_manager import manager as localai_manager

# Obrigatorio antes de qualquer chamada de modelo
localai_manager.ensure_model_loaded("gemma-4-e2b-it")
```

Fluxo interno de `ensure_model_loaded(target_model)`:
1. Lista todos os modelos carregados via `get_all_models()`.
2. Para cada modelo diferente de `target_model`, verifica se esta carregado via `is_model_loaded()`.
3. Descarrega modelos inativos via `unload_model()` (POST `/backend/shutdown`).

O singleton `manager` e instanciado uma vez no modulo e compartilhado por todos os consumidores.

### 6.2. Cliente HTTP (`src/localai_client.py`)

`LocalAIClient` e o cliente centralizado para todas as chamadas ao LocalAI. Fornece wrappers de alto nivel com retry, timeout e cache HTTP.

**Instancia singleton** via `get_localai_client()`:

```python
from src.localai_client import get_localai_client

client = get_localai_client()
```

**Metodos principais**:

| Metodo | Uso | Retorno |
|--------|-----|---------|
| `chat(prompt, system=, model=, temperature=, max_tokens=)` | Chat completion simples | `str` |
| `chat_json(prompt, system=, model=)` | Chat que retorna JSON parseado automaticamente | `Any` |
| `achat(prompt, ...)` | Versao async do chat | `str` (coroutine) |
| `chat_stream(prompt, ...)` | Streaming de tokens | `Iterator[str]` |
| `classify_batch(texts, labels=, model=)` | Classificacao em lote de textos | `list[str]` |
| `embed(texts, model=)` | Gera embeddings para textos | `list[list[float]]` |
| `enrich_column(df, column, task=)` | Aplica tarefa de IA em coluna de DataFrame | `pd.DataFrame` |
| `summarize_plans(df, group_by=)` | Gera resumos analiticos por grupo | `pd.DataFrame` |
| `submit_job(prompt, ...)` | Job assincrono (batch processing) | `dict` |
| `health()` | Verifica se o LocalAI esta respondendo | `dict` |

O metodo `_post()` implementa retry com backoff exponencial (`LOCALAI_MAX_RETRIES`) e cache HTTP de 7 dias via `http_cache.py`.

### 6.3. Selecao de Modelos (`config/settings.py`)

Todos os modelos estao centralizados no dicionario `LOCALAI_MODELS`. **Nunca** hardcode o nome de um modelo -- sempre importe de `config.settings`:

```python
from config.settings import LOCALAI_MODELS, LOCALAI_DEFAULT_MODEL

# Usar alias para selecionar modelo
model_id = LOCALAI_MODELS["gemma"]       # "gemma-4-e2b-it"
model_id = LOCALAI_MODELS["fast"]        # "qwen2.5-1.5b-instruct-q4-k-m"
model_id = LOCALAI_MODELS["analysis"]    # "llama-3.1-8b-q4-k-m"
model_id = LOCALAI_MODELS["embedding"]   # "nomic-embed-text-v1.5"
```

| Alias | Modelo | Uso Recomendado | Velocidade |
|-------|--------|-----------------|------------|
| `gemma` | `gemma-4-e2b-it` | Padrao RAG, redacao PT-BR | 36.8 tok/s |
| `fast` | `qwen2.5-1.5b-instruct-q4-k-m` | Triagem diaria, NER | 88.9 tok/s |
| `analysis` | `llama-3.1-8b-q4-k-m` | Analise investigativa profunda | 7.7 tok/s |
| `code` | `Qwen2.5-Coder-7B-Instruct-GGUF` | Codigo | -- |
| `general` | `gemma-4-e2b-it` | Uso geral | 36.8 tok/s |
| `embedding` | `nomic-embed-text-v1.5` | Embeddings Qdrant (768d) | -- |
| `router` | `intelligent-router` | Roteamento inteligente | -- |

### 6.4. Padrão de Uso Completo

```python
from src.localai_manager import manager as localai_manager
from src.localai_client import get_localai_client
from config.settings import LOCALAI_MODELS

# 1. Garantir VRAM exclusiva
localai_manager.ensure_model_loaded(LOCALAI_MODELS["gemma"])

# 2. Obter cliente singleton
client = get_localai_client()

# 3. Usar metodo apropriado
resumo = client.chat(
    "Gere um resumo do deputado AFONSO FLORENCE",
    system="Voce e um analista politico.",
    model=LOCALAI_MODELS["gemma"],
)

# Para classificacao em lote
categorias = client.classify_batch(
    ["motivo A", "motivo B"],
    labels=["FALTA_DOCUMENTACAO", "IRREGULARIDADE", "OUTROS"],
    model=LOCALAI_MODELS["fast"],
)
```

### 6.5. Pitfalls

1. **VRAM**: Sempre chamar `ensure_model_loaded()` antes de operacoes pesadas -- modelos concorrentes causam OOM.
2. **Singleton**: Usar `get_localai_client()` ao inves de instanciar `LocalAIClient()` diretamente.
3. **Modelos**: Nunca hardcode nomes de modelos -- use `LOCALAI_MODELS["alias"]`.
4. **Embeddings**: O modelo `nomic-embed-text-v1.5` gera vetores de 768d -- nao misturar dimensoes no Qdrant.
5. **Cache**: Respostas do LLM sao cacheadas por 7 dias -- limpar `output/.http_cache/` se necessario.

---

## 7. Padrões MCP Bridge

O `MCPToolBridge` (`src/mcp_tool_bridge.py`) converte ferramentas MCP (FastMCP) para o formato OpenAI function calling, permitindo que modelos locais invoquem tools governamentais e do dashboard.

### 7.1. Arquitetura

```
LLM LocalAI  <--function calling-->  MCPToolBridge  <--MCP protocol-->  mcp-brasil server (435+ tools)
                                         |
                                   handler_map
                                   (bypass MCP session)
```

### 7.2. Instancia Singleton

```python
from src.mcp_tool_bridge import get_mcp_bridge

bridge = get_mcp_bridge()
```

### 7.3. Descoberta de Tools

O bridge usa **meta-tools** (`search_tools`, `call_tool`) do mcp-brasil para descoberta dinamica, combinadas com um conjunto curado de tools relevantes para o dominio TransfereGov. As tools sao categorizadas em `TOOL_CATEGORIES`:

| Categoria | Prefixos |
|-----------|----------|
| `camara` | `camara` |
| `senado` | `senado` |
| `tse` | `tse` |
| `ibge` | `ibge` |
| `siconfi` | `siconfi` |
| `compras` | `compras`, `pncp`, `contratosgovbr`, `dadosabertos` |
| `dashboard` | `list_registered_charts`, `inspect_chart_health`, `get_chart_data_summary` |
| `meta` | `listar_features`, `recomendar_tools`, `planejar_consulta`, `executar_lote` |

```python
# Listar tools por categoria
camara_tools = bridge.list_tools(category="camara")

# Busca por texto
tools = bridge.list_tools(search="deputado")
```

### 7.4. Conversao para OpenAI Function Calling

```python
# Converter para formato OpenAI (inclui meta-tools por padrao)
tools_schema = bridge.to_openai_tools(
    categories=["camara", "ibge"],
    max_tools=30,
    include_meta=True,
)

# Usar com o LocalAI client diretamente
client = get_localai_client()
resp = client.chat("...", tools=tools_schema)
```

### 7.5. Agentic Loop

O metodo `agent_chat()` implementa o loop completo chat -> tool_calls -> execute -> repeat:

```python
result = bridge.agent_chat(
    "Quais municipios de Alagoas receberam emendas Pix?",
    categories=["camara", "transferegov"],
    max_turns=5,
    temperature=0.3,
)

# Retorno: {"response": "...", "tool_calls": [...], "turns": 3, "tools_available": 15}
```

### 7.6. Execucao de Tools

O bridge resolve handlers em tres camadas:
1. **Handlers customizados** registrados via `register_tool()`.
2. **Handler map** (`_build_handler_map()`): mapeamento direto de nomes de tools para funcoes Python do mcp-brasil, bypassando a session MCP.
3. **Fallback MCP**: `call_tool()` via session MCP (pode falhar sem session ativa).

O `_wrap_no_ctx()` envolve funcoes MCP async que exigem parametro `ctx` (FastMCP Context) para serem chamadas sem esse parametro -- injeta um mock minimo.

### 7.7. Pitfalls

1. **Handler map**: Construido sob demanda na primeira chamada -- importa modulos do mcp-brasil.
2. **Max tools**: LocalAI pode ter limites de tools -- usar `max_tools=30` como padrao.
3. **Tamanho de resultado**: Tool results sao truncados em 8000 chars antes de enviar ao LLM.
4. **Async/Sync**: Usar versoes async (`aagent_chat`, `execute_tool`) quando em contexto asyncio.

---

## 8. Padrões RAG

O pipeline RAG v3 combina indexacao vetorial no Qdrant com geracao de personas via LLM local. Dois modulos formam o nucleo: o indexador e o gerador de personas.

### 8.1. Indexador Vetorial (`src/enrichers/rag_qdrant_indexer.py`)

Indexa dados de deputados no Qdrant com embeddings `nomic-embed-text-v1.5` (768d, metrica Cosine).

**6 tipos de chunks indexados**:

| Tipo | Conteudo | Fonte DB |
|------|----------|----------|
| `perfil` | Nome, partido, UF do deputado | `parlamentares_dados` |
| `proposicao` | PLs e proposicoes legislativas | `parlamentar_proposicoes` |
| `emenda` | Emendas Pix com dados financeiros do municipio | `planos_acao` + `municipios_financeiro` |
| `voto` | Padrao de voto em votacoes nominais | `votacoes_camara` + `votos_camara` |
| `diario_oficial` | Atos do Diario Oficial da Uniao | `diario_oficial_atos` |
| `conexao_politica` | Partido do prefeito x partido do deputado | `prefeitos_dados` + `parlamentares_dados` |

```python
# Indexacao por deputado
python3 -m src.enrichers.rag_qdrant_indexer --nome "AFONSO FLORENCE"

# Rebuild completo (limpa e reindexa)
python3 -m src.enrichers.rag_qdrant_indexer --rebuild

# Via run.sh
./run.sh cron-qdrant --limit 10
```

**Requisitos**: Qdrant ativo em `QDRANT_URL` + modelo `nomic-embed-text-v1.5` carregado no LocalAI. A funcao `embed_text()` delega ao `LocalAIClient.embed()`.

### 8.2. Gerador de Personas (`src/enrichers/rag_persona.py`)

Gera dossies analiticos via Multi-Query RAG com 5 queries tematicas:

1. Padrao de voto e alinhamento politico em votacoes nominais.
2. Emendas parlamentares Pix, municipios beneficiarios e valores transferidos.
3. Proposicoes legislativas apresentadas e areas tematicas de foco.
4. Atos no diario oficial, fiscalizacao, decretos e movimentacoes relevantes.
5. Conexao politica local, partido dos prefeitos beneficiados e alinhamento eleitoral municipal (TSE x Emendas).

**Fluxo**:
```
search_context_multiquery()      5 queries x top-k chunks do Qdrant
         |
build_analysis_prompt()          prompt adaptativo baseado nos tipos de dados
         |
generate_persona_analysis()      LLM gera dossier (gemma-4-e2b-it)
         |
_save_persona()                  salva no DB com contexto_rag + fontes_usadas
```

```python
# Gerar persona de um deputado
python3 -m src.enrichers.rag_persona --nome "AFONSO FLORENCE"

# Regenerar (sobrescrever existente)
python3 -m src.enrichers.rag_persona --nome "AFONSO FLORENCE" --regerar

# Lote (50 deputados)
./run.sh cron-dossie --lote 50
```

**Configuracoes relevantes** (`config/settings.py`):

| Config | Valor Padrao | Descricao |
|--------|-------------|-----------|
| `RAG_LLM_MODEL` | `gemma-4-e2b-it` | Modelo para geracao de personas |
| `RAG_PERSONA_VERSION` | `3` | Versao do prompt (incrementar para nova versao) |
| `RAG_MIN_CHUNKS` | `3` | Minimo de chunks para gerar persona |
| `RAG_MAX_CHUNKS` | `30` | Maximo de chunks por deputado no contexto |
| `RAG_BATCH_SIZE` | `50` | Tamanho do batch para embedding |

### 8.3. Padrão de Uso nos Enrichers

```python
from src.localai_manager import manager as localai_manager
from src.localai_client import get_localai_client
from config.settings import LOCALAI_MODELS, RAG_LLM_MODEL

# 1. Preparar ambiente
localai_manager.ensure_model_loaded(LOCALAI_MODELS["embedding"])
# ... indexar dados no Qdrant ...

localai_manager.ensure_model_loaded(RAG_LLM_MODEL)
# ... gerar personas ...

client = get_localai_client()
embeddings = client.embed(["texto 1", "texto 2"], model=LOCALAI_MODELS["embedding"])
```

### 8.4. Pitfalls

1. **Dimensao do embedding**: `nomic-embed-text-v1.5` gera 768d -- nao misturar com outros modelos de dimensao diferente.
2. **Min chunks**: Se o Qdrant retornar menos de `RAG_MIN_CHUNKS` (3), a persona sera gerada com dados insuficientes.
3. **VRAM**: O pipeline RAG alterna entre modelo de embedding e modelo de geracao -- chamar `ensure_model_loaded()` entre as fases.
4. **Rebuild**: `--rebuild` apaga toda a colecao Qdrant e reindexa do zero -- usar com cuidado em producao.
5. **Versionamento**: Incrementar `RAG_PERSONA_VERSION` quando o prompt mudar para forcar regeneracao.

---

## 9. Fluxo de Trabalho de Contribuição e Pull Requests

1. **Nomenclatura de Branches**:
   - `feature/<nome>`: Novas funcionalidades ou novos graficos.
   - `fix/<descricao>`: Correcoes de bugs ou rotas.
   - `docs/<topico>`: Atualizacoes de documentacao.
   - `refactor/<modulo>`: Refatoracao de codigo sem alteracao funcional.
2. **Mensagens de Commit**: Mensagens em Portugues (PT-BR), concisas e sem emojis.
3. **Checklist Pre-Submissao de PR**:
   - [ ] Executou `pre-commit run --all-files` com 100% de aprovacao.
   - [ ] Executou `pytest` com sucesso.
   - [ ] Executou `python3 src/verify_graphs.py` com sucesso.
   - [ ] Verificou que `ensure_model_loaded()` e chamado antes de operacoes com LocalAI.
   - [ ] Usou `LOCALAI_MODELS["alias"]` ao inves de hardcode de nomes de modelos.
   - [ ] Garantia de que a pipeline do GitHub Actions passou em Python 3.11 e 3.12.
