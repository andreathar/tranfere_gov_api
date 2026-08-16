"""Tests for the SPU-Imoveis tool functions."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from mcp_brasil.data.spu_imoveis import tools
from mcp_brasil.data.spu_imoveis.schemas import (
    DatasetInfo,
    Imovel,
    ResumoOrgao,
    ResumoUF,
)


class _FakeCtx:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def info(self, msg: str, **_: Any) -> None:
        self.messages.append(msg)

    async def report_progress(self, *_: Any, **__: Any) -> None:
        pass


@pytest.mark.asyncio
async def test_info_dataset_spu_renders(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tools.client,
        "info_dataset",
        AsyncMock(
            return_value=DatasetInfo(
                nome="Raio-X APF — Patrimônio da União",
                url_csv="https://example/csv",
                url_datapackage="https://example/dp",
                total_linhas=54321,
                meses_referencia=["202405"],
                ultima_atualizacao_cache="2026-04-23T12:00:00+00:00",
            )
        ),
    )
    ctx = _FakeCtx()
    out = await tools.info_dataset_spu(ctx)  # type: ignore[arg-type]
    assert "54.321" in out
    assert "202405" in out
    assert "Raio-X APF" in out


@pytest.mark.asyncio
async def test_buscar_imoveis_spu_renders_table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tools.client,
        "buscar_imoveis",
        AsyncMock(
            return_value=[
                Imovel(
                    orgao_superior_sigla="MEC",
                    uf="SP",
                    municipio_nome="São Paulo",
                    regime_utilizacao="USO EM SERVIÇO PÚBLICO",
                    tipo_destinacao="Escola",
                    endereco="Rua A, 100",
                    valor_imovel=500000.0,
                )
            ]
        ),
    )
    ctx = _FakeCtx()
    out = await tools.buscar_imoveis_spu(
        ctx,  # type: ignore[arg-type]
        orgao_sigla="MEC",
        uf="SP",
        limite=5,
    )
    assert "MEC" in out
    assert "São Paulo" in out
    assert "R$" in out  # format_brl


@pytest.mark.asyncio
async def test_buscar_imoveis_spu_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tools.client, "buscar_imoveis", AsyncMock(return_value=[]))
    ctx = _FakeCtx()
    out = await tools.buscar_imoveis_spu(ctx, uf="ZZ")  # type: ignore[arg-type]
    assert "Nenhum imóvel encontrado" in out


@pytest.mark.asyncio
async def test_buscar_imoveis_spu_clamps_limite(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(return_value=[])
    monkeypatch.setattr(tools.client, "buscar_imoveis", mock)
    ctx = _FakeCtx()
    await tools.buscar_imoveis_spu(ctx, limite=999)  # type: ignore[arg-type]
    _, kwargs = mock.call_args
    assert kwargs["limite"] == 200


@pytest.mark.asyncio
async def test_resumo_orgaos_spu_formats(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tools.client,
        "resumo_por_orgao",
        AsyncMock(
            return_value=[
                ResumoOrgao(
                    orgao_superior_sigla="MGI",
                    orgao_superior_nome="MINISTÉRIO DA GESTÃO",
                    total_imoveis=18268,
                    area_total_m2=50_000_000.0,
                    valor_total=9_999_999.99,
                )
            ]
        ),
    )
    ctx = _FakeCtx()
    out = await tools.resumo_orgaos_spu(ctx, top=5)  # type: ignore[arg-type]
    assert "MGI" in out
    assert "18.268" in out
    assert "km²" in out


@pytest.mark.asyncio
async def test_resumo_ufs_spu_formats(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tools.client,
        "resumo_por_uf",
        AsyncMock(
            return_value=[
                ResumoUF(uf="DF", total_imoveis=10379, valor_total=1_000_000.0),
                ResumoUF(uf="SP", total_imoveis=6942, valor_total=500_000.0),
            ]
        ),
    )
    ctx = _FakeCtx()
    out = await tools.resumo_ufs_spu(ctx)  # type: ignore[arg-type]
    assert "DF" in out
    assert "SP" in out
    assert "10.379" in out
