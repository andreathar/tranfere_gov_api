"""anp_precos feature server — canned SQL tools backed by DuckDB."""

from fastmcp import FastMCP

from .prompts import analise_gasolina_uf, comparar_municipios
from .resources import catalogo_valores, info_dataset, schema_tabela
from .tools import (
    info_anp_precos,
    media_preco_por_bandeira,
    media_preco_uf,
    precos_por_municipio,
    refrescar_anp_precos,
    top_postos_caros,
    valores_distintos_anp,
)

mcp: FastMCP = FastMCP("mcp-brasil-anp_precos")

mcp.tool(info_anp_precos)
mcp.tool(valores_distintos_anp)
mcp.tool(precos_por_municipio)
mcp.tool(media_preco_uf)
mcp.tool(media_preco_por_bandeira)
mcp.tool(top_postos_caros)
mcp.tool(refrescar_anp_precos)

mcp.resource("data://schema", mime_type="application/json")(schema_tabela)
mcp.resource("data://valores", mime_type="application/json")(catalogo_valores)
mcp.resource("data://info", mime_type="application/json")(info_dataset)

mcp.prompt(analise_gasolina_uf)
mcp.prompt(comparar_municipios)
