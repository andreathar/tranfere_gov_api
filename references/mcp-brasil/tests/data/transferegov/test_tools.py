"""Tests for the transferegov tool functions.

Tools are tested by mocking client functions (never HTTP).
"""

from unittest.mock import AsyncMock, patch

import pytest

from mcp_brasil.data.transferegov import tools
from mcp_brasil.data.transferegov.constants import DEFAULT_PAGE_SIZE
from mcp_brasil.data.transferegov.schemas import TransferenciaEspecial

MODULE = "mcp_brasil.data.transferegov.client"


def _make_emenda(**kwargs: object) -> TransferenciaEspecial:
    defaults: dict[str, object] = {
        "id_plano_acao": 3221,
        "codigo_plano_acao": "0903-003221",
        "ano": 2024,
        "situacao": "CIENTE",
        "nome_parlamentar": "Dep. Fulano",
        "numero_emenda": "202427070006",
        "ano_emenda": "2024",
        "valor_custeio": 30000.0,
        "valor_investimento": 80000.0,
        "nome_beneficiario": "MUNICIPIO DE TERESINA",
        "uf_beneficiario": "PI",
    }
    defaults.update(kwargs)
    return TransferenciaEspecial(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# buscar_emendas_pix
# ---------------------------------------------------------------------------


class TestBuscarEmendasPix:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [_make_emenda()]
        with patch(f"{MODULE}.buscar_emendas_pix", new_callable=AsyncMock, return_value=mock_data):
            result = await tools.buscar_emendas_pix(ano=2024)
        assert "202427070006" in result
        assert "Dep. Fulano" in result
        assert "R$ 110.000,00" in result  # custeio 30k + investimento 80k

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        with patch(f"{MODULE}.buscar_emendas_pix", new_callable=AsyncMock, return_value=[]):
            result = await tools.buscar_emendas_pix()
        assert "Nenhuma emenda pix" in result


# ---------------------------------------------------------------------------
# buscar_emenda_por_autor
# ---------------------------------------------------------------------------


class TestBuscarEmendaPorAutor:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [_make_emenda()]
        with patch(
            f"{MODULE}.buscar_emenda_por_autor", new_callable=AsyncMock, return_value=mock_data
        ):
            result = await tools.buscar_emenda_por_autor("Fulano")
        assert "Dep. Fulano" in result
        assert "TERESINA" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        with patch(f"{MODULE}.buscar_emenda_por_autor", new_callable=AsyncMock, return_value=[]):
            result = await tools.buscar_emenda_por_autor("Inexistente")
        assert "Nenhuma emenda pix" in result


# ---------------------------------------------------------------------------
# detalhe_emenda
# ---------------------------------------------------------------------------


class TestDetalheEmenda:
    @pytest.mark.asyncio
    async def test_formats_detail(self) -> None:
        mock_data = _make_emenda(
            area_politica_publica="10-Saude / 302-Atencao Basica",
            cnpj_beneficiario="04218211000156",
        )
        with patch(f"{MODULE}.detalhe_emenda", new_callable=AsyncMock, return_value=mock_data):
            result = await tools.detalhe_emenda(3221)
        assert "202427070006" in result
        assert "R$ 30.000,00" in result  # custeio
        assert "R$ 80.000,00" in result  # investimento
        assert "Saude" in result

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        with patch(f"{MODULE}.detalhe_emenda", new_callable=AsyncMock, return_value=None):
            result = await tools.detalhe_emenda(999)
        assert "não encontrada" in result


# ---------------------------------------------------------------------------
# emendas_por_municipio
# ---------------------------------------------------------------------------


class TestEmendasPorMunicipio:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [_make_emenda()]
        with patch(
            f"{MODULE}.emendas_por_municipio", new_callable=AsyncMock, return_value=mock_data
        ):
            result = await tools.emendas_por_municipio("Teresina")
        assert "TERESINA" in result
        assert "R$ 110.000,00" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        with patch(f"{MODULE}.emendas_por_municipio", new_callable=AsyncMock, return_value=[]):
            result = await tools.emendas_por_municipio("Inexistente")
        assert "Nenhuma emenda pix" in result


# ---------------------------------------------------------------------------
# resumo_emendas_ano
# ---------------------------------------------------------------------------


class TestResumoEmendasAno:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [_make_emenda()]
        with patch(f"{MODULE}.resumo_emendas_ano", new_callable=AsyncMock, return_value=mock_data):
            result = await tools.resumo_emendas_ano(2024)
        assert "2024" in result
        assert "202427070006" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        with patch(f"{MODULE}.resumo_emendas_ano", new_callable=AsyncMock, return_value=[]):
            result = await tools.resumo_emendas_ano(2025)
        assert "Nenhuma emenda pix" in result


# ---------------------------------------------------------------------------
# Pagination hints
# ---------------------------------------------------------------------------


class TestPaginationHints:
    @pytest.mark.asyncio
    async def test_shows_next_page_hint(self) -> None:
        data = [_make_emenda(numero_emenda=f"EMD-{i}") for i in range(DEFAULT_PAGE_SIZE)]
        with patch(f"{MODULE}.buscar_emendas_pix", new_callable=AsyncMock, return_value=data):
            result = await tools.buscar_emendas_pix(ano=2024)
        assert "pagina=2" in result

    @pytest.mark.asyncio
    async def test_no_hint_below_page_size(self) -> None:
        data = [_make_emenda()]
        with patch(f"{MODULE}.buscar_emendas_pix", new_callable=AsyncMock, return_value=data):
            result = await tools.buscar_emendas_pix(ano=2024, pagina=1)
        assert "pagina=" not in result

    @pytest.mark.asyncio
    async def test_last_page_hint(self) -> None:
        data = [_make_emenda()]
        with patch(f"{MODULE}.buscar_emendas_pix", new_callable=AsyncMock, return_value=data):
            result = await tools.buscar_emendas_pix(ano=2024, pagina=2)
        assert "Última página" in result
