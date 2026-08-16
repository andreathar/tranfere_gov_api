"""Analysis prompts for the TCE-SC feature."""

from __future__ import annotations


def consultar_unidades_sc(municipio: str) -> str:
    """Consulta das unidades gestoras de um município de SC.

    Lista todas as unidades gestoras (prefeitura, câmara, autarquias,
    consórcios) de um município catarinense.

    Args:
        municipio: Nome do município (ex: "Florianópolis").
    """
    return (
        f"Consulte as unidades gestoras do município '{municipio}' em Santa Catarina.\n\n"
        "1. Use `listar_unidades_gestoras_sc` filtrando pelo município.\n"
        "2. Apresente a lista organizada por tipo (prefeitura, câmara, autarquias, etc.).\n"
        "3. Inclua o código de cada unidade para referência."
    )
