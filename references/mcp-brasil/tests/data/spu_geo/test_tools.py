"""Tests for the SPU-Geo tool functions (mocked client)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from mcp_brasil.data.spu_geo import tools
from mcp_brasil.data.spu_geo.schemas import FeatureGeo, ResultadoPonto


class _FakeCtx:
    """Minimal Context stub exposing the async logging methods used by tools."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    async def info(self, msg: str, **_: Any) -> None:
        self.messages.append(msg)

    async def report_progress(self, *_: Any, **__: Any) -> None:
        pass


@pytest.mark.asyncio
async def test_listar_camadas_spu_renders_table() -> None:
    ctx = _FakeCtx()
    out = await tools.listar_camadas_spu(ctx)  # type: ignore[arg-type]
    assert "GeoPortal SPU" in out
    assert "terreno_marinha" in out
    assert "imovel_localizacao" in out
    assert any("Listando camadas" in m for m in ctx.messages)


@pytest.mark.asyncio
async def test_consultar_ponto_spu_with_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=ResultadoPonto(
            lat=-22.9,
            lon=-43.2,
            camadas_encontradas=["terreno_marinha"],
            features=[
                FeatureGeo(
                    id="vw_app_trecho_terreno_marinha_a.1",
                    camada="terreno_marinha",
                    geometry_type="MultiPolygon",
                    properties={
                        "uf": "RJ",
                        "nome_trecho": "Rua Santo Cristo",
                        "area_aproximada": 13700.0,
                        "etapa_demarcacao": "Aprovado",
                    },
                )
            ],
        )
    )
    monkeypatch.setattr(tools.client, "verificar_ponto", mock)

    ctx = _FakeCtx()
    out = await tools.consultar_ponto_spu(ctx, -22.9, -43.2)  # type: ignore[arg-type]
    assert "está em terras da União" in out
    assert "terreno_marinha" in out
    assert "Rua Santo Cristo" in out
    assert "RJ" in out


@pytest.mark.asyncio
async def test_consultar_ponto_spu_no_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=ResultadoPonto(lat=0.0, lon=0.0, camadas_encontradas=[], features=[])
    )
    monkeypatch.setattr(tools.client, "verificar_ponto", mock)

    ctx = _FakeCtx()
    out = await tools.consultar_ponto_spu(ctx, 0.0, 0.0)  # type: ignore[arg-type]
    assert "não está em nenhuma" in out


@pytest.mark.asyncio
async def test_buscar_imoveis_area_spu_formats_table(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=[
            FeatureGeo(
                id="vw_imv_localizacao_imovel_p.1",
                camada="imovel_localizacao",
                geometry_type="Point",
                properties={
                    "rip": "00005569",
                    "tipo_imovel": "Terreno",
                    "id_uf": "RJ",
                    "municipio": "Rio de Janeiro",
                    "endereco": "Praça Santo Cristo",
                },
            )
        ]
    )
    monkeypatch.setattr(tools.client, "buscar_imoveis_bbox", mock)

    ctx = _FakeCtx()
    out = await tools.buscar_imoveis_area_spu(
        ctx,  # type: ignore[arg-type]
        bbox="-43.3,-23.0,-43.1,-22.8",
        limite=10,
    )
    assert "00005569" in out
    assert "Rio de Janeiro" in out
    assert "Terreno" in out
    mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_buscar_imoveis_area_spu_clamps_limite(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(return_value=[])
    monkeypatch.setattr(tools.client, "buscar_imoveis_bbox", mock)

    ctx = _FakeCtx()
    await tools.buscar_imoveis_area_spu(ctx, bbox="0,0,1,1", limite=999)  # type: ignore[arg-type]
    _, kwargs = mock.call_args
    assert kwargs["feature_count"] == 100


@pytest.mark.asyncio
async def test_buscar_imoveis_area_spu_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tools.client, "buscar_imoveis_bbox", AsyncMock(return_value=[]))
    ctx = _FakeCtx()
    out = await tools.buscar_imoveis_area_spu(ctx, bbox="0,0,1,1")  # type: ignore[arg-type]
    assert "Nenhum imóvel" in out


@pytest.mark.asyncio
async def test_detalhar_camada_spu_valid() -> None:
    ctx = _FakeCtx()
    out = await tools.detalhar_camada_spu(ctx, "terreno_marinha")  # type: ignore[arg-type]
    assert "Trechos de Terreno de Marinha" in out
    assert "spunet:vw_app_trecho_terreno_marinha_a" in out


@pytest.mark.asyncio
async def test_detalhar_camada_spu_invalid() -> None:
    ctx = _FakeCtx()
    out = await tools.detalhar_camada_spu(ctx, "inexistente")  # type: ignore[arg-type]
    assert "não encontrada" in out
