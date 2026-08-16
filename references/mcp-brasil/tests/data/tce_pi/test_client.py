"""Tests for the TCE-PI HTTP client."""

import pytest
import respx
from httpx import Response

from mcp_brasil.data.tce_pi import client
from mcp_brasil.data.tce_pi.constants import (
    CREDORES_URL,
    DESPESAS_TOTAL_URL,
    DESPESAS_URL,
    ORGAOS_URL,
    PREFEITURAS_URL,
    RECEITAS_TOTAL_URL,
    RECEITAS_URL,
)


class TestListarPrefeituras:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_prefeituras(self) -> None:
        respx.get(PREFEITURAS_URL).mock(
            return_value=Response(
                200,
                json=[
                    {
                        "id": 133,
                        "nome": "Teresina",
                        "codIBGE": "2211001",
                        "urlPrefeitura": "http://www.teresina.pi.gov.br",
                        "urlCamara": "http://www.teresina.pi.leg.br",
                    }
                ],
            )
        )
        result = await client.listar_prefeituras()
        assert len(result) == 1
        assert result[0].nome == "Teresina"
        assert result[0].codIBGE == "2211001"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(PREFEITURAS_URL).mock(return_value=Response(200, json=[]))
        result = await client.listar_prefeituras()
        assert result == []


class TestBuscarPrefeitura:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_search_results(self) -> None:
        url = f"{PREFEITURAS_URL}/Teresina"
        respx.get(url).mock(
            return_value=Response(
                200,
                json=[{"id": 133, "nome": "Teresina", "codIBGE": "2211001"}],
            )
        )
        result = await client.buscar_prefeitura("Teresina")
        assert len(result) == 1
        assert result[0].id == 133


class TestConsultarGestor:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_gestor(self) -> None:
        url = f"{PREFEITURAS_URL}/133/gestor"
        respx.get(url).mock(
            return_value=Response(
                200,
                json={
                    "nome": "SILVIO MENDES",
                    "inicio_gestao": "2025-01-01T00:00:00.000Z",
                },
            )
        )
        result = await client.consultar_gestor(133)
        assert result is not None
        assert result.nome == "SILVIO MENDES"

    @pytest.mark.asyncio
    @respx.mock
    async def test_error_response(self) -> None:
        url = f"{PREFEITURAS_URL}/999/gestor"
        respx.get(url).mock(return_value=Response(200, json={"err": "Not found"}))
        result = await client.consultar_gestor(999)
        assert result is None


class TestConsultarDespesas:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_despesas(self) -> None:
        url = f"{DESPESAS_URL}/133"
        respx.get(url).mock(
            return_value=Response(
                200,
                json=[
                    {
                        "exercicio": 2024,
                        "empenhada": 1000000.50,
                        "liquidada": 900000.25,
                        "paga": 850000.00,
                    }
                ],
            )
        )
        result = await client.consultar_despesas(133)
        assert len(result) == 1
        assert result[0].exercicio == 2024
        assert result[0].empenhada == 1000000.50


class TestConsultarDespesasTotal:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_totals(self) -> None:
        respx.get(DESPESAS_TOTAL_URL).mock(
            return_value=Response(
                200,
                json=[{"exercicio": 2023, "empenhada": 5e9, "liquidada": 4.8e9, "paga": 4.5e9}],
            )
        )
        result = await client.consultar_despesas_total()
        assert len(result) == 1
        assert result[0].exercicio == 2023


class TestConsultarDespesasPorFuncao:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_funcoes(self) -> None:
        url = f"{DESPESAS_URL}/133/2024/porFuncao"
        respx.get(url).mock(
            return_value=Response(
                200,
                json=[
                    {"funcao": "Administração", "paga": 500000.00},
                    {"funcao": "Saúde", "paga": 300000.00},
                ],
            )
        )
        result = await client.consultar_despesas_por_funcao(133, 2024)
        assert len(result) == 2
        assert result[0].funcao == "Administração"


class TestConsultarReceitas:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_receitas(self) -> None:
        url = f"{RECEITAS_URL}/133/2024"
        respx.get(url).mock(
            return_value=Response(
                200,
                json=[
                    {
                        "categoria": "Receitas Correntes",
                        "origem": "Transferência Corrente",
                        "receita": "PNAE",
                        "prevista": 14151000,
                        "arrecadada": 14161240,
                    }
                ],
            )
        )
        result = await client.consultar_receitas(133, 2024)
        assert len(result) == 1
        assert result[0].categoria == "Receitas Correntes"


class TestConsultarReceitasTotal:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_totals(self) -> None:
        respx.get(RECEITAS_TOTAL_URL).mock(
            return_value=Response(
                200,
                json=[{"exercicio": 2023, "prevista": 1e10, "arrecadada": 9e9}],
            )
        )
        result = await client.consultar_receitas_total()
        assert len(result) == 1
        assert result[0].exercicio == 2023


class TestListarOrgaos:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_orgaos(self) -> None:
        url = f"{ORGAOS_URL}/2024"
        respx.get(url).mock(
            return_value=Response(
                200,
                json=[
                    {"id": "010101", "nome": "ASSEMBLEIA LEGISLATIVA", "sigla": "ALEPI"},
                    {"id": "020201", "nome": "TRIBUNAL DE JUSTICA", "sigla": "TJPI"},
                ],
            )
        )
        result = await client.listar_orgaos(2024)
        assert len(result) == 2
        assert result[0].sigla == "ALEPI"


class TestConsultarCredores:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_credores(self) -> None:
        url = f"{CREDORES_URL}/133/2024"
        respx.get(url).mock(
            return_value=Response(
                200,
                json=[
                    {"nome": "INSS", "pago": 53553610.35},
                    {"nome": "CONSORCIO XYZ", "pago": 66241070.36},
                ],
            )
        )
        result = await client.consultar_credores(133, 2024)
        assert len(result) == 2
        assert result[0].nome == "INSS"
