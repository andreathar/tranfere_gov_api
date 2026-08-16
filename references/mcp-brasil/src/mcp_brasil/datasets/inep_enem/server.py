"""inep_enem feature server."""

from fastmcp import FastMCP

from .prompts import comparar_ufs, panorama_notas_uf
from .resources import catalogo_valores, info_dataset, schema_tabela
from .tools import (
    info_enem,
    media_notas_por_grupo,
    media_notas_uf,
    refrescar_enem,
    top_municipios_por_media,
    valores_distintos_enem,
)

mcp: FastMCP = FastMCP("mcp-brasil-inep_enem")

mcp.tool(info_enem)
mcp.tool(valores_distintos_enem)
mcp.tool(media_notas_uf)
mcp.tool(media_notas_por_grupo)
mcp.tool(top_municipios_por_media)
mcp.tool(refrescar_enem)

mcp.resource("data://schema", mime_type="application/json")(schema_tabela)
mcp.resource("data://valores", mime_type="application/json")(catalogo_valores)
mcp.resource("data://info", mime_type="application/json")(info_dataset)

mcp.prompt(panorama_notas_uf)
mcp.prompt(comparar_ufs)
