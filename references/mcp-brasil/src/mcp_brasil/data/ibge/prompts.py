"""Prompts for the IBGE feature — analysis templates for LLMs.

Prompts provide reusable message templates that guide LLM interactions.
They appear in client UIs (e.g., Claude Desktop) as slash-commands.
"""

from __future__ import annotations


def resumo_estado(uf: str) -> str:
    """Gera um resumo analítico completo de um estado brasileiro.

    Cria um template de análise que orienta o LLM a consultar dados
    de população, PIB, municípios e indicadores geográficos do estado.

    Args:
        uf: Sigla do estado com 2 letras (ex: SP, RJ, PI, BA).
    """
    return (
        f"Faça uma análise completa do estado {uf.upper()} usando os dados do IBGE.\n\n"
        "Inclua as seguintes informações:\n"
        f"1. Use a tool listar_estados para confirmar o nome e região de {uf.upper()}\n"
        f"2. Use buscar_municipios(uf='{uf.upper()}') para contar os municípios\n"
        f"3. Use consultar_agregado(indicador='populacao', nivel='estado', "
        f"localidade='{uf.upper()}') para a população\n"
        f"4. Use consultar_agregado(indicador='pib', nivel='estado', "
        f"localidade='{uf.upper()}') para o PIB\n"
        f"5. Use consultar_agregado(indicador='pib_per_capita', nivel='estado', "
        f"localidade='{uf.upper()}') para o PIB per capita\n\n"
        "Apresente os dados em um resumo organizado com:\n"
        "- Dados gerais (nome, região, capital estimada)\n"
        "- Demografia (população, número de municípios)\n"
        "- Economia (PIB, PIB per capita)\n"
        "- Contexto comparativo com outros estados da mesma região"
    )


def comparativo_regional() -> str:
    """Gera uma comparação entre as 5 macro-regiões do Brasil.

    Cria um template que orienta o LLM a comparar indicadores
    de população, PIB e desenvolvimento entre Norte, Nordeste,
    Sudeste, Sul e Centro-Oeste.
    """
    return (
        "Faça uma análise comparativa das 5 macro-regiões do Brasil usando dados do IBGE.\n\n"
        "Passos:\n"
        "1. Use listar_regioes para obter as 5 regiões\n"
        "2. Use consultar_agregado(indicador='populacao', nivel='regiao') "
        "para população por região\n"
        "3. Use consultar_agregado(indicador='pib', nivel='regiao') "
        "para PIB por região\n"
        "4. Use consultar_agregado(indicador='pib_per_capita', nivel='regiao') "
        "para PIB per capita por região\n\n"
        "Apresente:\n"
        "- Tabela comparativa com população, PIB e PIB per capita de cada região\n"
        "- Ranking por cada indicador\n"
        "- Análise das desigualdades regionais\n"
        "- Destaque para a concentração econômica no Sudeste"
    )
