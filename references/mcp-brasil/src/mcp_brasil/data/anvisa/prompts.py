"""Analysis prompts for the ANVISA feature.

Prompts are reusable templates that guide LLM interactions.
They instruct the LLM on which tools to call and how to analyze the data.
"""

from __future__ import annotations


def pesquisa_medicamento(nome: str) -> str:
    """Pesquisa completa sobre um medicamento no Bulário ANVISA.

    Orienta o LLM a buscar o medicamento, consultar sua bula e
    apresentar informações relevantes.

    Args:
        nome: Nome do medicamento para pesquisar.
    """
    return (
        f"Faça uma pesquisa completa sobre o medicamento '{nome}' no Bulário ANVISA.\n\n"
        "Passos:\n"
        f"1. Use buscar_medicamento(nome='{nome}') para encontrar o medicamento\n"
        "2. Identifique o número do processo nos resultados\n"
        "3. Use consultar_bula(numero_processo=...) para acessar as bulas\n"
        "4. Use listar_categorias() se precisar explicar a categoria regulatória\n\n"
        "Apresente:\n"
        "- Nome comercial e princípio ativo\n"
        "- Empresa fabricante\n"
        "- Categoria regulatória (genérico, similar, referência etc.)\n"
        "- Indicações principais (se disponível na bula)\n"
        "- Links para bulas do paciente e do profissional"
    )
