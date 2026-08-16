"""RENAME feature server — registers tools, resources, and prompts.

This file only registers components. Zero business logic (ADR-001 rule #4).
"""

from fastmcp import FastMCP

from .prompts import consulta_medicamento_sus
from .resources import catalogo_rename, grupos_terapeuticos
from .tools import (
    buscar_medicamento_rename,
    estatisticas_rename,
    listar_grupos_terapeuticos,
    listar_por_grupo_terapeutico,
    verificar_disponibilidade_sus,
)

mcp = FastMCP("mcp-brasil-rename")

# Tools (5)
mcp.tool(buscar_medicamento_rename, tags={"busca", "medicamento", "rename"})
mcp.tool(listar_por_grupo_terapeutico, tags={"listagem", "grupo", "terapeutico"})
mcp.tool(verificar_disponibilidade_sus, tags={"consulta", "sus", "disponibilidade"})
mcp.tool(listar_grupos_terapeuticos, tags={"listagem", "grupos", "categorias"})
mcp.tool(estatisticas_rename, tags={"estatisticas", "resumo", "rename"})

# Resources (URIs without namespace prefix — mount adds "rename/" automatically)
mcp.resource("data://catalogo", mime_type="application/json")(catalogo_rename)
mcp.resource("data://grupos-terapeuticos", mime_type="application/json")(grupos_terapeuticos)

# Prompts
mcp.prompt(consulta_medicamento_sus)
