"""Tests for the FNDE tool functions.

Tools are tested by mocking client functions (never HTTP).
Context is mocked via MagicMock with async methods.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_brasil.data.fnde import tools
from mcp_brasil.data.fnde.schemas import (
    FundebMatricula,
    PnaeAluno,
    PnateTransporte,
    PnldLivro,
)

CLIENT_MODULE = "mcp_brasil.data.fnde.client"


def _mock_ctx() -> MagicMock:
    """Create a mock Context with async log methods."""
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    return ctx


# ---------------------------------------------------------------------------
# consultar_fundeb_matriculas
# ---------------------------------------------------------------------------


class TestConsultarFundebMatriculas:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            FundebMatricula.model_validate(
                {
                    "AnoCenso": 2018,
                    "Uf": "SP",
                    "MunicipioGe": "SAO PAULO",
                    "TipoRedeEducacao": "EDUCAÇÃO PÚBLICA",
                    "DescricaoTipoEducacao": "ENSINO REGULAR",
                    "DescricaoTipoEnsino": "ENSINO FUNDAMENTAL",
                    "DescricaoTipoTurma": "ANOS INICIAIS",
                    "DescricaoTipoCargaHoraria": "PARCIAL",
                    "DescricaoTipoLocalizacao": "URBANA",
                    "QtdMatricula": 12345,
                }
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_fundeb_matriculas",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_fundeb_matriculas(ctx, ano=2018, uf="SP")
        assert "SP" in result
        assert "SAO PAULO" in result
        assert "ENSINO FUNDAMENTAL" in result
        assert "12.345" in result

    @pytest.mark.asyncio
    async def test_empty_result(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_fundeb_matriculas",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.consultar_fundeb_matriculas(ctx, ano=2025)
        assert "Nenhuma" in result


# ---------------------------------------------------------------------------
# consultar_pnae_alunos
# ---------------------------------------------------------------------------


class TestConsultarPnaeAlunos:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            PnaeAluno.model_validate(
                {
                    "Co_alunos_atendidos": "123",
                    "Ano": "2022",
                    "Estado": "BA",
                    "Municipio": "SALVADOR",
                    "Regiao": "NORDESTE",
                    "Esfera_governo": "MUNICIPAL",
                    "Etapa_ensino": "CRECHE",
                    "Qt_alunos_pnae": 5000,
                }
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_pnae_alunos",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_pnae_alunos(ctx, ano="2022", estado="BA")
        assert "BA" in result
        assert "SALVADOR" in result
        assert "CRECHE" in result

    @pytest.mark.asyncio
    async def test_empty_result(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_pnae_alunos",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.consultar_pnae_alunos(ctx, ano="2099")
        assert "Nenhum" in result


# ---------------------------------------------------------------------------
# consultar_pnld_livros
# ---------------------------------------------------------------------------


class TestConsultarPnldLivros:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            PnldLivro.model_validate(
                {
                    "Programa": "PNLD",
                    "Ano": "2019",
                    "Editora": "EDITORA ATICA S/A",
                    "Cod_livro": "0032P19011001IL",
                    "Titulo_livro": "ÁPIS LÍNGUA PORTUGUESA - 1º ANO",
                    "Criterio": "200821 - DISTRIB PNLD 2019",
                    "Qt_titulos": 8236,
                    "Custo_titulos": 86889.80,
                }
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_pnld_livros",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_pnld_livros(ctx, ano="2019")
        assert "EDITORA ATICA" in result
        assert "2019" in result
        assert "R$" in result

    @pytest.mark.asyncio
    async def test_empty_result(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_pnld_livros",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.consultar_pnld_livros(ctx)
        assert "Nenhum" in result


# ---------------------------------------------------------------------------
# consultar_pnate_transporte
# ---------------------------------------------------------------------------


class TestConsultarPnateTransporte:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            PnateTransporte.model_validate(
                {
                    "Uf": "AM",
                    "Municipio": "MANAUS",
                    "EntidadeExecutora": "PREF MUN DE MANAUS",
                    "Cnpj": "04365326000169",
                    "QtdAlunosAtendidos": 15000,
                }
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_pnate_transporte",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_pnate_transporte(ctx, uf="AM")
        assert "AM" in result
        assert "MANAUS" in result
        assert "PREF MUN DE MANAUS" in result

    @pytest.mark.asyncio
    async def test_empty_result(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_pnate_transporte",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.consultar_pnate_transporte(ctx, uf="XX")
        assert "Nenhum" in result
