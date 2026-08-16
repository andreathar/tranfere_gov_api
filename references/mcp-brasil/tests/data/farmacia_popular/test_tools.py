"""Tests for the Farmácia Popular tool functions.

Tools are tested by mocking client functions (never HTTP).
Context is mocked via MagicMock with async methods.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_brasil.data.farmacia_popular import tools
from mcp_brasil.data.farmacia_popular.schemas import (
    EstatisticasPrograma,
    FarmaciaEstabelecimento,
    Medicamento,
)

CLIENT_MODULE = "mcp_brasil.data.farmacia_popular.client"


def _mock_ctx() -> MagicMock:
    """Create a mock Context with async log methods."""
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    return ctx


# ---------------------------------------------------------------------------
# buscar_farmacias
# ---------------------------------------------------------------------------


class TestBuscarFarmacias:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            FarmaciaEstabelecimento(
                codigo_cnes="3456789",
                nome_fantasia="Farmácia Central",
                endereco="Rua das Flores, 100",
                tipo_gestao="Privado",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_farmacias",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_farmacias(ctx, codigo_municipio="355030")
        assert "Farmácia Central" in result
        assert "3456789" in result
        assert "1 resultados" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_farmacias",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_farmacias(ctx)
        assert "Nenhuma farmácia" in result


# ---------------------------------------------------------------------------
# listar_medicamentos
# ---------------------------------------------------------------------------


class TestListarMedicamentos:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            Medicamento(
                nome="Losartana",
                principio_ativo="Losartana Potássica",
                apresentacao="Comprimido 50mg",
                indicacao="Hipertensão",
                gratuito=True,
            ),
        ]
        ctx = _mock_ctx()
        with patch(f"{CLIENT_MODULE}.listar_medicamentos", return_value=mock_data):
            result = await tools.listar_medicamentos(ctx)
        assert "Losartana" in result
        assert "1 itens" in result


# ---------------------------------------------------------------------------
# verificar_medicamento
# ---------------------------------------------------------------------------


class TestVerificarMedicamento:
    @pytest.mark.asyncio
    async def test_found(self) -> None:
        mock_data = [
            Medicamento(
                nome="Losartana",
                principio_ativo="Losartana Potássica",
                apresentacao="Comprimido 50mg",
                indicacao="Hipertensão",
                gratuito=True,
            ),
        ]
        ctx = _mock_ctx()
        with patch(f"{CLIENT_MODULE}.buscar_medicamento_por_nome", return_value=mock_data):
            result = await tools.verificar_medicamento(ctx, nome="losartana")
        assert "encontrado" in result
        assert "Losartana" in result

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        ctx = _mock_ctx()
        with patch(f"{CLIENT_MODULE}.buscar_medicamento_por_nome", return_value=[]):
            result = await tools.verificar_medicamento(ctx, nome="xyz")
        assert "não foi encontrado" in result


# ---------------------------------------------------------------------------
# buscar_por_indicacao
# ---------------------------------------------------------------------------


class TestBuscarPorIndicacao:
    @pytest.mark.asyncio
    async def test_found(self) -> None:
        mock_data = [
            Medicamento(
                nome="Metformina 500mg",
                principio_ativo="Cloridrato de Metformina",
                apresentacao="Comprimido 500mg",
                indicacao="Diabetes",
                gratuito=True,
            ),
        ]
        ctx = _mock_ctx()
        with patch(f"{CLIENT_MODULE}.buscar_por_indicacao", return_value=mock_data):
            result = await tools.buscar_por_indicacao(ctx, indicacao="diabetes")
        assert "Diabetes" in result
        assert "Metformina" in result

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        ctx = _mock_ctx()
        with patch(f"{CLIENT_MODULE}.buscar_por_indicacao", return_value=[]):
            result = await tools.buscar_por_indicacao(ctx, indicacao="inexistente")
        assert "Nenhum medicamento" in result


# ---------------------------------------------------------------------------
# estatisticas_programa
# ---------------------------------------------------------------------------


class TestEstatisticasPrograma:
    @pytest.mark.asyncio
    async def test_formats_stats(self) -> None:
        mock_stats = EstatisticasPrograma(
            total_medicamentos=33,
            total_indicacoes=9,
            todos_gratuitos=True,
            indicacoes=["Hipertensão", "Diabetes"],
            medicamentos_por_indicacao={"Hipertensão": 7, "Diabetes": 6},
        )
        ctx = _mock_ctx()
        with patch(f"{CLIENT_MODULE}.obter_estatisticas", return_value=mock_stats):
            result = await tools.estatisticas_programa(ctx)
        assert "Estatísticas" in result
        assert "Hipertensão" in result
        assert "Diabetes" in result


# ---------------------------------------------------------------------------
# verificar_elegibilidade
# ---------------------------------------------------------------------------


class TestVerificarElegibilidade:
    @pytest.mark.asyncio
    async def test_returns_info(self) -> None:
        ctx = _mock_ctx()
        result = await tools.verificar_elegibilidade(ctx)
        assert "Requisitos" in result
        assert "CPF" in result
        assert "receita" in result.lower()
        assert "120 dias" in result


# ---------------------------------------------------------------------------
# municipios_atendidos
# ---------------------------------------------------------------------------


class TestMunicipiosAtendidos:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            FarmaciaEstabelecimento(
                codigo_cnes="111",
                nome_fantasia="Farm A",
                codigo_municipio="355030",
            ),
            FarmaciaEstabelecimento(
                codigo_cnes="222",
                nome_fantasia="Farm B",
                codigo_municipio="355030",
            ),
            FarmaciaEstabelecimento(
                codigo_cnes="333",
                nome_fantasia="Farm C",
                codigo_municipio="355060",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_farmacias",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.municipios_atendidos(ctx, codigo_uf="35")
        assert "2 município(s)" in result
        assert "3 farmácia(s)" in result
        assert "355030" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_farmacias",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.municipios_atendidos(ctx, codigo_uf="99")
        assert "Nenhuma farmácia" in result


# ---------------------------------------------------------------------------
# farmacia_mais_proxima
# ---------------------------------------------------------------------------


class TestFarmaciaMaisProxima:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            FarmaciaEstabelecimento(
                codigo_cnes="444",
                nome_fantasia="Farmácia Saúde",
                endereco="Av. Brasil, 500",
                tipo_gestao="Privado",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_farmacias",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.farmacia_mais_proxima(ctx, codigo_municipio="355030")
        assert "Farmácia Saúde" in result
        assert "444" in result
        assert "1 resultado(s)" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_farmacias",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.farmacia_mais_proxima(ctx, codigo_municipio="000000")
        assert "Nenhuma farmácia" in result
