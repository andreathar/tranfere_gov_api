"""Integration tests for inep_censo_escolar — minimal CSV fixture + real DuckDB."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastmcp import Client

from mcp_brasil import settings

# Minimal fixture — headers match what the real Inep CSV ships.
_CENSO_FIXTURE = (
    "NU_ANO_CENSO;NO_REGIAO;SG_UF;NO_UF;NO_MUNICIPIO;CO_MUNICIPIO;CO_ENTIDADE;"
    "NO_ENTIDADE;TP_DEPENDENCIA;TP_LOCALIZACAO;TP_SITUACAO_FUNCIONAMENTO;"
    "DS_ENDERECO;NO_BAIRRO;CO_CEP;"
    "IN_AGUA_POTAVEL;IN_ENERGIA_REDE_PUBLICA;IN_ESGOTO_REDE_PUBLICA;IN_INTERNET;"
    "IN_BIBLIOTECA;IN_QUADRA_ESPORTES;IN_LABORATORIO_CIENCIAS;"
    "IN_LABORATORIO_INFORMATICA;IN_REFEITORIO\n"
    "2023;Sudeste;SP;São Paulo;São Paulo;3550308;35000100;"
    "EE ESCOLA A;2;1;1;R DOS ANDRADAS 100;CENTRO;01234000;1;1;1;1;1;1;0;1;1\n"
    "2023;Sudeste;SP;São Paulo;Campinas;3509502;35000200;"
    "EMEI ESCOLA B;3;1;1;AV PAULISTA 200;CENTRO;13010000;1;1;0;0;0;1;0;0;1\n"
    "2023;Sudeste;SP;São Paulo;São Paulo;3550308;35000300;"
    "ESCOLA PARTICULAR C;4;1;1;R DA CONSOLACAO 300;CONSOLACAO;01301000;1;1;1;1;1;1;1;1;1\n"
    "2023;Sudeste;RJ;Rio de Janeiro;Rio de Janeiro;3304557;33000100;"
    "CE ESCOLA D;2;2;1;ESTRADA RURAL KM 5;ZONA RURAL;20000000;0;1;0;0;0;0;0;0;1\n"
)


@pytest.fixture
def tmp_cache(monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tempfile.mkdtemp(prefix="mcp-brasil-censo-test-")
    monkeypatch.setattr(settings, "DATASET_CACHE_DIR", d)
    monkeypatch.setattr(settings, "DATASETS_ENABLED", ["inep_censo_escolar"])
    return Path(d)


@pytest.fixture
def patch_stage(tmp_cache: Path):
    """Short-circuit _stage_source so tests skip ZIP download+extraction."""

    def fake(spec, url, zip_member, dest, timeout):
        dest.write_text(_CENSO_FIXTURE, encoding="utf-8")
        return dest.stat().st_size

    with patch(
        "mcp_brasil._shared.datasets.loader._stage_source",
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
async def test_info_before_load(tmp_cache: Path) -> None:
    from mcp_brasil.datasets.inep_censo_escolar.server import mcp

    async with Client(mcp) as c:
        r = await c.call_tool("info_censo_escolar", {})
    assert "Cached:** não" in _text(r)


@pytest.mark.asyncio
async def test_buscar_escolas_filter_uf(tmp_cache: Path, patch_stage) -> None:
    from mcp_brasil.datasets.inep_censo_escolar.server import mcp

    async with Client(mcp) as c:
        r = await c.call_tool("buscar_escolas", {"uf": "SP", "limite": 10})
    text = _text(r)
    assert "ESCOLA A" in text
    assert "ESCOLA D" not in text  # RJ


@pytest.mark.asyncio
async def test_buscar_escolas_filter_dependencia(tmp_cache: Path, patch_stage) -> None:
    from mcp_brasil.datasets.inep_censo_escolar.server import mcp

    async with Client(mcp) as c:
        r = await c.call_tool("buscar_escolas", {"uf": "SP", "dependencia": 4, "limite": 10})
    text = _text(r)
    assert "ESCOLA PARTICULAR C" in text
    assert "Privada" in text


@pytest.mark.asyncio
async def test_escola_detalhe(tmp_cache: Path, patch_stage) -> None:
    from mcp_brasil.datasets.inep_censo_escolar.server import mcp

    async with Client(mcp) as c:
        r = await c.call_tool("escola_detalhe", {"co_entidade": 35000100})
    text = _text(r)
    assert "EE ESCOLA A" in text
    assert "Infraestrutura" in text


@pytest.mark.asyncio
async def test_resumo_uf(tmp_cache: Path, patch_stage) -> None:
    from mcp_brasil.datasets.inep_censo_escolar.server import mcp

    async with Client(mcp) as c:
        r = await c.call_tool("resumo_uf", {"uf": "SP"})
    text = _text(r)
    # SP has: Estadual (1), Municipal (1), Privada (1)
    assert "Estadual" in text
    assert "Municipal" in text
    assert "Privada" in text


@pytest.mark.asyncio
async def test_valores_distintos_sguf(tmp_cache: Path, patch_stage) -> None:
    from mcp_brasil.datasets.inep_censo_escolar.server import mcp

    async with Client(mcp) as c:
        r = await c.call_tool("valores_distintos_censo", {"coluna": "SG_UF"})
    text = _text(r)
    assert "SP" in text
    assert "RJ" in text


@pytest.mark.asyncio
async def test_top_municipios(tmp_cache: Path, patch_stage) -> None:
    from mcp_brasil.datasets.inep_censo_escolar.server import mcp

    async with Client(mcp) as c:
        r = await c.call_tool("top_municipios_por_escolas", {"uf": "SP", "limite": 5})
    text = _text(r)
    assert "São Paulo" in text
