"""Tests for the RENAME tool functions."""

from unittest.mock import AsyncMock

import pytest

from mcp_brasil.data.rename import tools
from mcp_brasil.data.rename.schemas import MedicamentoRename


@pytest.fixture
def ctx() -> AsyncMock:
    mock = AsyncMock()
    mock.info = AsyncMock()
    mock.warning = AsyncMock()
    return mock


SAMPLE_MED = MedicamentoRename(
    nome="Paracetamol",
    principio_ativo="Paracetamol",
    apresentacao="Comprimido 500mg",
    grupo="Analgésicos e Antipiréticos",
    via="Oral",
    disponivel_ubs=True,
)

SAMPLE_MED_HOSPITAL = MedicamentoRename(
    nome="Morfina",
    principio_ativo="Sulfato de Morfina",
    apresentacao="Solução Injetável 10mg/ml",
    grupo="Analgésicos e Antipiréticos",
    via="Injetável",
    disponivel_ubs=False,
)


# ---------------------------------------------------------------------------
# buscar_medicamento_rename
# ---------------------------------------------------------------------------


class TestBuscarMedicamentoRename:
    @pytest.mark.asyncio
    async def test_returns_table(self, ctx: AsyncMock) -> None:
        result = await tools.buscar_medicamento_rename(ctx, "paracetamol")
        assert "Paracetamol" in result
        assert "RENAME" in result

    @pytest.mark.asyncio
    async def test_no_results(self, ctx: AsyncMock) -> None:
        result = await tools.buscar_medicamento_rename(ctx, "inexistente_xyz")
        assert "nenhum medicamento encontrado" in result.lower()


# ---------------------------------------------------------------------------
# listar_por_grupo_terapeutico
# ---------------------------------------------------------------------------


class TestListarPorGrupoTerapeutico:
    @pytest.mark.asyncio
    async def test_returns_table(self, ctx: AsyncMock) -> None:
        result = await tools.listar_por_grupo_terapeutico(ctx, "Antibióticos")
        assert "Amoxicilina" in result
        assert "Antibióticos" in result

    @pytest.mark.asyncio
    async def test_no_results(self, ctx: AsyncMock) -> None:
        result = await tools.listar_por_grupo_terapeutico(ctx, "grupo_inexistente")
        assert "Nenhum medicamento" in result
        assert "Grupos disponíveis" in result


# ---------------------------------------------------------------------------
# verificar_disponibilidade_sus
# ---------------------------------------------------------------------------


class TestVerificarDisponibilidadeSus:
    @pytest.mark.asyncio
    async def test_found(self, ctx: AsyncMock) -> None:
        result = await tools.verificar_disponibilidade_sus(ctx, "paracetamol")
        assert "Disponibilidade no SUS" in result
        assert "Disponível em UBS" in result

    @pytest.mark.asyncio
    async def test_hospital_only(self, ctx: AsyncMock) -> None:
        result = await tools.verificar_disponibilidade_sus(ctx, "morfina")
        assert "Apenas unidades especializadas" in result

    @pytest.mark.asyncio
    async def test_not_found(self, ctx: AsyncMock) -> None:
        result = await tools.verificar_disponibilidade_sus(ctx, "inexistente_xyz")
        assert "não foi encontrado" in result.lower()


# ---------------------------------------------------------------------------
# listar_grupos_terapeuticos
# ---------------------------------------------------------------------------


class TestListarGruposTerapeuticos:
    @pytest.mark.asyncio
    async def test_returns_all_groups(self, ctx: AsyncMock) -> None:
        result = await tools.listar_grupos_terapeuticos(ctx)
        assert "Grupos Terapêuticos" in result
        assert "20 grupos" in result
        assert "Antibióticos" in result

    @pytest.mark.asyncio
    async def test_numbered_list(self, ctx: AsyncMock) -> None:
        result = await tools.listar_grupos_terapeuticos(ctx)
        assert "1." in result
        assert "20." in result


# ---------------------------------------------------------------------------
# estatisticas_rename
# ---------------------------------------------------------------------------


class TestEstatisticasRename:
    @pytest.mark.asyncio
    async def test_returns_stats(self, ctx: AsyncMock) -> None:
        result = await tools.estatisticas_rename(ctx)
        assert "Estatísticas da RENAME" in result
        assert "Total de medicamentos" in result
        assert "Grupos terapêuticos" in result
        assert "Disponíveis em UBS" in result

    @pytest.mark.asyncio
    async def test_includes_via_breakdown(self, ctx: AsyncMock) -> None:
        result = await tools.estatisticas_rename(ctx)
        assert "Por via de administração" in result
        assert "Oral" in result

    @pytest.mark.asyncio
    async def test_includes_group_breakdown(self, ctx: AsyncMock) -> None:
        result = await tools.estatisticas_rename(ctx)
        assert "Por grupo terapêutico" in result
        assert "Antibióticos" in result
