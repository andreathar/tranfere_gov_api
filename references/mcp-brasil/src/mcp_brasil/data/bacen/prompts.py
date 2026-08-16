"""Prompts for the Bacen feature — economic analysis templates for LLMs.

Prompts provide reusable message templates that guide LLM interactions.
They appear in client UIs (e.g., Claude Desktop) as slash-commands.
"""

from __future__ import annotations


def analise_economica(periodo: str = "últimos 12 meses") -> str:
    """Gera um panorama da conjuntura econômica brasileira.

    Cria um template que orienta o LLM a consultar os principais
    indicadores econômicos e produzir uma análise integrada.

    Args:
        periodo: Período de análise (ex: "últimos 12 meses", "2024", "jan/2024 a dez/2024").
    """
    return (
        f"Faça uma análise da conjuntura econômica brasileira para o período: {periodo}.\n\n"
        "Passos:\n"
        "1. Use indicadores_atuais() para obter o panorama atual "
        "(Selic, IPCA, IPCA 12m, Dólar, IBC-Br)\n"
        "2. Use ultimos_valores(codigo=432, quantidade=12) para a evolução da Selic\n"
        "3. Use ultimos_valores(codigo=433, quantidade=12) para a evolução do IPCA mensal\n"
        "4. Use ultimos_valores(codigo=3698, quantidade=12) para a evolução do câmbio\n"
        "5. Use ultimos_valores(codigo=24364, quantidade=12) para a evolução do IBC-Br\n\n"
        "Apresente:\n"
        "- Resumo executivo dos indicadores atuais\n"
        "- Tendência de cada indicador (alta, estável, queda)\n"
        "- Relações entre os indicadores (ex: Selic vs IPCA, câmbio vs IBC-Br)\n"
        "- Perspectiva geral: a economia está aquecendo, desaquecendo ou estável?"
    )


def comparar_indicadores(codigos: str, periodo: str = "últimos 12 meses") -> str:
    """Compara séries temporais específicas do BCB.

    Cria um template de análise comparativa entre indicadores selecionados.

    Args:
        codigos: Códigos das séries separados por vírgula (ex: "432,433,3698").
        periodo: Período de análise.
    """
    lista_codigos = [c.strip() for c in codigos.split(",")]
    codigos_formatados = ", ".join(lista_codigos)

    return (
        f"Compare os seguintes indicadores do Banco Central: {codigos_formatados}\n"
        f"Período de análise: {periodo}\n\n"
        "Passos:\n"
        + "\n".join(
            f"{i + 1}. Use metadados_serie(codigo={c}) para entender cada série"
            for i, c in enumerate(lista_codigos)
        )
        + "\n"
        + "\n".join(
            f"{len(lista_codigos) + i + 1}. "
            f"Use ultimos_valores(codigo={c}, quantidade=12) para dados recentes"
            for i, c in enumerate(lista_codigos)
        )
        + "\n\nApresente:\n"
        "- Descrição de cada indicador (nome, unidade, periodicidade)\n"
        "- Tabela comparativa com valores recentes\n"
        "- Variação percentual de cada série no período\n"
        "- Correlações ou relações observadas entre os indicadores"
    )
