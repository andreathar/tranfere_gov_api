"""Tests for the TCE-PI tool functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_brasil.data.tce_pi import tools
from mcp_brasil.data.tce_pi.schemas import (
    DespesaAnual,
    DespesaFuncao,
    Gestor,
    Orgao,
    Prefeitura,
    ReceitaDetalhe,
)

CLIENT_MODULE = "mcp_brasil.data.tce_pi.client"


def _mock_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    return ctx


class TestListarPrefeiturasPi:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            Prefeitura(id=133, nome="Teresina", codIBGE="2211001"),
            Prefeitura(id=1, nome="Acauã", codIBGE="2200053"),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_prefeituras",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.listar_prefeituras_pi(ctx)
        assert "Teresina" in result
        assert "Acauã" in result
        assert "2 municípios" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_prefeituras",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.listar_prefeituras_pi(ctx)
        assert "Nenhuma prefeitura" in result

    @pytest.mark.asyncio
    async def test_truncates_at_50(self) -> None:
        mock_data = [Prefeitura(id=i, nome=f"Cidade {i}") for i in range(60)]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_prefeituras",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.listar_prefeituras_pi(ctx)
        assert "e mais 10 municípios" in result


class TestBuscarPrefeituraPi:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_prefeitura = [
            Prefeitura(
                id=133,
                nome="Teresina",
                codIBGE="2211001",
                urlPrefeitura="http://www.teresina.pi.gov.br",
            )
        ]
        mock_gestor = Gestor(
            nome="SILVIO MENDES",
            inicio_gestao="2025-01-01T00:00:00.000Z",
        )
        ctx = _mock_ctx()
        with (
            patch(
                f"{CLIENT_MODULE}.buscar_prefeitura",
                new_callable=AsyncMock,
                return_value=mock_prefeitura,
            ),
            patch(
                f"{CLIENT_MODULE}.consultar_gestor",
                new_callable=AsyncMock,
                return_value=mock_gestor,
            ),
        ):
            result = await tools.buscar_prefeitura_pi(ctx, nome="Teresina")
        assert "Teresina" in result
        assert "SILVIO MENDES" in result
        assert "2025-01-01" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_prefeitura",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_prefeitura_pi(ctx, nome="XYZXYZ")
        assert "Nenhuma prefeitura" in result


class TestConsultarDespesasPi:
    @pytest.mark.asyncio
    async def test_formats_historico(self) -> None:
        mock_data = [
            DespesaAnual(
                exercicio=2024,
                empenhada=1000000,
                liquidada=900000,
                paga=850000,
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_despesas",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_despesas_pi(ctx, id_prefeitura=133)
        assert "2024" in result
        assert "Histórico anual" in result

    @pytest.mark.asyncio
    async def test_includes_funcoes(self) -> None:
        mock_anuais = [
            DespesaAnual(exercicio=2024, empenhada=1e6, liquidada=9e5, paga=8.5e5),
        ]
        mock_funcoes = [
            DespesaFuncao(funcao="Saúde", paga=300000),
            DespesaFuncao(funcao="Educação", paga=250000),
        ]
        ctx = _mock_ctx()
        with (
            patch(
                f"{CLIENT_MODULE}.consultar_despesas",
                new_callable=AsyncMock,
                return_value=mock_anuais,
            ),
            patch(
                f"{CLIENT_MODULE}.consultar_despesas_por_funcao",
                new_callable=AsyncMock,
                return_value=mock_funcoes,
            ),
        ):
            result = await tools.consultar_despesas_pi(ctx, id_prefeitura=133, exercicio=2024)
        assert "Saúde" in result
        assert "Educação" in result
        assert "por função" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_despesas",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.consultar_despesas_pi(ctx, id_prefeitura=999)
        assert "Nenhuma despesa" in result


class TestConsultarReceitasPi:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            ReceitaDetalhe(
                categoria="Receitas Correntes",
                origem="Transferência",
                receita="PNAE",
                prevista=14151000,
                arrecadada=14161240,
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_receitas",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_receitas_pi(ctx, id_prefeitura=133, exercicio=2024)
        assert "Receitas Correntes" in result
        assert "PNAE" in result
        assert "1 itens" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_receitas",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.consultar_receitas_pi(ctx, id_prefeitura=999, exercicio=2024)
        assert "Nenhuma receita" in result


class TestListarOrgaosPi:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            Orgao(id="010101", nome="ASSEMBLEIA LEGISLATIVA", sigla="ALEPI"),
            Orgao(id="020201", nome="TRIBUNAL DE JUSTICA", sigla="TJPI"),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_orgaos",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.listar_orgaos_pi(ctx, exercicio=2024)
        assert "ASSEMBLEIA LEGISLATIVA" in result
        assert "ALEPI" in result
        assert "2 órgãos" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_orgaos",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.listar_orgaos_pi(ctx, exercicio=2000)
        assert "Nenhum órgão" in result
