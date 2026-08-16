"""Tests for the Fórum Brasileiro de Segurança Pública tool functions."""

from unittest.mock import AsyncMock

import pytest

from mcp_brasil.data.forum_seguranca import tools
from mcp_brasil.data.forum_seguranca.schemas import Comunidade, Publicacao, ResultadoBusca


def _make_ctx() -> AsyncMock:
    ctx = AsyncMock()
    ctx.info = AsyncMock()
    return ctx


def _make_publicacao(**kwargs: object) -> Publicacao:
    defaults: dict[str, object] = {
        "uuid": "pub-001",
        "titulo": "Anuário 2023",
        "autores": ["Fórum Brasileiro de Segurança Pública"],
        "resumo": "Análise anual de dados de segurança pública.",
        "data_publicacao": "2023",
        "editora": "FBSP",
        "assuntos": ["segurança", "violência"],
        "uri": "https://publicacoes.forumseguranca.org.br/handle/1",
    }
    defaults.update(kwargs)
    return Publicacao(**defaults)  # type: ignore[arg-type]


class TestBuscarPublicacoesSeguranca:
    @pytest.mark.asyncio
    async def test_returns_formatted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        resultado = ResultadoBusca(
            total=50,
            pagina=0,
            total_paginas=5,
            publicacoes=[_make_publicacao()],
        )
        monkeypatch.setattr(
            "mcp_brasil.data.forum_seguranca.tools.client.buscar_publicacoes",
            AsyncMock(return_value=resultado),
        )
        result = await tools.buscar_publicacoes_seguranca("anuário", _make_ctx())
        assert "50 publicações encontradas" in result
        assert "Anuário 2023" in result
        assert "pub-001" in result
        assert "pagina=1" in result  # pagination hint

    @pytest.mark.asyncio
    async def test_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "mcp_brasil.data.forum_seguranca.tools.client.buscar_publicacoes",
            AsyncMock(return_value=ResultadoBusca()),
        )
        result = await tools.buscar_publicacoes_seguranca("xyz", _make_ctx())
        assert "Nenhuma publicação" in result


class TestListarTemasSeguranca:
    @pytest.mark.asyncio
    async def test_returns_formatted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        comunidades = [
            Comunidade(
                uuid="d044c00f-7c26-4249-8da4-336e953fe557",
                nome="Anuário Brasileiro de Segurança Pública",
                descricao="Dados anuais de segurança pública.",
                quantidade_itens=18,
            ),
        ]
        monkeypatch.setattr(
            "mcp_brasil.data.forum_seguranca.tools.client.listar_comunidades",
            AsyncMock(return_value=comunidades),
        )
        result = await tools.listar_temas_seguranca(_make_ctx())
        assert "1 comunidades temáticas" in result
        assert "Anuário Brasileiro" in result
        assert "18" in result

    @pytest.mark.asyncio
    async def test_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "mcp_brasil.data.forum_seguranca.tools.client.listar_comunidades",
            AsyncMock(return_value=[]),
        )
        result = await tools.listar_temas_seguranca(_make_ctx())
        assert "Nenhuma comunidade" in result


class TestDetalharPublicacaoSeguranca:
    @pytest.mark.asyncio
    async def test_returns_details(self, monkeypatch: pytest.MonkeyPatch) -> None:
        pub = _make_publicacao(
            issn="1983-7364",
            assuntos=["segurança", "violência", "homicídio"],
        )
        monkeypatch.setattr(
            "mcp_brasil.data.forum_seguranca.tools.client.detalhar_publicacao",
            AsyncMock(return_value=pub),
        )
        result = await tools.detalhar_publicacao_seguranca("pub-001", _make_ctx())
        assert "Anuário 2023" in result
        assert "FBSP" in result
        assert "1983-7364" in result
        assert "segurança" in result
        assert "Resumo" in result

    @pytest.mark.asyncio
    async def test_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "mcp_brasil.data.forum_seguranca.tools.client.detalhar_publicacao",
            AsyncMock(return_value=None),
        )
        result = await tools.detalhar_publicacao_seguranca("nonexistent", _make_ctx())
        assert "não encontrada" in result


class TestBuscarPorTemaSeguranca:
    @pytest.mark.asyncio
    async def test_returns_formatted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        resultado = ResultadoBusca(
            total=5,
            pagina=0,
            total_paginas=1,
            publicacoes=[_make_publicacao(titulo="Anuário edição especial")],
        )
        monkeypatch.setattr(
            "mcp_brasil.data.forum_seguranca.tools.client.buscar_por_tema",
            AsyncMock(return_value=resultado),
        )
        result = await tools.buscar_por_tema_seguranca(
            "d044c00f-7c26-4249-8da4-336e953fe557", _make_ctx(), query="anuário"
        )
        assert "5 publicações" in result
        assert "Anuário edição especial" in result
        assert "Anuário Brasileiro de Segurança Pública" in result

    @pytest.mark.asyncio
    async def test_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "mcp_brasil.data.forum_seguranca.tools.client.buscar_por_tema",
            AsyncMock(return_value=ResultadoBusca()),
        )
        result = await tools.buscar_por_tema_seguranca(
            "d044c00f-7c26-4249-8da4-336e953fe557", _make_ctx()
        )
        assert "Nenhuma publicação" in result
