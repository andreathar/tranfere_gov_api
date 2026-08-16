"""Prompts for the ANA feature — analysis templates for LLMs.

Prompts provide reusable message templates that guide LLM interactions.
"""

from __future__ import annotations


def analise_bacia(bacia: str) -> str:
    """Gera uma análise hidrológica completa de uma bacia hidrográfica.

    Cria um template de análise que orienta o LLM a consultar estações,
    dados telemétricos e reservatórios de uma bacia hidrográfica brasileira.

    Args:
        bacia: Nome ou código da bacia hidrográfica (ex: "Paraná", "São Francisco").
    """
    return (
        f"Faça uma análise hidrológica completa da bacia {bacia} "
        "usando os dados da ANA.\n\n"
        "Passos:\n"
        f"1. Use buscar_estacoes(nome_estacao='{bacia}') para encontrar estações na bacia\n"
        "2. Para as principais estações encontradas, use consultar_telemetria "
        "para obter dados recentes de nível e vazão\n"
        "3. Use monitorar_reservatorios() para verificar o nível dos reservatórios "
        "na bacia\n\n"
        "Apresente:\n"
        "- Quantidade de estações fluviométricas e pluviométricas na bacia\n"
        "- Dados de nível e vazão das principais estações\n"
        "- Situação dos reservatórios (volume útil, vazões)\n"
        "- Análise geral da situação hídrica da bacia"
    )
