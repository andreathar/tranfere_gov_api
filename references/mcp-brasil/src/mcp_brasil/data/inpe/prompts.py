"""Prompts for the INPE feature — analysis templates for LLMs.

Prompts provide reusable message templates that guide LLM interactions.
They appear in client UIs (e.g., Claude Desktop) as slash-commands.
"""

from __future__ import annotations


def monitoramento_ambiental(regiao: str = "Amazônia") -> str:
    """Gera uma análise de monitoramento ambiental de uma região.

    Cria um template que orienta o LLM a consultar dados de queimadas,
    desmatamento e alertas DETER para uma região específica.

    Args:
        regiao: Nome da região ou bioma a analisar (ex: Amazônia, Cerrado, PA).
    """
    return (
        f"Faça uma análise completa de monitoramento ambiental da região: {regiao}.\n\n"
        "Passos sugeridos:\n"
        "1. Use dados_satelite() para listar os satélites de monitoramento disponíveis\n"
        f"2. Use buscar_focos_queimadas(estado ou bioma relacionado a '{regiao}') "
        "para obter focos de incêndio recentes\n"
        f"3. Use alertas_deter(bioma ou estado relacionado a '{regiao}') "
        "para verificar alertas de desmatamento\n"
        f"4. Use consultar_desmatamento(bioma ou estado relacionado a '{regiao}') "
        "para dados históricos do PRODES\n\n"
        "Apresente a análise com:\n"
        "- Resumo da situação atual (focos de queimadas e alertas recentes)\n"
        "- Evolução histórica do desmatamento na região\n"
        "- Principais municípios afetados\n"
        "- Comparação entre biomas, se aplicável\n"
        "- Recomendações de monitoramento"
    )
