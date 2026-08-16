"""Atlas da Violência feature server — registers tools and resources.

This file only registers components. Zero business logic (ADR-001 rule #4).
"""

from fastmcp import FastMCP

from .resources import abrangencias_atlas, temas_atlas
from .tools import (
    consultar_serie_violencia,
    consultar_valores_por_regiao,
    consultar_valores_violencia,
    listar_fontes_violencia,
    listar_metadados_violencia,
    listar_series_tema,
    listar_temas_violencia,
)

mcp = FastMCP("mcp-brasil-atlas-violencia")

# Tools
mcp.tool(listar_temas_violencia, tags={"listagem", "atlas-violencia", "temas"})
mcp.tool(listar_series_tema, tags={"listagem", "atlas-violencia", "series"})
mcp.tool(consultar_valores_violencia, tags={"consulta", "atlas-violencia", "dados"})
mcp.tool(consultar_valores_por_regiao, tags={"consulta", "atlas-violencia", "regional"})
mcp.tool(consultar_serie_violencia, tags={"consulta", "atlas-violencia", "metadados"})
mcp.tool(listar_fontes_violencia, tags={"listagem", "atlas-violencia", "fontes"})
mcp.tool(listar_metadados_violencia, tags={"listagem", "atlas-violencia", "metadados"})

# Resources
mcp.resource("data://temas-atlas-violencia", mime_type="application/json")(temas_atlas)
mcp.resource("data://abrangencias-atlas", mime_type="application/json")(abrangencias_atlas)
