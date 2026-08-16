"""Tests for the TCE-PE tool functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_brasil.data.tce_pe import tools
from mcp_brasil.data.tce_pe.schemas import (
    Contrato,
    Despesa,
    Fornecedor,
    Licitacao,
    UnidadeJurisdicionada,
)

CLIENT_MODULE = "mcp_brasil.data.tce_pe.client"


def _mock_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    return ctx


# ---------------------------------------------------------------------------
# buscar_unidades_pe
# ---------------------------------------------------------------------------


class TestBuscarUnidadesPe:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            UnidadeJurisdicionada(codigo="123", nome="PREFEITURA DO RECIFE", municipio="Recife"),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_unidades",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_unidades_pe(ctx)
        assert "PREFEITURA DO RECIFE" in result
        assert "`123`" in result
        assert "1 unidades" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_unidades",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_unidades_pe(ctx)
        assert "Nenhuma unidade jurisdicionada" in result


# ---------------------------------------------------------------------------
# buscar_licitacoes_pe
# ---------------------------------------------------------------------------


class TestBuscarLicitacoesPe:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            Licitacao(
                numero_licitacao="001/2024",
                ano_licitacao=2024,
                modalidade="Pregão Eletrônico",
                objeto="Material escolar",
                valor_estimado=150000.0,
                situacao="Homologada",
                municipio="Recife",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_licitacoes",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_licitacoes_pe(ctx, 2024)
        assert "001/2024" in result
        assert "Pregão Eletrônico" in result
        assert "R$ 150.000,00" in result
        assert "Homologada" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_licitacoes",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_licitacoes_pe(ctx, 2024)
        assert "Nenhuma licitação encontrada" in result

    @pytest.mark.asyncio
    async def test_truncates_long_list(self) -> None:
        mock_data = [
            Licitacao(numero_licitacao=f"{i:03d}/2024", objeto=f"Obj {i}") for i in range(25)
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_licitacoes",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_licitacoes_pe(ctx, 2024)
        assert "Mostrando 20 de 25" in result


# ---------------------------------------------------------------------------
# buscar_contratos_pe
# ---------------------------------------------------------------------------


class TestBuscarContratosPe:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            Contrato(
                numero_contrato="CT-001/2024",
                objeto="Merenda escolar",
                valor_contrato=500000.0,
                fornecedor="EMPRESA ABC",
                municipio="Recife",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_contratos",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_contratos_pe(ctx, 2024)
        assert "CT-001/2024" in result
        assert "EMPRESA ABC" in result
        assert "R$ 500.000,00" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_contratos",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_contratos_pe(ctx, 2024)
        assert "Nenhum contrato encontrado" in result


# ---------------------------------------------------------------------------
# buscar_despesas_pe
# ---------------------------------------------------------------------------


class TestBuscarDespesasPe:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            Despesa(
                numero_empenho="2024NE001",
                fornecedor="EMPRESA XYZ",
                valor_empenhado=25000.0,
                valor_pago=18000.0,
                funcao="Educação",
                historico="Pagamento de serviços",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_despesas",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_despesas_pe(ctx, 2024)
        assert "2024NE001" in result
        assert "EMPRESA XYZ" in result
        assert "R$ 25.000,00" in result
        assert "R$ 18.000,00" in result
        assert "Educação" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_despesas",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_despesas_pe(ctx, 2024)
        assert "Nenhuma despesa encontrada" in result


# ---------------------------------------------------------------------------
# buscar_fornecedores_pe
# ---------------------------------------------------------------------------


class TestBuscarFornecedoresPe:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            Fornecedor(cpf_cnpj="06990590000123", nome="GOOGLE BRASIL"),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_fornecedores",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_fornecedores_pe(ctx, nome="GOOGLE")
        assert "GOOGLE BRASIL" in result
        assert "`06990590000123`" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_fornecedores",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_fornecedores_pe(ctx, nome="INEXISTENTE")
        assert "Nenhum fornecedor encontrado" in result
