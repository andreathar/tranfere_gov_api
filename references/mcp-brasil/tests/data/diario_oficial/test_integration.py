"""Integration tests for the Diário Oficial feature using fastmcp.Client.

These tests verify the full pipeline: server -> tools -> client (mocked HTTP).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from mcp_brasil.data.diario_oficial.schemas import (
    CidadeQueridoDiario,
    DiarioOficial,
    DiarioResultado,
    PublicacaoDOU,
    ResultadoDOU,
)
from mcp_brasil.data.diario_oficial.server import mcp

CLIENT_MODULE = "mcp_brasil.data.diario_oficial.client"
CLIENT_DOU_MODULE = "mcp_brasil.data.diario_oficial.client_dou"


class TestToolsRegistered:
    @pytest.mark.asyncio
    async def test_all_11_tools_registered(self) -> None:
        async with Client(mcp) as c:
            tool_list = await c.list_tools()
            names = {t.name for t in tool_list}
            expected = {
                # Municipal (QD)
                "buscar_diarios",
                "buscar_diarios_regiao",
                "buscar_cidades",
                "listar_territorios",
                "listar_diarios_recentes",
                # Federal (DOU)
                "dou_buscar",
                "dou_ler_publicacao",
                "dou_edicao_do_dia",
                "dou_buscar_por_orgao",
                "dou_buscar_avancado",
                # Unificado
                "buscar_diario_unificado",
            }
            assert expected.issubset(names), f"Missing: {expected - names}"

    @pytest.mark.asyncio
    async def test_tools_have_docstrings(self) -> None:
        async with Client(mcp) as c:
            tool_list = await c.list_tools()
            for tool in tool_list:
                assert tool.description, f"Tool {tool.name} has no description"


class TestResourcesRegistered:
    @pytest.mark.asyncio
    async def test_all_6_resources_registered(self) -> None:
        async with Client(mcp) as c:
            resources = await c.list_resources()
            uris = {str(r.uri) for r in resources}
            expected = {
                "data://capitais-cobertas",
                "data://ufs-cobertas",
                "data://dicas-busca",
                "data://secoes-dou",
                "data://tipos-publicacao-dou",
                "data://orgaos-federais-dou",
            }
            assert expected.issubset(uris), f"Missing: {expected - uris}"


class TestPromptsRegistered:
    @pytest.mark.asyncio
    async def test_all_7_prompts_registered(self) -> None:
        async with Client(mcp) as c:
            prompts = await c.list_prompts()
            names = {p.name for p in prompts}
            expected = {
                "investigar_empresa",
                "monitorar_licitacoes",
                "rastrear_nomeacoes",
                "comparar_municipios",
                "rastrear_cadeia_regulatoria",
                "investigar_cnpj_diarios",
                "monitorar_diario_completo",
            }
            assert expected.issubset(names), f"Missing: {expected - names}"


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_buscar_diarios_e2e(self) -> None:
        mock_data = DiarioResultado(
            total_gazettes=1,
            gazettes=[
                DiarioOficial(
                    territory_id="3550308",
                    territory_name="São Paulo",
                    state_code="SP",
                    date="2024-01-15",
                    edition_number="1234",
                    is_extra_edition=False,
                    txt_url="https://example.com/gazette.txt",
                    excerpts=["Contrato de licitação"],
                ),
            ],
        )
        with patch(
            f"{CLIENT_MODULE}.buscar_diarios",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("buscar_diarios", {"texto": "licitação"})
                assert "São Paulo" in result.data
                assert "2024-01-15" in result.data

    @pytest.mark.asyncio
    async def test_dou_buscar_e2e(self) -> None:
        mock_data = ResultadoDOU(
            total=1,
            publicacoes=[
                PublicacaoDOU(
                    titulo="Decreto nº 999",
                    orgao="Presidência da República",
                    data_publicacao="2024-01-15",
                    resumo="Regulamenta lei X",
                ),
            ],
        )
        with patch(
            f"{CLIENT_DOU_MODULE}.buscar_dou",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("dou_buscar", {"termo": "decreto"})
                assert "Decreto nº 999" in result.data
                assert "Presidência" in result.data

    @pytest.mark.asyncio
    async def test_buscar_diario_unificado_e2e(self) -> None:
        mock_qd = DiarioResultado(
            total_gazettes=1,
            gazettes=[
                DiarioOficial(
                    territory_name="São Paulo",
                    state_code="SP",
                    date="2024-01-15",
                    excerpts=["Resultado municipal"],
                ),
            ],
        )
        mock_dou = ResultadoDOU(
            total=1,
            publicacoes=[
                PublicacaoDOU(
                    titulo="Portaria Federal",
                    orgao="Ministério X",
                    data_publicacao="2024-01-15",
                ),
            ],
        )
        with (
            patch(
                f"{CLIENT_MODULE}.buscar_diarios",
                new_callable=AsyncMock,
                return_value=mock_qd,
            ),
            patch(
                f"{CLIENT_DOU_MODULE}.buscar_dou",
                new_callable=AsyncMock,
                return_value=mock_dou,
            ),
        ):
            async with Client(mcp) as c:
                result = await c.call_tool(
                    "buscar_diario_unificado",
                    {"texto": "teste"},
                )
                assert "DOU Federal" in result.data
                assert "Diários Municipais" in result.data
                assert "Portaria Federal" in result.data
                assert "São Paulo" in result.data

    @pytest.mark.asyncio
    async def test_buscar_diarios_regiao_e2e(self) -> None:
        mock_data = DiarioResultado(
            total_gazettes=1,
            gazettes=[
                DiarioOficial(
                    territory_name="São Paulo",
                    state_code="SP",
                    date="2024-01-15",
                    excerpts=["Resultado regional"],
                ),
            ],
        )
        with patch(
            f"{CLIENT_MODULE}.buscar_diarios",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool(
                    "buscar_diarios_regiao",
                    {"texto": "licitação", "uf": "SP"},
                )
                assert "São Paulo" in result.data

    @pytest.mark.asyncio
    async def test_buscar_cidades_e2e(self) -> None:
        mock_data = [
            CidadeQueridoDiario(
                territory_id="3550308",
                territory_name="São Paulo",
                state_code="SP",
            )
        ]
        with patch(
            f"{CLIENT_MODULE}.buscar_cidades",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("buscar_cidades", {"nome": "São Paulo"})
                assert "São Paulo" in result.data
                assert "3550308" in result.data
