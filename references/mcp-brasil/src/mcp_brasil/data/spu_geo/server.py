"""spu_geo feature server — registers tools, resources, and prompts."""

from fastmcp import FastMCP

from .prompts import analise_terreno_uniao, imoveis_em_area
from .resources import catalogo_camadas, glossario_patrimonial, info_api
from .tools import (
    buscar_imoveis_area_spu,
    consultar_ponto_spu,
    detalhar_camada_spu,
    listar_camadas_spu,
)

mcp: FastMCP = FastMCP("mcp-brasil-spu_geo")

mcp.tool(listar_camadas_spu)
mcp.tool(detalhar_camada_spu)
mcp.tool(consultar_ponto_spu)
mcp.tool(buscar_imoveis_area_spu)

mcp.resource("data://catalogo", mime_type="application/json")(catalogo_camadas)
mcp.resource("data://glossario", mime_type="application/json")(glossario_patrimonial)
mcp.resource("data://info", mime_type="application/json")(info_api)

mcp.prompt(analise_terreno_uniao)
mcp.prompt(imoveis_em_area)
