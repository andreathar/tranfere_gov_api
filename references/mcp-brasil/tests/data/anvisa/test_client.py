"""Tests for the ANVISA HTTP client."""

import httpx
import pytest
import respx

from mcp_brasil.data.anvisa import client
from mcp_brasil.data.anvisa.constants import BULARIO_BUSCA_URL, BULARIO_MEDICAMENTO_URL

# ---------------------------------------------------------------------------
# buscar_medicamento
# ---------------------------------------------------------------------------


class TestBuscarMedicamento:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_results(self) -> None:
        respx.get(BULARIO_BUSCA_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "content": [
                        {
                            "idProduto": "12345",
                            "nomeProduto": "Dipirona Sódica",
                            "razaoSocial": "Lab Exemplo",
                            "principioAtivo": "DIPIRONA SÓDICA",
                            "categoriaRegulatoria": "Genérico",
                            "numeroProcesso": "25351.123456/2020-00",
                            "numeroRegistro": "1.2345.6789",
                        }
                    ]
                },
            )
        )
        result = await client.buscar_medicamento(nome="dipirona")
        assert len(result) == 1
        assert result[0].nome_produto == "Dipirona Sódica"
        assert result[0].principio_ativo == "DIPIRONA SÓDICA"
        assert result[0].categoria_regulatoria == "Genérico"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(BULARIO_BUSCA_URL).mock(return_value=httpx.Response(200, json={"content": []}))
        result = await client.buscar_medicamento(nome="inexistente")
        assert result == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_query_params(self) -> None:
        route = respx.get(BULARIO_BUSCA_URL).mock(
            return_value=httpx.Response(200, json={"content": []})
        )
        await client.buscar_medicamento(nome="dipirona", pagina=2, limit=5)
        req_url = str(route.calls[0].request.url)
        assert "nome=dipirona" in req_url
        assert "pagina=2" in req_url
        assert "limit=5" in req_url


# ---------------------------------------------------------------------------
# buscar_por_principio_ativo
# ---------------------------------------------------------------------------


class TestBuscarPorPrincipioAtivo:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_results(self) -> None:
        respx.get(BULARIO_BUSCA_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "content": [
                        {
                            "idProduto": "67890",
                            "nomeProduto": "Losartana Potássica",
                            "razaoSocial": "Lab Genérico",
                            "principioAtivo": "LOSARTANA POTÁSSICA",
                            "categoriaRegulatoria": "Genérico",
                            "numeroRegistro": "1.6789.0123",
                        }
                    ]
                },
            )
        )
        result = await client.buscar_por_principio_ativo(principio_ativo="losartana")
        assert len(result) == 1
        assert result[0].principio_ativo == "LOSARTANA POTÁSSICA"

    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_principio_ativo_param(self) -> None:
        route = respx.get(BULARIO_BUSCA_URL).mock(
            return_value=httpx.Response(200, json={"content": []})
        )
        await client.buscar_por_principio_ativo(principio_ativo="metformina")
        req_url = str(route.calls[0].request.url)
        assert "principioAtivo=metformina" in req_url


# ---------------------------------------------------------------------------
# consultar_bula
# ---------------------------------------------------------------------------


class TestConsultarBula:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_bulas_from_dict(self) -> None:
        url = f"{BULARIO_MEDICAMENTO_URL}/25351.123456/2020-00"
        respx.get(url).mock(
            return_value=httpx.Response(
                200,
                json={
                    "content": [
                        {
                            "idBula": "999",
                            "idProduto": "12345",
                            "nomeProduto": "Dipirona",
                            "razaoSocial": "Lab Exemplo",
                            "tipoBula": "PACIENTE",
                            "dataPublicacao": "2024-01-15",
                            "urlBula": "https://consultas.anvisa.gov.br/bula/999",
                        }
                    ]
                },
            )
        )
        result = await client.consultar_bula(numero_processo="25351.123456/2020-00")
        assert len(result) == 1
        assert result[0].tipo_bula == "PACIENTE"
        assert result[0].url_bula is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_bulas_from_list(self) -> None:
        url = f"{BULARIO_MEDICAMENTO_URL}/25351.999/2020-00"
        respx.get(url).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "idBula": "888",
                        "tipoBula": "PROFISSIONAL",
                        "dataPublicacao": "2024-06-01",
                    }
                ],
            )
        )
        result = await client.consultar_bula(numero_processo="25351.999/2020-00")
        assert len(result) == 1
        assert result[0].tipo_bula == "PROFISSIONAL"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        url = f"{BULARIO_MEDICAMENTO_URL}/0000"
        respx.get(url).mock(return_value=httpx.Response(200, json={"content": []}))
        result = await client.consultar_bula(numero_processo="0000")
        assert result == []


