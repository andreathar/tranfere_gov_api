"""HTTP client for the CNES/DataSUS API.

Endpoints:
    - /estabelecimentos          → buscar_estabelecimentos
    - /estabelecimentos/{cnes}   → buscar_estabelecimento_por_cnes
    - /profissionais             → buscar_profissionais
    - /tipodeestabelecimento     → listar_tipos_estabelecimento
    - /leitos                    → consultar_leitos
    - InfoDengue alertcity       → buscar_alertas_dengue
    - InfoGripe CSV              → buscar_situacao_gripe
"""

from __future__ import annotations

import csv
import datetime
import importlib.resources
import io
import json
import logging
import unicodedata
from typing import Any

from mcp_brasil._shared.http_client import create_client, http_get
from mcp_brasil.exceptions import HttpClientError

from .constants import (
    BASES_DATASUS,
    DEFAULT_LIMIT,
    DOENCAS_SINAN,
    ESTABELECIMENTOS_URL,
    INFODENGUE_API_BASE,
    INFOGRIPE_ALERTA_URL,
    LEITOS_URL,
    MAX_LIMIT,
    MAX_LIMIT_LEITOS,
    NIVEIS_ALERTA_DENGUE,
    TIPOS_URL,
)
from .schemas import (
    AlertaDengue,
    AlertaGripe,
    BaseDATASUS,
    DoencaNotificavel,
    Estabelecimento,
    EstabelecimentoDetalhe,
    Leito,
    MunicipioGeocode,
    TipoEstabelecimento,
)

logger = logging.getLogger(__name__)


def _ensure_list(data: Any, url: str) -> list[dict[str, Any]]:
    """Extract a list of dicts from the API response.

    The DataSUS API returns either a list or a dict with a single key
    containing the list (e.g. {"estabelecimentos": [...]}).
    """
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # Try to extract the first list-valued key (e.g. "estabelecimentos")
        for v in data.values():
            if isinstance(v, list):
                return v
        return []
    raise HttpClientError(
        f"Unexpected response from {url}: expected list/dict, got {type(data).__name__}"
    )


def _ensure_dict(data: Any, url: str) -> dict[str, Any]:
    """Validate that API response is a dict."""
    if isinstance(data, dict):
        return data
    raise HttpClientError(
        f"Unexpected response from {url}: expected dict, got {type(data).__name__}"
    )


def _parse_estabelecimento(raw: dict[str, Any]) -> Estabelecimento:
    """Parse a raw establishment dict into an Estabelecimento model."""
    return Estabelecimento(
        codigo_cnes=str(raw.get("codigo_cnes", "") or ""),
        nome_fantasia=raw.get("nome_fantasia"),
        nome_razao_social=raw.get("nome_razao_social"),
        natureza_organizacao=raw.get("natureza_organizacao_entidade"),
        tipo_gestao=raw.get("tipo_gestao"),
        codigo_tipo=str(raw.get("codigo_tipo_unidade", "") or ""),
        descricao_tipo=raw.get("descricao_turno_atendimento"),
        codigo_municipio=str(raw.get("codigo_municipio", "") or ""),
        codigo_uf=str(raw.get("codigo_uf", "") or ""),
        endereco=raw.get("endereco_estabelecimento"),
    )


def _parse_tipo(raw: dict[str, Any]) -> TipoEstabelecimento:
    """Parse a raw type dict into a TipoEstabelecimento model."""
    return TipoEstabelecimento(
        codigo=str(raw.get("codigo_tipo_unidade", "") or ""),
        descricao=raw.get("descricao_tipo_unidade"),
    )


def _parse_leito(raw: dict[str, Any]) -> Leito:
    """Parse a raw hospital/bed dict from hospitais-e-leitos endpoint."""
    return Leito(
        codigo_cnes=str(raw.get("nome_do_hospital", "") or ""),
        tipo_leito=raw.get("descricao_do_tipo_da_unidade"),
        especialidade=raw.get("descricao_da_natureza_juridica_do_hosptial"),
        existente=raw.get("quantidade_total_de_leitos_do_hosptial"),
        sus=raw.get("quantidade_total_de_leitos_sus_do_hosptial"),
    )


