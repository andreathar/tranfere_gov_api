"""Tests for tabua_mares prompts."""

from __future__ import annotations

from mcp_brasil.data.tabua_mares.prompts import analise_navegacao, consulta_mares


def test_consulta_mares_returns_instructions() -> None:
    result = consulta_mares("pb", 1)
    assert "PB" in result
    assert "listar_portos" in result
    assert "consultar_tabua_mare" in result


def test_analise_navegacao_returns_instructions() -> None:
    result = analise_navegacao(-7.11, -34.86, "rj")
    assert "RJ" in result
    assert "porto_mais_proximo" in result
    assert "navegação" in result.lower()
