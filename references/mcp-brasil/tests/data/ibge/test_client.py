"""Tests for the IBGE HTTP client."""

import httpx
import pytest
import respx

from mcp_brasil.data.ibge import client
from mcp_brasil.data.ibge.constants import (
    AGREGADOS_URL,
    CNAE_URL,
    LOCALIDADES_URL,
    MALHAS_URL,
    NOMES_URL,
)

# ---------------------------------------------------------------------------
# listar_estados
# ---------------------------------------------------------------------------


class TestListarEstados:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_states(self) -> None:
        respx.get(f"{LOCALIDADES_URL}/estados").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": 35,
                        "sigla": "SP",
                        "nome": "São Paulo",
                        "regiao": {"id": 3, "sigla": "SE", "nome": "Sudeste"},
                    }
                ],
            )
        )
        result = await client.listar_estados()
        assert len(result) == 1
        assert result[0].sigla == "SP"
        assert result[0].regiao.nome == "Sudeste"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(f"{LOCALIDADES_URL}/estados").mock(return_value=httpx.Response(200, json=[]))
        result = await client.listar_estados()
        assert result == []


# ---------------------------------------------------------------------------
# listar_municipios
# ---------------------------------------------------------------------------


class TestListarMunicipios:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_municipalities(self) -> None:
        respx.get(f"{LOCALIDADES_URL}/estados/PI/municipios").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": 2211001, "nome": "Teresina"},
                    {"id": 2207702, "nome": "Parnaíba"},
                ],
            )
        )
        result = await client.listar_municipios("PI")
        assert len(result) == 2
        assert result[0].nome == "Teresina"

    @pytest.mark.asyncio
    @respx.mock
    async def test_uf_uppercase(self) -> None:
        route = respx.get(f"{LOCALIDADES_URL}/estados/SP/municipios").mock(
            return_value=httpx.Response(200, json=[])
        )
        await client.listar_municipios("sp")
        assert route.called


# ---------------------------------------------------------------------------
# listar_regioes
# ---------------------------------------------------------------------------


class TestListarRegioes:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_regions(self) -> None:
        respx.get(f"{LOCALIDADES_URL}/regioes").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": 1, "sigla": "N", "nome": "Norte"},
                    {"id": 2, "sigla": "NE", "nome": "Nordeste"},
                ],
            )
        )
        result = await client.listar_regioes()
        assert len(result) == 2
        assert result[0].sigla == "N"


# ---------------------------------------------------------------------------
# consultar_nome
# ---------------------------------------------------------------------------


class TestConsultarNome:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_name(self) -> None:
        respx.get(f"{NOMES_URL}/João").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "nome": "JOÃO",
                        "sexo": None,
                        "localidade": "BR",
                        "res": [
                            {"periodo": "[1930,1940[", "frequencia": 60155},
                            {"periodo": "[1940,1950[", "frequencia": 141772},
                        ],
                    }
                ],
            )
        )
        result = await client.consultar_nome("João")
        assert len(result) == 1
        assert result[0].nome == "JOÃO"
        assert len(result[0].res) == 2
        assert result[0].res[0].frequencia == 60155

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(f"{NOMES_URL}/Xyz").mock(return_value=httpx.Response(200, json=[]))
        result = await client.consultar_nome("Xyz")
        assert result == []


# ---------------------------------------------------------------------------
# ranking_nomes
# ---------------------------------------------------------------------------


class TestRankingNomes:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_ranking(self) -> None:
        respx.get(f"{NOMES_URL}/ranking").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "localidade": "BR",
                        "sexo": None,
                        "res": [
                            {"nome": "MARIA", "frequencia": 11734129, "ranking": 1},
                            {"nome": "JOSÉ", "frequencia": 5754529, "ranking": 2},
                        ],
                    }
                ],
            )
        )
        result = await client.ranking_nomes()
        assert len(result) == 1
        assert result[0].res[0].nome == "MARIA"

    @pytest.mark.asyncio
    @respx.mock
    async def test_with_filters(self) -> None:
        route = respx.get(f"{NOMES_URL}/ranking").mock(return_value=httpx.Response(200, json=[]))
        await client.ranking_nomes(localidade="33", sexo="F")
        req_url = str(route.calls[0].request.url)
        assert "localidade=33" in req_url
        assert "sexo=F" in req_url


# ---------------------------------------------------------------------------
# consultar_agregado
# ---------------------------------------------------------------------------


