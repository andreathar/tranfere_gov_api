"""Tests for the bacen HTTP client."""

from unittest.mock import patch

import httpx
import pytest
import respx

from mcp_brasil.data.bacen import client
from mcp_brasil.data.bacen.constants import BCB_API_BASE

# ---------------------------------------------------------------------------
# _format_date
# ---------------------------------------------------------------------------


class TestFormatDate:
    def test_iso_to_br(self) -> None:
        assert client._format_date("2024-01-15") == "15/01/2024"

    def test_already_br(self) -> None:
        assert client._format_date("15/01/2024") == "15/01/2024"

    def test_short_string(self) -> None:
        assert client._format_date("2024") == "2024"


# ---------------------------------------------------------------------------
# _parse_valor
# ---------------------------------------------------------------------------


class TestParseValor:
    def test_parses_correctly(self) -> None:
        raw = {"data": "15/01/2024", "valor": "13.25"}
        result = client._parse_valor(raw)
        assert result.data == "15/01/2024"
        assert result.valor == 13.25


# ---------------------------------------------------------------------------
# buscar_valores
# ---------------------------------------------------------------------------


class TestBuscarValores:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_values(self) -> None:
        url = f"{BCB_API_BASE}.432/dados"
        respx.get(url).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"data": "01/01/2024", "valor": "11.75"},
                    {"data": "02/01/2024", "valor": "11.50"},
                ],
            )
        )
        result = await client.buscar_valores(432)
        assert len(result) == 2
        assert result[0].data == "01/01/2024"
        assert result[0].valor == 11.75
        assert result[1].valor == 11.50

    @pytest.mark.asyncio
    @respx.mock
    async def test_with_date_range(self) -> None:
        url = f"{BCB_API_BASE}.433/dados"
        route = respx.get(url).mock(return_value=httpx.Response(200, json=[]))
        await client.buscar_valores(433, data_inicial="2024-01-01", data_final="2024-06-30")
        req_url = str(route.calls[0].request.url)
        assert "dataInicial=01%2F01%2F2024" in req_url
        assert "dataFinal=30%2F06%2F2024" in req_url

    @pytest.mark.asyncio
    @respx.mock
    async def test_non_list_response(self) -> None:
        url = f"{BCB_API_BASE}.999/dados"
        respx.get(url).mock(return_value=httpx.Response(200, json={"error": "not found"}))
        result = await client.buscar_valores(999)
        assert result == []


# ---------------------------------------------------------------------------
# buscar_ultimos
# ---------------------------------------------------------------------------


class TestBuscarUltimos:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_last_n_values(self) -> None:
        url = f"{BCB_API_BASE}.432/dados/ultimos/5"
        respx.get(url).mock(
            return_value=httpx.Response(
                200,
                json=[{"data": f"0{i}/01/2024", "valor": str(10 + i)} for i in range(1, 6)],
            )
        )
        result = await client.buscar_ultimos(432, 5)
        assert len(result) == 5
        assert result[0].valor == 11.0

    @pytest.mark.asyncio
    @respx.mock
    async def test_default_quantity(self) -> None:
        url = f"{BCB_API_BASE}.433/dados/ultimos/10"
        respx.get(url).mock(return_value=httpx.Response(200, json=[]))
        result = await client.buscar_ultimos(433)
        assert result == []


# ---------------------------------------------------------------------------
# buscar_metadados
# ---------------------------------------------------------------------------


class TestBuscarMetadados:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_metadata(self) -> None:
        url = f"{BCB_API_BASE}.432/metadados"
        respx.get(url).mock(
            return_value=httpx.Response(
                200,
                json={
                    "codigo": 432,
                    "nome": "Taxa Selic anualizada",
                    "unidade": "% a.a.",
                    "periodicidade": {"descricaoPortugues": "Diária"},
                    "fonte": "Banco Central do Brasil",
                    "especial": False,
                },
            )
        )
        result = await client.buscar_metadados(432)
        assert result.codigo == 432
        assert result.nome == "Taxa Selic anualizada"
        assert result.unidade == "% a.a."
        assert result.periodicidade == "Diária"

    @pytest.mark.asyncio
    @respx.mock
    async def test_periodicidade_as_string(self) -> None:
        url = f"{BCB_API_BASE}.433/metadados"
        respx.get(url).mock(
            return_value=httpx.Response(
                200,
                json={
                    "codigo": 433,
                    "nome": "IPCA",
                    "periodicidade": "Mensal",
                },
            )
        )
        result = await client.buscar_metadados(433)
        assert result.periodicidade == "Mensal"

    @pytest.mark.asyncio
    @respx.mock
    async def test_missing_fields_use_defaults(self) -> None:
        url = f"{BCB_API_BASE}.999/metadados"
        respx.get(url).mock(return_value=httpx.Response(200, json={}))
        result = await client.buscar_metadados(999)
        assert result.codigo == 999
        assert result.nome == "Série 999"
        assert result.unidade == "Não informada"


