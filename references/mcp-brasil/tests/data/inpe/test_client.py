"""Tests for the INPE HTTP client."""

import httpx
import pytest
import respx

from mcp_brasil.data.inpe import client
from mcp_brasil.data.inpe.constants import DETER_URL, FOCOS_URL, PRODES_URL, SATELITES_URL

# ---------------------------------------------------------------------------
# buscar_focos
# ---------------------------------------------------------------------------


class TestBuscarFocos:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_focos(self) -> None:
        respx.get(FOCOS_URL).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "123456",
                        "latitude": -10.5,
                        "longitude": -50.3,
                        "data_hora": "2024-03-15T14:30:00",
                        "satelite": "AQUA_M-T",
                        "municipio": "São Félix do Xingu",
                        "estado": "PA",
                        "bioma": "Amazônia",
                        "dias_sem_chuva": 15,
                        "risco_fogo": 0.85,
                        "frp": 42.5,
                    }
                ],
            )
        )
        result = await client.buscar_focos(estado="PA")
        assert len(result) == 1
        assert result[0].municipio == "São Félix do Xingu"
        assert result[0].satelite == "AQUA_M-T"
        assert result[0].risco_fogo == 0.85
        assert result[0].frp == 42.5

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(FOCOS_URL).mock(return_value=httpx.Response(200, json=[]))
        result = await client.buscar_focos()
        assert result == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_passes_params(self) -> None:
        route = respx.get(FOCOS_URL).mock(return_value=httpx.Response(200, json=[]))
        await client.buscar_focos(
            estado="MT", data_inicio="2024-01-01", data_fim="2024-03-15", satelite="NPP-375"
        )
        req_url = str(route.calls[0].request.url)
        assert "estado_id=MT" in req_url
        assert "data_inicio=2024-01-01" in req_url
        assert "data_fim=2024-03-15" in req_url
        assert "satelite=NPP-375" in req_url
        assert "pais_id=33" in req_url


# ---------------------------------------------------------------------------
# buscar_alertas_deter
# ---------------------------------------------------------------------------


class TestBuscarAlertasDeter:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_alerts(self) -> None:
        respx.get(DETER_URL).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "789",
                        "data": "2024-03-15",
                        "area_km2": 1.5,
                        "municipio": "Altamira",
                        "estado": "PA",
                        "bioma": "Amazônia",
                        "classe": "DESMATAMENTO_CR",
                        "satelite": "CBERS-4A",
                    }
                ],
            )
        )
        result = await client.buscar_alertas_deter(bioma="Amazônia")
        assert len(result) == 1
        assert result[0].municipio == "Altamira"
        assert result[0].area_km2 == 1.5
        assert result[0].classe == "DESMATAMENTO_CR"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(DETER_URL).mock(return_value=httpx.Response(200, json=[]))
        result = await client.buscar_alertas_deter()
        assert result == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_passes_params(self) -> None:
        route = respx.get(DETER_URL).mock(return_value=httpx.Response(200, json=[]))
        await client.buscar_alertas_deter(
            bioma="Amazônia", estado="pa", data_inicio="2024-01-01", data_fim="2024-03-15"
        )
        req_url = str(route.calls[0].request.url)
        assert "bioma=Amaz" in req_url
        assert "estado=PA" in req_url
        assert "data_inicio=2024-01-01" in req_url
        assert "data_fim=2024-03-15" in req_url


# ---------------------------------------------------------------------------
# buscar_dados_prodes
# ---------------------------------------------------------------------------


class TestBuscarDadosProdes:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_data(self) -> None:
        respx.get(PRODES_URL).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "ano": 2023,
                        "bioma": "Amazônia",
                        "area_km2": 9001.0,
                        "estado": "PA",
                        "municipio": "São Félix do Xingu",
                    }
                ],
            )
        )
        result = await client.buscar_dados_prodes(bioma="Amazônia", ano=2023)
        assert len(result) == 1
        assert result[0].ano == 2023
        assert result[0].area_km2 == 9001.0
        assert result[0].municipio == "São Félix do Xingu"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(PRODES_URL).mock(return_value=httpx.Response(200, json=[]))
        result = await client.buscar_dados_prodes()
        assert result == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_passes_params(self) -> None:
        route = respx.get(PRODES_URL).mock(return_value=httpx.Response(200, json=[]))
        await client.buscar_dados_prodes(bioma="Cerrado", estado="mt", ano=2022)
        req_url = str(route.calls[0].request.url)
        assert "bioma=Cerrado" in req_url
        assert "estado=MT" in req_url
        assert "ano=2022" in req_url


# ---------------------------------------------------------------------------
# listar_satelites
# ---------------------------------------------------------------------------


class TestListarSatelites:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_satellites(self) -> None:
        respx.get(SATELITES_URL).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"nome": "AQUA_M-T", "descricao": "EOS/NASA"},
                    {"nome": "TERRA_M-T", "descricao": "EOS/NASA"},
                    {"nome": "NPP-375", "descricao": "Suomi NPP/NASA"},
                ],
            )
        )
        result = await client.listar_satelites()
        assert len(result) == 3
        assert result[0].nome == "AQUA_M-T"
        assert result[2].descricao == "Suomi NPP/NASA"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(SATELITES_URL).mock(return_value=httpx.Response(200, json=[]))
        result = await client.listar_satelites()
        assert result == []
