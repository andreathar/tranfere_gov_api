"""INEP feature server — registers tools.

This file only registers components. Zero business logic (ADR-001 rule #4).
"""

from fastmcp import FastMCP

from .tools import (
    consultar_ideb,
    gerar_url_download_inep,
    listar_indicadores_educacionais,
    listar_microdados_inep,
)

mcp = FastMCP("mcp-brasil-inep")

mcp.tool(consultar_ideb, tags={"educação", "ideb", "avaliação"})
mcp.tool(listar_microdados_inep, tags={"educação", "microdados", "catálogo"})
mcp.tool(gerar_url_download_inep, tags={"educação", "microdados", "download"})
mcp.tool(listar_indicadores_educacionais, tags={"educação", "indicadores"})
