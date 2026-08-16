"""Analysis prompts for the TCE-RJ feature."""

from __future__ import annotations


def analisar_municipio_rj(municipio: str) -> str:
    """Análise completa de um município fluminense no TCE-RJ.

    Verifica licitações, contratos, compras diretas, obras paralisadas,
    penalidades e prestação de contas de um município do Rio de Janeiro.

    Args:
        municipio: Nome do município em MAIÚSCULAS (ex: "NITEROI").
    """
    return (
        f"Analise a situação do município {municipio} no TCE-RJ:\n\n"
        "1. Use `buscar_licitacoes` para ver os processos licitatórios recentes\n"
        "2. Use `buscar_contratos_municipio` para listar contratos vigentes\n"
        "3. Use `buscar_compras_diretas` para verificar dispensas e inexigibilidades\n"
        "4. Use `buscar_obras_paralisadas` para identificar obras paradas no município\n"
        "5. Use `buscar_penalidades` para verificar multas aplicadas pelo TCE-RJ\n"
        "6. Use `buscar_prestacao_contas` para ver o parecer sobre as contas do prefeito\n\n"
        "Apresente um resumo consolidado com:\n"
        "- Volume de licitações e contratos\n"
        "- Eventuais irregularidades (compras diretas excessivas, obras paradas)\n"
        "- Situação das contas do prefeito\n"
        "- Penalidades aplicadas\n"
    )
