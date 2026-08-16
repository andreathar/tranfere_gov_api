"""Tests for the SPU-Imoveis HTTP client."""

from __future__ import annotations

import re

import httpx
import pytest
import respx

from mcp_brasil.data.spu_imoveis import client
from mcp_brasil.data.spu_imoveis.constants import PATRIMONIO_UNIAO_CSV_URL

_CSV_FIXTURE = (
    "orgao_superior_codigo_siorg,orgao_superior_nome,orgao_superior_sigla,"
    "orgao_codigo_siorg,orgao_nome,orgao_sigla,orgao_como_no_raiox_nome,"
    "orgao_como_no_raiox_sigla,ano_mes_referencia,regime_utilizacao,"
    "tipo_destinacao,tipo_imovel,endereco,municipio_nome,municipio_cod_ibge,uf,"
    "metro_quadrado_area,metro_quadrado_construida,valor_imovel,valor_aluguel\n"
    "26,PRESIDÊNCIA DA REPÚBLICA,PR,26,PR,PR,PR,PR,202405,CESSÃO - OUTROS,"
    "Palácio,Palácio,PAL JABURU,BRASÍLIA,5300108,DF,"
    "203798.0,3559.93,2933860.69,0.0\n"
    "20000,MINISTÉRIO DA EDUCAÇÃO,MEC,20000,MEC,MEC,MEC,MEC,202405,"
    "USO EM SERVIÇO PÚBLICO,Escola,Escola,RUA TESTE,SÃO PAULO,3550308,SP,"
    "1200.0,800.0,500000.00,0.0\n"
    "52000,MINISTÉRIO DA DEFESA,MD,52000,MD,MD,MD,MD,202405,IMÓVEL FUNCIONAL,"
    "Apartamento,Apartamento,SQN 101,BRASÍLIA,5300108,DF,"
    "90.0,80.0,300000.00,24000.00\n"
)


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    client._clear_cache()


@pytest.mark.asyncio
async def test_load_rows_downloads_csv_once() -> None:
    with respx.mock() as mock:
        route = mock.get(url__regex=re.escape(PATRIMONIO_UNIAO_CSV_URL)).mock(
            return_value=httpx.Response(
                200, text=_CSV_FIXTURE, headers={"content-type": "text/csv"}
            )
        )
        rows1 = await client._load_rows()
        rows2 = await client._load_rows()

    assert route.call_count == 1
    assert len(rows1) == 3
    assert rows1 == rows2
    assert rows1[0]["orgao_superior_sigla"] == "PR"


@pytest.mark.asyncio
async def test_parse_float_br_handles_locales() -> None:
    assert client._parse_float_br("543,25") == pytest.approx(543.25)
    assert client._parse_float_br("543.25") == pytest.approx(543.25)
    assert client._parse_float_br("-") is None
    assert client._parse_float_br("") is None
    assert client._parse_float_br("abc") is None


@pytest.mark.asyncio
async def test_buscar_imoveis_filters_by_orgao() -> None:
    with respx.mock() as mock:
        mock.get(url__regex=re.escape(PATRIMONIO_UNIAO_CSV_URL)).mock(
            return_value=httpx.Response(200, text=_CSV_FIXTURE)
        )
        result = await client.buscar_imoveis(orgao_sigla="MEC")

    assert len(result) == 1
    assert result[0].orgao_superior_sigla == "MEC"
    assert result[0].uf == "SP"
    assert result[0].area_terreno_m2 == pytest.approx(1200.0)


@pytest.mark.asyncio
async def test_buscar_imoveis_filters_by_uf_and_regime() -> None:
    with respx.mock() as mock:
        mock.get(url__regex=re.escape(PATRIMONIO_UNIAO_CSV_URL)).mock(
            return_value=httpx.Response(200, text=_CSV_FIXTURE)
        )
        result = await client.buscar_imoveis(uf="DF", regime="funcional")

    assert len(result) == 1
    assert result[0].orgao_superior_sigla == "MD"
    assert result[0].regime_utilizacao == "IMÓVEL FUNCIONAL"


@pytest.mark.asyncio
async def test_buscar_imoveis_respects_limite() -> None:
    with respx.mock() as mock:
        mock.get(url__regex=re.escape(PATRIMONIO_UNIAO_CSV_URL)).mock(
            return_value=httpx.Response(200, text=_CSV_FIXTURE)
        )
        result = await client.buscar_imoveis(limite=2)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_buscar_imoveis_no_match_returns_empty() -> None:
    with respx.mock() as mock:
        mock.get(url__regex=re.escape(PATRIMONIO_UNIAO_CSV_URL)).mock(
            return_value=httpx.Response(200, text=_CSV_FIXTURE)
        )
        result = await client.buscar_imoveis(uf="ZZ")
    assert result == []


@pytest.mark.asyncio
async def test_resumo_por_orgao_aggregates() -> None:
    with respx.mock() as mock:
        mock.get(url__regex=re.escape(PATRIMONIO_UNIAO_CSV_URL)).mock(
            return_value=httpx.Response(200, text=_CSV_FIXTURE)
        )
        res = await client.resumo_por_orgao(top=5)

    assert len(res) == 3
    siglas = {r.orgao_superior_sigla for r in res}
    assert siglas == {"PR", "MEC", "MD"}
    # Sorted desc by count (all three have 1 — tie allowed)
    pr = next(r for r in res if r.orgao_superior_sigla == "PR")
    assert pr.total_imoveis == 1
    assert pr.valor_total == pytest.approx(2933860.69)


@pytest.mark.asyncio
async def test_resumo_por_uf_aggregates() -> None:
    with respx.mock() as mock:
        mock.get(url__regex=re.escape(PATRIMONIO_UNIAO_CSV_URL)).mock(
            return_value=httpx.Response(200, text=_CSV_FIXTURE)
        )
        res = await client.resumo_por_uf()

    df = next(r for r in res if r.uf == "DF")
    assert df.total_imoveis == 2
    assert df.valor_aluguel_total == pytest.approx(24000.0)
    sp = next(r for r in res if r.uf == "SP")
    assert sp.total_imoveis == 1


@pytest.mark.asyncio
async def test_info_dataset_returns_metadata() -> None:
    with respx.mock() as mock:
        mock.get(url__regex=re.escape(PATRIMONIO_UNIAO_CSV_URL)).mock(
            return_value=httpx.Response(200, text=_CSV_FIXTURE)
        )
        info = await client.info_dataset()

    assert info.total_linhas == 3
    assert info.meses_referencia == ["202405"]
    assert "patrimonio-uniao.csv" in info.url_csv


@pytest.mark.asyncio
async def test_fetch_error_wraps_in_httpclienterror() -> None:
    from mcp_brasil.exceptions import HttpClientError

    with respx.mock() as mock:
        mock.get(url__regex=re.escape(PATRIMONIO_UNIAO_CSV_URL)).mock(
            return_value=httpx.Response(500, text="boom")
        )
        with pytest.raises(HttpClientError):
            await client._load_rows(force=True)
