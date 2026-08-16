"""IBAMA feature server."""

from fastmcp import FastMCP

from .prompts import analise_autuacoes
from .resources import catalogo_datasets_chave
from .tools import (
    buscar_datasets_ibama,
    datasets_chave_ibama,
    detalhe_dataset_ibama,
    listar_datasets_ibama,
)

mcp = FastMCP("mcp-brasil-ibama")

mcp.tool(listar_datasets_ibama, tags={"listagem", "catalogo"})
mcp.tool(buscar_datasets_ibama, tags={"busca", "catalogo"})
mcp.tool(detalhe_dataset_ibama, tags={"detalhe", "recursos"})
mcp.tool(datasets_chave_ibama, tags={"listagem", "referencia"})

mcp.resource("data://datasets-chave", mime_type="application/json")(catalogo_datasets_chave)

mcp.prompt(analise_autuacoes)
