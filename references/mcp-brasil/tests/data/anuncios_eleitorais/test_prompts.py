"""Tests for anuncios_eleitorais prompts — unit + Client integration."""

from __future__ import annotations

import pytest
from fastmcp import Client

from mcp_brasil.data.anuncios_eleitorais.prompts import transparencia_anuncios
from mcp_brasil.data.anuncios_eleitorais.server import mcp


class TestTransparenciaAnuncios:
    """Tests for transparencia_anuncios prompt."""

    def test_retorna_instrucoes(self) -> None:
        result = transparencia_anuncios(termo="educação")
        assert isinstance(result, str)
        assert "educação" in result

    def test_sem_parametros(self) -> None:
        result = transparencia_anuncios()
        assert "Brasil" in result

    def test_com_estado(self) -> None:
        result = transparencia_anuncios(estado="São Paulo")
        assert "São Paulo" in result
        assert "buscar_anuncios_por_regiao" in result

    def test_com_termo_e_estado(self) -> None:
        result = transparencia_anuncios(termo="saúde", estado="RJ")
        assert "saúde" in result
        assert "RJ" in result

    def test_inclui_foco_cidadao(self) -> None:
        result = transparencia_anuncios()
        assert "transparência" in result.lower()


class TestPromptRegistration:
    """Test prompts are properly registered via Client."""

    @pytest.mark.asyncio
    async def test_prompts_registrados(self) -> None:
        async with Client(mcp) as c:
            prompts = await c.list_prompts()
            names = [p.name for p in prompts]
            assert "transparencia_anuncios" in names

    @pytest.mark.asyncio
    async def test_chamar_transparencia_anuncios(self) -> None:
        async with Client(mcp) as c:
            result = await c.get_prompt(
                "transparencia_anuncios",
                arguments={"termo": "Teste"},
            )
            assert len(result.messages) > 0
            text = result.messages[0].content.text  # type: ignore[union-attr]
            assert "Teste" in text
