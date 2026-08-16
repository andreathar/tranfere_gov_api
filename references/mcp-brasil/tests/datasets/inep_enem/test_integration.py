"""Integration tests for inep_enem — minimal CSV fixture + real DuckDB."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastmcp import Client

from mcp_brasil import settings

# Minimal ENEM fixture — subset of real columns, 5 sample rows.
_ENEM_FIXTURE = (
    "NU_INSCRICAO;NU_ANO;TP_FAIXA_ETARIA;TP_SEXO;TP_COR_RACA;TP_ESCOLA;"
    "SG_UF_ESC;SG_UF_PROVA;NO_MUNICIPIO_PROVA;"
    "TP_PRESENCA_CN;TP_PRESENCA_CH;TP_PRESENCA_LC;TP_PRESENCA_MT;"
    "NU_NOTA_CN;NU_NOTA_CH;NU_NOTA_LC;NU_NOTA_MT;NU_NOTA_REDACAO;TP_LINGUA;TP_ST_CONCLUSAO\n"
    # SP public, present
    "111111111111;2023;3;M;3;2;SP;SP;SAO PAULO;1;1;1;1;650,5;700,0;620,3;750,0;800,0;0;1\n"
    # SP private, present
    "222222222222;2023;4;F;1;3;SP;SP;SAO PAULO;1;1;1;1;720,0;780,5;710,2;820,0;900,0;0;1\n"
    # SP public, present, campinas
    "333333333333;2023;5;F;3;2;SP;SP;CAMPINAS;1;1;1;1;600,0;680,0;590,0;700,0;760,0;1;1\n"
    # RJ public, absent dia 1 — should be excluded from averages
    "444444444444;2023;3;M;2;2;RJ;RJ;RIO DE JANEIRO;1;0;0;1;;;;550,0;;0;1\n"
    # RJ private, present
    "555555555555;2023;4;F;1;3;RJ;RJ;RIO DE JANEIRO;1;1;1;1;710,0;720,0;690,0;800,0;850,0;0;1\n"
)


@pytest.fixture
def tmp_cache(monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tempfile.mkdtemp(prefix="mcp-brasil-enem-test-")
    monkeypatch.setattr(settings, "DATASET_CACHE_DIR", d)
    monkeypatch.setattr(settings, "DATASETS_ENABLED", ["inep_enem"])
    return Path(d)


@pytest.fixture
def patch_stage(tmp_cache: Path):
    def fake(spec, url, zip_member, dest, timeout):
        dest.write_text(_ENEM_FIXTURE, encoding="utf-8")
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
    from mcp_brasil.datasets.inep_enem.server import mcp

    async with Client(mcp) as c:
        r = await c.call_tool("info_enem", {})
    assert "Cached:** não" in _text(r)


@pytest.mark.asyncio
async def test_media_notas_uf_sp(tmp_cache: Path, patch_stage) -> None:
    from mcp_brasil.datasets.inep_enem.server import mcp

    async with Client(mcp) as c:
        r = await c.call_tool("media_notas_uf", {"uf": "SP"})
    text = _text(r)
    assert "Presentes: 3" in text
    assert "Redação" in text


@pytest.mark.asyncio
async def test_media_notas_uf_rj_exclui_ausentes(tmp_cache: Path, patch_stage) -> None:
    from mcp_brasil.datasets.inep_enem.server import mcp

    async with Client(mcp) as c:
        r = await c.call_tool("media_notas_uf", {"uf": "RJ"})
    text = _text(r)
    # Only 1 present in RJ (555555...) — the absent one should be filtered out
    assert "Presentes: 1" in text


@pytest.mark.asyncio
async def test_media_por_grupo_escola(tmp_cache: Path, patch_stage) -> None:
    from mcp_brasil.datasets.inep_enem.server import mcp

    async with Client(mcp) as c:
        r = await c.call_tool("media_notas_por_grupo", {"coluna": "TP_ESCOLA", "uf": "SP"})
    text = _text(r)
    assert "Pública" in text
    assert "Privada" in text


@pytest.mark.asyncio
async def test_valores_distintos(tmp_cache: Path, patch_stage) -> None:
    from mcp_brasil.datasets.inep_enem.server import mcp

    async with Client(mcp) as c:
        r = await c.call_tool("valores_distintos_enem", {"coluna": "SG_UF_PROVA"})
    text = _text(r)
    assert "SP" in text
    assert "RJ" in text


@pytest.mark.asyncio
async def test_valores_distintos_rejeita_pii(tmp_cache: Path, patch_stage) -> None:
    from mcp_brasil.datasets.inep_enem.server import mcp

    async with Client(mcp) as c:
        r = await c.call_tool("valores_distintos_enem", {"coluna": "NU_INSCRICAO"})
    assert "não permitida" in _text(r)


@pytest.mark.asyncio
async def test_top_municipios(tmp_cache: Path, patch_stage) -> None:
    from mcp_brasil.datasets.inep_enem.server import mcp

    async with Client(mcp) as c:
        r = await c.call_tool(
            "top_municipios_por_media",
            {"uf": "SP", "minimo_participantes": 1, "limite": 5},
        )
    text = _text(r)
    assert "SAO PAULO" in text or "CAMPINAS" in text
