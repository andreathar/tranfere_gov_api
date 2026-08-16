"""Prompts for the anp_precos feature — price analysis templates."""

from __future__ import annotations


def analise_gasolina_uf(uf: str = "SP") -> str:
    """Análise de preços de gasolina em uma UF.

    Args:
        uf: Sigla da UF.
    """
    return (
        f"Faça uma análise dos preços de gasolina em {uf}.\n\n"
        "Passos:\n"
        f"1. media_preco_uf(uf='{uf}', produto='GASOLINA') — panorama estatístico\n"
        f"2. media_preco_por_bandeira(uf='{uf}', produto='GASOLINA') — comparação por bandeira\n"
        f"3. top_postos_caros(uf='{uf}', produto='GASOLINA', limite=10) — postos mais caros\n\n"
        "Apresente: média estadual, faixa min/max, variação por bandeira, "
        "destaques geográficos (municípios fora da curva)."
    )


def comparar_municipios(municipio_a: str, municipio_b: str, uf: str) -> str:
    """Compara preços de gasolina entre dois municípios da mesma UF.

    Args:
        municipio_a: Primeiro município.
        municipio_b: Segundo município.
        uf: UF comum.
    """
    return (
        f"Compare preços de gasolina entre {municipio_a} e {municipio_b} em {uf}.\n\n"
        f"1. precos_por_municipio('{municipio_a}', '{uf}', 'GASOLINA')\n"
        f"2. precos_por_municipio('{municipio_b}', '{uf}', 'GASOLINA')\n\n"
        "Calcule a média em cada município, identifique o mais barato "
        "e compare a dispersão de preços (diferença min/max)."
    )
