"""Transparência feature server — registers tools, resources, and prompts.

This file only registers components. Zero business logic (ADR-001 rule #4).
"""

from fastmcp import FastMCP

from .prompts import analise_despesas, auditoria_fornecedor, verificacao_compliance
from .resources import bases_sancoes, categorias_beneficios, endpoints_disponiveis, info_api
from .tools import (
    buscar_acordos_leniencia,
    buscar_cartoes_pagamento,
    buscar_contrato_numero,
    buscar_contratos,
    buscar_contratos_geral,
    buscar_contratos_licitacao,
    buscar_convenio_numero,
    buscar_convenios,
    buscar_documentos_despesa,
    buscar_documentos_emenda,
    buscar_emendas,
    buscar_empenhos_licitacao,
    buscar_empresas_beneficios_fiscais,
    buscar_imoveis_funcionais,
    buscar_itens_contratados,
    buscar_itens_empenho,
    buscar_itens_licitados,
    buscar_licitacao_por_processo,
    buscar_licitacoes,
    buscar_nota_fiscal_chave,
    buscar_notas_fiscais,
    buscar_participantes_licitacao,
    buscar_pep,
    buscar_permissionarios_imoveis,
    buscar_remuneracoes_servidores,
    buscar_renuncias_fiscais,
    buscar_sancoes,
    buscar_servidores,
    buscar_servidores_por_orgao,
    buscar_termos_aditivos,
    buscar_unidades_gestoras,
    buscar_viagens_orgao,
    consultar_beneficio_social,
    consultar_bolsa_familia,
    consultar_cnpj,
    consultar_coronavirus_despesas,
    consultar_coronavirus_transferencias,
    consultar_cpf,
    consultar_despesas,
    consultar_despesas_funcional,
    consultar_despesas_orgao,
    consultar_garantia_safra,
    consultar_peti,
    consultar_seguro_defeso,
    consultar_viagens,
    detalhar_contrato,
    detalhar_convenio,
    detalhar_licitacao,
    detalhar_sancao,
    detalhar_servidor,
    detalhar_viagem,
    listar_funcoes_cargos,
    listar_modalidades_licitacao,
    listar_orgaos,
)

mcp = FastMCP("mcp-brasil-transparencia")

# Tools — existentes
mcp.tool(buscar_contratos, tags={"busca", "contratos", "fornecedores"})
mcp.tool(consultar_despesas, tags={"consulta", "despesas", "orcamento"})
mcp.tool(buscar_servidores, tags={"busca", "servidores", "funcionalismo"})
mcp.tool(buscar_licitacoes, tags={"busca", "licitacoes", "compras"})
mcp.tool(consultar_bolsa_familia, tags={"consulta", "bolsa-familia", "beneficios-sociais"})
mcp.tool(buscar_sancoes, tags={"busca", "sancoes", "compliance", "anticorrupcao"})
mcp.tool(buscar_emendas, tags={"busca", "emendas", "orcamento"})
mcp.tool(consultar_viagens, tags={"consulta", "viagens", "diarias"})
mcp.tool(buscar_convenios, tags={"busca", "convenios", "transferencias"})
mcp.tool(buscar_cartoes_pagamento, tags={"busca", "cartao-corporativo", "despesas"})
mcp.tool(buscar_pep, tags={"busca", "pep", "compliance"})
mcp.tool(buscar_acordos_leniencia, tags={"busca", "leniencia", "anticorrupcao"})
mcp.tool(buscar_notas_fiscais, tags={"busca", "notas-fiscais", "despesas"})
mcp.tool(consultar_beneficio_social, tags={"consulta", "beneficios-sociais", "bpc"})
mcp.tool(consultar_cpf, tags={"consulta", "cpf", "pessoa-fisica"})
mcp.tool(consultar_cnpj, tags={"consulta", "cnpj", "pessoa-juridica"})
mcp.tool(detalhar_contrato, tags={"detalhe", "contratos"})
mcp.tool(detalhar_servidor, tags={"detalhe", "servidores", "remuneracao"})

# Tools — imóveis funcionais
mcp.tool(buscar_imoveis_funcionais, tags={"busca", "imoveis", "patrimonio"})
mcp.tool(buscar_permissionarios_imoveis, tags={"busca", "imoveis", "permissionarios"})

