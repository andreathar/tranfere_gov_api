"""Tests for the TCE-CE tool functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_brasil.data.tce_ce import tools
from mcp_brasil.data.tce_ce.schemas import (
    Contrato,
    ContratoResultado,
    Empenho,
    EmpenhoResultado,
    Licitacao,
    Municipio,
)

CLIENT_MODULE = "mcp_brasil.data.tce_ce.client"


def _mock_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    return ctx


# ---------------------------------------------------------------------------
# listar_municipios_ce
# ---------------------------------------------------------------------------


class TestListarMunicipiosCe:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            Municipio(codigo_municipio="057", nome_municipio="FORTALEZA"),
            Municipio(codigo_municipio="150", nome_municipio="SOBRAL"),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_municipios",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.listar_municipios_ce(ctx)
        assert "FORTALEZA" in result
        assert "`057`" in result
        assert "SOBRAL" in result
        assert "2 municípios" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_municipios",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.listar_municipios_ce(ctx)
        assert "Nenhum município encontrado" in result


# ---------------------------------------------------------------------------
# buscar_licitacoes_ce
# ---------------------------------------------------------------------------


class TestBuscarLicitacoesCe:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            Licitacao(
                codigo_municipio="057",
                numero_licitacao="2024/001",
                data_realizacao="2024-03-15",
                modalidade_licitacao="Pregão Eletrônico",
                objeto="Aquisição de material escolar",
                valor_orcado_estimado=150000.0,
                data_homologacao="2024-04-01",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_licitacoes",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_licitacoes_ce(ctx, "057", "2024-01-01_2024-12-31")
        assert "2024/001" in result
        assert "Pregão Eletrônico" in result
        assert "material escolar" in result
        assert "R$ 150.000,00" in result
        assert "2024-04-01" in result
        assert "1 licitações" in result or "1 licitaç" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_licitacoes",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_licitacoes_ce(ctx, "057", "2024-01-01")
        assert "Nenhuma licitação encontrada" in result

    @pytest.mark.asyncio
    async def test_truncates_long_list(self) -> None:
        mock_data = [
            Licitacao(
                codigo_municipio="057",
                numero_licitacao=f"2024/{i:03d}",
                objeto=f"Objeto {i}",
            )
            for i in range(25)
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_licitacoes",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_licitacoes_ce(ctx, "057", "2024-01-01")
        assert "Mostrando 20 de 25" in result


# ---------------------------------------------------------------------------
# buscar_contratos_ce
# ---------------------------------------------------------------------------


class TestBuscarContratosCe:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = ContratoResultado(
            contratos=[
                Contrato(
                    codigo_municipio="057",
                    numero_contrato="CT-2024/001",
                    data_contrato="2024-02-15",
                    tipo_contrato="Compras",
                    objeto="Fornecimento de merenda escolar",
                    valor_total_contrato=500000.0,
                    data_fim_vigencia="2024-12-31",
                ),
            ],
            total=1,
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_contratos",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_contratos_ce(ctx, "057", "2024-01-01_2024-12-31")
        assert "CT-2024/001" in result
        assert "Compras" in result
        assert "merenda" in result
        assert "R$ 500.000,00" in result
        assert "2024-12-31" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        mock_data = ContratoResultado(contratos=[], total=0)
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_contratos",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_contratos_ce(ctx, "057", "2024-01-01")
        assert "Nenhum contrato encontrado" in result

    @pytest.mark.asyncio
    async def test_pagination_hint(self) -> None:
        mock_data = ContratoResultado(
            contratos=[
                Contrato(codigo_municipio="057", numero_contrato=f"CT-{i}") for i in range(20)
            ]
            + [Contrato(codigo_municipio="057", numero_contrato="CT-EXTRA")],
            total=50,
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_contratos",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_contratos_ce(ctx, "057", "2024-01-01")
        assert "Mostrando 20 de 50" in result
        assert "deslocamento=" in result


# ---------------------------------------------------------------------------
# buscar_empenhos_ce
# ---------------------------------------------------------------------------


class TestBuscarEmpenhosCe:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = EmpenhoResultado(
            empenhos=[
                Empenho(
                    codigo_municipio=57,
                    numero_empenho="2024NE000123",
                    data_emissao="2024-01-15",
                    valor_empenho=25000.0,
                    nome_negociante="EMPRESA ABC LTDA",
                    historico="Pagamento referente ao contrato CT-001",
                ),
            ],
            total=1,
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_empenhos",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_empenhos_ce(ctx, 57, 202401)
        assert "2024NE000123" in result
        assert "EMPRESA ABC LTDA" in result
        assert "R$ 25.000,00" in result
        assert "contrato CT-001" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        mock_data = EmpenhoResultado(empenhos=[], total=0)
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_empenhos",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_empenhos_ce(ctx, 57, 202401)
        assert "Nenhum empenho encontrado" in result

    @pytest.mark.asyncio
    async def test_pagination_hint(self) -> None:
        mock_data = EmpenhoResultado(
            empenhos=[Empenho(codigo_municipio=57, numero_empenho=f"NE-{i}") for i in range(20)]
            + [Empenho(codigo_municipio=57, numero_empenho="NE-EXTRA")],
            total=80,
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_empenhos",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_empenhos_ce(ctx, 57, 202401)
        assert "Mostrando 20 de 80" in result
        assert "deslocamento=" in result
