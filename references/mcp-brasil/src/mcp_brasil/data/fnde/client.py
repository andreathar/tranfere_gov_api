"""HTTP client for the FNDE OData APIs.

Endpoints (OData v4 on Olinda platform):
    - FUNDEB_Matriculas        → consultar_fundeb_matriculas
    - PNAE_Numero_Alunos       → consultar_pnae_alunos
    - PNLD                     → consultar_pnld_livros
    - PNATE_Alunos_Atendidos   → consultar_pnate_transporte
"""

from __future__ import annotations

from typing import Any

from mcp_brasil._shared.http_client import http_get

from .constants import (
    FUNDEB_URL,
    ODATA_DEFAULT_TOP,
    ODATA_FORMAT,
    ODATA_MAX_TOP,
    PNAE_URL,
    PNATE_URL,
    PNLD_URL,
)
from .schemas import FundebMatricula, PnaeAluno, PnateTransporte, PnldLivro


def _build_odata_params(
    *,
    filters: list[str] | None = None,
    top: int = ODATA_DEFAULT_TOP,
    skip: int = 0,
    order_by: str | None = None,
) -> dict[str, Any]:
    """Build OData query parameters."""
    top = min(top, ODATA_MAX_TOP)
    params: dict[str, Any] = {
        "$format": ODATA_FORMAT,
        "$top": top,
    }
    if skip > 0:
        params["$skip"] = skip
    if filters:
        params["$filter"] = " and ".join(filters)
    if order_by:
        params["$orderby"] = order_by
    return params


async def consultar_fundeb_matriculas(
    *,
    ano: int | None = None,
    uf: str | None = None,
    municipio: str | None = None,
    top: int = ODATA_DEFAULT_TOP,
    skip: int = 0,
) -> list[FundebMatricula]:
    """Fetch FUNDEB enrollment data by year/state/municipality."""
    filters: list[str] = []
    if ano:
        filters.append(f"AnoCenso eq {ano}")
    if uf:
        filters.append(f"Uf eq '{uf.upper()}'")
    if municipio:
        filters.append(f"contains(MunicipioGe,'{municipio.upper()}')")

    params = _build_odata_params(filters=filters, top=top, skip=skip)
    data = await http_get(FUNDEB_URL, params=params)
    return [FundebMatricula.model_validate(item) for item in data.get("value", [])]


async def consultar_pnae_alunos(
    *,
    ano: str | None = None,
    estado: str | None = None,
    municipio: str | None = None,
    top: int = ODATA_DEFAULT_TOP,
    skip: int = 0,
) -> list[PnaeAluno]:
    """Fetch PNAE (school feeding) data by year/state/municipality."""
    filters: list[str] = []
    if ano:
        filters.append(f"Ano eq '{ano}'")
    if estado:
        filters.append(f"Estado eq '{estado.upper()}'")
    if municipio:
        filters.append(f"contains(Municipio,'{municipio.upper()}')")

    params = _build_odata_params(filters=filters, top=top, skip=skip)
    data = await http_get(PNAE_URL, params=params)
    return [PnaeAluno.model_validate(item) for item in data.get("value", [])]


async def consultar_pnld_livros(
    *,
    ano: str | None = None,
    editora: str | None = None,
    titulo: str | None = None,
    top: int = ODATA_DEFAULT_TOP,
    skip: int = 0,
) -> list[PnldLivro]:
    """Fetch PNLD (textbook distribution) data."""
    filters: list[str] = []
    if ano:
        filters.append(f"Ano eq '{ano}'")
    if editora:
        filters.append(f"contains(Editora,'{editora.upper()}')")
    if titulo:
        filters.append(f"contains(Titulo_livro,'{titulo.upper()}')")

    params = _build_odata_params(filters=filters, top=top, skip=skip)
    data = await http_get(PNLD_URL, params=params)
    return [PnldLivro.model_validate(item) for item in data.get("value", [])]


async def consultar_pnate_transporte(
    *,
    uf: str | None = None,
    municipio: str | None = None,
    top: int = ODATA_DEFAULT_TOP,
    skip: int = 0,
) -> list[PnateTransporte]:
    """Fetch PNATE (school transport) data by state/municipality."""
    filters: list[str] = []
    if uf:
        filters.append(f"Uf eq '{uf.upper()}'")
    if municipio:
        filters.append(f"contains(Municipio,'{municipio.upper()}')")

    params = _build_odata_params(filters=filters, top=top, skip=skip)
    data = await http_get(PNATE_URL, params=params)
    return [PnateTransporte.model_validate(item) for item in data.get("value", [])]
