"""Dados Abertos sub-server — registers Compras.gov.br tools.

This file only registers components. Zero business logic (ADR-001 rule #4).
"""

from fastmcp import FastMCP

from .tools import (
    buscar_contratos,
    buscar_dispensas,
    buscar_licitacoes,
    buscar_material_catmat,
    buscar_pregoes,
    buscar_servico_catser,
    buscar_uasg,
    consultar_fornecedor,
)

mcp = FastMCP("dadosabertos")

# Tools
mcp.tool(buscar_licitacoes, tags={"busca", "licitacoes", "compras"})
mcp.tool(buscar_pregoes, tags={"busca", "pregoes", "compras"})
mcp.tool(buscar_dispensas, tags={"busca", "dispensas", "compras"})
mcp.tool(buscar_contratos, tags={"busca", "contratos", "compras"})
mcp.tool(consultar_fornecedor, tags={"consulta", "fornecedores", "compras"})
mcp.tool(buscar_material_catmat, tags={"busca", "catmat", "materiais"})
mcp.tool(buscar_servico_catser, tags={"busca", "catser", "servicos"})
mcp.tool(buscar_uasg, tags={"busca", "uasg", "orgaos"})
