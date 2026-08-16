"""HTTP client for the TCE-RS open data portal.

The TCE-RS portal is CKAN-based but without the DataStore extension.
Data access is via direct JSON file downloads and the CKAN metadata API.

Data files:
    - /dados/auxiliar/municipios.json       → listar_municipios
    - /dados/municipal/educacao-indice/     → buscar_indices_educacao
    - /dados/municipal/saude-indice/        → buscar_indices_saude
    - /dados/municipal/gastos-lrf-mde-asps/ → buscar_gestao_fiscal

CKAN API:
    - /api/3/action/package_search          → buscar_datasets
"""

from __future__ import annotations

from typing import Any

from mcp_brasil._shared.http_client import http_get

from .constants import (
    CKAN_MAX_ROWS,
    EDUCACAO_INDICE_URL,
    GESTAO_FISCAL_URL,
    MUNICIPIOS_URL,
    PACKAGE_SEARCH_URL,
    PORTAL_BASE,
    SAUDE_INDICE_URL,
)
from .schemas import Dataset, GestaoFiscal, IndiceEducacao, IndiceSaude, Municipio


def _extract_items(data: Any) -> list[dict[str, Any]]:
    """Extract the item list from a TCE-RS JSON response.

    Data files wrap arrays in a root key (e.g. {"municipios": [...]}).
    This function extracts the first list value found.
    """
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                return value
    return []


async def listar_municipios() -> list[Municipio]:
    """Fetch the list of RS municipalities from auxiliar/municipios.json."""
    data = await http_get(MUNICIPIOS_URL)
    items = _extract_items(data)
    return [
        Municipio(
            codigo=item.get("COD_MUNICIPIO"),
            nome=item.get("NOME_MUNICIPIO"),
            uf=item.get("UF"),
            codigo_ibge=item.get("CD_MUNICIPIO_IBGE"),
        )
        for item in items
    ]


async def buscar_indices_educacao(ano: int) -> list[IndiceEducacao]:
    """Fetch education compliance indices for a given year.

    Args:
        ano: Year to query (e.g. 2024).
    """
    url = f"{EDUCACAO_INDICE_URL}/{ano}.json"
    data = await http_get(url)
    items = _extract_items(data)
    return [
        IndiceEducacao(
            ano=item.get("Ano"),
            codigo_orgao=item.get("CD_Orgao"),
            nome_orgao=item.get("NM_Orgao"),
            valor_despesa=item.get("VL_Despesa"),
            valor_receita=item.get("VL_Receita"),
            indice=item.get("VL_IndiceEducacao"),
        )
        for item in items
    ]


async def buscar_indices_saude(ano: int) -> list[IndiceSaude]:
    """Fetch health compliance indices for a given year.

    Args:
        ano: Year to query (e.g. 2024).
    """
    url = f"{SAUDE_INDICE_URL}/{ano}.json"
    data = await http_get(url)
    items = _extract_items(data)
    return [
        IndiceSaude(
            ano=item.get("Ano"),
            codigo_orgao=item.get("CD_Orgao"),
            nome_orgao=item.get("NM_Orgao"),
            valor_despesa=item.get("VL_Despesa"),
            valor_receita=item.get("VL_Receita"),
            indice=item.get("VL_IndiceSaude"),
        )
        for item in items
    ]


async def buscar_gestao_fiscal(ano: int) -> list[GestaoFiscal]:
    """Fetch municipal fiscal management (LRF) data for a given year.

    Args:
        ano: Year to query (e.g. 2024).
    """
    url = f"{GESTAO_FISCAL_URL}/{ano}.json"
    data = await http_get(url)
    items = _extract_items(data)
    return [
        GestaoFiscal(
            ano=item.get("Ano"),
            codigo_orgao=item.get("CD_Orgao"),
            nome_orgao=item.get("NM_Orgao"),
            receita_corrente_liquida=item.get("VL_ReceitaCorrenteLiquida"),
            despesa_pessoal=item.get("VL_DespesaPessoal"),
            divida_consolidada=item.get("VL_DividaConsolidada"),
            operacoes_credito=item.get("VL_OperacoesCredito"),
            receita_mde=item.get("VL_ReceitaMDE"),
            despesa_mde=item.get("VL_DespesaMDE"),
            receita_asps=item.get("VL_ReceitaASPS"),
            despesa_asps=item.get("VL_DespesaASPS"),
        )
        for item in items
    ]


async def buscar_datasets(
    query: str,
    grupo: str | None = None,
    limite: int = 10,
) -> tuple[list[Dataset], int]:
    """Search datasets via the CKAN package_search API.

    Args:
        query: Search query (Solr syntax).
        grupo: Filter by CKAN group (e.g. "despesa", "licitacoes").
        limite: Maximum results (1-50).

    Returns:
        Tuple of (list of datasets, total count).
    """
    rows = min(max(limite, 1), CKAN_MAX_ROWS)
    params: dict[str, Any] = {"q": query, "rows": rows}
    if grupo:
        params["fq"] = f"groups:{grupo}"

    data: dict[str, Any] = await http_get(PACKAGE_SEARCH_URL, params=params)

    result: dict[str, Any] = data.get("result", {})
    total: int = result.get("count", 0)
    packages: list[dict[str, Any]] = result.get("results", [])

    datasets: list[Dataset] = []
    for pkg in packages:
        groups: list[dict[str, Any]] = pkg.get("groups", [])
        grupo_nome = groups[0].get("title") if groups else None

        datasets.append(
            Dataset(
                nome=pkg.get("name"),
                titulo=pkg.get("title"),
                grupo=grupo_nome,
                notas=(pkg.get("notes") or "")[:200] or None,
                url=f"{PORTAL_BASE}/dataset/{pkg.get('name', '')}",
                num_recursos=pkg.get("num_resources"),
            )
        )

    return datasets, total
