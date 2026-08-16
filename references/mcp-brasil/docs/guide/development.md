# Desenvolvimento

## Setup

```bash
git clone https://github.com/jonatassoares/mcp-brasil.git
cd mcp-brasil
make dev              # Instalar dependencias (prod + dev)
```

Requer:
- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (package manager)

## Comandos

| Comando | O que faz |
|---------|-----------|
| `make sync` | `uv sync` (somente prod) |
| `make dev` | `uv sync --group dev` (prod + dev) |
| `make test` | `pytest -v` |
| `make test-feature F=ibge` | Testes de uma feature especifica |
| `make lint` | `ruff check` + `ruff format --check` |
| `make ruff` | `ruff check --fix` + `ruff format` (auto-fix) |
| `make types` | `mypy` (strict) |
| `make ci` | lint + types + test (gate de pre-commit) |
| `make run` | Server via stdio |
| `make serve` | Server via HTTP na porta 8000 |
| `make inspect` | Lista tools/resources/prompts registrados |
| `make build` | `uv build` (sdist + wheel) |
| `make changelog` | Gera CHANGELOG.md via git-cliff |
| `make version` | Mostra versao atual |

## Estrutura de testes

Testes espelham `src/`:

```
tests/
├── conftest.py
├── test_discovery.py          # recomendar_tools, build_catalog
├── test_root_server.py        # root server integration
├── _shared/                   # Utilitarios compartilhados
│   ├── test_batch.py
│   ├── test_cache.py
│   ├── test_feature.py
│   ├── test_formatting.py
│   ├── test_http_client.py
│   ├── test_lifespan.py
│   ├── test_rate_limiter.py
│   ├── test_settings.py
│   └── test_validators.py
├── data/                      # Features de dados
│   ├── ibge/
│   │   ├── test_tools.py      # Mock client, testa logica
│   │   ├── test_client.py     # respx mock HTTP
│   │   └── test_integration.py # fastmcp.Client e2e
│   └── ...
└── agentes/
    └── redator/
        ├── test_tools.py
        ├── test_prompts.py
        └── test_integration.py
```

### Padroes de teste

**`test_tools.py`** — Mocka `client.*`, testa logica e formatacao:

```python
@pytest.mark.asyncio
async def test_buscar_items():
    with patch.object(tools, "client") as mock:
        mock.buscar_items = AsyncMock(return_value=[...])
        result = await tools.buscar_items(termo="test")
    assert "esperado" in result
```

**`test_client.py`** — Usa `respx` para mockar HTTP:

```python
@pytest.mark.asyncio
@respx.mock
async def test_buscar_items_http():
    respx.get(f"{API_BASE}/items").mock(
        return_value=Response(200, json=[...])
    )
    result = await client.buscar_items()
    assert len(result) == 1
```

**`test_integration.py`** — Testa via protocolo MCP com `fastmcp.Client`:

```python
@pytest.mark.asyncio
async def test_tool_via_mcp():
    async with Client(mcp) as client:
        tools = await client.list_tools()
        assert "buscar_items" in [t.name for t in tools]
```

## Lint e tipos

### ruff

- Line length: 99
- Auto-fix: `make ruff`
- Config: `pyproject.toml` section `[tool.ruff]`

### mypy

- Strict mode
- Config: `pyproject.toml` section `[tool.mypy]`
- Rode: `make types`

## CI

GitHub Actions roda em Python 3.10, 3.11, 3.12 e 3.13:

```yaml
# .github/workflows/ci.yml
- ruff check + format check
- mypy strict
- pytest
```

## Commits

Conventional Commits:

```
feat(ibge): add tool consultar_populacao
fix(bacen): handle empty response from SGS
test(ibge): add integration tests for localidades
docs: update README with bacen feature
```

## Releases

Gerenciadas pela skill `/release`:

```bash
/release -patch           # Bug fix
/release -minor           # Nova feature
/release -major           # Breaking change
/release -minor -push     # + push to remote
/release -minor -publish  # + push + PyPI
```

Ou via Makefile:

```bash
make release-patch    # CI + bump patch + changelog + tag
make release-minor    # CI + bump minor + changelog + tag
make release-major    # CI + bump major + changelog + tag
```

### Quando fazer release

| Situacao | Bump |
|----------|------|
| Nova feature completa (nova API, novo agente) | **minor** |
| Bug fix, ajuste de endpoint, melhoria interna | **patch** |
| Breaking change (renomear tools, mudar API publica) | **major** |
| Apenas docs, testes, refactor interno | Nenhum |

### Criterios obrigatorios

1. `make ci` verde
2. Working tree limpa (tudo commitado)
3. Branch `main`
4. CHANGELOG.md atualizado (via `git-cliff`)

## Contribuindo

1. Fork o repositorio
2. Crie a feature em `src/mcp_brasil/data/{feature}/` ou `agentes/{feature}/`
3. Siga a [anatomia de feature](adding-features.md)
4. Adicione testes em `tests/data/{feature}/`
5. Rode `make ci` — tudo deve passar
6. Abra um PR