# ---------------------------------------------------------------------------
# buscar_indicadores_atuais
# ---------------------------------------------------------------------------


class TestBuscarIndicadoresAtuais:
    @pytest.mark.asyncio
    @respx.mock
    async def test_fetches_all_indicators(self) -> None:
        # Mock last value for each of the 5 key indicators
        for ind in client.INDICADORES_CHAVE:
            url = f"{BCB_API_BASE}.{ind['codigo']}/dados/ultimos/1"
            respx.get(url).mock(
                return_value=httpx.Response(
                    200,
                    json=[{"data": "01/03/2024", "valor": "10.5"}],
                )
            )
        result = await client.buscar_indicadores_atuais()
        assert len(result) == 5
        assert all("indicador" in r for r in result)
        assert all(r.get("valor") == 10.5 for r in result)

    @pytest.mark.asyncio
    @respx.mock
    async def test_handles_errors_gracefully(self) -> None:
        for ind in client.INDICADORES_CHAVE:
            url = f"{BCB_API_BASE}.{ind['codigo']}/dados/ultimos/1"
            respx.get(url).mock(return_value=httpx.Response(500, text="Error"))

        with patch("mcp_brasil._shared.http_client.asyncio.sleep"):
            result = await client.buscar_indicadores_atuais()
        assert len(result) == 5
        assert all("erro" in r for r in result)

    @pytest.mark.asyncio
    @respx.mock
    async def test_handles_empty_data(self) -> None:
        for ind in client.INDICADORES_CHAVE:
            url = f"{BCB_API_BASE}.{ind['codigo']}/dados/ultimos/1"
            respx.get(url).mock(return_value=httpx.Response(200, json=[]))
        result = await client.buscar_indicadores_atuais()
        assert len(result) == 5
        assert all("erro" in r for r in result)


# ---------------------------------------------------------------------------
# buscar_expectativas_focus
# ---------------------------------------------------------------------------


class TestBuscarExpectativasFocus:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_expectations(self) -> None:
        from mcp_brasil.data.bacen.constants import FOCUS_ENDPOINT

        respx.get(FOCUS_ENDPOINT).mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "Indicador": "IPCA",
                            "Data": "2024-03-15",
                            "DataReferencia": "2024",
                            "Media": 3.76,
                            "Mediana": 3.75,
                            "DesvioPadrao": 0.18,
                            "Minimo": 2.50,
                            "Maximo": 5.00,
                            "baseCalculo": 80,
                        },
                        {
                            "Indicador": "IPCA",
                            "Data": "2024-03-08",
                            "DataReferencia": "2024",
                            "Media": 3.80,
                            "Mediana": 3.78,
                            "DesvioPadrao": 0.20,
                            "Minimo": 2.60,
                            "Maximo": 5.10,
                            "baseCalculo": 75,
                        },
                    ]
                },
            )
        )
        result = await client.buscar_expectativas_focus(indicador="IPCA", limite=2)
        assert len(result) == 2
        assert result[0].indicador == "IPCA"
        assert result[0].data == "2024-03-15"
        assert result[0].mediana == 3.75
        assert result[0].media == 3.76
        assert result[0].base_calculo == 80
        assert result[1].data == "2024-03-08"

    @pytest.mark.asyncio
    @respx.mock
    async def test_with_data_inicio(self) -> None:
        from mcp_brasil.data.bacen.constants import FOCUS_ENDPOINT

        route = respx.get(FOCUS_ENDPOINT).mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        await client.buscar_expectativas_focus(
            indicador="Selic", data_inicio="2024-01-01", limite=5
        )
        req_url = str(route.calls[0].request.url)
        assert "Data" in req_url and "ge" in req_url and "2024-01-01" in req_url

    @pytest.mark.asyncio
    async def test_invalid_indicator_returns_empty(self) -> None:
        result = await client.buscar_expectativas_focus(indicador="INVALIDO")
        assert result == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_non_list_value_returns_empty(self) -> None:
        from mcp_brasil.data.bacen.constants import FOCUS_ENDPOINT

        respx.get(FOCUS_ENDPOINT).mock(
            return_value=httpx.Response(200, json={"value": "not a list"})
        )
        result = await client.buscar_expectativas_focus(indicador="IPCA")
        assert result == []
