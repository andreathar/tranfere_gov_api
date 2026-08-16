"""Tests for the TCE-RS HTTP client."""

import pytest
import respx
from httpx import Response

from mcp_brasil.data.tce_rs import client
from mcp_brasil.data.tce_rs.constants import (
    EDUCACAO_INDICE_URL,
    GESTAO_FISCAL_URL,
    MUNICIPIOS_URL,
    PACKAGE_SEARCH_URL,
    SAUDE_INDICE_URL,
)

# ---------------------------------------------------------------------------
# _extract_items
# ---------------------------------------------------------------------------


class TestExtractItems:
    def test_list_input(self) -> None:
        assert client._extract_items([{"a": 1}]) == [{"a": 1}]

    def test_dict_with_list_value(self) -> None:
        data = {"municipios": [{"a": 1}, {"a": 2}]}
        assert client._extract_items(data) == [{"a": 1}, {"a": 2}]

    def test_empty_dict(self) -> None:
        assert client._extract_items({}) == []

    def test_non_list_values(self) -> None:
        assert client._extract_items({"key": "string"}) == []

    def test_none_input(self) -> None:
        assert client._extract_items(None) == []


# ---------------------------------------------------------------------------
# listar_municipios
# ---------------------------------------------------------------------------


class TestListarMunicipios:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_municipios(self) -> None:
        respx.get(MUNICIPIOS_URL).mock(
            return_value=Response(
                200,
                json={
                    "municipios": [
                        {
                            "COD_MUNICIPIO": 1,
                            "NOME_MUNICIPIO": "AGUDO",
                            "UF": "RS",
                            "CD_MUNICIPIO_IBGE": 4300109,
                        },
                        {
                            "COD_MUNICIPIO": 2,
                            "NOME_MUNICIPIO": "PORTO ALEGRE",
                            "UF": "RS",
                            "CD_MUNICIPIO_IBGE": 4314902,
                        },
                    ]
                },
            )
        )
        result = await client.listar_municipios()
        assert len(result) == 2
        assert result[0].nome == "AGUDO"
        assert result[0].codigo == 1
        assert result[0].codigo_ibge == 4300109
        assert result[1].nome == "PORTO ALEGRE"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(MUNICIPIOS_URL).mock(return_value=Response(200, json={"municipios": []}))
        result = await client.listar_municipios()
        assert result == []


# ---------------------------------------------------------------------------
# buscar_indices_educacao
# ---------------------------------------------------------------------------


class TestBuscarIndicesEducacao:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_indices(self) -> None:
        url = f"{EDUCACAO_INDICE_URL}/2024.json"
        respx.get(url).mock(
            return_value=Response(
                200,
                json={
                    "indice_educacao": [
                        {
                            "Ano": 2024,
                            "CD_Orgao": 100,
                            "NM_Orgao": "PREFEITURA DE PORTO ALEGRE",
                            "VL_Despesa": 500000.0,
                            "VL_Receita": 1800000.0,
                            "VL_IndiceEducacao": 0.2778,
                        }
                    ]
                },
            )
        )
        result = await client.buscar_indices_educacao(2024)
        assert len(result) == 1
        assert result[0].nome_orgao == "PREFEITURA DE PORTO ALEGRE"
        assert result[0].indice == 0.2778
        assert result[0].valor_despesa == 500000.0

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        url = f"{EDUCACAO_INDICE_URL}/2024.json"
        respx.get(url).mock(return_value=Response(200, json={"indice_educacao": []}))
        result = await client.buscar_indices_educacao(2024)
        assert result == []


# ---------------------------------------------------------------------------
# buscar_indices_saude
# ---------------------------------------------------------------------------


class TestBuscarIndicesSaude:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_indices(self) -> None:
        url = f"{SAUDE_INDICE_URL}/2024.json"
        respx.get(url).mock(
            return_value=Response(
                200,
                json={
                    "indice_saude": [
                        {
                            "Ano": 2024,
                            "CD_Orgao": 200,
                            "NM_Orgao": "PREFEITURA DE CAXIAS DO SUL",
                            "VL_Despesa": 300000.0,
                            "VL_Receita": 1500000.0,
                            "VL_IndiceSaude": 0.20,
                        }
                    ]
                },
            )
        )
        result = await client.buscar_indices_saude(2024)
        assert len(result) == 1
        assert result[0].nome_orgao == "PREFEITURA DE CAXIAS DO SUL"
        assert result[0].indice == 0.20

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        url = f"{SAUDE_INDICE_URL}/2024.json"
        respx.get(url).mock(return_value=Response(200, json={"indice_saude": []}))
        result = await client.buscar_indices_saude(2024)
        assert result == []


