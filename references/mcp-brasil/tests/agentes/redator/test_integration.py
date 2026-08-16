"""Integration tests for the Redator Oficial feature using fastmcp.Client."""

import pytest
from fastmcp import Client

from mcp_brasil.agentes.redator.server import mcp


class TestToolsRegistered:
    @pytest.mark.asyncio
    async def test_all_5_tools_registered(self) -> None:
        async with Client(mcp) as c:
            tool_list = await c.list_tools()
            names = {t.name for t in tool_list}
            expected = {
                "formatar_data_extenso",
                "gerar_numeracao",
                "consultar_pronome_tratamento",
                "validar_documento",
                "listar_tipos_documento",
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
    async def test_all_9_resources_registered(self) -> None:
        async with Client(mcp) as c:
            resources = await c.list_resources()
            uris = {str(r.uri) for r in resources}
            expected = {
                "template://despacho",
                "template://oficio",
                "template://portaria",
                "template://parecer",
                "template://nota_tecnica",
                "template://ata",
                "normas://manual_redacao",
                "normas://pronomes",
                "normas://fechos",
            }
            assert expected.issubset(uris), f"Missing: {expected - uris}"


class TestPromptsRegistered:
    @pytest.mark.asyncio
    async def test_all_5_prompts_registered(self) -> None:
        async with Client(mcp) as c:
            prompts = await c.list_prompts()
            names = {p.name for p in prompts}
            expected = {
                "redator_despacho",
                "redator_oficio",
                "redator_portaria",
                "redator_parecer",
                "redator_nota_tecnica",
            }
            assert expected.issubset(names), f"Missing: {expected - names}"


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_formatar_data_e2e(self) -> None:
        async with Client(mcp) as c:
            result = await c.call_tool(
                "formatar_data_extenso",
                {"cidade": "Teresina", "estado": "PI"},
            )
            assert "Teresina," in result.data

    @pytest.mark.asyncio
    async def test_gerar_numeracao_e2e(self) -> None:
        async with Client(mcp) as c:
            result = await c.call_tool(
                "gerar_numeracao",
                {"tipo": "memorando", "numero": 42, "ano": 2026, "setor": "GAB"},
            )
            assert "OFÍCIO Nº 42/2026/GAB" in result.data

    @pytest.mark.asyncio
    async def test_consultar_pronome_e2e(self) -> None:
        async with Client(mcp) as c:
            result = await c.call_tool(
                "consultar_pronome_tratamento",
                {"cargo": "Governador"},
            )
            assert "Vossa Excelência" in result.data

    @pytest.mark.asyncio
    async def test_listar_tipos_e2e(self) -> None:
        async with Client(mcp) as c:
            result = await c.call_tool("listar_tipos_documento", {})
            assert "despacho" in result.data
            assert "memorando" in result.data.lower()


class TestResourceExecution:
    @pytest.mark.asyncio
    async def test_read_template_oficio(self) -> None:
        async with Client(mcp) as c:
            content = await c.read_resource("template://oficio")
            text = content[0].text if hasattr(content[0], "text") else str(content[0])
            assert "OFÍCIO" in text

    @pytest.mark.asyncio
    async def test_read_template_despacho(self) -> None:
        async with Client(mcp) as c:
            content = await c.read_resource("template://despacho")
            text = content[0].text if hasattr(content[0], "text") else str(content[0])
            assert "DESPACHO" in text

    @pytest.mark.asyncio
    async def test_read_normas_manual(self) -> None:
        async with Client(mcp) as c:
            content = await c.read_resource("normas://manual_redacao")
            text = content[0].text if hasattr(content[0], "text") else str(content[0])
            assert "Impessoalidade" in text

    @pytest.mark.asyncio
    async def test_read_normas_pronomes_3a_edicao(self) -> None:
        async with Client(mcp) as c:
            content = await c.read_resource("normas://pronomes")
            text = content[0].text if hasattr(content[0], "text") else str(content[0])
            assert "Excelentíssimo" in text
            assert "Digníssimo" in text  # mentioned as abolished


class TestPromptExecution:
    @pytest.mark.asyncio
    async def test_prompt_oficio(self) -> None:
        async with Client(mcp) as c:
            result = await c.get_prompt(
                "redator_oficio",
                arguments={
                    "destinatario": "João da Silva",
                    "cargo_destinatario": "Secretário",
                    "assunto": "Cessão de servidor",
                },
            )
            messages = result.messages
            assert len(messages) == 2
            assert "OFÍCIO" in messages[0].content.text
            assert "Cessão de servidor" in messages[0].content.text

    @pytest.mark.asyncio
    async def test_prompt_despacho(self) -> None:
        async with Client(mcp) as c:
            result = await c.get_prompt(
                "redator_despacho",
                arguments={"assunto": "Aprovar licença"},
            )
            messages = result.messages
            assert len(messages) == 2
            assert "DESPACHO" in messages[0].content.text
            assert "Aprovar licença" in messages[0].content.text
