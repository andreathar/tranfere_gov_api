"""Redator Oficial feature server — registers tools, resources, and prompts.

This file only registers components. Zero business logic (ADR-001 rule #4).
"""

from fastmcp import FastMCP

from .prompts import (
    redator_despacho,
    redator_nota_tecnica,
    redator_oficio,
    redator_parecer,
    redator_portaria,
)
from .resources import (
    get_fechos_oficiais,
    get_manual_redacao,
    get_pronomes_tratamento,
    get_template_ata,
    get_template_despacho,
    get_template_nota_tecnica,
    get_template_oficio,
    get_template_parecer,
    get_template_portaria,
)
from .tools import (
    consultar_pronome_tratamento,
    formatar_data_extenso,
    gerar_numeracao,
    listar_tipos_documento,
    validar_documento,
)

mcp = FastMCP("mcp-brasil-redator")

# Tools (5)
mcp.tool(formatar_data_extenso, tags={"formatacao", "data", "redacao-oficial"})
mcp.tool(gerar_numeracao, tags={"formatacao", "numeracao", "redacao-oficial"})
mcp.tool(consultar_pronome_tratamento, tags={"consulta", "pronomes", "redacao-oficial"})
mcp.tool(validar_documento, tags={"validacao", "documento", "redacao-oficial"})
mcp.tool(listar_tipos_documento, tags={"listagem", "tipos-documento", "redacao-oficial"})

# Prompts (5)
mcp.prompt(redator_oficio)
mcp.prompt(redator_despacho)
mcp.prompt(redator_portaria)
mcp.prompt(redator_parecer)
mcp.prompt(redator_nota_tecnica)

# Resources (9)
mcp.resource("template://oficio")(get_template_oficio)
mcp.resource("template://despacho")(get_template_despacho)
mcp.resource("template://portaria")(get_template_portaria)
mcp.resource("template://parecer")(get_template_parecer)
mcp.resource("template://nota_tecnica")(get_template_nota_tecnica)
mcp.resource("template://ata")(get_template_ata)
mcp.resource("normas://manual_redacao")(get_manual_redacao)
mcp.resource("normas://pronomes")(get_pronomes_tratamento)
mcp.resource("normas://fechos")(get_fechos_oficiais)
