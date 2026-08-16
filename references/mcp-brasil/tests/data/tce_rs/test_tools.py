"""Tests for the TCE-RS tool functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_brasil.data.tce_rs import tools
from mcp_brasil.data.tce_rs.schemas import (
    Dataset,
    GestaoFiscal,
    IndiceEducacao,
    IndiceSaude,
    Municipio,
)

CLIENT_MODULE = "mcp_brasil.data.tce_rs.client"


def _mock_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    return ctx


# ---------------------------------------------------------------------------
# listar_municipios_rs
# ---------------------------------------------------------------------------


class TestListarMunicipiosRs:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            Municipio(codigo=1, nome="AGUDO", uf="RS", codigo_ibge=4300109),
            Municipio(codigo=2, nome="PORTO ALEGRE", uf="RS", codigo_ibge=4314902),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_municipios",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.listar_municipios_rs(ctx)
        assert "AGUDO" in result
        assert "PORTO ALEGRE" in result
        assert "`1`" in result
        assert "IBGE: 4300109" in result
        assert "2 municípios" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_municipios",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.listar_municipios_rs(ctx)
        assert "Nenhum município" in result

    @pytest.mark.asyncio
    async def test_truncates_at_50(self) -> None:
        mock_data = [Municipio(codigo=i, nome=f"CIDADE {i}") for i in range(60)]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_municipios",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.listar_municipios_rs(ctx)
        assert "Mostrando 50 de 60" in result


# ---------------------------------------------------------------------------
# buscar_indices_educacao_rs
# ---------------------------------------------------------------------------


class TestBuscarIndicesEducacaoRs:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            IndiceEducacao(
                ano=2024,
                codigo_orgao=100,
                nome_orgao="PREFEITURA DE PORTO ALEGRE",
                valor_despesa=500000.0,
                valor_receita=1800000.0,
                indice=0.2778,
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_indices_educacao",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_indices_educacao_rs(ctx, 2024)
        assert "PREFEITURA DE PORTO ALEGRE" in result
        assert "27,78%" in result
        assert "R$ 500.000,00" in result
        assert "1 índices" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_indices_educacao",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_indices_educacao_rs(ctx, 2024)
        assert "Nenhum índice de educação" in result

    @pytest.mark.asyncio
    async def test_filters_by_municipio(self) -> None:
        mock_data = [
            IndiceEducacao(nome_orgao="PREFEITURA DE PORTO ALEGRE", indice=0.28),
            IndiceEducacao(nome_orgao="PREFEITURA DE CAXIAS DO SUL", indice=0.26),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_indices_educacao",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_indices_educacao_rs(ctx, 2024, municipio="CAXIAS")
        assert "CAXIAS DO SUL" in result
        assert "PORTO ALEGRE" not in result

    @pytest.mark.asyncio
    async def test_truncates_at_30(self) -> None:
        mock_data = [IndiceEducacao(nome_orgao=f"PREFEITURA {i}", indice=0.25) for i in range(35)]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_indices_educacao",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_indices_educacao_rs(ctx, 2024)
        assert "Mostrando 30 de 35" in result


# ---------------------------------------------------------------------------
# buscar_indices_saude_rs
# ---------------------------------------------------------------------------


class TestBuscarIndicesSaudeRs:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            IndiceSaude(
                nome_orgao="PREFEITURA DE CAXIAS DO SUL",
                valor_despesa=300000.0,
                valor_receita=1500000.0,
                indice=0.20,
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_indices_saude",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_indices_saude_rs(ctx, 2024)
        assert "CAXIAS DO SUL" in result
        assert "20,00%" in result
        assert "R$ 300.000,00" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_indices_saude",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_indices_saude_rs(ctx, 2024)
        assert "Nenhum índice de saúde" in result

    @pytest.mark.asyncio
    async def test_filters_by_municipio(self) -> None:
        mock_data = [
            IndiceSaude(nome_orgao="PREFEITURA DE PORTO ALEGRE", indice=0.18),
            IndiceSaude(nome_orgao="PREFEITURA DE PELOTAS", indice=0.16),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_indices_saude",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_indices_saude_rs(ctx, 2024, municipio="PELOTAS")
        assert "PELOTAS" in result
        assert "PORTO ALEGRE" not in result


# ---------------------------------------------------------------------------
# buscar_gestao_fiscal_rs
# ---------------------------------------------------------------------------


class TestBuscarGestaoFiscalRs:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            GestaoFiscal(
                nome_orgao="PREFEITURA DE PORTO ALEGRE",
                receita_corrente_liquida=10000000.0,
                despesa_pessoal=4500000.0,
                divida_consolidada=2000000.0,
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_gestao_fiscal",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_gestao_fiscal_rs(ctx, 2024)
        assert "PREFEITURA DE PORTO ALEGRE" in result
        assert "R$ 10.000.000,00" in result
        assert "R$ 4.500.000,00" in result
        assert "R$ 2.000.000,00" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_gestao_fiscal",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_gestao_fiscal_rs(ctx, 2024)
        assert "Nenhum dado de gestão fiscal" in result

    @pytest.mark.asyncio
    async def test_filters_by_municipio(self) -> None:
        mock_data = [
            GestaoFiscal(nome_orgao="PREFEITURA DE PORTO ALEGRE"),
            GestaoFiscal(nome_orgao="PREFEITURA DE CANOAS"),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_gestao_fiscal",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_gestao_fiscal_rs(ctx, 2024, municipio="CANOAS")
        assert "CANOAS" in result
        assert "PORTO ALEGRE" not in result

    @pytest.mark.asyncio
    async def test_truncates_at_20(self) -> None:
        mock_data = [GestaoFiscal(nome_orgao=f"PREFEITURA {i}") for i in range(25)]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_gestao_fiscal",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_gestao_fiscal_rs(ctx, 2024)
        assert "Mostrando 20 de 25" in result


# ---------------------------------------------------------------------------
# buscar_datasets_rs
# ---------------------------------------------------------------------------


class TestBuscarDatasetsRs:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = (
            [
                Dataset(
                    nome="balancete-de-despesa-consolidado-2024",
                    titulo="Balancete de Despesa Consolidado 2024",
                    grupo="Despesa",
                    notas="Dados consolidados.",
                    url="https://dados.tce.rs.gov.br/dataset/balancete-de-despesa-consolidado-2024",
                    num_recursos=9,
                ),
            ],
            1,
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_datasets",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_datasets_rs(ctx, "consolidado 2024")
        assert "Balancete de Despesa Consolidado 2024" in result
        assert "[Despesa]" in result
        assert "9 recursos" in result
        assert "1 datasets encontrados" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_datasets",
            new_callable=AsyncMock,
            return_value=([], 0),
        ):
            result = await tools.buscar_datasets_rs(ctx, "inexistente")
        assert "Nenhum dataset" in result
