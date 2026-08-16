"""HTTP client for the INPE API.

Endpoints:
    - BD Queimadas: focos de incêndio detectados por satélite
    - TerraBrasilis DETER: alertas de desmatamento em tempo quase real
    - TerraBrasilis PRODES: desmatamento histórico (anual)
    - Satélites: lista de satélites disponíveis para monitoramento
"""

from __future__ import annotations

from typing import Any

from mcp_brasil._shared.http_client import http_get

from .constants import DEFAULT_LIMIT, DETER_URL, FOCOS_URL, PRODES_URL, SATELITES_URL
from .schemas import AlertaDeter, DadosProdes, FocoQueimada, Satelite


async def buscar_focos(
    *,
    estado: str | None = None,
    data_inicio: str | None = None,
    data_fim: str | None = None,
    satelite: str | None = None,
    limite: int = DEFAULT_LIMIT,
) -> list[FocoQueimada]:
    """Fetch fire hotspots from BD Queimadas.

    Args:
        estado: 2-letter state code (e.g. "PA", "MT").
        data_inicio: Start date in YYYY-MM-DD format.
        data_fim: End date in YYYY-MM-DD format.
        satelite: Satellite name (e.g. "AQUA_M-T", "NPP-375").
        limite: Maximum number of results.
    """
    params: dict[str, Any] = {"pais_id": 33, "limit": limite}
    if estado:
        params["estado_id"] = estado.upper()
    if data_inicio:
        params["data_inicio"] = data_inicio
    if data_fim:
        params["data_fim"] = data_fim
    if satelite:
        params["satelite"] = satelite

    data: list[dict[str, Any]] = await http_get(FOCOS_URL, params=params)

    return [
        FocoQueimada(
            id=str(item.get("id", "")),
            latitude=float(item.get("latitude", 0)),
            longitude=float(item.get("longitude", 0)),
            data_hora=str(item.get("data_hora", "")),
            satelite=str(item.get("satelite", "")),
            municipio=str(item.get("municipio", "")),
            estado=str(item.get("estado", "")),
            bioma=str(item.get("bioma", "")),
            dias_sem_chuva=item.get("dias_sem_chuva"),
            risco_fogo=item.get("risco_fogo"),
            frp=item.get("frp"),
        )
        for item in data
    ]


async def buscar_alertas_deter(
    *,
    bioma: str | None = None,
    estado: str | None = None,
    data_inicio: str | None = None,
    data_fim: str | None = None,
) -> list[AlertaDeter]:
    """Fetch DETER deforestation alerts.

    Args:
        bioma: Biome name (e.g. "Amazônia", "Cerrado").
        estado: 2-letter state code (e.g. "PA", "MT").
        data_inicio: Start date in YYYY-MM-DD format.
        data_fim: End date in YYYY-MM-DD format.
    """
    params: dict[str, str] = {}
    if bioma:
        params["bioma"] = bioma
    if estado:
        params["estado"] = estado.upper()
    if data_inicio:
        params["data_inicio"] = data_inicio
    if data_fim:
        params["data_fim"] = data_fim

    data: list[dict[str, Any]] = await http_get(DETER_URL, params=params or None)

    return [
        AlertaDeter(
            id=str(item.get("id", "")),
            data=str(item.get("data", "")),
            area_km2=float(item.get("area_km2", 0)),
            municipio=str(item.get("municipio", "")),
            estado=str(item.get("estado", "")),
            bioma=str(item.get("bioma", "")),
            classe=str(item.get("classe", "")),
            satelite=str(item.get("satelite", "")),
        )
        for item in data
    ]


async def buscar_dados_prodes(
    *,
    bioma: str | None = None,
    estado: str | None = None,
    ano: int | None = None,
) -> list[DadosProdes]:
    """Fetch PRODES historical deforestation data.

    Args:
        bioma: Biome name (e.g. "Amazônia", "Cerrado").
        estado: 2-letter state code (e.g. "PA", "MT").
        ano: Year to query (e.g. 2023).
    """
    params: dict[str, str | int] = {}
    if bioma:
        params["bioma"] = bioma
    if estado:
        params["estado"] = estado.upper()
    if ano:
        params["ano"] = ano

    data: list[dict[str, Any]] = await http_get(PRODES_URL, params=params or None)

    return [
        DadosProdes(
            ano=int(item.get("ano", 0)),
            bioma=str(item.get("bioma", "")),
            area_km2=float(item.get("area_km2", 0)),
            estado=str(item.get("estado", "")),
            municipio=str(item.get("municipio", "")),
        )
        for item in data
    ]


async def listar_satelites() -> list[Satelite]:
    """Fetch list of available monitoring satellites."""
    data: list[dict[str, Any]] = await http_get(SATELITES_URL)

    return [
        Satelite(
            nome=str(item.get("nome", "")),
            descricao=str(item.get("descricao", "")),
        )
        for item in data
    ]
