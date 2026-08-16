"""Tests for the DENASUS tool functions."""

from unittest.mock import AsyncMock, patch

import pytest

from mcp_brasil.data.denasus import tools
from mcp_brasil.data.denasus.schemas import (
    AtividadeAuditoria,
    PlanoAuditoria,
    RelatorioAnual,
)

CLIENT_MODULE = "mcp_brasil.data.denasus.client"


@pytest.fixture
def ctx() -> AsyncMock:
    mock = AsyncMock()
    mock.info = AsyncMock()
    mock.warning = AsyncMock()
    return mock


SAMPLE_ATIVIDADES = [
    AtividadeAuditoria(
        titulo="Auditoria no Hospital Regional - BA",
        data="15/03/2024",
        uf="BA",
        tipo="Auditoria",
        situacao="Concluída",
        resumo="Verificação de procedimentos.",
        url_detalhe="/detalhe/1",
    ),
    AtividadeAuditoria(
        titulo="Monitoramento SUS em Teresina - PI",
        data="20/01/2024",
        uf="PI",
        tipo="Monitoramento",
        situacao="Concluída",
    ),
]

SAMPLE_RELATORIOS = [
    RelatorioAnual(
        ano=2024,
        titulo="Relatório de Atividades 2024",
        url_pdf="/relatorio-2024.pdf",
    ),
    RelatorioAnual(
        ano=2023,
        titulo="Relatório de Atividades 2023",
        url_pdf="/relatorio-2023.pdf",
    ),
]

SAMPLE_PLANOS = [
    PlanoAuditoria(
        ano=2025,
        titulo="Plano de Auditoria 2025",
        url_pdf="/plano-2025.pdf",
    ),
]


# ---------------------------------------------------------------------------
# buscar_auditorias
# ---------------------------------------------------------------------------


class TestBuscarAuditorias:
    @pytest.mark.asyncio
    async def test_returns_all(self, ctx: AsyncMock) -> None:
        with patch(
            f"{CLIENT_MODULE}.listar_atividades_auditoria",
            new_callable=AsyncMock,
            return_value=SAMPLE_ATIVIDADES,
        ):
            result = await tools.buscar_auditorias(ctx)
            assert "Atividades de Auditoria" in result
            assert "BA" in result
            assert "2 resultado" in result

    @pytest.mark.asyncio
    async def test_filter_by_uf(self, ctx: AsyncMock) -> None:
        with patch(
            f"{CLIENT_MODULE}.listar_atividades_auditoria",
            new_callable=AsyncMock,
            return_value=SAMPLE_ATIVIDADES,
        ):
            result = await tools.buscar_auditorias(ctx, uf="BA")
            assert "1 resultado" in result
            assert "BA" in result

    @pytest.mark.asyncio
    async def test_filter_by_keyword(self, ctx: AsyncMock) -> None:
        with patch(
            f"{CLIENT_MODULE}.listar_atividades_auditoria",
            new_callable=AsyncMock,
            return_value=SAMPLE_ATIVIDADES,
        ):
            result = await tools.buscar_auditorias(ctx, palavra_chave="Hospital")
            assert "1 resultado" in result

    @pytest.mark.asyncio
    async def test_no_results(self, ctx: AsyncMock) -> None:
        with patch(
            f"{CLIENT_MODULE}.listar_atividades_auditoria",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_auditorias(ctx)
            assert "Nenhuma atividade" in result

    @pytest.mark.asyncio
    async def test_handles_error(self, ctx: AsyncMock) -> None:
        with patch(
            f"{CLIENT_MODULE}.listar_atividades_auditoria",
            new_callable=AsyncMock,
            side_effect=Exception("Connection failed"),
        ):
            result = await tools.buscar_auditorias(ctx)
            assert "indisponível" in result


# ---------------------------------------------------------------------------
# listar_relatorios_anuais
# ---------------------------------------------------------------------------


class TestListarRelatoriosAnuais:
    @pytest.mark.asyncio
    async def test_returns_reports(self, ctx: AsyncMock) -> None:
        with patch(
            f"{CLIENT_MODULE}.listar_relatorios_anuais",
            new_callable=AsyncMock,
            return_value=SAMPLE_RELATORIOS,
        ):
            result = await tools.listar_relatorios_anuais(ctx)
            assert "Relatórios Anuais" in result
            assert "2024" in result
            assert "2023" in result

    @pytest.mark.asyncio
    async def test_no_reports(self, ctx: AsyncMock) -> None:
        with patch(
            f"{CLIENT_MODULE}.listar_relatorios_anuais",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.listar_relatorios_anuais(ctx)
            assert "Nenhum relatório" in result


# ---------------------------------------------------------------------------
# listar_planos
# ---------------------------------------------------------------------------


class TestListarPlanos:
    @pytest.mark.asyncio
    async def test_returns_plans(self, ctx: AsyncMock) -> None:
        with patch(
            f"{CLIENT_MODULE}.listar_planos_auditoria",
            new_callable=AsyncMock,
            return_value=SAMPLE_PLANOS,
        ):
            result = await tools.listar_planos(ctx)
            assert "Planos de Auditoria" in result
            assert "2025" in result

    @pytest.mark.asyncio
    async def test_no_plans(self, ctx: AsyncMock) -> None:
        with patch(
            f"{CLIENT_MODULE}.listar_planos_auditoria",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.listar_planos(ctx)
            assert "Nenhum plano" in result


# ---------------------------------------------------------------------------
# verificar_municipio
# ---------------------------------------------------------------------------


class TestVerificarMunicipio:
    @pytest.mark.asyncio
    async def test_found(self, ctx: AsyncMock) -> None:
        with patch(
            f"{CLIENT_MODULE}.listar_atividades_auditoria",
            new_callable=AsyncMock,
            return_value=SAMPLE_ATIVIDADES,
        ):
            result = await tools.verificar_municipio(ctx, "Teresina")
            assert "Teresina" in result
            assert "1 encontrada" in result

    @pytest.mark.asyncio
    async def test_found_with_uf(self, ctx: AsyncMock) -> None:
        with patch(
            f"{CLIENT_MODULE}.listar_atividades_auditoria",
            new_callable=AsyncMock,
            return_value=SAMPLE_ATIVIDADES,
        ):
            result = await tools.verificar_municipio(ctx, "Teresina", uf="PI")
            assert "Teresina" in result

    @pytest.mark.asyncio
    async def test_not_found(self, ctx: AsyncMock) -> None:
        with patch(
            f"{CLIENT_MODULE}.listar_atividades_auditoria",
            new_callable=AsyncMock,
            return_value=SAMPLE_ATIVIDADES,
        ):
            result = await tools.verificar_municipio(ctx, "Manaus")
            assert "Nenhuma auditoria" in result


# ---------------------------------------------------------------------------
# informacoes_sna
# ---------------------------------------------------------------------------


class TestInformacoesSna:
    @pytest.mark.asyncio
    async def test_returns_info(self, ctx: AsyncMock) -> None:
        result = await tools.informacoes_sna(ctx)
        assert "Sistema Nacional de Auditoria" in result
        assert "DENASUS" in result
        assert "Lei" in result
