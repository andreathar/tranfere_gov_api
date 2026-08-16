"""HTTP client for the TransfereGov API (PostgREST).

PostgREST API — no auth, filters via query params (column=operator.value).
Pagination via limit/offset query params.

Endpoints:
    - /transferenciasespeciais/plano_acao_especial → buscar_emendas_pix
"""

from __future__ import annotations

from typing import Any

from mcp_brasil._shared.http_client import http_get

from .constants import DEFAULT_PAGE_SIZE, PLANO_ACAO_URL
from .schemas import TransferenciaEspecial


def _build_query(
    filters: dict[str, str],
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
    order: str | None = None,
) -> dict[str, str]:
    """Build PostgREST query params from a dict of column=operator.value filters."""
    params: dict[str, str] = dict(filters)
    params["limit"] = str(limit)
    params["offset"] = str(offset)
    if order:
        params["order"] = order
    return params


def _parse_transferencia(raw: dict[str, Any]) -> TransferenciaEspecial:
    """Parse a raw TransfereGov JSON into a TransferenciaEspecial model."""
    return TransferenciaEspecial(
        id_plano_acao=raw.get("id_plano_acao"),
        codigo_plano_acao=raw.get("codigo_plano_acao"),
        ano=raw.get("ano_plano_acao"),
        situacao=raw.get("situacao_plano_acao"),
        nome_parlamentar=raw.get("nome_parlamentar_emenda_plano_acao"),
        numero_emenda=raw.get("numero_emenda_parlamentar_plano_acao"),
        ano_emenda=raw.get("ano_emenda_parlamentar_plano_acao"),
        valor_custeio=raw.get("valor_custeio_plano_acao"),
        valor_investimento=raw.get("valor_investimento_plano_acao"),
        cnpj_beneficiario=raw.get("cnpj_beneficiario_plano_acao"),
        nome_beneficiario=raw.get("nome_beneficiario_plano_acao"),
        uf_beneficiario=raw.get("uf_beneficiario_plano_acao"),
        area_politica_publica=raw.get("codigo_descricao_areas_politicas_publicas_plano_acao"),
    )


async def _get(filters: dict[str, str], pagina: int = 1) -> list[TransferenciaEspecial]:
    """Make a GET to the TransfereGov API with PostgREST filters."""
    offset = (pagina - 1) * DEFAULT_PAGE_SIZE
    params = _build_query(filters, limit=DEFAULT_PAGE_SIZE, offset=offset)
    data = await http_get(PLANO_ACAO_URL, params=params)
    if isinstance(data, list):
        return [_parse_transferencia(item) for item in data]
    return []


async def buscar_emendas_pix(
    ano: int | None = None,
    uf: str | None = None,
    pagina: int = 1,
) -> list[TransferenciaEspecial]:
    """Lista transferências especiais (emendas pix).

    Args:
        ano: Ano do plano de ação.
        uf: UF do beneficiário.
        pagina: Número da página.
    """
    filters: dict[str, str] = {}
    if ano:
        filters["ano_plano_acao"] = f"eq.{ano}"
    if uf:
        filters["uf_beneficiario_plano_acao"] = f"eq.{uf.upper()}"
    return await _get(filters, pagina)


async def buscar_emenda_por_autor(
    nome_autor: str,
    ano: int | None = None,
    pagina: int = 1,
) -> list[TransferenciaEspecial]:
    """Busca emendas pix por nome do parlamentar.

    Args:
        nome_autor: Nome (ou parte do nome) do autor da emenda.
        ano: Ano do plano de ação (opcional).
        pagina: Número da página.
    """
    filters: dict[str, str] = {
        "nome_parlamentar_emenda_plano_acao": f"ilike.*{nome_autor}*",
    }
    if ano:
        filters["ano_plano_acao"] = f"eq.{ano}"
    return await _get(filters, pagina)


async def detalhe_emenda(id_plano_acao: int) -> TransferenciaEspecial | None:
    """Busca detalhe de uma emenda pix específica.

    Args:
        id_plano_acao: ID do plano de ação.
    """
    filters: dict[str, str] = {"id_plano_acao": f"eq.{id_plano_acao}"}
    params = _build_query(filters, limit=1, offset=0)
    data = await http_get(PLANO_ACAO_URL, params=params)
    if isinstance(data, list) and len(data) > 0:
        return _parse_transferencia(data[0])
    return None


async def emendas_por_municipio(
    nome_municipio: str,
    ano: int | None = None,
    pagina: int = 1,
) -> list[TransferenciaEspecial]:
    """Busca emendas pix destinadas a um município.

    Args:
        nome_municipio: Nome (ou parte do nome) do município beneficiário.
        ano: Ano do plano de ação (opcional).
        pagina: Número da página.
    """
    filters: dict[str, str] = {
        "nome_beneficiario_plano_acao": f"ilike.*{nome_municipio}*",
    }
    if ano:
        filters["ano_plano_acao"] = f"eq.{ano}"
    return await _get(filters, pagina)


async def resumo_emendas_ano(
    ano: int,
    pagina: int = 1,
) -> list[TransferenciaEspecial]:
    """Lista emendas pix de um ano para visão geral.

    Args:
        ano: Ano do plano de ação.
        pagina: Número da página.
    """
    filters: dict[str, str] = {"ano_plano_acao": f"eq.{ano}"}
    return await _get(filters, pagina)
