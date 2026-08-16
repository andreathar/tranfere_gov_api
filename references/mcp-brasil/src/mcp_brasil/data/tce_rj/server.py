"""TCE-RJ feature server — registers tools, resources, and prompts.

This file only registers components. Zero business logic (ADR-001 rule #4).
"""

from fastmcp import FastMCP

from .prompts import analisar_municipio_rj
from .resources import endpoints_disponiveis
from .tools import (
    buscar_compras_diretas,
    buscar_concessoes,
    buscar_contratos_municipio,
    buscar_licitacoes,
    buscar_obras_paralisadas,
    buscar_penalidades,
    buscar_prestacao_contas,
)

mcp = FastMCP("mcp-brasil-tce-rj")

# Tools
mcp.tool(buscar_licitacoes)
mcp.tool(buscar_contratos_municipio)
mcp.tool(buscar_compras_diretas)
mcp.tool(buscar_obras_paralisadas)
mcp.tool(buscar_penalidades)
mcp.tool(buscar_prestacao_contas)
mcp.tool(buscar_concessoes)

# Resources
mcp.resource("data://endpoints-disponiveis", mime_type="application/json")(endpoints_disponiveis)

# Prompts
mcp.prompt(analisar_municipio_rj)
