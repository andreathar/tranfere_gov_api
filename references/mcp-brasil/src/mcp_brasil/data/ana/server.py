"""ANA feature server — registers tools, resources, and prompts.

This file only registers components. Zero business logic (ADR-001 rule #4).
"""

from fastmcp import FastMCP

from .prompts import analise_bacia
from .resources import tipos_estacao
from .tools import buscar_estacoes, consultar_telemetria, monitorar_reservatorios

mcp = FastMCP("mcp-brasil-ana")

# Tools
mcp.tool(buscar_estacoes, tags={"busca", "estacoes", "hidrologia"})
mcp.tool(consultar_telemetria, tags={"consulta", "telemetria", "nivel-agua", "vazao"})
mcp.tool(monitorar_reservatorios, tags={"consulta", "reservatorios", "volume"})

# Resources (URIs without namespace prefix — mount adds "ana/" automatically)
mcp.resource("data://tipos-estacao", mime_type="application/json")(tipos_estacao)

# Prompts
mcp.prompt(analise_bacia)
