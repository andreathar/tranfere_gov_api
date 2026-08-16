"""TCE-CE feature server — registers tools, resources, and prompts.

This file only registers components. Zero business logic (ADR-001 rule #4).
"""

from fastmcp import FastMCP

from .prompts import analisar_municipio_ce
from .resources import endpoints_tce_ce
from .tools import (
    buscar_contratos_ce,
    buscar_empenhos_ce,
    buscar_licitacoes_ce,
    listar_municipios_ce,
)

mcp = FastMCP("mcp-brasil-tce-ce")

# Tools
mcp.tool(listar_municipios_ce)
mcp.tool(buscar_licitacoes_ce)
mcp.tool(buscar_contratos_ce)
mcp.tool(buscar_empenhos_ce)

# Resources
mcp.resource("data://endpoints", mime_type="application/json")(endpoints_tce_ce)

# Prompts
mcp.prompt(analisar_municipio_ce)