async def buscar_estabelecimentos(
    *,
    codigo_municipio: str | None = None,
    codigo_uf: str | None = None,
    status: int | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> list[Estabelecimento]:
    """Search health establishments from CNES.

    API: GET /estabelecimentos

    Args:
        codigo_municipio: IBGE municipality code (e.g. "355030").
        codigo_uf: IBGE state code (e.g. "35").
        status: 1 for active, 0 for inactive.
        limit: Max results per page.
        offset: Pagination offset.
    """
    params: dict[str, Any] = {
        "limit": min(limit, MAX_LIMIT),
        "offset": offset,
    }
    if codigo_municipio:
        params["codigo_municipio"] = codigo_municipio
    if codigo_uf:
        params["codigo_uf"] = codigo_uf
    if status is not None:
        params["status"] = status

    raw = await http_get(ESTABELECIMENTOS_URL, params=params)
    data = _ensure_list(raw, ESTABELECIMENTOS_URL)
    return [_parse_estabelecimento(item) for item in data]


async def listar_tipos_estabelecimento() -> list[TipoEstabelecimento]:
    """Fetch all establishment types from CNES.

    API: GET /tipodeestabelecimento
    """
    raw = await http_get(TIPOS_URL)
    data = _ensure_list(raw, TIPOS_URL)
    return [_parse_tipo(item) for item in data]


async def consultar_leitos(
    *,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> list[Leito]:
    """Search hospitals and beds from DataSUS.

    API: GET /assistencia-a-saude/hospitais-e-leitos

    Args:
        limit: Max results per page (max 1000).
        offset: Pagination offset.
    """
    params: dict[str, Any] = {
        "limit": min(limit, MAX_LIMIT_LEITOS),
        "offset": offset,
    }

    raw = await http_get(LEITOS_URL, params=params)
    data = _ensure_list(raw, LEITOS_URL)
    return [_parse_leito(item) for item in data]


def _parse_estabelecimento_detalhe(raw: dict[str, Any]) -> EstabelecimentoDetalhe:
    """Parse a raw establishment dict into an EstabelecimentoDetalhe model."""
    return EstabelecimentoDetalhe(
        codigo_cnes=str(raw.get("codigo_cnes", "") or ""),
        nome_fantasia=raw.get("nome_fantasia"),
        nome_razao_social=raw.get("nome_razao_social"),
        natureza_organizacao=raw.get("natureza_organizacao_entidade"),
        tipo_gestao=raw.get("tipo_gestao"),
        codigo_tipo=str(raw.get("codigo_tipo_unidade", "") or ""),
        descricao_tipo=raw.get("descricao_turno_atendimento"),
        codigo_municipio=str(raw.get("codigo_municipio", "") or ""),
        codigo_uf=str(raw.get("codigo_uf", "") or ""),
        endereco=raw.get("endereco_estabelecimento"),
        bairro=raw.get("bairro_estabelecimento"),
        cep=raw.get("codigo_cep_estabelecimento"),
        telefone=raw.get("numero_telefone_estabelecimento"),
        latitude=raw.get("latitude_estabelecimento_decimo_grau"),
        longitude=raw.get("longitude_estabelecimento_decimo_grau"),
        cnpj=raw.get("numero_cnpj"),
        data_atualizacao=raw.get("data_atualizacao"),
    )


async def buscar_estabelecimento_por_cnes(cnes: str) -> EstabelecimentoDetalhe | None:
    """Fetch a single establishment by its CNES code.

    API: GET /estabelecimentos/{cnes}

    Args:
        cnes: CNES code (7 digits).
    """
    url = f"{ESTABELECIMENTOS_URL}/{cnes}"
    raw = await http_get(url)
    if not raw:
        return None
    data = _ensure_dict(raw, url)
    return _parse_estabelecimento_detalhe(data)


async def buscar_estabelecimentos_por_tipo(
    *,
    codigo_tipo: str,
    codigo_municipio: str | None = None,
    codigo_uf: str | None = None,
    status: int = 1,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> list[Estabelecimento]:
    """Search establishments filtered by type code.

    API: GET /estabelecimentos

    Args:
        codigo_tipo: Establishment type code (e.g. "73" for Pronto Atendimento).
        codigo_municipio: IBGE municipality code.
        codigo_uf: IBGE state code.
        status: 1 for active, 0 for inactive.
        limit: Max results per page.
        offset: Pagination offset.
    """
    params: dict[str, Any] = {
        "codigo_tipo_unidade": codigo_tipo,
        "status": status,
        "limit": min(limit, MAX_LIMIT),
        "offset": offset,
    }
    if codigo_municipio:
        params["codigo_municipio"] = codigo_municipio
    if codigo_uf:
        params["codigo_uf"] = codigo_uf

    raw = await http_get(ESTABELECIMENTOS_URL, params=params)
    data = _ensure_list(raw, ESTABELECIMENTOS_URL)
    return [_parse_estabelecimento(item) for item in data]


# ---------------------------------------------------------------------------
# Geocode — busca de municípios por nome
# ---------------------------------------------------------------------------

_geocode_cache: list[dict[str, str]] | None = None


def _normalize(text: str) -> str:
    """Remove accents and lowercase for fuzzy matching."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _load_geocode_data() -> list[dict[str, str]]:
    """Load bundled geocode data (cached after first call)."""
    global _geocode_cache
    if _geocode_cache is not None:
        return _geocode_cache

    pkg = importlib.resources.files("mcp_brasil.data.saude")
    geo_file = pkg.joinpath("geocode_municipios.json")
    _geocode_cache = json.loads(geo_file.read_text(encoding="utf-8"))
    return _geocode_cache


def buscar_municipio_geocodigo(
    nome: str,
    uf: str | None = None,
) -> list[MunicipioGeocode]:
    """Search municipalities by name (accent-insensitive).

    In-memory search over bundled JSON data. No HTTP call.
    Exact matches are returned first, then partial matches.

    Args:
        nome: Municipality name or partial name.
        uf: Optional UF abbreviation filter (e.g. "SP", "RJ").
    """
    data = _load_geocode_data()
    nome_norm = _normalize(nome)
    uf_upper = uf.upper() if uf else None

    exact: list[MunicipioGeocode] = []
    partial: list[MunicipioGeocode] = []
    for entry in data:
        if uf_upper and entry["uf"] != uf_upper:
            continue
        entry_norm = _normalize(entry["nome"])
        if nome_norm not in entry_norm:
            continue
        mun = MunicipioGeocode(
            nome=entry["nome"],
            uf=entry["uf"],
            geocodigo=entry["geocodigo"],
        )
        if entry_norm == nome_norm:
            exact.append(mun)
        else:
            partial.append(mun)
    return exact + partial


# ---------------------------------------------------------------------------
# InfoDengue — alertas de arboviroses
# ---------------------------------------------------------------------------


async def buscar_alertas_dengue(
    *,
    geocodigo: str,
    doenca: str = "dengue",
    ew_start: int = 1,
    ew_end: int = 52,
    ey_start: int = 0,
    ey_end: int = 0,
) -> list[AlertaDengue]:
    """Fetch dengue/chikungunya/zika alerts from InfoDengue API.

    API: GET https://info.dengue.mat.br/api/alertcity

    Args:
        geocodigo: IBGE municipality geocode (7 digits).
        doenca: Disease key (dengue, chikungunya, zika).
        ew_start: Epidemiological week start.
        ew_end: Epidemiological week end.
        ey_start: Epidemiological year start.
        ey_end: Epidemiological year end.
    """
    params: dict[str, Any] = {
        "geocode": geocodigo,
        "disease": doenca,
        "format": "json",
        "ew_start": ew_start,
        "ew_end": ew_end,
        "ey_start": ey_start,
        "ey_end": ey_end,
    }

    raw = await http_get(INFODENGUE_API_BASE, params=params)
    if not isinstance(raw, list):
        return []

    results: list[AlertaDengue] = []
    for item in raw:
        nivel = item.get("nivel")
        data_ini = item.get("data_iniSE")
        if isinstance(data_ini, (int, float)):
            # API returns timestamp in milliseconds — convert to date string
            data_ini = datetime.datetime.fromtimestamp(
                data_ini / 1000, tz=datetime.timezone.utc
            ).strftime("%Y-%m-%d")
        results.append(
            AlertaDengue(
                semana_epidemiologica=item.get("SE"),
                data_inicio_se=str(data_ini) if data_ini is not None else None,
                casos_estimados=item.get("casos_est"),
                casos_notificados=item.get("casos"),
                nivel=nivel,
                nivel_descricao=NIVEIS_ALERTA_DENGUE.get(nivel, "Desconhecido") if nivel else None,
                incidencia_100k=item.get("p_inc100k"),
                rt=item.get("Rt"),
                populacao=item.get("pop"),
                receptividade=item.get("receptession_level"),
                transmissao=item.get("transmission_evidence"),
            )
        )
    return results


# ---------------------------------------------------------------------------
# InfoGripe — situação de síndrome gripal
# ---------------------------------------------------------------------------


async def buscar_situacao_gripe() -> list[AlertaGripe]:
    """Fetch current flu/SRAG alert status from InfoGripe CSV.

    Source: Fiocruz GitLab repository (CSV download).
    """
    async with create_client() as http_client:
        try:
            response = await http_client.get(INFOGRIPE_ALERTA_URL)
            response.raise_for_status()
        except Exception as exc:
            raise HttpClientError(f"Request to InfoGripe failed: {exc}") from exc

    text = response.text
    reader = csv.DictReader(io.StringIO(text))

    results: list[AlertaGripe] = []
    for row in reader:
        try:
            results.append(
                AlertaGripe(
                    uf=row.get("UF") or row.get("uf"),
                    semana_epidemiologica=_safe_int(row.get("epiweek") or row.get("SE")),
                    ano=_safe_int(row.get("epiyear") or row.get("ano")),
                    situacao=row.get("situation_name") or row.get("situacao"),
                    nivel=row.get("level") or row.get("nivel"),
                    casos_estimados=_safe_float(
                        row.get("estimated_cases") or row.get("casos_est")
                    ),
                    casos_notificados=_safe_int(row.get("notified_cases") or row.get("casos")),
                    limite_inferior=_safe_float(row.get("ci_lower") or row.get("limiar_inferior")),
                    limite_superior=_safe_float(row.get("ci_upper") or row.get("limiar_superior")),
                )
            )
        except (ValueError, KeyError):
            continue  # skip malformed rows

    return results


def _safe_int(val: str | None) -> int | None:
    """Parse an int from a string, returning None on failure."""
    if val is None:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _safe_float(val: str | None) -> float | None:
    """Parse a float from a string, returning None on failure."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# In-memory — bases DATASUS e doenças SINAN
# ---------------------------------------------------------------------------


def listar_bases_datasus() -> list[BaseDATASUS]:
    """Return metadata for DATASUS databases (in-memory)."""
    return [BaseDATASUS(**b) for b in BASES_DATASUS]


def listar_doencas_notificaveis(
    categoria: str | None = None,
) -> list[DoencaNotificavel]:
    """Return notifiable diseases from SINAN (in-memory).

    Args:
        categoria: Optional category filter (e.g. "Arbovirose", "Respiratória").
    """
    doencas = [DoencaNotificavel(**d) for d in DOENCAS_SINAN]
    if categoria:
        cat_norm = _normalize(categoria)
        doencas = [d for d in doencas if cat_norm in _normalize(d.categoria)]
    return doencas
