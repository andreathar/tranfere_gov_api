"""HTTP client for the Tabua Mares API.

Endpoints:
    - GET /api/v2/states — lista estados costeiros
    - GET /api/v2/harbor_names/{state} — portos por estado
    - GET /api/v2/harbors/{ids} — detalhes de portos
    - GET /api/v2/tabua-mare/{harbor}/{month}/{days} — tábua de marés
    - GET /api/v2/nearested-harbor/{state}/{lat_lng} — porto mais próximo (estado)
    - GET /api/v2/nearest-harbor-independent-state/{lat_lng} — porto mais próximo (geral)
    - GET /geo-tabua-mare/{lat_lng}/{state}/{month}/{days} — tábua por geolocalização
"""

from __future__ import annotations

from typing import Any

from mcp_brasil._shared.http_client import http_get

from .constants import (
    GEO_TABUA_MARE_URL,
    HARBOR_NAMES_URL,
    HARBORS_URL,
    NEAREST_HARBOR_INDEPENDENT_URL,
    NEAREST_HARBOR_URL,
    STATES_URL,
    TABUA_MARE_URL,
)
from .schemas import Porto, PortoResumo, TabuaMare


async def listar_estados() -> list[str]:
    """Lista os estados costeiros disponíveis.

    Returns:
        Lista de siglas dos estados (ex: ['al', 'ap', 'ba', ...]).
    """
    resp: dict[str, Any] = await http_get(STATES_URL)
    data: list[str] = resp.get("data", [])
    return data


async def listar_portos_estado(estado: str) -> list[PortoResumo]:
    """Lista os portos de um estado.

    Args:
        estado: Sigla do estado em minúsculo (ex: pb, rj, sp).

    Returns:
        Lista de portos com id, ano, nome e instituição coletora.
    """
    resp: dict[str, Any] = await http_get(f"{HARBOR_NAMES_URL}/{estado.lower()}")
    return [PortoResumo(**p) for p in resp.get("data", [])]


async def buscar_portos(ids: list[str]) -> list[Porto]:
    """Busca detalhes de portos por IDs.

    Args:
        ids: Lista de IDs de portos (ex: ['pb01', 'pe02']).

    Returns:
        Lista de portos com detalhes completos.
    """
    ids_param = "[" + ",".join(ids) + "]"
    resp: dict[str, Any] = await http_get(f"{HARBORS_URL}/{ids_param}")
    return [Porto(**p) for p in resp.get("data", [])]


async def consultar_tabua_mare(
    porto_id: str,
    mes: int,
    dias: str,
) -> list[TabuaMare]:
    """Consulta a tábua de marés de um porto para um período.

    Args:
        porto_id: ID do porto (ex: 'pb01').
        mes: Mês desejado (1-12).
        dias: Dias no formato '[1,2,3]' ou '[1,5-13]'.

    Returns:
        Dados da tábua de marés.
    """
    dias_param = dias if dias.startswith("[") else f"[{dias}]"
    resp: dict[str, Any] = await http_get(f"{TABUA_MARE_URL}/{porto_id}/{mes}/{dias_param}")
    return [TabuaMare(**t) for t in resp.get("data", [])]


async def porto_mais_proximo(
    estado: str,
    lat: float,
    lng: float,
) -> list[Porto]:
    """Encontra o porto mais próximo dentro de um estado.

    Args:
        estado: Sigla do estado (ex: pb, rj, sp).
        lat: Latitude (ex: -7.11509).
        lng: Longitude (ex: -34.864).

    Returns:
        Porto mais próximo.
    """
    coords = f"[{lat},{lng}]"
    resp: dict[str, Any] = await http_get(f"{NEAREST_HARBOR_URL}/{estado.lower()}/{coords}")
    return [Porto(**p) for p in resp.get("data", [])]


async def porto_mais_proximo_geral(lat: float, lng: float) -> list[Porto]:
    """Encontra o porto mais próximo independente do estado.

    Args:
        lat: Latitude (ex: -7.11509).
        lng: Longitude (ex: -34.864).

    Returns:
        Porto mais próximo.
    """
    coords = f"[{lat},{lng}]"
    resp: dict[str, Any] = await http_get(f"{NEAREST_HARBOR_INDEPENDENT_URL}/{coords}")
    return [Porto(**p) for p in resp.get("data", [])]


async def tabua_mare_por_geolocalizacao(
    lat: float,
    lng: float,
    estado: str,
    mes: int,
    dias: str,
) -> list[TabuaMare]:
    """Obtém a tábua de marés do porto mais próximo por geolocalização.

    Args:
        lat: Latitude (ex: -7.11509).
        lng: Longitude (ex: -34.864).
        estado: Sigla do estado (ex: pb, rj, sp).
        mes: Mês (1-12).
        dias: Dias no formato '[1,2,3]' ou '[1,5-13]'.

    Returns:
        Dados da tábua de marés do porto mais próximo.
    """
    coords = f"[{lat},{lng}]"
    dias_param = dias if dias.startswith("[") else f"[{dias}]"
    resp: dict[str, Any] = await http_get(
        f"{GEO_TABUA_MARE_URL}/{coords}/{estado.lower()}/{mes}/{dias_param}"
    )
    return [TabuaMare(**t) for t in resp.get("data", [])]
