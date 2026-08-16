"""IPEADATA feature server."""

from fastmcp import FastMCP

from .prompts import analise_historica
from .resources import catalogo_populares, catalogo_temas
from .tools import buscar_serie, metadados_serie, series_populares, ultimo_valor, valores_serie

mcp = FastMCP("mcp-brasil-ipeadata")

mcp.tool(buscar_serie, tags={"busca", "series", "catalogo"})
mcp.tool(metadados_serie, tags={"detalhe", "series", "metadados"})
mcp.tool(valores_serie, tags={"consulta", "series", "historicas"})
mcp.tool(ultimo_valor, tags={"consulta", "series", "atual"})
mcp.tool(series_populares, tags={"listagem", "catalogo", "referencia"})

mcp.resource("data://catalogo-populares", mime_type="application/json")(catalogo_populares)
mcp.resource("data://temas", mime_type="application/json")(catalogo_temas)

mcp.prompt(analise_historica)
