"""Tests for the DENASUS scraping client."""

from unittest.mock import AsyncMock, patch

import pytest

from mcp_brasil.data.denasus import client
from mcp_brasil.data.denasus.constants import ATIVIDADES_URL, PLANOS_URL, RELATORIOS_URL

# Sample HTML that mimics current gov.br structure (h2 headings in #content-core)
SAMPLE_ATIVIDADES_HTML = """
<html>
<body>
<div id="content-core">
    <h2><a href="/detalhe/1">Auditoria no Hospital Regional - BA</a></h2>
    <p>Verificação de procedimentos no hospital regional. publicado 15/03/2024</p>
    <h2><a href="/detalhe/2">Monitoramento SUS - SP</a></h2>
    <p>Monitoramento de indicadores de saúde. publicado 20/01/2024</p>
    <h2><a href="/detalhe/3">Inspeção em Teresina - PI</a></h2>
    <p>Inspeção em unidades de saúde de Teresina. publicado 05/06/2024</p>
</div>
</body>
</html>
"""

SAMPLE_RELATORIOS_HTML = """
<html>
<body>
<div id="content-core">
    <h2><a href="/relatorio-2024.pdf">Relatório de Atividades 2024</a></h2>
    <p>Relatório consolidado publicado 15/10/2024 Arquivo</p>
    <h2><a href="/relatorio-2023.pdf">Relatório de Atividades 2023</a></h2>
    <p>Relatório consolidado publicado 10/10/2023 Arquivo</p>
    <h2><a href="/relatorio-2022.pdf">Relatório de Atividades 2022</a></h2>
    <p>Relatório consolidado publicado 08/10/2022 Arquivo</p>
</div>
</body>
</html>
"""

SAMPLE_PLANOS_HTML = """
<html>
<body>
<div id="content-core">
    <h2><a href="/plano-2025.pdf">Plano de Auditoria 2025</a></h2>
    <p>Departamento Nacional de Auditoria do SUS</p>
    <h2><a href="/plano-2024.pdf">Plano de Auditoria 2024</a></h2>
    <p>Departamento Nacional de Auditoria do SUS</p>
</div>
</body>
</html>
"""

EMPTY_HTML = "<html><body></body></html>"


def _mock_fetch_page(url_html_map: dict[str, str]) -> AsyncMock:
    """Create a mock for _fetch_page that returns parsed HTML."""
    from bs4 import BeautifulSoup

    async def mock_fetch(url: str) -> BeautifulSoup:
        html = url_html_map.get(url, EMPTY_HTML)
        return BeautifulSoup(html, "lxml")

    return AsyncMock(side_effect=mock_fetch)


# ---------------------------------------------------------------------------
# listar_atividades_auditoria
# ---------------------------------------------------------------------------


class TestListarAtividadesAuditoria:
    @pytest.mark.asyncio
    async def test_parses_activities(self) -> None:
        mock = _mock_fetch_page({ATIVIDADES_URL: SAMPLE_ATIVIDADES_HTML})
        with patch.object(client, "_fetch_page", mock):
            result = await client.listar_atividades_auditoria()
            assert len(result) == 3
            assert result[0].titulo == "Auditoria no Hospital Regional - BA"
            assert result[0].uf == "BA"
            assert result[0].tipo == "Auditoria"
            assert result[0].url_detalhe == "/detalhe/1"

    @pytest.mark.asyncio
    async def test_extracts_uf(self) -> None:
        mock = _mock_fetch_page({ATIVIDADES_URL: SAMPLE_ATIVIDADES_HTML})
        with patch.object(client, "_fetch_page", mock):
            result = await client.listar_atividades_auditoria()
            ufs = [a.uf for a in result]
            assert "BA" in ufs
            assert "SP" in ufs
            assert "PI" in ufs

    @pytest.mark.asyncio
    async def test_classifies_types(self) -> None:
        mock = _mock_fetch_page({ATIVIDADES_URL: SAMPLE_ATIVIDADES_HTML})
        with patch.object(client, "_fetch_page", mock):
            result = await client.listar_atividades_auditoria()
            tipos = [a.tipo for a in result]
            assert "Auditoria" in tipos
            assert "Monitoramento" in tipos
            assert "Inspeção" in tipos

    @pytest.mark.asyncio
    async def test_empty_page(self) -> None:
        mock = _mock_fetch_page({ATIVIDADES_URL: EMPTY_HTML})
        with patch.object(client, "_fetch_page", mock):
            result = await client.listar_atividades_auditoria()
            assert result == []


# ---------------------------------------------------------------------------
# listar_relatorios_anuais
# ---------------------------------------------------------------------------


class TestListarRelatoriosAnuais:
    @pytest.mark.asyncio
    async def test_parses_reports(self) -> None:
        mock = _mock_fetch_page({RELATORIOS_URL: SAMPLE_RELATORIOS_HTML})
        with patch.object(client, "_fetch_page", mock):
            result = await client.listar_relatorios_anuais()
            assert len(result) == 3
            assert result[0].ano == 2024
            assert result[0].titulo == "Relatório de Atividades 2024"
            assert result[0].url_pdf == "/relatorio-2024.pdf"

    @pytest.mark.asyncio
    async def test_empty_page(self) -> None:
        mock = _mock_fetch_page({RELATORIOS_URL: EMPTY_HTML})
        with patch.object(client, "_fetch_page", mock):
            result = await client.listar_relatorios_anuais()
            assert result == []


# ---------------------------------------------------------------------------
# listar_planos_auditoria
# ---------------------------------------------------------------------------


class TestListarPlanosAuditoria:
    @pytest.mark.asyncio
    async def test_parses_plans(self) -> None:
        mock = _mock_fetch_page({PLANOS_URL: SAMPLE_PLANOS_HTML})
        with patch.object(client, "_fetch_page", mock):
            result = await client.listar_planos_auditoria()
            assert len(result) == 2
            assert result[0].ano == 2025
            assert result[0].url_pdf == "/plano-2025.pdf"

    @pytest.mark.asyncio
    async def test_empty_page(self) -> None:
        mock = _mock_fetch_page({PLANOS_URL: EMPTY_HTML})
        with patch.object(client, "_fetch_page", mock):
            result = await client.listar_planos_auditoria()
            assert result == []


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_extrair_uf_found(self) -> None:
        assert client._extrair_uf("Auditoria Hospital - BA") == "BA"

    def test_extrair_uf_not_found(self) -> None:
        assert client._extrair_uf("Auditoria sem estado") is None

    def test_extrair_uf_ignores_non_uf(self) -> None:
        assert client._extrair_uf("Relatório DO sistema") is None

    def test_classificar_tipo_auditoria(self) -> None:
        assert client._classificar_tipo("Auditoria no hospital") == "Auditoria"

    def test_classificar_tipo_monitoramento(self) -> None:
        assert client._classificar_tipo("Monitoramento do SUS") == "Monitoramento"

    def test_classificar_tipo_inspecao(self) -> None:
        assert client._classificar_tipo("Inspeção em unidade") == "Inspeção"

    def test_classificar_tipo_verificacao(self) -> None:
        assert client._classificar_tipo("Verificação de procedimentos") == "Verificação"

    def test_classificar_tipo_outro(self) -> None:
        assert client._classificar_tipo("Atividade qualquer") == "Outro"

    def test_extrair_ano_found(self) -> None:
        assert client._extrair_ano("Relatório 2024") == 2024

    def test_extrair_ano_not_found(self) -> None:
        assert client._extrair_ano("Sem ano aqui") is None
