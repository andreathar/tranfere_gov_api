"""Tests for the INEP tool functions.

Tools are tested by mocking client functions (never HTTP).
Context is mocked via MagicMock with async methods.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_brasil.data.inep import tools
from mcp_brasil.data.inep.schemas import IdebUrl, IndicadorEducacional, MicrodadosDataset

CLIENT_MODULE = "mcp_brasil.data.inep.client"


def _mock_ctx() -> MagicMock:
    """Create a mock Context with async log methods."""
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    return ctx


# ---------------------------------------------------------------------------
# consultar_ideb
# ---------------------------------------------------------------------------


class TestConsultarIdeb:
    @pytest.mark.asyncio
    async def test_formats_table_with_urls(self) -> None:
        mock_data = [
            IdebUrl(
                nivel="regioes_ufs",
                etapa=None,
                ano=2023,
                url="https://download.inep.gov.br/ideb/resultados/divulgacao_regioes_ufs_ideb_2023.xlsx",
                tamanho_estimado="~200 KB",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.gerar_urls_ideb",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_ideb(ctx, ano=2023)
        assert "2023" in result
        assert "download.inep.gov.br" in result

    @pytest.mark.asyncio
    async def test_empty_result_shows_valid_options(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.gerar_urls_ideb",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.consultar_ideb(ctx, ano=9999)
        assert "Nenhum" in result
        assert "Níveis válidos" in result

    @pytest.mark.asyncio
    async def test_default_ano_is_latest(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.gerar_urls_ideb",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_fn:
            await tools.consultar_ideb(ctx)
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args[1]
        assert call_kwargs["ano"] == 2023


# ---------------------------------------------------------------------------
# listar_microdados_inep
# ---------------------------------------------------------------------------


class TestListarMicrodadosInep:
    @pytest.mark.asyncio
    async def test_lists_all_datasets(self) -> None:
        mock_data = [
            MicrodadosDataset(
                codigo="censo_escolar",
                nome="Censo Escolar da Educação Básica",
                descricao="Dados de escolas e matrículas",
                frequencia="Anual",
                anos_disponiveis=[2022, 2023],
                url_template="https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_{ano}.zip",
            ),
            MicrodadosDataset(
                codigo="enem",
                nome="Exame Nacional do Ensino Médio",
                descricao="Notas e questionário",
                frequencia="Anual",
                anos_disponiveis=[2022, 2023],
                url_template="https://download.inep.gov.br/microdados/microdados_enem_{ano}.zip",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_microdados",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.listar_microdados_inep(ctx)
        assert "Censo Escolar" in result
        assert "ENEM" in result or "enem" in result
        assert "2 datasets" in result


# ---------------------------------------------------------------------------
# gerar_url_download_inep
# ---------------------------------------------------------------------------


class TestGerarUrlDownloadInep:
    @pytest.mark.asyncio
    async def test_generates_url(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.gerar_url_microdados",
            new_callable=AsyncMock,
            return_value="https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_2023.zip",
        ):
            result = await tools.gerar_url_download_inep(ctx, dataset="censo_escolar", ano=2023)
        assert "download.inep.gov.br" in result
        assert "2023" in result

    @pytest.mark.asyncio
    async def test_invalid_dataset(self) -> None:
        mock_datasets = [
            MicrodadosDataset(
                codigo="censo_escolar",
                nome="Censo Escolar",
                descricao="...",
                frequencia="Anual",
                anos_disponiveis=[2023],
                url_template="...",
            ),
        ]
        ctx = _mock_ctx()
        with (
            patch(
                f"{CLIENT_MODULE}.gerar_url_microdados",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                f"{CLIENT_MODULE}.listar_microdados",
                new_callable=AsyncMock,
                return_value=mock_datasets,
            ),
        ):
            result = await tools.gerar_url_download_inep(ctx, dataset="invalido", ano=2023)
        assert "não encontrado" in result


# ---------------------------------------------------------------------------
# listar_indicadores_educacionais
# ---------------------------------------------------------------------------


class TestListarIndicadoresEducacionais:
    @pytest.mark.asyncio
    async def test_lists_indicators(self) -> None:
        mock_data = [
            IndicadorEducacional(
                codigo="taxa_distorcao_idade_serie",
                nome="Taxa de Distorção Idade-Série",
                descricao="Percentual de alunos com idade acima da esperada",
            ),
            IndicadorEducacional(
                codigo="taxa_rendimento",
                nome="Taxas de Rendimento Escolar",
                descricao="Taxas de aprovação, reprovação e abandono",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_indicadores",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.listar_indicadores_educacionais(ctx)
        assert "Distorção" in result
        assert "Rendimento" in result
        assert "2 indicadores" in result
