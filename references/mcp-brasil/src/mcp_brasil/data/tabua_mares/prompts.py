"""Analysis prompts for the Tabua Mares feature.

Prompts are reusable templates that guide LLM interactions.
They instruct the LLM on which tools to call and how to analyze the data.

In Claude Desktop, prompts appear as selectable options (similar to slash commands).
"""

from __future__ import annotations


def consulta_mares(estado: str, mes: int) -> str:
    """Consulta completa de marés para um estado e mês.

    Guia o LLM a buscar portos e tábua de marés para planejar atividades
    costeiras como pesca, navegação ou surfe.

    Args:
        estado: Sigla do estado costeiro (ex: rj, sp, pb).
        mes: Mês para consulta (1-12).
    """
    return (
        f"Faça uma consulta completa de marés para o estado '{estado.upper()}' "
        f"no mês {mes}:\n\n"
        "1. Use `listar_portos` para ver os portos disponíveis no estado\n"
        "2. Para cada porto, use `consultar_tabua_mare` para obter os dados do mês\n"
        "3. Apresente um resumo com:\n"
        "   - Nome e localização de cada porto\n"
        "   - Horários de maré alta e baixa mais relevantes\n"
        "   - Nível médio do mar\n"
        "4. Destaque os dias com maiores amplitudes de maré"
    )


def analise_navegacao(lat: float, lng: float, estado: str) -> str:
    """Análise de condições de maré para navegação em uma localização.

    Guia o LLM a encontrar o porto mais próximo e analisar as condições
    de maré para navegação segura.

    Args:
        lat: Latitude da localização.
        lng: Longitude da localização.
        estado: Sigla do estado costeiro.
    """
    return (
        f"Analise as condições de maré para navegação nas coordenadas "
        f"({lat}, {lng}) no estado {estado.upper()}:\n\n"
        "1. Use `porto_mais_proximo` para encontrar o porto de referência\n"
        "2. Use `consultar_tabua_mare` para obter as marés dos próximos dias\n"
        "3. Apresente:\n"
        "   - Porto de referência e distância aproximada\n"
        "   - Horários de maré alta (bom para entrada/saída de embarcações)\n"
        "   - Horários de maré baixa (atenção a calados)\n"
        "   - Amplitude de maré do dia\n"
        "4. Dê recomendações para navegação segura"
    )
