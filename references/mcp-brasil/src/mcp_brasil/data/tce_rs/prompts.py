"""Analysis prompts for the TCE-RS feature."""

from __future__ import annotations


def analisar_municipio_rs(municipio: str, ano: int = 2024) -> str:
    """Análise fiscal e de compliance de um município do RS.

    Gera uma análise completa usando dados de educação, saúde e gestão
    fiscal do TCE-RS para verificar o cumprimento de obrigações legais.

    Args:
        municipio: Nome do município (ex: "Porto Alegre").
        ano: Ano de referência (padrão: 2024).
    """
    return (
        f"Analise o município '{municipio}' no ano {ano} usando dados do TCE-RS.\n\n"
        "Siga estes passos:\n\n"
        "1. Use `buscar_indices_educacao_rs` para verificar o índice de educação (MDE).\n"
        "   O mínimo constitucional é 25% da receita em educação.\n\n"
        "2. Use `buscar_indices_saude_rs` para verificar o índice de saúde (ASPS).\n"
        "   O mínimo constitucional é 15% da receita em saúde.\n\n"
        "3. Use `buscar_gestao_fiscal_rs` para analisar a gestão fiscal (LRF):\n"
        "   - Receita corrente líquida\n"
        "   - Despesa com pessoal (limite: 54% da RCL para executivo)\n"
        "   - Dívida consolidada\n\n"
        "4. Apresente um resumo com:\n"
        "   - Cumprimento dos mínimos de educação e saúde (✅ ou ❌)\n"
        "   - Situação fiscal (despesa com pessoal vs limite LRF)\n"
        "   - Alertas se algum indicador estiver crítico"
    )
