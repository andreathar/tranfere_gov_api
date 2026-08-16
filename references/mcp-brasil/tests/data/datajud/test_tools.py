"""Tests for the DataJud tool functions.

Tools are tested by mocking client functions (never HTTP).
"""

from unittest.mock import AsyncMock, patch

import pytest

from mcp_brasil.data.datajud import tools
from mcp_brasil.data.datajud.schemas import Movimentacao, Processo, ProcessoDetalhe

MODULE = "mcp_brasil.data.datajud.client"


class TestBuscarProcessos:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            Processo(
                numero="0001234-56.2024.8.26.0100",
                classe="Procedimento Comum Cível",
                assunto="Dano Moral",
                tribunal="TJSP",
                orgao_julgador="1ª Vara Cível",
                data_ajuizamento="2024-03-15",
            )
        ]
        with patch(f"{MODULE}.buscar_processos", new_callable=AsyncMock, return_value=mock_data):
            result = await tools.buscar_processos("dano moral", "tjsp")
        assert "0001234" in result
        assert "Dano Moral" in result
        assert "TJSP" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        with patch(f"{MODULE}.buscar_processos", new_callable=AsyncMock, return_value=[]):
            result = await tools.buscar_processos("inexistente")
        assert "Nenhum processo" in result


class TestBuscarProcessoPorNumero:
    @pytest.mark.asyncio
    async def test_formats_details(self) -> None:
        mock_data = ProcessoDetalhe(
            numero="0001234-56.2024.8.26.0100",
            classe="Procedimento Comum Cível",
            tribunal="TJSP",
            orgao_julgador="1ª Vara Cível",
            data_ajuizamento="2024-03-15",
            movimentacoes=[
                Movimentacao(data="2024-03-15", nome="Distribuição"),
                Movimentacao(data="2024-04-01", nome="Citação"),
            ],
        )
        with patch(
            f"{MODULE}.buscar_processo_por_numero",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_processo_por_numero("0001234-56.2024.8.26.0100")
        assert "0001234" in result
        assert "Distribuição" in result
        assert "Citação" in result

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        with patch(
            f"{MODULE}.buscar_processo_por_numero",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await tools.buscar_processo_por_numero("9999999")
        assert "não encontrado" in result


class TestBuscarProcessosPorClasse:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            Processo(
                numero="0001234",
                classe="Mandado de Segurança",
                assunto="Direito Administrativo",
                orgao_julgador="2ª Vara",
                data_ajuizamento="2024-01-10",
            )
        ]
        with patch(
            f"{MODULE}.buscar_processos_por_classe",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_processos_por_classe("Mandado de Segurança")
        assert "Mandado de Segurança" in result
        assert "0001234" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        with patch(
            f"{MODULE}.buscar_processos_por_classe",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_processos_por_classe("Classe Inexistente")
        assert "Nenhum processo" in result


class TestBuscarProcessosPorAssunto:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            Processo(
                numero="0005678",
                classe="Ação Civil Pública",
                assunto="Direito Ambiental",
                orgao_julgador="3ª Vara",
                data_ajuizamento="2024-02-20",
            )
        ]
        with patch(
            f"{MODULE}.buscar_processos_por_assunto",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_processos_por_assunto("Direito Ambiental")
        assert "Direito Ambiental" in result
        assert "0005678" in result


class TestBuscarProcessosPorOrgao:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            Processo(
                numero="0009999",
                classe="Execução Fiscal",
                assunto="Tributário",
                orgao_julgador="1ª Vara de Execuções Fiscais",
                data_ajuizamento="2024-05-01",
            )
        ]
        with patch(
            f"{MODULE}.buscar_processos_por_orgao",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_processos_por_orgao("1ª Vara de Execuções Fiscais")
        assert "Execução Fiscal" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        with patch(
            f"{MODULE}.buscar_processos_por_orgao",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_processos_por_orgao("Vara Inexistente")
        assert "Nenhum processo" in result


class TestBuscarProcessosAvancado:
    @pytest.mark.asyncio
    async def test_formats_table_with_pagination(self) -> None:
        mock_processos = [
            Processo(
                numero="0001234",
                classe="Execução Fiscal",
                assunto="Dívida Ativa",
                orgao_julgador="Vara de Execuções",
                data_ajuizamento="2024-01-01",
            )
        ]
        with patch(
            f"{MODULE}.buscar_processos_avancado",
            new_callable=AsyncMock,
            return_value=(mock_processos, [1681366085550]),
        ):
            result = await tools.buscar_processos_avancado(
                tribunal="tjdft", classe_codigo=1116, orgao_codigo=13597
            )
        assert "Execução Fiscal" in result
        assert "1681366085550" in result
        assert "Próxima página" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        with patch(
            f"{MODULE}.buscar_processos_avancado",
            new_callable=AsyncMock,
            return_value=([], None),
        ):
            result = await tools.buscar_processos_avancado(tribunal="tjdft")
        assert "Nenhum processo" in result

    @pytest.mark.asyncio
    async def test_no_next_page(self) -> None:
        mock_processos = [Processo(numero="0001234", classe="Ação Penal")]
        with patch(
            f"{MODULE}.buscar_processos_avancado",
            new_callable=AsyncMock,
            return_value=(mock_processos, None),
        ):
            result = await tools.buscar_processos_avancado(tribunal="tjsp")
        assert "0001234" in result
        assert "Próxima página" not in result


class TestConsultarMovimentacoes:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            Movimentacao(data="2024-03-15", nome="Distribuição", complemento="Livre"),
            Movimentacao(data="2024-04-01", nome="Citação", complemento="Via correio"),
        ]
        with patch(
            f"{MODULE}.consultar_movimentacoes",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_movimentacoes("0001234")
        assert "Distribuição" in result
        assert "Citação" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        with patch(
            f"{MODULE}.consultar_movimentacoes",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.consultar_movimentacoes("9999999")
        assert "Nenhuma movimentação" in result
