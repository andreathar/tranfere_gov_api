# Adicionando Features

Guia para adicionar uma nova API publica brasileira ao mcp-brasil.

## Visao geral

Cada API e uma pasta auto-contida em `src/mcp_brasil/data/`. Crie a pasta seguindo a convencao e o server descobre automaticamente — zero configuracao manual.

```
src/mcp_brasil/data/{feature}/
├── __init__.py     # FEATURE_META (obrigatorio)
├── server.py       # mcp: FastMCP (obrigatorio)
├── tools.py        # Funcoes das tools
├── client.py       # HTTP async para a API
├── schemas.py      # Pydantic models
└── constants.py    # URLs, enums, codigos
```

## Passo 1: Criar `constants.py`

Defina URLs base e codigos fixos. **Zero imports** de outros modulos do projeto.

```python
# src/mcp_brasil/data/exemplo/constants.py

EXEMPLO_API_BASE = "https://api.exemplo.gov.br/v1"

# Codigos fixos, enums, mapeamentos
TIPOS_CONSULTA = {
    "1": "Tipo A",
    "2": "Tipo B",
}
```

## Passo 2: Criar `schemas.py`

Defina os modelos Pydantic para os dados da API. **Zero logica** — apenas `BaseModel`.

```python
# src/mcp_brasil/data/exemplo/schemas.py
from pydantic import BaseModel, Field


class ItemExemplo(BaseModel):
    id: int
    nome: str
    valor: float = Field(description="Valor em reais")
    data: str | None = None


class RespostaExemplo(BaseModel):
    items: list[ItemExemplo]
    total: int
```

## Passo 3: Criar `client.py`

Faz as chamadas HTTP async. Usa `http_get` do `_shared/http_client.py`. Retorna Pydantic models — **nunca formata para LLM**.

```python
# src/mcp_brasil/data/exemplo/client.py
from mcp_brasil._shared.http_client import http_get
from .constants import EXEMPLO_API_BASE
from .schemas import ItemExemplo


async def buscar_items(
    termo: str | None = None,
    ano: int | None = None,
    pagina: int = 1,
) -> list[ItemExemplo]:
    """Busca items na API de exemplo."""
    params: dict[str, str | int] = {"pagina": pagina}
    if termo:
        params["q"] = termo
    if ano:
        params["ano"] = ano

    data = await http_get(f"{EXEMPLO_API_BASE}/items", params=params)
    return [ItemExemplo(**item) for item in data]


async def obter_item(item_id: int) -> ItemExemplo:
    """Obtem detalhes de um item."""
    data = await http_get(f"{EXEMPLO_API_BASE}/items/{item_id}")
    return ItemExemplo(**data)
```

### Opcoes de HTTP

```python
from mcp_brasil._shared.http_client import http_get, http_post

# GET com headers customizados
data = await http_get(url, params=params, headers={"Authorization": "Bearer xxx"})

# POST com body JSON
data = await http_post(url, json_body={"query": "..."})

# Retry automatico em 429/5xx/timeout com backoff exponencial
# Configuravel via MCP_BRASIL_HTTP_TIMEOUT e MCP_BRASIL_HTTP_MAX_RETRIES
```

## Passo 4: Criar `tools.py`

Define as funcoes que o LLM pode chamar. **Nunca faz HTTP** — delega para `client.py`.

```python
# src/mcp_brasil/data/exemplo/tools.py
from mcp_brasil._shared.formatting import markdown_table, format_brl
from . import client


async def buscar_items(
    termo: str | None = None,
    ano: int | None = None,
    pagina: int = 1,
) -> str:
    """Busca items na API de exemplo.

    Args:
        termo: Termo de busca (opcional)
        ano: Ano de referencia (opcional)
        pagina: Numero da pagina (default: 1)

    Returns:
        Tabela formatada com os resultados
    """
    items = await client.buscar_items(termo=termo, ano=ano, pagina=pagina)

    if not items:
        return "Nenhum item encontrado."

    headers = ["ID", "Nome", "Valor", "Data"]
    rows = [
        [str(i.id), i.nome, format_brl(i.valor), i.data or "N/A"]
        for i in items
    ]
    return markdown_table(headers, rows)


async def obter_item(item_id: int) -> str:
    """Obtem detalhes de um item especifico.

    Args:
        item_id: ID do item

    Returns:
        Detalhes formatados do item
    """
    item = await client.obter_item(item_id)
    return (
        f"**{item.nome}**\n"
        f"- ID: {item.id}\n"
        f"- Valor: {format_brl(item.valor)}\n"
        f"- Data: {item.data or 'N/A'}"
    )
```

**Regras importantes:**
- Toda tool **deve ter docstring** — o LLM usa para decidir quando chamar
- Use `Args:` e `Returns:` na docstring para parametros
- `async def` obrigatorio
- Type hints completos em todos os parametros

## Passo 5: Criar `server.py`

Registra as tools no FastMCP. **Zero logica de negocio** — apenas registro.

```python
# src/mcp_brasil/data/exemplo/server.py
from fastmcp import FastMCP
from . import tools

mcp = FastMCP("exemplo")

mcp.tool(tools.buscar_items)
mcp.tool(tools.obter_item)
```

Se a feature tiver resources ou prompts:

