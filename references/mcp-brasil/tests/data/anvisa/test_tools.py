"""Tests for the ANVISA tool functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_brasil.data.anvisa import tools
from mcp_brasil.data.anvisa.schemas import (
    BulaMedicamento,
    CategoriaMedicamento,
    MedicamentoBulario,
)

CLIENT_MODULE = "mcp_brasil.data.anvisa.client"


def _mock_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    return ctx


# ---------------------------------------------------------------------------
# buscar_medicamento
# ---------------------------------------------------------------------------


class TestBuscarMedicamento:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            MedicamentoBulario(
                nome_produto="Dipirona Sódica",
                principio_ativo="DIPIRONA SÓDICA",
                razao_social="Lab Exemplo",
                categoria_regulatoria="Genérico",
                numero_processo="25351.123456/2020-00",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_medicamento",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_medicamento(ctx, nome="dipirona")
        assert "Dipirona Sódica" in result
        assert "Genérico" in result
        assert "1 resultado" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_medicamento",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_medicamento(ctx, nome="xyz")
        assert "Nenhum medicamento" in result


# ---------------------------------------------------------------------------
# buscar_por_principio_ativo
# ---------------------------------------------------------------------------


class TestBuscarPorPrincipioAtivo:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            MedicamentoBulario(
                nome_produto="Losartana Genérica",
                principio_ativo="LOSARTANA POTÁSSICA",
                razao_social="Lab Gen",
                categoria_regulatoria="Genérico",
                numero_registro="1.2345.6789",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_por_principio_ativo",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_por_principio_ativo(ctx, principio_ativo="losartana")
        assert "LOSARTANA" in result
        assert "1 resultado" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_por_principio_ativo",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_por_principio_ativo(ctx, principio_ativo="xyz")
        assert "Nenhum medicamento" in result


# ---------------------------------------------------------------------------
# consultar_bula
# ---------------------------------------------------------------------------


class TestConsultarBula:
    @pytest.mark.asyncio
    async def test_formats_bulas(self) -> None:
        mock_data = [
            BulaMedicamento(
                id_bula="999",
                nome_produto="Dipirona",
                empresa="Lab Exemplo",
                tipo_bula="PACIENTE",
                data_publicacao="2024-01-15",
                url_bula="https://example.com/bula/999",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_bula",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_bula(ctx, numero_processo="25351.123/2020-00")
        assert "Dipirona" in result
        assert "PACIENTE" in result
        assert "https://example.com/bula/999" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_bula",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.consultar_bula(ctx, numero_processo="0000")
        assert "Nenhuma bula" in result


# ---------------------------------------------------------------------------
# listar_categorias
# ---------------------------------------------------------------------------


class TestListarCategorias:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            CategoriaMedicamento(codigo="1", descricao="Novo"),
            CategoriaMedicamento(codigo="2", descricao="Genérico"),
        ]
        ctx = _mock_ctx()
        with patch(f"{CLIENT_MODULE}.listar_categorias", return_value=mock_data):
            result = await tools.listar_categorias(ctx)
        assert "Novo" in result
        assert "Genérico" in result
        assert "2 categorias" in result


# ---------------------------------------------------------------------------
# informacoes_bula
# ---------------------------------------------------------------------------


class TestInformacoesBula:
    @pytest.mark.asyncio
    async def test_returns_sections(self) -> None:
        ctx = _mock_ctx()
        result = await tools.informacoes_bula(ctx)
        assert "Indicações" in result
        assert "Contraindicações" in result
        assert "Posologia" in result
        assert "Reações adversas" in result


# ---------------------------------------------------------------------------
# buscar_por_categoria
# ---------------------------------------------------------------------------


class TestBuscarPorCategoria:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            MedicamentoBulario(
                nome_produto="Genérico X",
                principio_ativo="PRINCIPIO X",
                razao_social="Lab Gen",
                categoria_regulatoria="Genérico",
                numero_processo="123/2020",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_por_categoria",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_por_categoria(ctx, categoria="Genérico")
        assert "Genérico" in result
        assert "1 resultado" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_por_categoria",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_por_categoria(ctx, categoria="Inexistente")
        assert "Nenhum medicamento" in result


# ---------------------------------------------------------------------------
# buscar_genericos
# ---------------------------------------------------------------------------


class TestBuscarGenericos:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            MedicamentoBulario(
                nome_produto="Losartana Genérica",
                principio_ativo="LOSARTANA",
                razao_social="Lab Gen",
                numero_registro="1.2345",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_generico",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_genericos(ctx, nome="losartana")
        assert "Genéricos" in result
        assert "Losartana" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_generico",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_genericos(ctx, nome="xyz")
        assert "Nenhum genérico" in result


# ---------------------------------------------------------------------------
# verificar_registro
# ---------------------------------------------------------------------------


class TestVerificarRegistro:
    @pytest.mark.asyncio
    async def test_found(self) -> None:
        mock_data = [
            MedicamentoBulario(
                nome_produto="Dipirona",
                principio_ativo="DIPIRONA",
                razao_social="Lab X",
                categoria_regulatoria="Genérico",
                numero_registro="1.2345",
                data_vencimento_registro="2030-01-01",
                numero_processo="123/2020",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_medicamento",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.verificar_registro(ctx, nome="dipirona")
        assert "Registro ANVISA" in result
        assert "1.2345" in result
        assert "Registro ativo" in result

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_medicamento",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.verificar_registro(ctx, nome="xyz")
        assert "Nenhum registro" in result


# ---------------------------------------------------------------------------
# buscar_por_empresa
# ---------------------------------------------------------------------------


class TestBuscarPorEmpresa:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            MedicamentoBulario(
                nome_produto="Med X",
                principio_ativo="PRINCIPIO",
                razao_social="EMS S/A",
                categoria_regulatoria="Genérico",
                numero_registro="1.2345",
            ),
            MedicamentoBulario(
                nome_produto="Outro Med",
                razao_social="Outro Lab",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_medicamento",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_por_empresa(ctx, empresa="EMS")
        assert "Med X" in result
        assert "1 resultado" in result
        # Should NOT contain the other lab's medicine
        assert "Outro Med" not in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_medicamento",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_por_empresa(ctx, empresa="Inexistente")
        assert "Nenhum medicamento" in result


# ---------------------------------------------------------------------------
# resumo_regulatorio
# ---------------------------------------------------------------------------


class TestResumoRegulatorio:
    @pytest.mark.asyncio
    async def test_formats_summary(self) -> None:
        mock_med = [
            MedicamentoBulario(
                nome_produto="Dipirona",
                principio_ativo="DIPIRONA",
                razao_social="Lab X",
                categoria_regulatoria="Genérico",
                numero_registro="1.2345",
                numero_processo="123/2020",
            ),
        ]
        mock_bula = [
            BulaMedicamento(tipo_bula="PACIENTE"),
        ]
        ctx = _mock_ctx()
        with (
            patch(
                f"{CLIENT_MODULE}.buscar_medicamento",
                new_callable=AsyncMock,
                return_value=mock_med,
            ),
            patch(
                f"{CLIENT_MODULE}.consultar_bula",
                new_callable=AsyncMock,
                return_value=mock_bula,
            ),
        ):
            result = await tools.resumo_regulatorio(ctx, nome="dipirona")
        assert "Resumo Regulatório" in result
        assert "Dipirona" in result
        assert "PACIENTE" in result

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_medicamento",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.resumo_regulatorio(ctx, nome="xyz")
        assert "Nenhum medicamento" in result
