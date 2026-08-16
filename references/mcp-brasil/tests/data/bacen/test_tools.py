"""Tests for the bacen tool functions.

Tools are tested by mocking client functions and catalog lookups.
Context is mocked via MagicMock with async methods.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_brasil.data.bacen import tools
from mcp_brasil.data.bacen.catalog import SerieBCB
from mcp_brasil.data.bacen.schemas import SerieMetadados, SerieValor

CLIENT_MODULE = "mcp_brasil.data.bacen.client"
CATALOG_MODULE = "mcp_brasil.data.bacen.tools"


def _mock_ctx() -> MagicMock:
    """Create a mock Context with async log methods."""
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    return ctx


SAMPLE_SERIE_INFO = SerieBCB(
    codigo=432, nome="Selic anualizada", categoria="Juros", periodicidade="Diária"
)


# ---------------------------------------------------------------------------
# consultar_serie
# ---------------------------------------------------------------------------


class TestConsultarSerie:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        valores = [
            SerieValor(data="01/01/2024", valor=11.75),
            SerieValor(data="02/01/2024", valor=11.50),
        ]
        ctx = _mock_ctx()
        with (
            patch(f"{CLIENT_MODULE}.buscar_valores", new_callable=AsyncMock, return_value=valores),
            patch(f"{CATALOG_MODULE}.buscar_serie_por_codigo", return_value=SAMPLE_SERIE_INFO),
        ):
            result = await tools.consultar_serie(432, ctx)
        assert "Selic anualizada" in result
        assert "11,7500" in result
        assert "2 registros" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        ctx = _mock_ctx()
        with patch(f"{CLIENT_MODULE}.buscar_valores", new_callable=AsyncMock, return_value=[]):
            result = await tools.consultar_serie(999, ctx)
        assert "Nenhum dado encontrado" in result


# ---------------------------------------------------------------------------
# ultimos_valores
# ---------------------------------------------------------------------------


class TestUltimosValores:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        valores = [SerieValor(data=f"0{i}/01/2024", valor=10.0 + i) for i in range(1, 4)]
        ctx = _mock_ctx()
        with (
            patch(f"{CLIENT_MODULE}.buscar_ultimos", new_callable=AsyncMock, return_value=valores),
            patch(f"{CATALOG_MODULE}.buscar_serie_por_codigo", return_value=SAMPLE_SERIE_INFO),
        ):
            result = await tools.ultimos_valores(432, ctx, quantidade=3)
        assert "Selic anualizada" in result
        assert "últimos 3 valores" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        ctx = _mock_ctx()
        with patch(f"{CLIENT_MODULE}.buscar_ultimos", new_callable=AsyncMock, return_value=[]):
            result = await tools.ultimos_valores(999, ctx)
        assert "Nenhum dado encontrado" in result


# ---------------------------------------------------------------------------
# metadados_serie
# ---------------------------------------------------------------------------


class TestMetadadosSerie:
    @pytest.mark.asyncio
    async def test_from_api(self) -> None:
        meta = SerieMetadados(
            codigo=432,
            nome="Selic anualizada",
            unidade="% a.a.",
            periodicidade="Diária",
            fonte="BCB",
        )
        ctx = _mock_ctx()
        with (
            patch(f"{CLIENT_MODULE}.buscar_metadados", new_callable=AsyncMock, return_value=meta),
            patch(f"{CATALOG_MODULE}.buscar_serie_por_codigo", return_value=SAMPLE_SERIE_INFO),
        ):
            result = await tools.metadados_serie(432, ctx)
        assert "Selic anualizada" in result
        assert "% a.a." in result
        assert "Juros" in result

    @pytest.mark.asyncio
    async def test_fallback_to_catalog(self) -> None:
        from mcp_brasil.exceptions import HttpClientError

        ctx = _mock_ctx()
        with (
            patch(
                f"{CLIENT_MODULE}.buscar_metadados",
                new_callable=AsyncMock,
                side_effect=HttpClientError("fail"),
            ),
            patch(f"{CATALOG_MODULE}.buscar_serie_por_codigo", return_value=SAMPLE_SERIE_INFO),
        ):
            result = await tools.metadados_serie(432, ctx)
        assert "catálogo interno" in result
        assert "Selic anualizada" in result

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        from mcp_brasil.exceptions import HttpClientError

        ctx = _mock_ctx()
        with (
            patch(
                f"{CLIENT_MODULE}.buscar_metadados",
                new_callable=AsyncMock,
                side_effect=HttpClientError("fail"),
            ),
            patch(f"{CATALOG_MODULE}.buscar_serie_por_codigo", return_value=None),
        ):
            result = await tools.metadados_serie(99999, ctx)
        assert "não encontrada" in result


# ---------------------------------------------------------------------------
# series_populares
# ---------------------------------------------------------------------------


class TestSeriesPopulares:
    @pytest.mark.asyncio
    async def test_all_categories(self) -> None:
        ctx = _mock_ctx()
        result = await tools.series_populares(ctx)
        assert "Catálogo BCB" in result
        assert "Juros" in result
        assert "Inflação" in result

    @pytest.mark.asyncio
    async def test_filter_category(self) -> None:
        ctx = _mock_ctx()
        result = await tools.series_populares(ctx, categoria="Câmbio")
        assert "Câmbio" in result
        assert "Dólar" in result

    @pytest.mark.asyncio
    async def test_unknown_category(self) -> None:
        ctx = _mock_ctx()
        result = await tools.series_populares(ctx, categoria="Inexistente")
        assert "Nenhuma série encontrada" in result


# ---------------------------------------------------------------------------
# buscar_serie
# ---------------------------------------------------------------------------


class TestBuscarSerie:
    @pytest.mark.asyncio
    async def test_finds_series(self) -> None:
        ctx = _mock_ctx()
        result = await tools.buscar_serie("selic", ctx)
        assert "séries encontradas" in result
        assert "Selic" in result

    @pytest.mark.asyncio
    async def test_no_results(self) -> None:
        ctx = _mock_ctx()
        result = await tools.buscar_serie("xyzqwerty", ctx)
        assert "Nenhuma série encontrada" in result
        assert "Sugestões" in result


# ---------------------------------------------------------------------------
# indicadores_atuais
# ---------------------------------------------------------------------------


class TestIndicadoresAtuais:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            {"indicador": "Selic (a.a.)", "codigo": 432, "data": "01/03/2024", "valor": 10.5},
            {"indicador": "IPCA mensal (%)", "codigo": 433, "data": "01/03/2024", "valor": 0.83},
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_indicadores_atuais",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.indicadores_atuais(ctx)
        assert "Indicadores Econômicos" in result
        assert "Selic" in result
        assert "10,5000" in result

    @pytest.mark.asyncio
    async def test_with_errors(self) -> None:
        mock_data = [
            {"indicador": "Selic (a.a.)", "codigo": 432, "erro": "timeout"},
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_indicadores_atuais",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.indicadores_atuais(ctx)
        assert "timeout" in result


# ---------------------------------------------------------------------------
# calcular_variacao
# ---------------------------------------------------------------------------


class TestCalcularVariacao:
    @pytest.mark.asyncio
    async def test_calculates_variation(self) -> None:
        valores = [
            SerieValor(data="01/01/2024", valor=10.0),
            SerieValor(data="01/02/2024", valor=12.0),
            SerieValor(data="01/03/2024", valor=15.0),
        ]
        ctx = _mock_ctx()
        with (
            patch(f"{CLIENT_MODULE}.buscar_valores", new_callable=AsyncMock, return_value=valores),
            patch(f"{CATALOG_MODULE}.buscar_serie_por_codigo", return_value=SAMPLE_SERIE_INFO),
        ):
            result = await tools.calcular_variacao(
                432, ctx, data_inicial="2024-01-01", data_final="2024-03-01"
            )
        assert "Variação" in result
        assert "+50,00%" in result
        assert "Máximo" in result

    @pytest.mark.asyncio
    async def test_by_periodos(self) -> None:
        valores = [
            SerieValor(data="01/01/2024", valor=100.0),
            SerieValor(data="02/01/2024", valor=90.0),
        ]
        ctx = _mock_ctx()
        with (
            patch(f"{CLIENT_MODULE}.buscar_ultimos", new_callable=AsyncMock, return_value=valores),
            patch(f"{CATALOG_MODULE}.buscar_serie_por_codigo", return_value=SAMPLE_SERIE_INFO),
        ):
            result = await tools.calcular_variacao(432, ctx, periodos=5)
        assert "-10,00%" in result

    @pytest.mark.asyncio
    async def test_insufficient_data(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_valores",
            new_callable=AsyncMock,
            return_value=[SerieValor(data="01/01/2024", valor=10.0)],
        ):
            result = await tools.calcular_variacao(432, ctx)
        assert "insuficientes" in result


# ---------------------------------------------------------------------------
# comparar_series
# ---------------------------------------------------------------------------


class TestCompararSeries:
    @pytest.mark.asyncio
    async def test_compares_two_series(self) -> None:
        valores_a = [
            SerieValor(data="01/01/2024", valor=10.0),
            SerieValor(data="01/06/2024", valor=12.0),
        ]
        valores_b = [
            SerieValor(data="01/01/2024", valor=5.0),
            SerieValor(data="01/06/2024", valor=4.0),
        ]
        ctx = _mock_ctx()
        with (
            patch(
                f"{CLIENT_MODULE}.buscar_valores",
                new_callable=AsyncMock,
                side_effect=[valores_a, valores_b],
            ),
            patch(f"{CATALOG_MODULE}.buscar_serie_por_codigo", return_value=SAMPLE_SERIE_INFO),
        ):
            result = await tools.comparar_series([432, 433], "01/01/2024", "01/06/2024", ctx)
        assert "Comparação" in result
        assert "Variação" in result

    @pytest.mark.asyncio
    async def test_invalid_count(self) -> None:
        ctx = _mock_ctx()
        result = await tools.comparar_series([432], "01/01/2024", "01/06/2024", ctx)
        assert "entre 2 e 5" in result

    @pytest.mark.asyncio
    async def test_handles_errors(self) -> None:
        ctx = _mock_ctx()
        with (
            patch(
                f"{CLIENT_MODULE}.buscar_valores",
                new_callable=AsyncMock,
                side_effect=Exception("network error"),
            ),
            patch(f"{CATALOG_MODULE}.buscar_serie_por_codigo", return_value=SAMPLE_SERIE_INFO),
        ):
            result = await tools.comparar_series([432, 433], "01/01/2024", "01/06/2024", ctx)
        assert "erro" in result.lower()


# ---------------------------------------------------------------------------
# _calculate_variation
# ---------------------------------------------------------------------------


class TestCalculateVariation:
    def test_positive(self) -> None:
        assert tools._calculate_variation(100, 150) == 50.0

    def test_negative(self) -> None:
        assert tools._calculate_variation(100, 80) == -20.0

    def test_zero_initial(self) -> None:
        assert tools._calculate_variation(0, 50) == 0.0

    def test_no_change(self) -> None:
        assert tools._calculate_variation(100, 100) == 0.0


# ---------------------------------------------------------------------------
# expectativas_focus
# ---------------------------------------------------------------------------


class TestExpectativasFocus:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        from mcp_brasil.data.bacen.schemas import ExpectativaFocus

        expectativas = [
            ExpectativaFocus(
                indicador="IPCA",
                data="2024-03-15",
                data_referencia="2024",
                media=3.76,
                mediana=3.75,
                desvio_padrao=0.18,
                minimo=2.50,
                maximo=5.00,
                base_calculo=80,
            ),
            ExpectativaFocus(
                indicador="IPCA",
                data="2024-03-08",
                data_referencia="2024",
                media=3.80,
                mediana=3.78,
                desvio_padrao=0.20,
                minimo=2.60,
                maximo=5.10,
                base_calculo=75,
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_expectativas_focus",
            new_callable=AsyncMock,
            return_value=expectativas,
        ):
            result = await tools.expectativas_focus(ctx, indicador="IPCA")
        assert "Boletim Focus" in result
        assert "IPCA" in result
        assert "3,75" in result
        assert "3,76" in result
        assert "2024" in result
        assert "80" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_expectativas_focus",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.expectativas_focus(ctx, indicador="IPCA")
        assert "Nenhuma expectativa encontrada" in result

    @pytest.mark.asyncio
    async def test_invalid_indicator(self) -> None:
        ctx = _mock_ctx()
        result = await tools.expectativas_focus(ctx, indicador="INVALIDO")
        assert "não disponível" in result
        assert "IPCA" in result
