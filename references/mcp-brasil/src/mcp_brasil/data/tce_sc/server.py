"""TCE-SC feature server — registers tools, resources, and prompts.

This file only registers components. Zero business logic (ADR-001 rule #4).
"""

from fastmcp import FastMCP

from .prompts import consultar_unidades_sc
from .resources import endpoints_tce_sc
from .tools import listar_municipios_sc, listar_unidades_gestoras_sc

mcp = FastMCP("mcp-brasil-tce_sc")

# Tools
mcp.tool(listar_municipios_sc)
mcp.tool(listar_unidades_gestoras_sc)

# Resources (URIs without namespace — mount adds "tce_sc/" automatically)
mcp.resource("data://endpoints", mime_type="application/json")(endpoints_tce_sc)

# Prompts
mcp.prompt(consultar_unidades_sc)
