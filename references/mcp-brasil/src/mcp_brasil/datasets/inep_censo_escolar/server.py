"""inep_censo_escolar feature server."""

from fastmcp import FastMCP

from .prompts import comparar_infraestrutura, panorama_educacional_uf
from .resources import catalogo_valores, info_dataset, schema_tabela
from .tools import (
    buscar_escolas,
    escola_detalhe,
    info_censo_escolar,
    refrescar_censo_escolar,
    resumo_uf,
    top_municipios_por_escolas,
    valores_distintos_censo,
)

mcp: FastMCP = FastMCP("mcp-brasil-inep_censo_escolar")

mcp.tool(info_censo_escolar)
mcp.tool(valores_distintos_censo)
mcp.tool(buscar_escolas)
mcp.tool(escola_detalhe)
mcp.tool(resumo_uf)
mcp.tool(top_municipios_por_escolas)
mcp.tool(refrescar_censo_escolar)

mcp.resource("data://schema", mime_type="application/json")(schema_tabela)
mcp.resource("data://valores", mime_type="application/json")(catalogo_valores)
mcp.resource("data://info", mime_type="application/json")(info_dataset)

mcp.prompt(panorama_educacional_uf)
mcp.prompt(comparar_infraestrutura)
