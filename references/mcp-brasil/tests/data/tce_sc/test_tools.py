"""Tests for the TCE-SC tool functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_brasil.data.tce_sc import tools
from mcp_brasil.data.tce_sc.schemas import Municipio, UnidadeGestora

CLIENT_MODULE = "mcp_brasil.data.tce_sc.client"


def _mock_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    return ctx


class TestListarMunicipiosSc:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            Municipio(codigo_municipio=420540, nome_municipio="Florianópolis"),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_municipios",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.listar_municipios_sc(ctx)
        assert "Florianópolis" in result
        assert "`420540`" in result
        assert "1 municípios" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_municipios",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.listar_municipios_sc(ctx)
        assert "Nenhum município" in result

    @pytest.mark.asyncio
    async def test_truncates_at_50(self) -> None:
        mock_data = [Municipio(nome_municipio=f"CIDADE {i}") for i in range(60)]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_municipios",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.listar_municipios_sc(ctx)
        assert "Mostrando 50 de 60" in result


class TestListarUnidadesGestorasSc:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            UnidadeGestora(
                codigo_unidade=54010,
                nome_unidade="Prefeitura de Florianópolis",
                sigla_unidade=None,
                nome_municipio="Florianópolis",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_unidades_gestoras",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.listar_unidades_gestoras_sc(ctx)
        assert "Prefeitura de Florianópolis" in result
        assert "`54010`" in result
        assert "1 unidades" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_unidades_gestoras",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.listar_unidades_gestoras_sc(ctx)
        assert "Nenhuma unidade gestora" in result

    @pytest.mark.asyncio
    async def test_filters_by_municipio(self) -> None:
        mock_data = [
            UnidadeGestora(nome_unidade="Prefeitura Fpolis", nome_municipio="Florianópolis"),
            UnidadeGestora(nome_unidade="Prefeitura Joinville", nome_municipio="Joinville"),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_unidades_gestoras",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.listar_unidades_gestoras_sc(ctx, municipio="Joinville")
        assert "Joinville" in result
        assert "Florianópolis" not in result

    @pytest.mark.asyncio
    async def test_shows_sigla(self) -> None:
        mock_data = [
            UnidadeGestora(
                codigo_unidade=345,
                nome_unidade="Agência BADESC",
                sigla_unidade="BADESC",
                nome_municipio="Estado de SC",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_unidades_gestoras",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.listar_unidades_gestoras_sc(ctx)
        assert "(BADESC)" in result

    @pytest.mark.asyncio
    async def test_truncates_at_30(self) -> None:
        mock_data = [
            UnidadeGestora(nome_unidade=f"Unidade {i}", nome_municipio="X") for i in range(35)
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_unidades_gestoras",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.listar_unidades_gestoras_sc(ctx)
        assert "Mostrando 30 de 35" in result
