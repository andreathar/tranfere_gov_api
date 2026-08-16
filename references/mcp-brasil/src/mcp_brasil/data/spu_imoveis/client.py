"""HTTP client for the SPU-Imoveis feature.

Downloads the `patrimonio-uniao.csv` (~17MB, ~55k rows) from the Raio-X APF
dataset on repositorio.dados.gov.br and keeps the parsed rows in memory
with a TTL cache. All filtering happens in memory.

Endpoints:
    GET https://repositorio.dados.gov.br/seges/raio-x/patrimonio-uniao.csv
    GET https://repositorio.dados.gov.br/seges/raio-x/datapackage.json
"""

from __future__ import annotations

import asyncio
import csv
import io
import time
from collections import defaultdict
from typing import Any

from mcp_brasil._shared.http_client import create_client
from mcp_brasil.exceptions import HttpClientError

from .constants import (
    CSV_CACHE_TTL_SECONDS,
    DATAPACKAGE_JSON_URL,
    PATRIMONIO_UNIAO_CSV_URL,
)
from .schemas import DatasetInfo, Imovel, ResumoOrgao, ResumoUF

# Module-level TTL cache. Safe because the data is read-only after the load.
_CACHE: dict[str, Any] = {
    "rows": None,  # list[dict[str,str]]
    "fetched_at": 0.0,
}
_CACHE_LOCK = asyncio.Lock()


def _parse_float_br(value: str) -> float | None:
    """Parse a BR-locale numeric string (e.g. '543,25' or '543.25')."""
    if not value or value in {"-", "—", ""}:
        return None
    v = value.strip().replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return None


def _row_to_imovel(row: dict[str, str]) -> Imovel:
    return Imovel(
        orgao_superior_sigla=row.get("orgao_superior_sigla") or None,
        orgao_superior_nome=row.get("orgao_superior_nome") or None,
        orgao_sigla=row.get("orgao_sigla") or None,
        orgao_nome=row.get("orgao_nome") or None,
        ano_mes_referencia=row.get("ano_mes_referencia") or None,
        regime_utilizacao=row.get("regime_utilizacao") or None,
        tipo_destinacao=row.get("tipo_destinacao") or None,
        tipo_imovel=row.get("tipo_imovel") or None,
        endereco=row.get("endereco") or None,
        municipio_nome=row.get("municipio_nome") or None,
        municipio_cod_ibge=row.get("municipio_cod_ibge") or None,
        uf=(row.get("uf") or "").strip() or None,
        area_terreno_m2=_parse_float_br(row.get("metro_quadrado_area", "")),
        area_construida_m2=_parse_float_br(row.get("metro_quadrado_construida", "")),
        valor_imovel=_parse_float_br(row.get("valor_imovel", "")),
        valor_aluguel=_parse_float_br(row.get("valor_aluguel", "")),
    )


async def _fetch_csv_rows() -> list[dict[str, str]]:
    """Download the patrimonio-uniao.csv and return parsed rows."""
    async with create_client(
        timeout=120.0, headers={"Accept": "text/csv,application/octet-stream"}
    ) as http:
        try:
            resp = await http.get(PATRIMONIO_UNIAO_CSV_URL)
            resp.raise_for_status()
        except Exception as exc:
            raise HttpClientError(f"Failed to download patrimonio-uniao.csv: {exc}") from exc
        text = resp.text

    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


async def _load_rows(force: bool = False) -> list[dict[str, str]]:
    """Return cached rows, refreshing from the network if stale."""
    async with _CACHE_LOCK:
        now = time.time()
        rows = _CACHE["rows"]
        fetched_at = _CACHE["fetched_at"]
        stale = force or rows is None or (now - fetched_at) > CSV_CACHE_TTL_SECONDS
        if stale:
            rows = await _fetch_csv_rows()
            _CACHE["rows"] = rows
            _CACHE["fetched_at"] = now
        return list(rows or [])


def _clear_cache() -> None:
    """Test helper — drop the in-memory cache."""
    _CACHE["rows"] = None
    _CACHE["fetched_at"] = 0.0


async def info_dataset() -> DatasetInfo:
    """Return dataset-level metadata."""
    rows = await _load_rows()
    meses = sorted({r.get("ano_mes_referencia", "") for r in rows if r.get("ano_mes_referencia")})
    ts = _CACHE["fetched_at"]
    from datetime import datetime, timezone

    ultima = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None
    return DatasetInfo(
        nome="Raio-X APF — Patrimônio da União",
        url_csv=PATRIMONIO_UNIAO_CSV_URL,
        url_datapackage=DATAPACKAGE_JSON_URL,
        total_linhas=len(rows),
        meses_referencia=meses,
        ultima_atualizacao_cache=ultima,
    )


