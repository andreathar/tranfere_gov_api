"""Tests for the TCE-RN tool functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_brasil.data.tce_rn import tools
from mcp_brasil.data.tce_rn.schemas import (
    Contrato,
    Despesa,
    Jurisdicionado,
    Licitacao,
    Receita,
)

CLIENT_MODULE = "mcp_brasil.data.tce_rn.client"


def _mock_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    return ctx


class TestListarJurisdicionadosRn:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            Jurisdicionado(
                identificador_unidade=1,
                nome_orgao="PREFEITURA DE NATAL",
                cnpj="08241747000143",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_jurisdicionados",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.listar_jurisdicionados_rn(ctx)
        assert "PREFEITURA DE NATAL" in result
        assert "`1`" in result
        assert "`08241747000143`" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_jurisdicionados",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.listar_jurisdicionados_rn(ctx)
        assert "Nenhuma entidade" in result


class TestBuscarDespesasRn:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            Despesa(
                descricao_elemento_despesa="Vencimentos",
                valor_empenho_ate_periodo=900000.0,
                valor_pago_ate_periodo=800000.0,
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_despesas",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_despesas_rn(ctx, 2024, 6, 1)
        assert "Vencimentos" in result
        assert "R$ 900.000,00" in result
        assert "R$ 800.000,00" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_despesas",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_despesas_rn(ctx, 2024, 1, 999)
        assert "Nenhuma despesa" in result


class TestBuscarReceitasRn:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            Receita(
                descricao_receita="Impostos sobre Patrimônio",
                valor_previsto_atualizado=520000.0,
                valor_realizado_no_exercicio=480000.0,
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_receitas",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_receitas_rn(ctx, 2024, 6, 1)
        assert "Impostos sobre Patrimônio" in result
        assert "R$ 520.000,00" in result
        assert "R$ 480.000,00" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_receitas",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_receitas_rn(ctx, 2024, 1, 999)
        assert "Nenhuma receita" in result


class TestBuscarLicitacoesRn:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            Licitacao(
                numero_licitacao="001",
                ano_licitacao="2024",
                modalidade="Pregao Eletronico",
                descricao_objeto="Material de escritório",
                valor_total_orcado=50000.0,
                situacao="HOMOLOGADA",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_licitacoes",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_licitacoes_rn(ctx, 1, "2024-01-01", "2024-12-31")
        assert "001" in result
        assert "Pregao Eletronico" in result
        assert "R$ 50.000,00" in result
        assert "HOMOLOGADA" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_licitacoes",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_licitacoes_rn(ctx, 999, "2024-01-01", "2024-12-31")
        assert "Nenhuma licitação" in result


class TestBuscarContratosRn:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            Contrato(
                numero_contrato="CT-001",
                ano_contrato=2024,
                objeto_contrato="Fornecimento de material",
                valor_contrato=150000.0,
                nome_contratado="EMPRESA XYZ LTDA",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_contratos",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_contratos_rn(ctx, 1)
        assert "CT-001" in result
        assert "EMPRESA XYZ LTDA" in result
        assert "R$ 150.000,00" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_contratos",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_contratos_rn(ctx, 999)
        assert "Nenhum contrato" in result
