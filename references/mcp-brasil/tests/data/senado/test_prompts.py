"""Tests for Senado prompts — analysis templates."""

import pytest

from mcp_brasil.data.senado.prompts import (
    acompanhar_materia,
    analise_votacao_senado,
    perfil_senador,
)


class TestAcompanharMateria:
    def test_returns_string(self) -> None:
        result = acompanhar_materia("PEC", "45", "2024")
        assert isinstance(result, str)

    def test_contains_materia(self) -> None:
        result = acompanhar_materia("PEC", "45", "2024")
        assert "PEC 45/2024" in result

    def test_contains_tool_instructions(self) -> None:
        result = acompanhar_materia("PEC", "45", "2024")
        assert "buscar_materia" in result
        assert "detalhe_materia" in result
        assert "consultar_tramitacao_materia" in result
        assert "votos_materia" in result
        assert "textos_materia" in result


class TestPerfilSenador:
    def test_returns_string(self) -> None:
        result = perfil_senador("5012")
        assert isinstance(result, str)

    def test_contains_codigo(self) -> None:
        result = perfil_senador("5012")
        assert "5012" in result

    def test_contains_tool_instructions(self) -> None:
        result = perfil_senador("5012")
        assert "buscar_senador" in result
        assert "votacoes_senador" in result


class TestAnaliseVotacaoSenado:
    def test_returns_string(self) -> None:
        result = analise_votacao_senado("VOT-001")
        assert isinstance(result, str)

    def test_contains_codigo(self) -> None:
        result = analise_votacao_senado("VOT-001")
        assert "VOT-001" in result

    def test_contains_tool_instructions(self) -> None:
        result = analise_votacao_senado("VOT-001")
        assert "detalhe_votacao" in result


class TestPromptsIntegration:
    @pytest.mark.asyncio
    async def test_prompts_registered(self) -> None:
        from fastmcp import Client

        from mcp_brasil.data.senado.server import mcp

        async with Client(mcp) as c:
            prompts = await c.list_prompts()
            names = {p.name for p in prompts}
            assert "acompanhar_materia" in names
            assert "perfil_senador" in names
            assert "analise_votacao_senado" in names

    @pytest.mark.asyncio
    async def test_get_acompanhar_prompt(self) -> None:
        from fastmcp import Client

        from mcp_brasil.data.senado.server import mcp

        async with Client(mcp) as c:
            result = await c.get_prompt(
                "acompanhar_materia",
                {"sigla_tipo": "PEC", "numero": "45", "ano": "2024"},
            )
            text = result.messages[0].content.text  # type: ignore[union-attr]
            assert "PEC 45/2024" in text
