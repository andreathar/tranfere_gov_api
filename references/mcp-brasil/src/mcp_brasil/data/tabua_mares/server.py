"""Tabua Mares feature server — registers tools, resources, and prompts.

This file only registers components. Zero business logic (ADR-001 rule #4).
"""

from fastmcp import FastMCP

from .prompts import analise_navegacao, consulta_mares
from .resources import estados_costeiros
from .tools import (
    buscar_portos,
    consultar_tabua_mare,
    listar_estados_costeiros,
    listar_portos,
    porto_mais_proximo,
    porto_mais_proximo_geral,
    tabua_mare_por_geolocalizacao,
)

mcp = FastMCP("mcp-brasil-tabua_mares")

# Tools
mcp.tool(listar_estados_costeiros)
mcp.tool(listar_portos)
mcp.tool(buscar_portos)
mcp.tool(consultar_tabua_mare)
mcp.tool(porto_mais_proximo)
mcp.tool(porto_mais_proximo_geral)
mcp.tool(tabua_mare_por_geolocalizacao)

# Resources (URIs without namespace prefix — mount adds "tabua_mares/" automatically)
mcp.resource("data://estados-costeiros", mime_type="application/json")(estados_costeiros)

# Prompts
mcp.prompt(consulta_mares)
mcp.prompt(analise_navegacao)