class TestConsultarAgregado:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_values(self) -> None:
        url = f"{AGREGADOS_URL}/6579/periodos/-6/variaveis/9324"
        respx.get(url).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "9324",
                        "resultados": [
                            {
                                "series": [
                                    {
                                        "localidade": {"id": "35", "nome": "São Paulo"},
                                        "serie": {"2021": "44411238"},
                                    }
                                ]
                            }
                        ],
                    }
                ],
            )
        )
        result = await client.consultar_agregado(6579, 9324)
        assert len(result) == 1
        assert result[0].localidade_nome == "São Paulo"
        assert result[0].valor == "44411238"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_resultados(self) -> None:
        url = f"{AGREGADOS_URL}/6579/periodos/-6/variaveis/9324"
        respx.get(url).mock(return_value=httpx.Response(200, json=[{"resultados": []}]))
        result = await client.consultar_agregado(6579, 9324)
        assert result == []


# ---------------------------------------------------------------------------
# listar_pesquisas
# ---------------------------------------------------------------------------


class TestListarPesquisas:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_list(self) -> None:
        respx.get(AGREGADOS_URL).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": "CA", "nome": "Censo Agropecuário", "agregados": []},
                ],
            )
        )
        result = await client.listar_pesquisas()
        assert len(result) == 1
        assert result[0]["nome"] == "Censo Agropecuário"


# ---------------------------------------------------------------------------
# _malha_tipo
# ---------------------------------------------------------------------------


class TestMalhaTipo:
    def test_brasil(self) -> None:
        assert client._malha_tipo("BR") == "paises"

    def test_regiao(self) -> None:
        assert client._malha_tipo("3") == "regioes"

    def test_estado(self) -> None:
        assert client._malha_tipo("35") == "estados"

    def test_municipio(self) -> None:
        assert client._malha_tipo("3550308") == "municipios"

    def test_strips_whitespace(self) -> None:
        assert client._malha_tipo(" br ") == "paises"


# ---------------------------------------------------------------------------
# buscar_malha_metadados
# ---------------------------------------------------------------------------


class TestBuscarMalhaMetadados:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_metadata(self) -> None:
        respx.get(f"{MALHAS_URL}/estados/35/metadados").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "35",
                        "nivel-geografico": "Estado",
                        "centroide": {"latitude": -22.19, "longitude": -48.79},
                        "area": {"dimensao": 248219.481},
                        "regiao-limitrofe": [
                            {"latitude": -25.31, "longitude": -53.11},
                            {"latitude": -19.78, "longitude": -44.16},
                        ],
                    }
                ],
            )
        )
        result = await client.buscar_malha_metadados("35")
        assert result.id == "35"
        assert result.nivel_geografico == "Estado"
        assert result.area_km2 == 248219.481
        assert result.centroide_lat == -22.19

    @pytest.mark.asyncio
    @respx.mock
    async def test_missing_area(self) -> None:
        respx.get(f"{MALHAS_URL}/estados/35/metadados").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "35",
                        "nivel-geografico": "Estado",
                        "centroide": {"latitude": -22.19, "longitude": -48.79},
                    }
                ],
            )
        )
        result = await client.buscar_malha_metadados("35")
        assert result.area_km2 is None


# ---------------------------------------------------------------------------
# buscar_cnae_subclasse
# ---------------------------------------------------------------------------


class TestBuscarCnaeSubclasse:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_full_hierarchy(self) -> None:
        respx.get(f"{CNAE_URL}/subclasses/6201501").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "6201-5/01",
                    "descricao": "DESENVOLVIMENTO DE PROGRAMAS DE COMPUTADOR SOB ENCOMENDA",
                    "atividades": ["Desenvolvimento de software", "Programação"],
                    "classe": {
                        "id": "6201-5",
                        "descricao": "DESENVOLVIMENTO DE PROGRAMAS SOB ENCOMENDA",
                        "grupo": {
                            "id": "62.0",
                            "descricao": "ATIVIDADES DOS SERVIÇOS DE TI",
                            "divisao": {
                                "id": "62",
                                "descricao": "ATIVIDADES DOS SERVIÇOS DE TI",
                                "secao": {
                                    "id": "J",
                                    "descricao": "INFORMAÇÃO E COMUNICAÇÃO",
                                },
                            },
                        },
                    },
                },
            )
        )
        result = await client.buscar_cnae_subclasse("6201501")
        assert result.id == "6201-5/01"
        assert result.secao_id == "J"
        assert result.divisao_id == "62"
        assert len(result.atividades) == 2


# ---------------------------------------------------------------------------
# listar_cnae_secoes
# ---------------------------------------------------------------------------


class TestListarCnaeSecoes:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_sections(self) -> None:
        respx.get(f"{CNAE_URL}/secoes").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": "A", "descricao": "AGRICULTURA"},
                    {"id": "B", "descricao": "INDÚSTRIAS EXTRATIVAS"},
                ],
            )
        )
        result = await client.listar_cnae_secoes()
        assert len(result) == 2
        assert result[0].id == "A"
