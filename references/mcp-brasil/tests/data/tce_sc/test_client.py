"""Tests for the TCE-SC HTTP client."""

import pytest
import respx
from httpx import Response

from mcp_brasil.data.tce_sc import client
from mcp_brasil.data.tce_sc.constants import MUNICIPIOS_URL, UNIDADES_GESTORAS_URL


class TestListarMunicipios:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_municipios(self) -> None:
        respx.get(MUNICIPIOS_URL).mock(
            return_value=Response(
                200,
                json=[
                    {"codigo_municipio": 420540, "nome_municipio": "Florianópolis"},
                    {"codigo_municipio": 420010, "nome_municipio": "Abelardo Luz"},
                ],
            )
        )
        result = await client.listar_municipios()
        assert len(result) == 2
        assert result[0].nome_municipio == "Florianópolis"
        assert result[0].codigo_municipio == 420540

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(MUNICIPIOS_URL).mock(return_value=Response(200, json=[]))
        result = await client.listar_municipios()
        assert result == []


class TestListarUnidadesGestoras:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_unidades(self) -> None:
        respx.get(UNIDADES_GESTORAS_URL).mock(
            return_value=Response(
                200,
                json=[
                    {
                        "codigo_unidade": 54010,
                        "nome_unidade": "Administração da Prefeitura Municipal de Florianópolis",
                        "sigla_unidade": None,
                        "nome_municipio": "Florianópolis",
                    },
                    {
                        "codigo_unidade": 345,
                        "nome_unidade": "Agência de Fomento do Estado de SC",
                        "sigla_unidade": "BADESC",
                        "nome_municipio": "Estado de Santa Catarina",
                    },
                ],
            )
        )
        result = await client.listar_unidades_gestoras()
        assert len(result) == 2
        assert result[0].codigo_unidade == 54010
        assert result[0].nome_municipio == "Florianópolis"
        assert result[1].sigla_unidade == "BADESC"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(UNIDADES_GESTORAS_URL).mock(return_value=Response(200, json=[]))
        result = await client.listar_unidades_gestoras()
        assert result == []
