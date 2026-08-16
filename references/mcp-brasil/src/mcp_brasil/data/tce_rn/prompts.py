"""Analysis prompts for the TCE-RN feature."""

from __future__ import annotations


def analisar_unidade_rn(id_unidade: int, ano: int = 2024) -> str:
    """Análise orçamentária e de licitações de uma unidade do RN.

    Gera uma análise completa usando dados de despesas, receitas,
    licitações e contratos do TCE-RN.

    Args:
        id_unidade: ID da unidade (obtido via listar_jurisdicionados_rn).
        ano: Ano de referência (padrão: 2024).
    """
    return (
        f"Analise a unidade {id_unidade} no ano {ano} usando dados do TCE-RN.\n\n"
        "Siga estes passos:\n\n"
        "1. Use `buscar_despesas_rn` com bimestre=6 para ver o acumulado anual.\n"
        "2. Use `buscar_receitas_rn` com bimestre=6 para ver arrecadação.\n"
        f"3. Use `buscar_licitacoes_rn` com período {ano}-01-01 a {ano}-12-31.\n"
        "4. Use `buscar_contratos_rn` para ver contratos vigentes.\n\n"
        "Apresente um resumo com:\n"
        "- Principais despesas e receitas\n"
        "- Licitações realizadas (quantidade e valor total)\n"
        "- Contratos vigentes (maiores valores)"
    )
