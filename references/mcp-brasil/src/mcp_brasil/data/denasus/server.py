"""DENASUS feature server — registers tools, resources, and prompts.

This file only registers components. Zero business logic (ADR-001 rule #4).
"""

from fastmcp import FastMCP

from .prompts import analise_auditoria_municipal
from .resources import sobre_denasus, tipos_atividade
from .tools import (
    buscar_auditorias,
    informacoes_sna,
    listar_planos,
    listar_relatorios_anuais,
    verificar_municipio,
)

mcp = FastMCP("mcp-brasil-denasus")

# Tools (5)
mcp.tool(buscar_auditorias, tags={"busca", "auditoria", "denasus"})
mcp.tool(listar_relatorios_anuais, tags={"listagem", "relatorios", "denasus"})
mcp.tool(listar_planos, tags={"listagem", "planos", "auditoria"})
mcp.tool(verificar_municipio, tags={"consulta", "municipio", "auditoria"})
mcp.tool(informacoes_sna, tags={"informacao", "sna", "denasus"})

# Resources (URIs without namespace prefix — mount adds "denasus/" automatically)
mcp.resource("data://sobre-denasus", mime_type="application/json")(sobre_denasus)
mcp.resource("data://tipos-atividade", mime_type="application/json")(tipos_atividade)

# Prompts
mcp.prompt(analise_auditoria_municipal)