# ---------------------------------------------------------------------------
# buscar_gestao_fiscal
# ---------------------------------------------------------------------------


class TestBuscarGestaoFiscal:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_data(self) -> None:
        url = f"{GESTAO_FISCAL_URL}/2024.json"
        respx.get(url).mock(
            return_value=Response(
                200,
                json={
                    "gestao_fiscal": [
                        {
                            "Ano": 2024,
                            "CD_Orgao": 100,
                            "NM_Orgao": "PREFEITURA DE PORTO ALEGRE",
                            "VL_ReceitaCorrenteLiquida": 10000000.0,
                            "VL_DespesaPessoal": 4500000.0,
                            "VL_DividaConsolidada": 2000000.0,
                            "VL_OperacoesCredito": 100000.0,
                            "VL_ReceitaMDE": 3000000.0,
                            "VL_DespesaMDE": 800000.0,
                            "VL_ReceitaASPS": 2500000.0,
                            "VL_DespesaASPS": 500000.0,
                        }
                    ]
                },
            )
        )
        result = await client.buscar_gestao_fiscal(2024)
        assert len(result) == 1
        gf = result[0]
        assert gf.nome_orgao == "PREFEITURA DE PORTO ALEGRE"
        assert gf.receita_corrente_liquida == 10000000.0
        assert gf.despesa_pessoal == 4500000.0
        assert gf.divida_consolidada == 2000000.0

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        url = f"{GESTAO_FISCAL_URL}/2024.json"
        respx.get(url).mock(return_value=Response(200, json={"gestao_fiscal": []}))
        result = await client.buscar_gestao_fiscal(2024)
        assert result == []


# ---------------------------------------------------------------------------
# buscar_datasets
# ---------------------------------------------------------------------------


class TestBuscarDatasets:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_datasets(self) -> None:
        respx.get(PACKAGE_SEARCH_URL).mock(
            return_value=Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "count": 1,
                        "results": [
                            {
                                "name": "balancete-de-despesa-consolidado-2024",
                                "title": "Balancete de Despesa Consolidado 2024",
                                "notes": "Dados de despesa consolidados.",
                                "num_resources": 9,
                                "groups": [{"title": "Despesa"}],
                            }
                        ],
                    },
                },
            )
        )
        datasets, total = await client.buscar_datasets("consolidado 2024")
        assert total == 1
        assert len(datasets) == 1
        ds = datasets[0]
        assert ds.nome == "balancete-de-despesa-consolidado-2024"
        assert ds.titulo == "Balancete de Despesa Consolidado 2024"
        assert ds.grupo == "Despesa"
        assert ds.num_recursos == 9
        assert "dataset/balancete-de-despesa-consolidado-2024" in (ds.url or "")

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_results(self) -> None:
        respx.get(PACKAGE_SEARCH_URL).mock(
            return_value=Response(
                200,
                json={"success": True, "result": {"count": 0, "results": []}},
            )
        )
        datasets, total = await client.buscar_datasets("inexistente")
        assert total == 0
        assert datasets == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_grupo_filter(self) -> None:
        respx.get(PACKAGE_SEARCH_URL).mock(
            return_value=Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "count": 5,
                        "results": [
                            {
                                "name": "licitacoes-consolidado-2024",
                                "title": "Licitacoes Consolidado 2024",
                                "num_resources": 1,
                                "groups": [{"title": "Licitacoes"}],
                            }
                        ],
                    },
                },
            )
        )
        datasets, total = await client.buscar_datasets("consolidado", grupo="licitacoes")
        assert total == 5
        assert len(datasets) == 1
        assert datasets[0].grupo == "Licitacoes"

    @pytest.mark.asyncio
    @respx.mock
    async def test_limits_rows(self) -> None:
        """Verify that limite is capped at CKAN_MAX_ROWS."""
        respx.get(PACKAGE_SEARCH_URL).mock(
            return_value=Response(
                200,
                json={"success": True, "result": {"count": 0, "results": []}},
            )
        )
        await client.buscar_datasets("test", limite=100)
        call = respx.calls[0]
        # rows param should be capped at 50
        assert call.request.url.params["rows"] == "50"

    @pytest.mark.asyncio
    @respx.mock
    async def test_dataset_without_groups(self) -> None:
        respx.get(PACKAGE_SEARCH_URL).mock(
            return_value=Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "count": 1,
                        "results": [
                            {
                                "name": "test",
                                "title": "Test",
                                "groups": [],
                            }
                        ],
                    },
                },
            )
        )
        datasets, _ = await client.buscar_datasets("test")
        assert datasets[0].grupo is None
