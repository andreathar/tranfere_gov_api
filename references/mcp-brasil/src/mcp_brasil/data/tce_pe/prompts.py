"""Analysis prompts for the TCE-PE feature."""

from __future__ import annotations


def analisar_municipio_pe(municipio: str, ano: int) -> str:
    """Análise de um município pernambucano no TCE-PE.

    Cruza licitações, contratos e despesas para avaliar
    a gestão de compras e despesas do município.

    Args:
        municipio: Nome do município (ex: "Recife").
        ano: Ano de referência (ex: 2024).
    """
    return (
        f"Analise a gestão do município {municipio} no ano {ano}:\n\n"
        f"1. Use `buscar_licitacoes_pe` com ano={ano} e municipio={municipio}\n"
        f"2. Use `buscar_contratos_pe` com ano={ano} e municipio={municipio}\n"
        f"3. Use `buscar_despesas_pe` com ano={ano} e municipio={municipio}\n"
        "4. Apresente um resumo com:\n"
        "   - Número de licitações e contratos no período\n"
        "   - Principais fornecedores por volume\n"
        "   - Volume total empenhado vs pago\n"
        "   - Áreas com maior gasto (funções)\n"
    )