```python
from fastmcp import FastMCP
from . import tools

mcp = FastMCP("exemplo")

# Tools
mcp.tool(tools.buscar_items)
mcp.tool(tools.obter_item)


# Resources (nao incluir nome da feature na URI — mount() adiciona o prefixo)
@mcp.resource("data://codigos")
async def codigos_resource() -> str:
    """Codigos de referencia."""
    return "..."


# Prompts
@mcp.prompt()
async def analise_prompt(tema: str) -> str:
    """Prompt para analise de dados."""
    return f"Analise os dados sobre {tema}..."
```

**Importante sobre URIs de resources:** NAO inclua o nome da feature na URI. O `mount(namespace=name)` adiciona automaticamente. Use `data://codigos`, nao `data://exemplo/codigos`.

## Passo 6: Criar `__init__.py`

Exporta `FEATURE_META` — obrigatorio para o auto-discovery.

```python
# src/mcp_brasil/data/exemplo/__init__.py
from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="exemplo",
    description="API de Exemplo — dados de demonstracao",
    version="0.1.0",
    api_base="https://api.exemplo.gov.br/v1",
    requires_auth=False,
    tags=["economia", "dados"],
)
```

### Campos do `FeatureMeta`

| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `name` | `str` | Sim | Identificador curto (nome da pasta) |
| `description` | `str` | Sim | Descricao legivel para humanos |
| `version` | `str` | Sim | Versao semver |
| `api_base` | `str` | Sim | URL base da API |
| `requires_auth` | `bool` | Nao | Se precisa de chave (default: `False`) |
| `auth_env_var` | `str` | Nao | Nome da env var com a chave |
| `enabled` | `bool` | Nao | Se esta ativa (default: `True`) |
| `tags` | `list[str]` | Nao | Tags de topico |

### Features com autenticacao

Se a API requer chave:

```python
FEATURE_META = FeatureMeta(
    name="exemplo",
    description="API de Exemplo (requer chave)",
    version="0.1.0",
    api_base="https://api.exemplo.gov.br/v1",
    requires_auth=True,
    auth_env_var="EXEMPLO_API_KEY",
)
```

Se `requires_auth=True` e a env var nao estiver definida, a feature e **ignorada silenciosamente** no startup.

## Passo 7: Criar testes

Testes espelham a estrutura de `src/`:

```
tests/data/exemplo/
├── test_tools.py        # Mock client, testa logica
├── test_client.py       # respx mock HTTP
└── test_integration.py  # fastmcp.Client e2e
```

### `test_tools.py` — Unit tests

```python
# tests/data/exemplo/test_tools.py
from unittest.mock import AsyncMock, patch
import pytest
from mcp_brasil.data.exemplo.schemas import ItemExemplo
from mcp_brasil.data.exemplo import tools


@pytest.mark.asyncio
async def test_buscar_items_retorna_tabela():
    mock_items = [
        ItemExemplo(id=1, nome="Item A", valor=100.50, data="2024-01-01"),
        ItemExemplo(id=2, nome="Item B", valor=200.00, data=None),
    ]
    with patch.object(tools, "client") as mock_client:
        mock_client.buscar_items = AsyncMock(return_value=mock_items)
        result = await tools.buscar_items(termo="test")

    assert "Item A" in result
    assert "R$" in result


@pytest.mark.asyncio
async def test_buscar_items_vazio():
    with patch.object(tools, "client") as mock_client:
        mock_client.buscar_items = AsyncMock(return_value=[])
        result = await tools.buscar_items()

    assert "Nenhum" in result
```

### `test_client.py` — HTTP mock

```python
# tests/data/exemplo/test_client.py
import pytest
import respx
from httpx import Response
from mcp_brasil.data.exemplo.client import buscar_items
from mcp_brasil.data.exemplo.constants import EXEMPLO_API_BASE


@pytest.mark.asyncio
@respx.mock
async def test_buscar_items_http():
    respx.get(f"{EXEMPLO_API_BASE}/items").mock(
        return_value=Response(200, json=[
            {"id": 1, "nome": "Item A", "valor": 100.50}
        ])
    )
    result = await buscar_items(termo="test")
    assert len(result) == 1
    assert result[0].nome == "Item A"
```

### `test_integration.py` — MCP e2e

```python
# tests/data/exemplo/test_integration.py
import pytest
from fastmcp import Client
from mcp_brasil.data.exemplo.server import mcp


@pytest.mark.asyncio
async def test_tool_buscar_items_via_mcp():
    async with Client(mcp) as client:
        tools = await client.list_tools()
        tool_names = [t.name for t in tools]
        assert "buscar_items" in tool_names
```

## Passo 8: Rodar e validar

```bash
make ci               # lint + types + test (tudo deve passar)
make test-feature F=exemplo  # so testes da feature
make inspect          # verificar se a feature aparece no registry
```

Pronto. O server descobre a nova pasta automaticamente — nenhum import manual necessario.

## Checklist

- [ ] `__init__.py` com `FEATURE_META` exportado
- [ ] `server.py` com `mcp: FastMCP` exportado
- [ ] `tools.py` com docstrings em todas as funcoes
- [ ] `client.py` faz HTTP, retorna Pydantic models
- [ ] `schemas.py` so tem BaseModel (zero logica)
- [ ] `constants.py` sem imports do projeto
- [ ] `async def` em todas as tools e clients
- [ ] Type hints completos
- [ ] Testes: `test_tools.py`, `test_client.py`, `test_integration.py`
- [ ] `make ci` verde