# Tools — renúncias fiscais
mcp.tool(buscar_renuncias_fiscais, tags={"busca", "renuncias", "tributos"})
mcp.tool(buscar_empresas_beneficios_fiscais, tags={"busca", "renuncias", "beneficios-fiscais"})

# Tools — órgãos
mcp.tool(listar_orgaos, tags={"referencia", "orgaos", "siape", "siafi"})

# Tools — coronavírus
mcp.tool(
    consultar_coronavirus_transferencias,
    tags={"consulta", "coronavirus", "transferencias"},
)
mcp.tool(consultar_coronavirus_despesas, tags={"consulta", "coronavirus", "despesas"})

# Tools — viagens (expandido)
mcp.tool(buscar_viagens_orgao, tags={"busca", "viagens", "orgao"})
mcp.tool(detalhar_viagem, tags={"detalhe", "viagens"})

# Tools — servidores (expandido)
mcp.tool(buscar_remuneracoes_servidores, tags={"busca", "servidores", "remuneracao"})
mcp.tool(buscar_servidores_por_orgao, tags={"busca", "servidores", "orgao"})
mcp.tool(listar_funcoes_cargos, tags={"referencia", "servidores", "funcoes", "cargos"})

# Tools — benefícios (expandido)
mcp.tool(consultar_seguro_defeso, tags={"consulta", "beneficios-sociais", "seguro-defeso"})
mcp.tool(consultar_garantia_safra, tags={"consulta", "beneficios-sociais", "garantia-safra"})
mcp.tool(consultar_peti, tags={"consulta", "beneficios-sociais", "peti"})

# Tools — licitações (expandido)
mcp.tool(detalhar_licitacao, tags={"detalhe", "licitacoes"})
mcp.tool(buscar_licitacao_por_processo, tags={"busca", "licitacoes", "processo"})
mcp.tool(buscar_participantes_licitacao, tags={"busca", "licitacoes", "participantes"})
mcp.tool(listar_modalidades_licitacao, tags={"referencia", "licitacoes", "modalidades"})
mcp.tool(buscar_itens_licitados, tags={"busca", "licitacoes", "itens"})
mcp.tool(buscar_empenhos_licitacao, tags={"busca", "licitacoes", "empenhos"})
mcp.tool(buscar_contratos_licitacao, tags={"busca", "licitacoes", "contratos"})
mcp.tool(buscar_unidades_gestoras, tags={"referencia", "licitacoes", "ugs"})

# Tools — emendas (expandido)
mcp.tool(buscar_documentos_emenda, tags={"busca", "emendas", "documentos"})

# Tools — despesas (expandido)
mcp.tool(consultar_despesas_orgao, tags={"consulta", "despesas", "orgao"})
mcp.tool(consultar_despesas_funcional, tags={"consulta", "despesas", "funcional"})
mcp.tool(buscar_documentos_despesa, tags={"busca", "despesas", "documentos"})
mcp.tool(buscar_itens_empenho, tags={"busca", "despesas", "empenho", "itens"})

# Tools — convênios (expandido)
mcp.tool(detalhar_convenio, tags={"detalhe", "convenios"})
mcp.tool(buscar_convenio_numero, tags={"busca", "convenios", "numero"})

# Tools — contratos (expandido)
mcp.tool(buscar_contratos_geral, tags={"busca", "contratos", "orgao"})
mcp.tool(buscar_contrato_numero, tags={"busca", "contratos", "numero"})
mcp.tool(buscar_termos_aditivos, tags={"busca", "contratos", "aditivos"})
mcp.tool(buscar_itens_contratados, tags={"busca", "contratos", "itens"})

# Tools — sanções (expandido)
mcp.tool(detalhar_sancao, tags={"detalhe", "sancoes"})

# Tools — notas fiscais (expandido)
mcp.tool(buscar_nota_fiscal_chave, tags={"busca", "notas-fiscais", "chave"})

# Resources (URIs without namespace prefix — mount adds "transparencia/" automatically)
mcp.resource("data://endpoints", mime_type="application/json")(endpoints_disponiveis)
mcp.resource("data://bases-sancoes", mime_type="application/json")(bases_sancoes)
mcp.resource("data://info-api", mime_type="application/json")(info_api)
mcp.resource("data://categorias-beneficios", mime_type="application/json")(categorias_beneficios)

# Prompts
mcp.prompt(auditoria_fornecedor)
mcp.prompt(analise_despesas)
mcp.prompt(verificacao_compliance)
