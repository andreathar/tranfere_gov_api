"""TCE-RS feature server — registers tools, resources, and prompts.

This file only registers components. Zero business logic (ADR-001 rule #4).
"""

from fastmcp import FastMCP

from .prompts import analisar_municipio_rs
from .resources import endpoints_tce_rs
from .tools import (
    buscar_datasets_rs,
    buscar_gestao_fiscal_rs,
    buscar_indices_educacao_rs,
    buscar_indices_saude_rs,
    listar_municipios_rs,
)

mcp = FastMCP("mcp-brasil-tce_rs")

# Tools
mcp.tool(listar_municipios_rs)
mcp.tool(buscar_indices_educacao_rs)
mcp.tool(buscar_indices_saude_rs)
mcp.tool(buscar_gestao_fiscal_rs)
mcp.tool(buscar_datasets_rs)

# Resources (URIs without namespace — mount adds "tce_rs/" automatically)
mcp.resource("data://endpoints", mime_type="application/json")(endpoints_tce_rs)

# Prompts
mcp.prompt(analisar_municipio_rs)
