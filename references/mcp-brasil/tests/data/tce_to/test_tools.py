"""Tests for the TCE-TO tool functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_brasil.data.tce_to import tools
from mcp_brasil.data.tce_to.schemas import Pauta, Pessoa, Processo, ProcessoResumo

CLIENT_MODULE = "mcp_brasil.data.tce_to.client"


def _mock_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    return ctx


class TestBuscarPessoasTo:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            Pessoa(
                id=100,
                nome="JOAO DA SILVA",
                codigo="***.123.***-00",
                processos=[
                    ProcessoResumo(
                        numero_ano="1234/2024",
                        assunto="PRESTACAO DE CONTAS",
                        entidade_origem_municipio="PALMAS",
                    )
                ],
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_pessoas",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_pessoas_to(ctx, nome="JOAO")
        assert "JOAO DA SILVA" in result
        assert "1234/2024" in result
        assert "PRESTACAO DE CONTAS" in result
        assert "1 processos" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_pessoas",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_pessoas_to(ctx, nome="INEXISTENTE")
        assert "Nenhuma pessoa" in result

    @pytest.mark.asyncio
    async def test_truncates_processos(self) -> None:
        procs = [ProcessoResumo(numero_ano=f"{i}/2024", assunto=f"Assunto {i}") for i in range(8)]
        mock_data = [Pessoa(nome="FULANO", processos=procs)]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_pessoas",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_pessoas_to(ctx, nome="FULANO")
        assert "e mais 3 processos" in result


class TestConsultarProcessoTo:
    @pytest.mark.asyncio
    async def test_formats_result(self) -> None:
        mock_data = Processo(
            numero_ano="1234/2024",
            assunto="PRESTACAO DE CONTAS",
            classe_assunto="CONTAS DE GOVERNO",
            entidade_origem="PREFEITURA DE PALMAS",
            entidade_origem_municipio="PALMAS",
            departamento_atual="1A CAMARA",
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_processo",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_processo_to(ctx, 1234, 2024)
        assert "1234/2024" in result
        assert "PRESTACAO DE CONTAS" in result
        assert "PREFEITURA DE PALMAS" in result

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_processo",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await tools.consultar_processo_to(ctx, 9999, 2024)
        assert "não encontrado" in result


class TestListarPautasTo:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            Pauta(
                data="31/03/2026",
                hora="14:30",
                tipo="ORDINARIA/VIDEOCONFERENCIA",
                origem="PRIMEIRA CAMARA",
                url="https://example.com/pauta/1",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_pautas",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.listar_pautas_to(ctx)
        assert "31/03/2026" in result
        assert "ORDINARIA/VIDEOCONFERENCIA" in result
        assert "PRIMEIRA CAMARA" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_pautas",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.listar_pautas_to(ctx)
        assert "Nenhuma pauta" in result
