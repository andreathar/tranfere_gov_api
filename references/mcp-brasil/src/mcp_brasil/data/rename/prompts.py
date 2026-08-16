"""Analysis prompts for the RENAME feature.

Prompts are reusable templates that guide LLM interactions.
They instruct the LLM on which tools to call and how to analyze the data.

In Claude Desktop, prompts appear as selectable options (similar to slash commands).
"""

from __future__ import annotations


def consulta_medicamento_sus(nome: str) -> str:
    """Assistente para consultar disponibilidade de medicamentos no SUS.

    Orienta o LLM a verificar se um medicamento está na RENAME e onde
    retirá-lo gratuitamente.

    Args:
        nome: Nome do medicamento ou princípio ativo (ex: "losartana").
    """
    return (
        f"Atue como um assistente de saúde pública para verificar a disponibilidade "
        f"de '{nome}' no Sistema Único de Saúde (SUS).\n\n"
        "Passos:\n"
        f"1. Use verificar_disponibilidade_sus(nome='{nome}') para checar se está na RENAME\n"
        f"2. Use buscar_medicamento_rename(nome='{nome}') para ver detalhes completos\n"
        "3. Informe se está disponível em UBS ou apenas em unidades especializadas\n\n"
        "Apresente:\n"
        "- Se o medicamento está na RENAME (é considerado essencial)\n"
        "- Apresentações disponíveis (comprimido, solução, injetável)\n"
        "- Onde retirar (UBS ou unidade especializada)\n"
        "- Se não encontrado, sugira usar a ANVISA para verificar registro"
    )
