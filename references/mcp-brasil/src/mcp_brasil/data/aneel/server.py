"""ANEEL feature server."""

from fastmcp import FastMCP

from .prompts import analise_geracao_distribuida
from .resources import catalogo_datasets_chave
from .tools import (
    buscar_datasets_aneel,
    datasets_chave_aneel,
    detalhe_dataset_aneel,
    listar_datasets_aneel,
)

mcp = FastMCP("mcp-brasil-aneel")

mcp.tool(listar_datasets_aneel, tags={"listagem", "catalogo"})
mcp.tool(buscar_datasets_aneel, tags={"busca", "catalogo"})
mcp.tool(detalhe_dataset_aneel, tags={"detalhe", "recursos"})
mcp.tool(datasets_chave_aneel, tags={"listagem", "referencia"})

mcp.resource("data://datasets-chave", mime_type="application/json")(catalogo_datasets_chave)

mcp.prompt(analise_geracao_distribuida)
