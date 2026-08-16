"""Integration tests for anp_precos — small CSV fixture, real DuckDB."""

from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from fastmcp import Client

from mcp_brasil import settings

# 16 columns matching the renamed schema (delim=";", header=True will be
# replaced by names=[...]+skip=1 in spec, so the actual header row we ship
# here is ignored for column naming but IS skipped as row 1).
_ANP_FIXTURE = (
    "Regiao - Sigla;Estado - Sigla;Municipio;Revenda;CNPJ da Revenda;"
    "Nome da Rua;Numero Rua;Complemento;Bairro;Cep;Produto;Data da Coleta;"
    "Valor de Venda;Valor de Compra;Unidade de Medida;Bandeira\n"
    "SE;SP;SAO PAULO;POSTO A LTDA; 11.111.111/0001-00;"
    "R DOS ANDRADAS;100;;CENTRO;01234-000;GASOLINA;15/06/2024;"
    "6,099;5,500;R$/l;SHELL\n"
    "SE;SP;SAO PAULO;POSTO B LTDA; 22.222.222/0001-00;"
    "AV PAULISTA;200;;BELA VISTA;01310-000;GASOLINA;16/06/2024;"
    "6,299;5,700;R$/l;IPIRANGA\n"
    "SE;SP;CAMPINAS;POSTO C LTDA; 33.333.333/0001-00;"
    "R 13 DE MAIO;50;;CENTRO;13010-000;GASOLINA;17/06/2024;"
    "6,199;5,600;R$/l;BR\n"
    "SE;RJ;RIO DE JANEIRO;POSTO D LTDA; 44.444.444/0001-00;"
    "AV COPACABANA;300;;COPACABANA;22020-000;GASOLINA;18/06/2024;"
    "6,399;5,800;R$/l;SHELL\n"
    "SE;SP;SAO PAULO;POSTO A LTDA; 11.111.111/0001-00;"
    "R DOS ANDRADAS;100;;CENTRO;01234-000;ETANOL;15/06/2024;"
    "4,299;3,800;R$/l;SHELL\n"
)


@pytest.fixture
def tmp_cache(monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tempfile.mkdtemp(prefix="mcp-brasil-anp-test-")
    monkeypatch.setattr(settings, "DATASET_CACHE_DIR", d)
    monkeypatch.setattr(settings, "DATASETS_ENABLED", ["anp_precos"])
    return Path(d)


@pytest.fixture
def patch_sources(monkeypatch: pytest.MonkeyPatch):
    """Shrink SOURCES to a single entry — keeps the test fast (1 download vs. 36)."""
    from mcp_brasil.datasets import anp_precos as feat

    single = (("https://example.invalid/anp-fixture.csv", None, "fixture"),)
    new_spec = replace(feat.DATASET_SPEC, sources=single, url=single[0][0])
    monkeypatch.setattr(feat, "DATASET_SPEC", new_spec)
    # tools/resources import DATASET_SPEC by name at import-time;
    # patching the module attribute doesn't retroactively bind those closures,
    # but executar_query uses the reference from the tools module:
    from mcp_brasil.datasets.anp_precos import tools as t

    monkeypatch.setattr(t, "DATASET_SPEC", new_spec)


@pytest.fixture
def patch_download(tmp_cache: Path):
    def fake(url: str, dest: Path, timeout: float, source_encoding: str = "utf-8") -> int:
        dest.write_text(_ANP_FIXTURE, encoding="utf-8")
        return dest.stat().st_size

    with patch(
        "mcp_brasil._shared.datasets.loader._download_to_file",
        side_effect=fake,
    ) as m:
        yield m


def _text(result) -> str:
    data = getattr(result, "data", None)
    if isinstance(data, str):
        return data
    content = getattr(result, "content", None)
    if content:
        t = getattr(content[0], "text", None)
        if isinstance(t, str):
            return t
    return str(result)


@pytest.mark.asyncio
async def test_info_before_load(tmp_cache: Path, patch_sources) -> None:
    from mcp_brasil.datasets.anp_precos.server import mcp

    async with Client(mcp) as c:
        r = await c.call_tool("info_anp_precos", {})
    assert "Cached localmente:** não" in _text(r)


@pytest.mark.asyncio
async def test_valores_distintos_produto(tmp_cache: Path, patch_sources, patch_download) -> None:
    from mcp_brasil.datasets.anp_precos.server import mcp

    async with Client(mcp) as c:
        r = await c.call_tool("valores_distintos_anp", {"coluna": "produto"})
    text = _text(r)
    assert "GASOLINA" in text
    assert "ETANOL" in text


@pytest.mark.asyncio
async def test_valores_distintos_rejeita_coluna_invalida(
    tmp_cache: Path, patch_sources, patch_download
) -> None:
    from mcp_brasil.datasets.anp_precos.server import mcp

    async with Client(mcp) as c:
        r = await c.call_tool("valores_distintos_anp", {"coluna": "cnpj_revenda"})
    assert "não permitida" in _text(r)


@pytest.mark.asyncio
async def test_precos_por_municipio_filtra(tmp_cache: Path, patch_sources, patch_download) -> None:
    from mcp_brasil.datasets.anp_precos.server import mcp

    async with Client(mcp) as c:
        r = await c.call_tool(
            "precos_por_municipio",
            {"municipio": "sao paulo", "uf": "SP", "produto": "GASOLINA"},
        )
    text = _text(r)
    assert "POSTO A" in text or "POSTO B" in text
    assert "CAMPINAS" not in text
    assert "RIO DE JANEIRO" not in text


@pytest.mark.asyncio
async def test_media_preco_uf(tmp_cache: Path, patch_sources, patch_download) -> None:
    from mcp_brasil.datasets.anp_precos.server import mcp

    async with Client(mcp) as c:
        r = await c.call_tool("media_preco_uf", {"uf": "SP", "produto": "GASOLINA"})
    text = _text(r)
    assert "Amostras" in text
    assert "Média" in text


@pytest.mark.asyncio
async def test_top_postos_caros(tmp_cache: Path, patch_sources, patch_download) -> None:
    from mcp_brasil.datasets.anp_precos.server import mcp

    async with Client(mcp) as c:
        r = await c.call_tool(
            "top_postos_caros", {"uf": "SP", "produto": "GASOLINA", "limite": 10}
        )
    text = _text(r)
    assert "POSTO" in text
