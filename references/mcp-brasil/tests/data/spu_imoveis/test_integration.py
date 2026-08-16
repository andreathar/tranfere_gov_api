"""End-to-end integration tests via fastmcp.Client with mocked HTTP."""

from __future__ import annotations

import re

import httpx
import pytest
import respx
from fastmcp import Client

from mcp_brasil.data.spu_imoveis import client as spu_client
from mcp_brasil.data.spu_imoveis.constants import PATRIMONIO_UNIAO_CSV_URL
from mcp_brasil.data.spu_imoveis.server import mcp

_CSV = (
    "orgao_superior_codigo_siorg,orgao_superior_nome,orgao_superior_sigla,"
    "orgao_codigo_siorg,orgao_nome,orgao_sigla,orgao_como_no_raiox_nome,"
    "orgao_como_no_raiox_sigla,ano_mes_referencia,regime_utilizacao,"
    "tipo_destinacao,tipo_imovel,endereco,municipio_nome,municipio_cod_ibge,uf,"
    "metro_quadrado_area,metro_quadrado_construida,valor_imovel,valor_aluguel\n"
    "20000,MINISTÉRIO DA EDUCAÇÃO,MEC,20000,MEC,MEC,MEC,MEC,202405,"
    "USO EM SERVIÇO PÚBLICO,Escola,Escola,RUA TESTE,SÃO PAULO,3550308,SP,"
    "1200.0,800.0,500000.00,0.0\n"
)


def _text(result: object) -> str:
    data = getattr(result, "data", None)
    if isinstance(data, str):
        return data
    content = getattr(result, "content", None)
    if content:
        first = content[0]
        text = getattr(first, "text", None)
        if isinstance(text, str):
            return text
    return str(result)


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    spu_client._clear_cache()


@pytest.mark.asyncio
async def test_info_dataset_end_to_end() -> None:
    with respx.mock() as mock:
        mock.get(url__regex=re.escape(PATRIMONIO_UNIAO_CSV_URL)).mock(
            return_value=httpx.Response(200, text=_CSV)
        )
        async with Client(mcp) as c:
            r = await c.call_tool("info_dataset_spu", {})

    text = _text(r)
    assert "Raio-X" in text
    assert "1" in text


@pytest.mark.asyncio
async def test_buscar_imoveis_end_to_end() -> None:
    with respx.mock() as mock:
        mock.get(url__regex=re.escape(PATRIMONIO_UNIAO_CSV_URL)).mock(
            return_value=httpx.Response(200, text=_CSV)
        )
        async with Client(mcp) as c:
            r = await c.call_tool("buscar_imoveis_spu", {"uf": "SP", "orgao_sigla": "MEC"})

    text = _text(r)
    assert "MEC" in text
    assert "SÃO PAULO" in text


@pytest.mark.asyncio
async def test_resumo_ufs_end_to_end() -> None:
    with respx.mock() as mock:
        mock.get(url__regex=re.escape(PATRIMONIO_UNIAO_CSV_URL)).mock(
            return_value=httpx.Response(200, text=_CSV)
        )
        async with Client(mcp) as c:
            r = await c.call_tool("resumo_ufs_spu", {})

    text = _text(r)
    assert "SP" in text


@pytest.mark.asyncio
async def test_resource_schema_reads_json() -> None:
    async with Client(mcp) as c:
        data = await c.read_resource("data://schema")
        text = data[0].text  # type: ignore[union-attr]
        assert "valor_imovel" in text
