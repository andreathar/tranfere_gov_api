"""Tests for the FNDE HTTP client."""

import httpx
import pytest
import respx

from mcp_brasil.data.fnde import client
from mcp_brasil.data.fnde.constants import FUNDEB_URL, PNAE_URL, PNATE_URL, PNLD_URL

# ---------------------------------------------------------------------------
# consultar_fundeb_matriculas
# ---------------------------------------------------------------------------


class TestConsultarFundebMatriculas:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_data(self) -> None:
        respx.get(FUNDEB_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "AnoCenso": 2018,
                            "Uf": "SP",
                            "MunicipioGe": "SAO PAULO",
                            "TipoRedeEducacao": "EDUCAÇÃO PÚBLICA",
                            "DescricaoTipoEducacao": "ENSINO REGULAR",
                            "DescricaoTipoEnsino": "ENSINO FUNDAMENTAL",
                            "DescricaoTipoTurma": "ANOS INICIAIS",
                            "DescricaoTipoCargaHoraria": "PARCIAL",
                            "DescricaoTipoLocalizacao": "URBANA",
                            "QtdMatricula": 12345,
                        }
                    ]
                },
            )
        )
        result = await client.consultar_fundeb_matriculas(ano=2018, uf="SP")
        assert len(result) == 1
        assert result[0].uf == "SP"
        assert result[0].municipio == "SAO PAULO"
        assert result[0].quantidade == 12345

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(FUNDEB_URL).mock(return_value=httpx.Response(200, json={"value": []}))
        result = await client.consultar_fundeb_matriculas(ano=2025)
        assert result == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_filters_are_applied(self) -> None:
        route = respx.get(FUNDEB_URL).mock(return_value=httpx.Response(200, json={"value": []}))
        await client.consultar_fundeb_matriculas(ano=2018, uf="RJ", municipio="NITEROI")
        assert route.called
        request = route.calls[0].request
        url_str = str(request.url)
        assert "AnoCenso" in url_str
        assert "2018" in url_str
        assert "RJ" in url_str
        assert "NITEROI" in url_str


# ---------------------------------------------------------------------------
# consultar_pnae_alunos
# ---------------------------------------------------------------------------


class TestConsultarPnaeAlunos:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_data(self) -> None:
        respx.get(PNAE_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "Co_alunos_atendidos": "123",
                            "Ano": "2022",
                            "Estado": "BA",
                            "Municipio": "SALVADOR",
                            "Regiao": "NORDESTE",
                            "Esfera_governo": "MUNICIPAL",
                            "Etapa_ensino": "CRECHE",
                            "Qt_alunos_pnae": 5000,
                        }
                    ]
                },
            )
        )
        result = await client.consultar_pnae_alunos(ano="2022", estado="BA")
        assert len(result) == 1
        assert result[0].estado == "BA"
        assert result[0].quantidade == 5000

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(PNAE_URL).mock(return_value=httpx.Response(200, json={"value": []}))
        result = await client.consultar_pnae_alunos(ano="2099")
        assert result == []


# ---------------------------------------------------------------------------
# consultar_pnld_livros
# ---------------------------------------------------------------------------


class TestConsultarPnldLivros:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_data(self) -> None:
        respx.get(PNLD_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "Programa": "PNLD",
                            "Ano": "2019",
                            "Editora": "EDITORA ATICA S/A",
                            "Cod_livro": "0032P19011001IL",
                            "Titulo_livro": "ÁPIS LÍNGUA PORTUGUESA",
                            "Criterio": "200821 - DISTRIB",
                            "Qt_titulos": 8236,
                            "Custo_titulos": 86889.80,
                        }
                    ]
                },
            )
        )
        result = await client.consultar_pnld_livros(ano="2019")
        assert len(result) == 1
        assert result[0].editora == "EDITORA ATICA S/A"
        assert result[0].custo == 86889.80

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(PNLD_URL).mock(return_value=httpx.Response(200, json={"value": []}))
        result = await client.consultar_pnld_livros()
        assert result == []


# ---------------------------------------------------------------------------
# consultar_pnate_transporte
# ---------------------------------------------------------------------------


class TestConsultarPnateTransporte:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_data(self) -> None:
        respx.get(PNATE_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "Uf": "AM",
                            "Municipio": "MANAUS",
                            "EntidadeExecutora": "PREF MUN DE MANAUS",
                            "Cnpj": "04365326000169",
                            "QtdAlunosAtendidos": 15000,
                        }
                    ]
                },
            )
        )
        result = await client.consultar_pnate_transporte(uf="AM")
        assert len(result) == 1
        assert result[0].uf == "AM"
        assert result[0].quantidade == 15000

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(PNATE_URL).mock(return_value=httpx.Response(200, json={"value": []}))
        result = await client.consultar_pnate_transporte(uf="XX")
        assert result == []