# ---------------------------------------------------------------------------
# listar_categorias
# ---------------------------------------------------------------------------


class TestListarCategorias:
    def test_returns_all_categories(self) -> None:
        result = client.listar_categorias()
        assert len(result) == 8
        descricoes = {c.descricao for c in result}
        assert "Genérico" in descricoes
        assert "Similar" in descricoes
        assert "Novo" in descricoes


# ---------------------------------------------------------------------------
# Parse functions
# ---------------------------------------------------------------------------


class TestParseMedicamento:
    def test_handles_missing_fields(self) -> None:
        result = client._parse_medicamento({})
        assert result.id_produto == ""
        assert result.nome_produto is None

    def test_parses_all_fields(self) -> None:
        result = client._parse_medicamento(
            {
                "idProduto": 123,
                "nomeProduto": "Test",
                "principioAtivo": "Active",
                "categoriaRegulatoria": "Genérico",
            }
        )
        assert result.id_produto == "123"
        assert result.nome_produto == "Test"
        assert result.categoria_regulatoria == "Genérico"


# ---------------------------------------------------------------------------
# buscar_por_categoria
# ---------------------------------------------------------------------------


class TestBuscarPorCategoria:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_results(self) -> None:
        respx.get(BULARIO_BUSCA_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "content": [
                        {
                            "idProduto": "111",
                            "nomeProduto": "Genérico X",
                            "categoriaRegulatoria": "Genérico",
                        }
                    ]
                },
            )
        )
        result = await client.buscar_por_categoria(categoria="Genérico")
        assert len(result) == 1
        assert result[0].categoria_regulatoria == "Genérico"

    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_params(self) -> None:
        route = respx.get(BULARIO_BUSCA_URL).mock(
            return_value=httpx.Response(200, json={"content": []})
        )
        await client.buscar_por_categoria(categoria="Similar", nome="test")
        req_url = str(route.calls[0].request.url)
        assert "categoriaRegulatoria=Similar" in req_url
        assert "nome=test" in req_url


# ---------------------------------------------------------------------------
# buscar_generico
# ---------------------------------------------------------------------------


class TestBuscarGenerico:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_generics(self) -> None:
        respx.get(BULARIO_BUSCA_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "content": [
                        {
                            "idProduto": "222",
                            "nomeProduto": "Losartana Gen",
                            "categoriaRegulatoria": "Genérico",
                        }
                    ]
                },
            )
        )
        result = await client.buscar_generico(nome="losartana")
        assert len(result) == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_generico_filter(self) -> None:
        route = respx.get(BULARIO_BUSCA_URL).mock(
            return_value=httpx.Response(200, json={"content": []})
        )
        await client.buscar_generico(nome="metformina")
        req_url = str(route.calls[0].request.url)
        assert "principioAtivo=metformina" in req_url


# ---------------------------------------------------------------------------
# Parse functions
# ---------------------------------------------------------------------------


class TestParseBula:
    def test_handles_missing_fields(self) -> None:
        result = client._parse_bula({})
        assert result.id_bula == ""
        assert result.url_bula is None

    def test_parses_all_fields(self) -> None:
        result = client._parse_bula(
            {
                "idBula": "999",
                "tipoBula": "PACIENTE",
                "urlBula": "https://example.com/bula",
                "razaoSocial": "Lab Test",
            }
        )
        assert result.id_bula == "999"
        assert result.tipo_bula == "PACIENTE"
        assert result.empresa == "Lab Test"
