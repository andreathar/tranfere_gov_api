"""Tests for the INPE tool functions.

Tools are tested by mocking client functions (never HTTP).
Context is mocked via MagicMock with async methods.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_brasil.data.inpe import tools
from mcp_brasil.data.inpe.schemas import (
    AlertaDeter,
    DadosProdes,
    FocoQueimada,
    Satelite,
)

CLIENT_MODULE = "mcp_brasil.data.inpe.client"


def _mock_ctx() -> MagicMock:
    """Create a mock Context with async log methods."""
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    return ctx


# ---------------------------------------------------------------------------
# buscar_focos_queimadas
# ---------------------------------------------------------------------------


class TestBuscarFocosQueimadas:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            FocoQueimada(
                id="123456",
                latitude=-10.5,
                longitude=-50.3,
                data_hora="2024-03-15T14:30:00",
                satelite="AQUA_M-T",
                municipio="São Félix do Xingu",
                estado="PA",
                bioma="Amazônia",
                dias_sem_chuva=15,
                risco_fogo=0.85,
                frp=42.5,
            ),
            FocoQueimada(
                id="123457",
                latitude=-12.1,
                longitude=-48.7,
                data_hora="2024-03-15T15:00:00",
                satelite="NPP-375",
                municipio="Altamira",
                estado="PA",
                bioma="Amazônia",
                risco_fogo=0.72,
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_focos", new_callable=AsyncMock, return_value=mock_data
        ):
            result = await tools.buscar_focos_queimadas(ctx, estado="PA")
        assert "São Félix do Xingu" in result
        assert "PA" in result
        assert "Amazônia" in result
        assert "AQUA_M-T" in result
        assert "2 resultados" in result
        assert "0,85" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(f"{CLIENT_MODULE}.buscar_focos", new_callable=AsyncMock, return_value=[]):
            result = await tools.buscar_focos_queimadas(ctx)
        assert "Nenhum foco" in result

    @pytest.mark.asyncio
    async def test_with_all_filters(self) -> None:
        mock_data = [
            FocoQueimada(
                id="1",
                latitude=-10.0,
                longitude=-50.0,
                data_hora="2024-03-15T14:00:00",
                satelite="AQUA_M-T",
                municipio="Teste",
                estado="MT",
                bioma="Cerrado",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_focos", new_callable=AsyncMock, return_value=mock_data
        ):
            result = await tools.buscar_focos_queimadas(
                ctx,
                estado="MT",
                data_inicio="2024-03-01",
                data_fim="2024-03-15",
                satelite="AQUA_M-T",
            )
        assert "estado=MT" in result
        assert "de 2024-03-01" in result
        assert "até 2024-03-15" in result

    @pytest.mark.asyncio
    async def test_risco_fogo_none(self) -> None:
        mock_data = [
            FocoQueimada(
                id="1",
                latitude=-10.0,
                longitude=-50.0,
                data_hora="2024-03-15T14:00:00",
                satelite="AQUA_M-T",
                municipio="Teste",
                estado="PA",
                bioma="Amazônia",
                risco_fogo=None,
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_focos", new_callable=AsyncMock, return_value=mock_data
        ):
            result = await tools.buscar_focos_queimadas(ctx)
        assert "—" in result


# ---------------------------------------------------------------------------
# consultar_desmatamento
# ---------------------------------------------------------------------------


class TestConsultarDesmatamento:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            DadosProdes(
                ano=2023,
                bioma="Amazônia",
                area_km2=9001.0,
                estado="PA",
                municipio="São Félix do Xingu",
            ),
            DadosProdes(
                ano=2023,
                bioma="Amazônia",
                area_km2=3500.5,
                estado="MT",
                municipio="Colniza",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_dados_prodes",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_desmatamento(ctx, bioma="amazonia", ano=2023)
        assert "São Félix do Xingu" in result
        assert "PA" in result
        assert "2023" in result
        assert "9.001,00" in result
        assert "2 registros" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_dados_prodes", new_callable=AsyncMock, return_value=[]
        ):
            result = await tools.consultar_desmatamento(ctx)
        assert "Nenhum dado de desmatamento" in result

    @pytest.mark.asyncio
    async def test_bioma_translation(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_dados_prodes",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_client:
            await tools.consultar_desmatamento(ctx, bioma="amazonia")
        mock_client.assert_called_once_with(bioma="Amazônia", estado=None, ano=None)


# ---------------------------------------------------------------------------
# alertas_deter
# ---------------------------------------------------------------------------


class TestAlertasDeter:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            AlertaDeter(
                id="789",
                data="2024-03-15",
                area_km2=1.5,
                municipio="Altamira",
                estado="PA",
                bioma="Amazônia",
                classe="DESMATAMENTO_CR",
                satelite="CBERS-4A",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_alertas_deter",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.alertas_deter(ctx, bioma="amazonia")
        assert "Altamira" in result
        assert "DESMATAMENTO_CR" in result
        assert "CBERS-4A" in result
        assert "1,50" in result
        assert "1 alertas" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_alertas_deter", new_callable=AsyncMock, return_value=[]
        ):
            result = await tools.alertas_deter(ctx)
        assert "Nenhum alerta DETER" in result

    @pytest.mark.asyncio
    async def test_with_date_filters(self) -> None:
        mock_data = [
            AlertaDeter(
                id="1",
                data="2024-03-15",
                area_km2=2.0,
                municipio="Teste",
                estado="PA",
                bioma="Amazônia",
                classe="DEGRADACAO",
                satelite="CBERS-4A",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_alertas_deter",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.alertas_deter(
                ctx, data_inicio="2024-03-01", data_fim="2024-03-15"
            )
        assert "de 2024-03-01" in result
        assert "até 2024-03-15" in result


# ---------------------------------------------------------------------------
# dados_satelite
# ---------------------------------------------------------------------------


class TestDadosSatelite:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            Satelite(nome="AQUA_M-T", descricao="EOS/NASA"),
            Satelite(nome="TERRA_M-T", descricao="EOS/NASA"),
            Satelite(nome="NPP-375", descricao="Suomi NPP/NASA"),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_satelites", new_callable=AsyncMock, return_value=mock_data
        ):
            result = await tools.dados_satelite(ctx)
        assert "AQUA_M-T" in result
        assert "TERRA_M-T" in result
        assert "NPP-375" in result
        assert "3 disponíveis" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(f"{CLIENT_MODULE}.listar_satelites", new_callable=AsyncMock, return_value=[]):
            result = await tools.dados_satelite(ctx)
        assert "Nenhum satélite" in result
