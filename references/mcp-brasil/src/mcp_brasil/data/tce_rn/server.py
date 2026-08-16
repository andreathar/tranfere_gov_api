"""TCE-RN feature server — registers tools, resources, and prompts.

This file only registers components. Zero business logic (ADR-001 rule #4).
"""

from fastmcp import FastMCP

from .prompts import analisar_unidade_rn
from .resources import endpoints_tce_rn
from .tools import (
    buscar_contratos_rn,
    buscar_despesas_rn,
    buscar_licitacoes_rn,
    buscar_receitas_rn,
    listar_jurisdicionados_rn,
)

mcp = FastMCP("mcp-brasil-tce_rn")

# Tools
mcp.tool(listar_jurisdicionados_rn)
mcp.tool(buscar_despesas_rn)
mcp.tool(buscar_receitas_rn)
mcp.tool(buscar_licitacoes_rn)
mcp.tool(buscar_contratos_rn)

# Resources
mcp.resource("data://endpoints", mime_type="application/json")(endpoints_tce_rn)

# Prompts
mcp.prompt(analisar_unidade_rn)
