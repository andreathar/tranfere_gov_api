"""spu_imoveis feature server — registers tools, resources, and prompts."""

from fastmcp import FastMCP

from .prompts import patrimonio_municipio, patrimonio_orgao
from .resources import catalogo_orgaos, info_api, schema_csv
from .tools import (
    buscar_imoveis_spu,
    info_dataset_spu,
    resumo_orgaos_spu,
    resumo_ufs_spu,
)

mcp: FastMCP = FastMCP("mcp-brasil-spu_imoveis")

mcp.tool(info_dataset_spu)
mcp.tool(buscar_imoveis_spu)
mcp.tool(resumo_orgaos_spu)
mcp.tool(resumo_ufs_spu)

mcp.resource("data://schema", mime_type="application/json")(schema_csv)
mcp.resource("data://orgaos", mime_type="application/json")(catalogo_orgaos)
mcp.resource("data://info", mime_type="application/json")(info_api)

mcp.prompt(patrimonio_orgao)
mcp.prompt(patrimonio_municipio)
