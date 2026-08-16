"""Prompts for IPEADATA."""

from __future__ import annotations


def analise_historica(termo: str = "IPCA") -> str:
    """Análise histórica de uma série IPEADATA.

    Args:
        termo: Nome da série buscado (ex: 'IPCA', 'Selic').
    """
    return (
        f"Analise a série IPEADATA relacionada a '{termo}'.\n\n"
        f"1. buscar_serie('{termo}') para localizar o código exato\n"
        "2. metadados_serie(codigo) para entender unidade, base, fonte\n"
        "3. valores_serie(codigo, limite=120) para 10 anos de histórico (mensal)\n\n"
        "Apresente: valor atual, variação no último ano, tendência de longo prazo."
    )
