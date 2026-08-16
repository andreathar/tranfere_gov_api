"""Analysis prompts for the TCE-TO feature."""

from __future__ import annotations


def analisar_pessoa_to(nome: str) -> str:
    """Análise de processos de uma pessoa no TCE-TO.

    Busca e analisa todos os processos vinculados a uma pessoa
    no Tribunal de Contas do Tocantins.

    Args:
        nome: Nome da pessoa a pesquisar.
    """
    return (
        f"Analise os processos de '{nome}' no TCE-TO.\n\n"
        "1. Use `buscar_pessoas_to` para encontrar a pessoa.\n"
        "2. Para cada processo relevante, use `consultar_processo_to` "
        "para obter detalhes.\n"
        "3. Apresente um resumo com:\n"
        "   - Quantidade total de processos\n"
        "   - Tipos de processos (classes de assunto)\n"
        "   - Entidades de origem\n"
        "   - Situação atual (departamento)"
    )
