"""Tests for the transferegov HTTP client."""

import httpx
import pytest
import respx

from mcp_brasil.data.transferegov import client
from mcp_brasil.data.transferegov.constants import PLANO_ACAO_URL

_SAMPLE_EMENDA = {
    "id_plano_acao": 3221,
    "codigo_plano_acao": "0903-003221",
    "ano_plano_acao": 2024,
    "situacao_plano_acao": "CIENTE",
    "nome_parlamentar_emenda_plano_acao": "Dep. Fulano da Silva",
    "numero_emenda_parlamentar_plano_acao": "202427070006",
    "ano_emenda_parlamentar_plano_acao": "2024",
    "valor_custeio_plano_acao": 30000.0,
    "valor_investimento_plano_acao": 80000.0,
    "cnpj_beneficiario_plano_acao": "04218211000156",
    "nome_beneficiario_plano_acao": "MUNICIPIO DE TERESINA",
    "uf_beneficiario_plano_acao": "PI",
    "codigo_descricao_areas_politicas_publicas_plano_acao": "10-Saude / 302-Atencao Basica",
}


# ---------------------------------------------------------------------------
# Helper: _build_query
# ---------------------------------------------------------------------------


class TestBuildQuery:
    def test_basic(self) -> None:
        result = client._build_query({"ano_plano_acao": "eq.2024"})
        assert result["ano_plano_acao"] == "eq.2024"
        assert result["limit"] == "15"
        assert result["offset"] == "0"

    def test_with_offset(self) -> None:
        result = client._build_query({}, limit=10, offset=20)
        assert result["limit"] == "10"
        assert result["offset"] == "20"

    def test_with_order(self) -> None:
        result = client._build_query({}, order="valor_custeio_plano_acao.desc")
        assert result["order"] == "valor_custeio_plano_acao.desc"


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class TestParseTransferencia:
    def test_full(self) -> None:
        result = client._parse_transferencia(_SAMPLE_EMENDA)
        assert result.numero_emenda == "202427070006"
        assert result.nome_parlamentar == "Dep. Fulano da Silva"
        assert result.valor_custeio == 30000.0
        assert result.valor_investimento == 80000.0
        assert result.nome_beneficiario == "MUNICIPIO DE TERESINA"

    def test_empty(self) -> None:
        result = client._parse_transferencia({})
        assert result.numero_emenda is None
        assert result.valor_custeio is None


# ---------------------------------------------------------------------------
# buscar_emendas_pix
# ---------------------------------------------------------------------------


class TestBuscarEmendasPix:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed(self) -> None:
        respx.get(PLANO_ACAO_URL).mock(return_value=httpx.Response(200, json=[_SAMPLE_EMENDA]))
        result = await client.buscar_emendas_pix(ano=2024)
        assert len(result) == 1
        assert result[0].numero_emenda == "202427070006"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty(self) -> None:
        respx.get(PLANO_ACAO_URL).mock(return_value=httpx.Response(200, json=[]))
        result = await client.buscar_emendas_pix()
        assert result == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_non_list_response(self) -> None:
        respx.get(PLANO_ACAO_URL).mock(
            return_value=httpx.Response(200, json={"error": "not found"})
        )
        result = await client.buscar_emendas_pix()
        assert result == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_with_uf_filter(self) -> None:
        route = respx.get(PLANO_ACAO_URL).mock(return_value=httpx.Response(200, json=[]))
        await client.buscar_emendas_pix(ano=2024, uf="PI")
        assert "uf_beneficiario_plano_acao=eq.PI" in str(route.calls[0].request.url)


# ---------------------------------------------------------------------------
# buscar_emenda_por_autor
# ---------------------------------------------------------------------------


class TestBuscarEmendaPorAutor:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed(self) -> None:
        respx.get(PLANO_ACAO_URL).mock(return_value=httpx.Response(200, json=[_SAMPLE_EMENDA]))
        result = await client.buscar_emenda_por_autor("Fulano")
        assert len(result) == 1
        assert result[0].nome_parlamentar == "Dep. Fulano da Silva"

    @pytest.mark.asyncio
    @respx.mock
    async def test_uses_ilike(self) -> None:
        route = respx.get(PLANO_ACAO_URL).mock(return_value=httpx.Response(200, json=[]))
        await client.buscar_emenda_por_autor("Lira")
        url_str = str(route.calls[0].request.url)
        assert "nome_parlamentar_emenda_plano_acao=ilike" in url_str
        assert "Lira" in url_str


# ---------------------------------------------------------------------------
# detalhe_emenda
# ---------------------------------------------------------------------------


class TestDetalheEmenda:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_detail(self) -> None:
        respx.get(PLANO_ACAO_URL).mock(return_value=httpx.Response(200, json=[_SAMPLE_EMENDA]))
        result = await client.detalhe_emenda(3221)
        assert result is not None
        assert result.numero_emenda == "202427070006"

    @pytest.mark.asyncio
    @respx.mock
    async def test_not_found(self) -> None:
        respx.get(PLANO_ACAO_URL).mock(return_value=httpx.Response(200, json=[]))
        result = await client.detalhe_emenda(999)
        assert result is None


# ---------------------------------------------------------------------------
# emendas_por_municipio
# ---------------------------------------------------------------------------


class TestEmendasPorMunicipio:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed(self) -> None:
        respx.get(PLANO_ACAO_URL).mock(return_value=httpx.Response(200, json=[_SAMPLE_EMENDA]))
        result = await client.emendas_por_municipio("Teresina")
        assert len(result) == 1
        assert result[0].nome_beneficiario == "MUNICIPIO DE TERESINA"

    @pytest.mark.asyncio
    @respx.mock
    async def test_uses_ilike(self) -> None:
        route = respx.get(PLANO_ACAO_URL).mock(return_value=httpx.Response(200, json=[]))
        await client.emendas_por_municipio("São Paulo")
        url_str = str(route.calls[0].request.url)
        assert "ilike" in url_str


# ---------------------------------------------------------------------------
# resumo_emendas_ano
# ---------------------------------------------------------------------------


class TestResumoEmendasAno:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed(self) -> None:
        respx.get(PLANO_ACAO_URL).mock(return_value=httpx.Response(200, json=[_SAMPLE_EMENDA]))
        result = await client.resumo_emendas_ano(2024)
        assert len(result) == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_filters_by_year(self) -> None:
        route = respx.get(PLANO_ACAO_URL).mock(return_value=httpx.Response(200, json=[]))
        await client.resumo_emendas_ano(2025)
        assert "ano_plano_acao=eq.2025" in str(route.calls[0].request.url)
