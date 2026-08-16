"""HTTP client for the ANVISA Bulário Eletrônico API.

The Bulário API is reverse-engineered from the ANVISA frontend at
consultas.anvisa.gov.br. Endpoints are not officially documented and
may change without notice.

Endpoints:
    - /bulario?nome={nome}            → buscar_medicamento
    - /bulario?principioAtivo={nome}  → buscar_por_principio_ativo
    - /bulario/medicamento/{processo} → consultar_bula
"""

from __future__ import annotations

from typing import Any

from mcp_brasil._shared.http_client import http_get

from .constants import (
    BULARIO_BUSCA_URL,
    BULARIO_MEDICAMENTO_URL,
    CATEGORIAS_MEDICAMENTO,
    DEFAULT_LIMIT,
    MAX_LIMIT,
)
from .schemas import BulaMedicamento, CategoriaMedicamento, MedicamentoBulario


def _parse_medicamento(raw: dict[str, Any]) -> MedicamentoBulario:
    """Parse a raw Bulário API response into a MedicamentoBulario model."""
    return MedicamentoBulario(
        id_produto=str(raw.get("idProduto", "") or ""),
        nome_produto=raw.get("nomeProduto"),
        razao_social=raw.get("razaoSocial"),
        cnpj=raw.get("cnpj"),
        numero_registro=raw.get("numeroRegistro"),
        data_vencimento_registro=raw.get("dataVencimentoRegistro"),
        principio_ativo=raw.get("principioAtivo"),
        categoria_regulatoria=raw.get("categoriaRegulatoria"),
        numero_processo=raw.get("numeroProcesso"),
    )


def _parse_bula(raw: dict[str, Any], nome_produto: str | None = None) -> BulaMedicamento:
    """Parse a raw bula dict into a BulaMedicamento model."""
    return BulaMedicamento(
        id_bula=str(raw.get("idBula", "") or ""),
        id_produto=str(raw.get("idProduto", "") or ""),
        nome_produto=nome_produto or raw.get("nomeProduto"),
        empresa=raw.get("razaoSocial") or raw.get("empresa"),
        tipo_bula=raw.get("tipoBula"),
        data_publicacao=raw.get("dataPublicacao"),
        url_bula=raw.get("urlBula"),
    )


async def buscar_medicamento(
    *,
    nome: str,
    pagina: int = 1,
    limit: int = DEFAULT_LIMIT,
) -> list[MedicamentoBulario]:
    """Search medications by commercial name in the Bulário.

    API: GET /bulario?nome={nome}&pagina={pagina}

    Args:
        nome: Medication name to search (partial match).
        pagina: Page number (1-based).
        limit: Max results per page.
    """
    params: dict[str, Any] = {
        "nome": nome,
        "pagina": pagina,
        "limit": min(limit, MAX_LIMIT),
    }
    data: dict[str, Any] = await http_get(BULARIO_BUSCA_URL, params=params)

    content = data.get("content", [])
    if isinstance(content, list):
        return [_parse_medicamento(item) for item in content]
    return []


async def buscar_por_principio_ativo(
    *,
    principio_ativo: str,
    pagina: int = 1,
    limit: int = DEFAULT_LIMIT,
) -> list[MedicamentoBulario]:
    """Search medications by active ingredient in the Bulário.

    API: GET /bulario?principioAtivo={principio_ativo}

    Args:
        principio_ativo: Active ingredient name (partial match).
        pagina: Page number (1-based).
        limit: Max results per page.
    """
    params: dict[str, Any] = {
        "principioAtivo": principio_ativo,
        "pagina": pagina,
        "limit": min(limit, MAX_LIMIT),
    }
    data: dict[str, Any] = await http_get(BULARIO_BUSCA_URL, params=params)

    content = data.get("content", [])
    if isinstance(content, list):
        return [_parse_medicamento(item) for item in content]
    return []


async def consultar_bula(*, numero_processo: str) -> list[BulaMedicamento]:
    """Fetch package inserts (bulas) for a medication by process number.

    API: GET /bulario/medicamento/{numero_processo}

    Args:
        numero_processo: ANVISA process number.
    """
    url = f"{BULARIO_MEDICAMENTO_URL}/{numero_processo}"
    data: dict[str, Any] = await http_get(url)

    # API returns a list of bulas or a dict with content
    if isinstance(data, list):
        return [_parse_bula(item) for item in data]

    content = data.get("content", [])
    if isinstance(content, list):
        return [_parse_bula(item) for item in content]
    return []


async def buscar_por_categoria(
    *,
    categoria: str,
    nome: str | None = None,
    pagina: int = 1,
    limit: int = DEFAULT_LIMIT,
) -> list[MedicamentoBulario]:
    """Search medications by regulatory category in the Bulário.

    API: GET /bulario?categoriaRegulatoria={categoria}&nome={nome}

    Args:
        categoria: Category name (e.g. "Genérico", "Similar", "Novo").
        nome: Optional medication name to combine with category.
        pagina: Page number (1-based).
        limit: Max results per page.
    """
    params: dict[str, Any] = {
        "categoriaRegulatoria": categoria,
        "pagina": pagina,
        "limit": min(limit, MAX_LIMIT),
    }
    if nome:
        params["nome"] = nome
    data: dict[str, Any] = await http_get(BULARIO_BUSCA_URL, params=params)

    content = data.get("content", [])
    if isinstance(content, list):
        return [_parse_medicamento(item) for item in content]
    return []


async def buscar_generico(
    *,
    nome: str,
    pagina: int = 1,
    limit: int = DEFAULT_LIMIT,
) -> list[MedicamentoBulario]:
    """Search generic medications equivalent to a reference drug.

    Uses the Bulário API filtering by 'Genérico' category and active ingredient.

    Args:
        nome: Reference drug name or active ingredient.
        pagina: Page number.
        limit: Max results.
    """
    # First search by active ingredient to find generics
    params: dict[str, Any] = {
        "principioAtivo": nome,
        "categoriaRegulatoria": "Genérico",
        "pagina": pagina,
        "limit": min(limit, MAX_LIMIT),
    }
    data: dict[str, Any] = await http_get(BULARIO_BUSCA_URL, params=params)

    content = data.get("content", [])
    if isinstance(content, list):
        return [_parse_medicamento(item) for item in content]
    return []


def listar_categorias() -> list[CategoriaMedicamento]:
    """Return all medication regulatory categories.

    Data source: static ANVISA categories.
    """
    return [
        CategoriaMedicamento(codigo=codigo, descricao=descricao)
        for codigo, descricao in CATEGORIAS_MEDICAMENTO.items()
    ]
