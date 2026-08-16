"""Tests for the Fórum Brasileiro de Segurança Pública HTTP client."""

import httpx
import pytest
import respx

from mcp_brasil.data.forum_seguranca import client
from mcp_brasil.data.forum_seguranca.constants import COMMUNITIES_URL, ITEM_URL, SEARCH_URL


def _make_search_response(
    items: list[dict[str, object]],
    total: int = 1,
    page: int = 0,
    total_pages: int = 1,
) -> dict[str, object]:
    """Build a DSpace discover search HAL+JSON response."""
    objects = []
    for item in items:
        objects.append(
            {
                "hitHighlights": [],
                "type": "discover",
                "_embedded": {
                    "indexableObject": {
                        "uuid": item.get("uuid", "abc-123"),
                        "name": item.get("name", "Publicação teste"),
                        "handle": item.get("handle", "123456789/1"),
                        "type": "item",
                        "metadata": item.get("metadata", {}),
                        "inArchive": True,
                        "discoverable": True,
                        "withdrawn": False,
                        "_links": {"self": {"href": "http://example.com"}},
                    },
                },
            }
        )
    return {
        "_embedded": {
            "searchResult": {
                "_embedded": {"objects": objects},
                "page": {
                    "size": len(items),
                    "totalElements": total,
                    "totalPages": total_pages,
                    "number": page,
                },
                "_links": {"self": {"href": SEARCH_URL}},
            },
        },
    }


def _make_item_metadata(
    titulo: str = "Publicação teste",
    autores: list[str] | None = None,
    resumo: str = "Resumo da publicação",
    data: str = "2023",
) -> dict[str, list[dict[str, str]]]:
    """Build DSpace Dublin Core metadata dict."""
    md: dict[str, list[dict[str, str]]] = {
        "dc.title": [{"value": titulo}],
        "dc.description.resumo": [{"value": resumo}],
        "dc.date.issued": [{"value": data}],
        "dc.publisher": [{"value": "Fórum Brasileiro de Segurança Pública"}],
        "dc.subject": [{"value": "segurança"}, {"value": "violência"}],
        "dc.identifier.uri": [{"value": "https://example.com/handle/1"}],
    }
    if autores:
        md["dc.contributor.author1"] = [{"value": a} for a in autores]
    return md


class TestBuscarPublicacoes:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_publications(self) -> None:
        metadata = _make_item_metadata(
            titulo="Anuário 2023",
            autores=["Autor A", "Autor B"],
        )
        response = _make_search_response(
            items=[{"uuid": "pub-001", "name": "Anuário 2023", "metadata": metadata}],
            total=105,
            total_pages=11,
        )
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=response))

        result = await client.buscar_publicacoes("anuário")
        assert result.total == 105
        assert len(result.publicacoes) == 1
        assert result.publicacoes[0].titulo == "Anuário 2023"
        assert result.publicacoes[0].autores == ["Autor A", "Autor B"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_results(self) -> None:
        response = _make_search_response(items=[], total=0, total_pages=0)
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=response))

        result = await client.buscar_publicacoes("xyznonexistent")
        assert result.total == 0
        assert result.publicacoes == []


class TestListarComunidades:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_communities(self) -> None:
        response = {
            "_embedded": {
                "communities": [
                    {
                        "uuid": "d044c00f-7c26-4249-8da4-336e953fe557",
                        "name": "Anuário Brasileiro de Segurança Pública",
                        "handle": "123456789/2",
                        "archivedItemsCount": 18,
                        "metadata": {
                            "dc.description": [
                                {"value": "O Anuário Brasileiro de Segurança Pública..."}
                            ],
                        },
                        "_links": {"self": {"href": "http://example.com"}},
                    },
                    {
                        "uuid": "068d69a5-d8e3-4d70-a218-22c60acdbf61",
                        "name": "Atlas da Violência",
                        "handle": "123456789/3",
                        "archivedItemsCount": 12,
                        "metadata": {},
                        "_links": {"self": {"href": "http://example.com"}},
                    },
                ],
            },
            "page": {"totalElements": 2, "totalPages": 1, "number": 0, "size": 20},
        }
        respx.get(COMMUNITIES_URL).mock(return_value=httpx.Response(200, json=response))

        result = await client.listar_comunidades()
        assert len(result) == 2
        assert result[0].nome == "Anuário Brasileiro de Segurança Pública"
        assert result[0].quantidade_itens == 18
        assert result[0].descricao == "O Anuário Brasileiro de Segurança Pública..."
        assert result[1].nome == "Atlas da Violência"
        assert result[1].descricao is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_skips_unnamed_communities(self) -> None:
        response = {
            "_embedded": {
                "communities": [
                    {
                        "uuid": "4ba11583-e45d-4e3c-ba34-b53398554a3f",
                        "name": "",
                        "metadata": {},
                        "archivedItemsCount": 0,
                        "_links": {"self": {"href": "http://example.com"}},
                    },
                ],
            },
            "page": {"totalElements": 1, "totalPages": 1, "number": 0, "size": 20},
        }
        respx.get(COMMUNITIES_URL).mock(return_value=httpx.Response(200, json=response))

        result = await client.listar_comunidades()
        assert result == []


class TestDetalharPublicacao:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_publication(self) -> None:
        metadata = _make_item_metadata(
            titulo="Atlas da Violência 2021",
            autores=["Ipea", "FBSP"],
            resumo="Análise de indicadores de violência.",
            data="2021",
        )
        item_response = {
            "uuid": "pub-002",
            "name": "Atlas da Violência 2021",
            "handle": "123456789/10",
            "type": "item",
            "metadata": metadata,
            "_links": {"self": {"href": "http://example.com"}},
        }
        respx.get(f"{ITEM_URL}/pub-002").mock(return_value=httpx.Response(200, json=item_response))

        result = await client.detalhar_publicacao("pub-002")
        assert result is not None
        assert result.titulo == "Atlas da Violência 2021"
        assert result.autores == ["Ipea", "FBSP"]
        assert result.resumo == "Análise de indicadores de violência."
        assert result.data_publicacao == "2021"

    @pytest.mark.asyncio
    @respx.mock
    async def test_not_found(self) -> None:
        respx.get(f"{ITEM_URL}/nonexistent").mock(return_value=httpx.Response(200, json={}))

        result = await client.detalhar_publicacao("nonexistent")
        assert result is None


class TestBuscarPorTema:
    @pytest.mark.asyncio
    @respx.mock
    async def test_scoped_search(self) -> None:
        metadata = _make_item_metadata(titulo="Publicação temática")
        response = _make_search_response(
            items=[{"uuid": "pub-003", "name": "Publicação temática", "metadata": metadata}],
            total=5,
        )
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=response))

        result = await client.buscar_por_tema("d044c00f-7c26-4249-8da4-336e953fe557", "anuário")
        assert result.total == 5
        assert len(result.publicacoes) == 1
        assert result.publicacoes[0].titulo == "Publicação temática"
