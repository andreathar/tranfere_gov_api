"""SINESP/MJSP feature server — registers tools and resources.

This file only registers components. Zero business logic (ADR-001 rule #4).
"""

from fastmcp import FastMCP

from .resources import grupos_tematicos, organizacoes_seguranca
from .tools import (
    buscar_datasets_mjsp,
    detalhar_dataset_mjsp,
    listar_datasets_grupo_seguranca,
    listar_datasets_mjsp,
    listar_datasets_organizacao,
    listar_organizacoes_mjsp,
)

mcp = FastMCP("mcp-brasil-sinesp")

# Tools
mcp.tool(listar_datasets_mjsp, tags={"listagem", "sinesp", "ckan"})
mcp.tool(buscar_datasets_mjsp, tags={"busca", "sinesp", "ckan"})
mcp.tool(detalhar_dataset_mjsp, tags={"consulta", "sinesp", "ckan"})
mcp.tool(listar_organizacoes_mjsp, tags={"listagem", "sinesp", "organizacoes"})
mcp.tool(listar_datasets_organizacao, tags={"listagem", "sinesp", "organizacoes"})
mcp.tool(listar_datasets_grupo_seguranca, tags={"listagem", "sinesp", "grupos"})

# Resources
mcp.resource("data://orgs-seguranca-mjsp", mime_type="application/json")(organizacoes_seguranca)
mcp.resource("data://grupos-tematicos-mjsp", mime_type="application/json")(grupos_tematicos)
