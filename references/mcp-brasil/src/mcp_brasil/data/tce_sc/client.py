"""HTTP client for the TCE-SC Portal da Transparência API.

The TCE-SC open API has only two unauthenticated endpoints:
    - /municipios.php      → listar_municipios
    - /unidades-gestoras.php → listar_unidades_gestoras

Both return flat JSON arrays with no pagination or filtering.
"""

from __future__ import annotations

from typing import Any

from mcp_brasil._shared.http_client import http_get

from .constants import MUNICIPIOS_URL, UNIDADES_GESTORAS_URL
from .schemas import Municipio, UnidadeGestora


async def listar_municipios() -> list[Municipio]:
    """Fetch the list of SC municipalities (295 total)."""
    data: list[dict[str, Any]] = await http_get(MUNICIPIOS_URL)
    return [
        Municipio(
            codigo_municipio=item.get("codigo_municipio"),
            nome_municipio=item.get("nome_municipio"),
        )
        for item in data
    ]


async def listar_unidades_gestoras() -> list[UnidadeGestora]:
    """Fetch all managing units in SC (~2768 total)."""
    data: list[dict[str, Any]] = await http_get(UNIDADES_GESTORAS_URL)
    return [
        UnidadeGestora(
            codigo_unidade=item.get("codigo_unidade"),
            nome_unidade=item.get("nome_unidade"),
            sigla_unidade=item.get("sigla_unidade"),
            nome_municipio=item.get("nome_municipio"),
        )
        for item in data
    ]
