"""Integration tests for the FNDE feature using fastmcp.Client.

These tests verify the full pipeline: server → tools → client (mocked HTTP).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from mcp_brasil.data.fnde.schemas import FundebMatricula, PnaeAluno
from mcp_brasil.data.fnde.server import mcp

CLIENT_MODULE = "mcp_brasil.data.fnde.client"


class TestToolsRegistered:
    @pytest.mark.asyncio
    async def test_all_4_tools_registered(self) -> None:
        async with Client(mcp) as c:
            tool_list = await c.list_tools()
            names = {t.name for t in tool_list}
            expected = {
                "consultar_fundeb_matriculas",
                "consultar_pnae_alunos",
                "consultar_pnld_livros",
                "consultar_pnate_transporte",
            }
            assert expected.issubset(names), f"Missing: {expected - names}"

    @pytest.mark.asyncio
    async def test_tools_have_docstrings(self) -> None:
        async with Client(mcp) as c:
            tool_list = await c.list_tools()
            for tool in tool_list:
                assert tool.description, f"Tool {tool.name} has no description"


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_consultar_fundeb_e2e(self) -> None:
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
        with patch(
            f"{CLIENT_MODULE}.consultar_fundeb_matriculas",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool(
                    "consultar_fundeb_matriculas", {"ano": 2018, "uf": "SP"}
                )
                assert "SP" in result.data
                assert "SAO PAULO" in result.data

    @pytest.mark.asyncio
    async def test_consultar_pnae_e2e(self) -> None:
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
        with patch(
            f"{CLIENT_MODULE}.consultar_pnae_alunos",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool(
                    "consultar_pnae_alunos", {"ano": "2022", "estado": "BA"}
                )
                assert "SALVADOR" in result.data
