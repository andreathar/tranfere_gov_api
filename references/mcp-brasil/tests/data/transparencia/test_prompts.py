"""Tests for Transparência prompts — analysis templates."""

import pytest

from mcp_brasil.data.transparencia.prompts import (
    analise_despesas,
    auditoria_fornecedor,
    verificacao_compliance,
)


class TestAuditoriaFornecedor:
    def test_returns_string(self) -> None:
        result = auditoria_fornecedor("12345678000190")
        assert isinstance(result, str)

    def test_contains_cpf_cnpj(self) -> None:
        result = auditoria_fornecedor("12345678000190")
        assert "12345678000190" in result

    def test_contains_tool_instructions(self) -> None:
        result = auditoria_fornecedor("12345678000190")
        assert "buscar_contratos" in result
        assert "buscar_sancoes" in result


class TestAnaliseDespesas:
    def test_returns_string(self) -> None:
        result = analise_despesas("01/2024", "12/2024")
        assert isinstance(result, str)

    def test_contains_period(self) -> None:
        result = analise_despesas("01/2024", "12/2024")
        assert "01/2024" in result
        assert "12/2024" in result

    def test_contains_tool_instructions(self) -> None:
        result = analise_despesas("01/2024", "12/2024")
        assert "consultar_despesas" in result
        assert "buscar_emendas" in result

    def test_with_uf_filter(self) -> None:
        result = analise_despesas("01/2024", "12/2024", uf="PI")
        assert "PI" in result


class TestVerificacaoCompliance:
    def test_returns_string(self) -> None:
        result = verificacao_compliance("Empresa XYZ")
        assert isinstance(result, str)

    def test_contains_consulta(self) -> None:
        result = verificacao_compliance("Empresa XYZ")
        assert "Empresa XYZ" in result

    def test_mentions_all_bases(self) -> None:
        result = verificacao_compliance("12345678000190")
        assert "CEIS" in result
        assert "CNEP" in result
        assert "CEPIM" in result
        assert "CEAF" in result

    def test_contains_tool_instructions(self) -> None:
        result = verificacao_compliance("12345678000190")
        assert "buscar_sancoes" in result
        assert "buscar_contratos" in result


class TestPromptsIntegration:
    @pytest.mark.asyncio
    async def test_prompts_registered(self) -> None:
        from fastmcp import Client

        from mcp_brasil.data.transparencia.server import mcp

        async with Client(mcp) as c:
            prompts = await c.list_prompts()
            names = {p.name for p in prompts}
            assert "auditoria_fornecedor" in names
            assert "analise_despesas" in names
            assert "verificacao_compliance" in names

    @pytest.mark.asyncio
    async def test_get_auditoria_prompt(self) -> None:
        from fastmcp import Client

        from mcp_brasil.data.transparencia.server import mcp

        async with Client(mcp) as c:
            result = await c.get_prompt("auditoria_fornecedor", {"cpf_cnpj": "12345678000190"})
            text = result.messages[0].content.text  # type: ignore[union-attr]
            assert "12345678000190" in text