def _filter_rows(
    rows: list[dict[str, str]],
    *,
    orgao_sigla: str | None = None,
    uf: str | None = None,
    municipio: str | None = None,
    regime: str | None = None,
    tipo_destinacao: str | None = None,
) -> list[dict[str, str]]:
    """In-memory filter over the loaded rows."""
    out = rows
    if orgao_sigla:
        needle = orgao_sigla.upper().strip()
        out = [
            r
            for r in out
            if (r.get("orgao_superior_sigla", "").upper() == needle)
            or (r.get("orgao_sigla", "").upper() == needle)
        ]
    if uf:
        u = uf.upper().strip()
        out = [r for r in out if r.get("uf", "").strip().upper() == u]
    if municipio:
        m = municipio.lower().strip()
        out = [r for r in out if m in r.get("municipio_nome", "").lower()]
    if regime:
        reg = regime.lower().strip()
        out = [r for r in out if reg in r.get("regime_utilizacao", "").lower()]
    if tipo_destinacao:
        td = tipo_destinacao.lower().strip()
        out = [r for r in out if td in r.get("tipo_destinacao", "").lower()]
    return out


async def buscar_imoveis(
    *,
    orgao_sigla: str | None = None,
    uf: str | None = None,
    municipio: str | None = None,
    regime: str | None = None,
    tipo_destinacao: str | None = None,
    limite: int = 50,
) -> list[Imovel]:
    """List imóveis matching the given filters."""
    rows = await _load_rows()
    filtered = _filter_rows(
        rows,
        orgao_sigla=orgao_sigla,
        uf=uf,
        municipio=municipio,
        regime=regime,
        tipo_destinacao=tipo_destinacao,
    )
    return [_row_to_imovel(r) for r in filtered[: max(1, limite)]]


async def resumo_por_orgao(top: int = 20) -> list[ResumoOrgao]:
    """Return aggregated counts/values grouped by orgão superior."""
    rows = await _load_rows()
    agg: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"nome": "", "count": 0, "area": 0.0, "area_c": 0.0, "valor": 0.0}
    )
    for r in rows:
        sigla = r.get("orgao_superior_sigla", "").strip() or "?"
        a = agg[sigla]
        a["nome"] = r.get("orgao_superior_nome", "").strip() or a["nome"]
        a["count"] += 1
        a["area"] += _parse_float_br(r.get("metro_quadrado_area", "")) or 0.0
        a["area_c"] += _parse_float_br(r.get("metro_quadrado_construida", "")) or 0.0
        a["valor"] += _parse_float_br(r.get("valor_imovel", "")) or 0.0

    resumos = [
        ResumoOrgao(
            orgao_superior_sigla=sigla,
            orgao_superior_nome=data["nome"],
            total_imoveis=data["count"],
            area_total_m2=data["area"],
            area_construida_total_m2=data["area_c"],
            valor_total=data["valor"],
        )
        for sigla, data in agg.items()
    ]
    resumos.sort(key=lambda x: x.total_imoveis, reverse=True)
    return resumos[: max(1, top)]


async def resumo_por_uf() -> list[ResumoUF]:
    """Return aggregated counts/values grouped by UF."""
    rows = await _load_rows()
    agg: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "count": 0,
            "area": 0.0,
            "area_c": 0.0,
            "valor": 0.0,
            "aluguel": 0.0,
        }
    )
    for r in rows:
        uf = (r.get("uf", "") or "").strip().upper() or "?"
        a = agg[uf]
        a["count"] += 1
        a["area"] += _parse_float_br(r.get("metro_quadrado_area", "")) or 0.0
        a["area_c"] += _parse_float_br(r.get("metro_quadrado_construida", "")) or 0.0
        a["valor"] += _parse_float_br(r.get("valor_imovel", "")) or 0.0
        a["aluguel"] += _parse_float_br(r.get("valor_aluguel", "")) or 0.0

    resumos = [
        ResumoUF(
            uf=uf,
            total_imoveis=data["count"],
            area_total_m2=data["area"],
            area_construida_total_m2=data["area_c"],
            valor_total=data["valor"],
            valor_aluguel_total=data["aluguel"],
        )
        for uf, data in agg.items()
    ]
    resumos.sort(key=lambda x: x.total_imoveis, reverse=True)
    return resumos
