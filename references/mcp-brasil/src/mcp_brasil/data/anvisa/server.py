"""ANVISA feature server — registers tools, resources, and prompts.

This file only registers components. Zero business logic (ADR-001 rule #4).
"""

from fastmcp import FastMCP

from .prompts import pesquisa_medicamento
from .resources import categorias_regulatorias, secoes_bula, tipos_bula
from .tools import (
    buscar_genericos,
    buscar_medicamento,
    buscar_por_categoria,
    buscar_por_empresa,
    buscar_por_principio_ativo,
    consultar_bula,
    informacoes_bula,
    listar_categorias,
    resumo_regulatorio,
    verificar_registro,
)

mcp = FastMCP("mcp-brasil-anvisa")

# Tools (10)
mcp.tool(buscar_medicamento, tags={"busca", "medicamento", "bulario", "anvisa"})
mcp.tool(buscar_por_principio_ativo, tags={"busca", "principio-ativo", "bulario"})
mcp.tool(consultar_bula, tags={"consulta", "bula", "medicamento"})
mcp.tool(listar_categorias, tags={"listagem", "categorias", "regulatorio"})
mcp.tool(informacoes_bula, tags={"informacao", "bula", "estrutura"})
mcp.tool(buscar_por_categoria, tags={"busca", "categoria", "regulatorio"})
mcp.tool(buscar_genericos, tags={"busca", "generico", "equivalente"})
mcp.tool(verificar_registro, tags={"consulta", "registro", "validade"})
mcp.tool(buscar_por_empresa, tags={"busca", "empresa", "laboratorio"})
mcp.tool(resumo_regulatorio, tags={"consulta", "resumo", "regulatorio"})

# Resources (URIs without namespace prefix — mount adds "anvisa/" automatically)
mcp.resource("data://categorias-regulatorias", mime_type="application/json")(
    categorias_regulatorias
)
mcp.resource("data://tipos-bula", mime_type="application/json")(tipos_bula)
mcp.resource("data://secoes-bula", mime_type="application/json")(secoes_bula)

# Prompts
mcp.prompt(pesquisa_medicamento)
