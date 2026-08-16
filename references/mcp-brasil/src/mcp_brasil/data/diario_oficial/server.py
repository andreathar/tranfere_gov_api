"""Diário Oficial feature server — registers tools, resources, and prompts.

This file only registers components. Zero business logic (ADR-001 rule #4).
"""

from fastmcp import FastMCP

from .prompts import (
    comparar_municipios,
    investigar_cnpj_diarios,
    investigar_empresa,
    monitorar_diario_completo,
    monitorar_licitacoes,
    rastrear_cadeia_regulatoria,
    rastrear_nomeacoes,
)
from .resources import (
    capitais_cobertas,
    dicas_busca_diario,
    orgaos_federais_dou,
    secoes_dou,
    tipos_publicacao_dou,
    ufs_com_cobertura,
)
from .tools import (
    buscar_cidades,
    buscar_diario_unificado,
    buscar_diarios,
    buscar_diarios_regiao,
    listar_diarios_recentes,
    listar_territorios,
)
from .tools_dou import (
    dou_buscar,
    dou_buscar_avancado,
    dou_buscar_por_orgao,
    dou_edicao_do_dia,
    dou_ler_publicacao,
)

mcp = FastMCP("mcp-brasil-diario-oficial")

# Tools — Diários Municipais (Querido Diário)
mcp.tool(buscar_diarios, tags={"busca", "diarios-oficiais", "municipal"})
mcp.tool(buscar_diarios_regiao, tags={"busca", "diarios-oficiais", "regional"})
mcp.tool(buscar_cidades, tags={"busca", "municipios", "cobertura"})
mcp.tool(listar_territorios, tags={"listagem", "municipios", "cobertura"})
mcp.tool(listar_diarios_recentes, tags={"listagem", "diarios-oficiais", "municipal"})

# Tools — DOU Federal (Imprensa Nacional)
mcp.tool(dou_buscar, tags={"busca", "dou", "federal"})
mcp.tool(dou_ler_publicacao, tags={"leitura", "dou", "federal"})
mcp.tool(dou_edicao_do_dia, tags={"listagem", "dou", "federal"})
mcp.tool(dou_buscar_por_orgao, tags={"busca", "dou", "orgao"})
mcp.tool(dou_buscar_avancado, tags={"busca", "dou", "avancado"})

# Tools — Busca Unificada (QD + DOU)
mcp.tool(buscar_diario_unificado, tags={"busca", "unificado", "federal", "municipal"})

# Resources
mcp.resource("data://capitais-cobertas", mime_type="application/json")(capitais_cobertas)
mcp.resource("data://ufs-cobertas", mime_type="application/json")(ufs_com_cobertura)
mcp.resource("data://dicas-busca", mime_type="application/json")(dicas_busca_diario)
mcp.resource("data://secoes-dou", mime_type="application/json")(secoes_dou)
mcp.resource("data://tipos-publicacao-dou", mime_type="application/json")(tipos_publicacao_dou)
mcp.resource("data://orgaos-federais-dou", mime_type="application/json")(orgaos_federais_dou)

# Prompts — Municipal
mcp.prompt(investigar_empresa)
mcp.prompt(monitorar_licitacoes)
mcp.prompt(rastrear_nomeacoes)
mcp.prompt(comparar_municipios)

# Prompts — Cruzados (Federal + Municipal)
mcp.prompt(rastrear_cadeia_regulatoria)
mcp.prompt(investigar_cnpj_diarios)
mcp.prompt(monitorar_diario_completo)
