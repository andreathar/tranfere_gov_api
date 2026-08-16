"""Prompts for the inep_censo_escolar feature."""

from __future__ import annotations


def panorama_educacional_uf(uf: str = "SP") -> str:
    """Panorama educacional de uma UF — escolas, dependência, infraestrutura.

    Args:
        uf: Sigla da UF.
    """
    return (
        f"Faça um panorama educacional do estado {uf}.\n\n"
        "Passos:\n"
        f"1. resumo_uf('{uf}') — total por dependência administrativa\n"
        f"2. top_municipios_por_escolas('{uf}', limite=10) — concentração geográfica\n"
        f"3. buscar_escolas(uf='{uf}', dependencia=3, localizacao=2, limite=5) — "
        "amostra de escolas municipais rurais\n\n"
        "Apresente: distribuição por dependência, municípios com mais escolas, "
        "observações sobre escolas rurais."
    )


def comparar_infraestrutura(municipio_a: str, municipio_b: str, uf: str) -> str:
    """Compara infraestrutura escolar entre 2 municípios.

    Args:
        municipio_a: Primeiro município.
        municipio_b: Segundo município.
        uf: UF comum.
    """
    return (
        f"Compare a infraestrutura escolar entre {municipio_a} e {municipio_b} em {uf}.\n\n"
        f"1. buscar_escolas(uf='{uf}', municipio='{municipio_a}', limite=20)\n"
        f"2. buscar_escolas(uf='{uf}', municipio='{municipio_b}', limite=20)\n"
        "3. Para uma amostra de cada, use escola_detalhe(co_entidade)\n\n"
        "Compare presença de: água potável, internet, biblioteca, quadra, laboratórios."
    )
