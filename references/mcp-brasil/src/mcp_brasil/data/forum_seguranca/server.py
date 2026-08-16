"""Fórum Segurança feature server — registers tools and resources.

This file only registers components. Zero business logic (ADR-001 rule #4).
"""

from fastmcp import FastMCP

from .resources import catalogo_comunidades
from .tools import (
    buscar_por_tema_seguranca,
    buscar_publicacoes_seguranca,
    detalhar_publicacao_seguranca,
    listar_temas_seguranca,
)

mcp = FastMCP("mcp-brasil-forum-seguranca")

# Tools
mcp.tool(buscar_publicacoes_seguranca, tags={"forum-seguranca", "publicacoes", "busca"})
mcp.tool(listar_temas_seguranca, tags={"forum-seguranca", "comunidades", "temas"})
mcp.tool(detalhar_publicacao_seguranca, tags={"forum-seguranca", "publicacoes", "detalhes"})
mcp.tool(buscar_por_tema_seguranca, tags={"forum-seguranca", "publicacoes", "temas", "busca"})

# Resources
mcp.resource("data://catalogo-comunidades", mime_type="application/json")(catalogo_comunidades)
