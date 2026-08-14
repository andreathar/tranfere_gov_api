import contextlib
import os
from typing import AsyncGenerator

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Limpar variáveis de proxy que possam quebrar o httpx interno do fastmcp
safe_env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}

# Parâmetros para rodar o servidor mcp-brasil via CLI
SERVER_PARAMS = StdioServerParameters(
    command="python3",
    args=["-m", "mcp_brasil.server"],
    env={
        **safe_env,
        "MCP_BRASIL_DATASETS": "tse_candidatos,tse_bens,tse_votacao,inep_censo_escolar,isp_rj",
        "MCP_BRASIL_TOOL_SEARCH": "none"  # Desabilita bm25 no backend para uso programático
    }
)

@contextlib.asynccontextmanager
async def get_mcp_client() -> AsyncGenerator[ClientSession, None]:
    """
    Context manager assíncrono para inicializar e gerenciar a sessão
    com o servidor mcp-brasil.

    Exemplo de uso:
    ```python
    async with get_mcp_client() as session:
        result = await session.call_tool("obter_deputado", {"id": 123})
        print(result)
    ```
    """
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session
