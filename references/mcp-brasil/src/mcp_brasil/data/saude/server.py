"""Saúde feature server — registers tools, resources, and prompts.

This file only registers components. Zero business logic (ADR-001 rule #4).
"""

from fastmcp import FastMCP

from .prompts import analise_epidemiologica, analise_rede_saude
from .resources import bases_datasus, codigos_uf_cnes, doencas_sinan
from .tools import (
    buscar_alertas_dengue,
    buscar_estabelecimento_por_cnes,
    buscar_estabelecimentos,
    buscar_municipio_geocodigo,
    buscar_por_coordenadas,
    buscar_por_tipo,
    buscar_profissionais,
    buscar_situacao_gripe,
    buscar_urgencias,
    comparar_municipios,
    consultar_leitos,
    listar_bases_datasus,
    listar_doencas_notificaveis,
    listar_tipos_estabelecimento,
    resumo_rede_municipal,
)

mcp = FastMCP("mcp-brasil-saude")

# Tools — CNES/DataSUS (10)
mcp.tool(buscar_estabelecimentos, tags={"busca", "estabelecimentos", "cnes", "sus"})
mcp.tool(buscar_profissionais, tags={"busca", "profissionais", "cnes"})
mcp.tool(listar_tipos_estabelecimento, tags={"listagem", "estabelecimentos", "tipos"})
mcp.tool(consultar_leitos, tags={"consulta", "leitos", "hospitalares"})
mcp.tool(buscar_urgencias, tags={"busca", "urgencia", "upa", "pronto-socorro", "emergencia"})
mcp.tool(buscar_por_tipo, tags={"busca", "estabelecimentos", "tipo", "cnes"})
mcp.tool(buscar_estabelecimento_por_cnes, tags={"consulta", "estabelecimento", "detalhe", "cnes"})
mcp.tool(buscar_por_coordenadas, tags={"busca", "estabelecimentos", "coordenadas", "proximidade"})
mcp.tool(resumo_rede_municipal, tags={"analise", "rede", "municipal", "resumo"})
mcp.tool(comparar_municipios, tags={"analise", "comparacao", "municipios"})

# Tools — Epidemiologia (5)
mcp.tool(buscar_alertas_dengue, tags={"epidemiologia", "dengue", "arbovirose", "infodengue"})
mcp.tool(buscar_situacao_gripe, tags={"epidemiologia", "gripe", "srag", "infogripe"})
mcp.tool(listar_bases_datasus, tags={"listagem", "datasus", "catalogo"})
mcp.tool(listar_doencas_notificaveis, tags={"listagem", "sinan", "doencas", "notificacao"})
mcp.tool(buscar_municipio_geocodigo, tags={"busca", "municipio", "geocodigo", "ibge"})

# Resources (URIs without namespace prefix — mount adds "saude/" automatically)
mcp.resource("data://codigos-uf", mime_type="application/json")(codigos_uf_cnes)
mcp.resource("data://bases-datasus", mime_type="application/json")(bases_datasus)
mcp.resource("data://doencas-sinan", mime_type="application/json")(doencas_sinan)

# Prompts
mcp.prompt(analise_rede_saude)
mcp.prompt(analise_epidemiologica)
