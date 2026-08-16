"""Contratos.gov.br sub-server — registers contract tools.

This file only registers components. Zero business logic (ADR-001 rule #4).
"""

from fastmcp import FastMCP

from .tools import (
    consultar_contrato_id,
    consultar_empenhos_contrato,
    consultar_faturas_contrato,
    consultar_historico_contrato,
    consultar_itens_contrato,
    consultar_terceirizados_contrato,
    listar_contratos_unidade,
)

mcp = FastMCP("contratosgovbr")

# Tools
mcp.tool(listar_contratos_unidade, tags={"contratos", "compras", "ug"})
mcp.tool(consultar_contrato_id, tags={"contratos", "compras", "consulta"})
mcp.tool(consultar_empenhos_contrato, tags={"contratos", "empenhos", "orcamento"})
mcp.tool(consultar_faturas_contrato, tags={"contratos", "faturas", "pagamento"})
mcp.tool(consultar_historico_contrato, tags={"contratos", "aditivos", "historico"})
mcp.tool(consultar_itens_contrato, tags={"contratos", "itens", "compras"})
mcp.tool(consultar_terceirizados_contrato, tags={"contratos", "terceirizados"})
