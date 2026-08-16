"""Prompts for the inep_enem feature."""

from __future__ import annotations


def panorama_notas_uf(uf: str = "SP") -> str:
    """Panorama estatístico das notas do ENEM em uma UF.

    Args:
        uf: Sigla da UF.
    """
    return (
        f"Faça um panorama das notas do ENEM em {uf}.\n\n"
        "Passos:\n"
        f"1. media_notas_uf('{uf}') — médias das 5 áreas\n"
        f"2. media_notas_por_grupo('TP_ESCOLA', uf='{uf}') — pública vs. privada\n"
        f"3. media_notas_por_grupo('TP_COR_RACA', uf='{uf}') — dimensão racial\n"
        f"4. top_municipios_por_media('{uf}', minimo_participantes=200, limite=10)\n\n"
        "Apresente: média estadual, gap pública/privada, diferenças raciais, "
        "municípios de destaque."
    )


def comparar_ufs(uf_a: str, uf_b: str) -> str:
    """Compara performance no ENEM entre 2 UFs.

    Args:
        uf_a: Primeira UF.
        uf_b: Segunda UF.
    """
    return (
        f"Compare as notas do ENEM entre {uf_a} e {uf_b}.\n\n"
        f"1. media_notas_uf('{uf_a}')\n"
        f"2. media_notas_uf('{uf_b}')\n"
        "3. Destaque diferenças por área e faça ranking por média geral."
    )
