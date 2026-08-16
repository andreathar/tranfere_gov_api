"""Tests for the INEP client.

Since INEP has no REST API, the client generates URLs and metadata.
Tests verify URL generation logic and catalog data.
"""

import pytest

from mcp_brasil.data.inep import client

# ---------------------------------------------------------------------------
# gerar_urls_ideb
# ---------------------------------------------------------------------------


class TestGerarUrlsIdeb:
    @pytest.mark.asyncio
    async def test_generates_url_for_specific_year(self) -> None:
        urls = await client.gerar_urls_ideb(ano=2023, nivel="regioes_ufs")
        assert len(urls) == 1
        assert urls[0].ano == 2023
        assert "regioes_ufs_ideb_2023" in urls[0].url

    @pytest.mark.asyncio
    async def test_generates_urls_for_all_etapas(self) -> None:
        urls = await client.gerar_urls_ideb(ano=2023, nivel="escolas")
        assert len(urls) == 3  # anos_iniciais, anos_finais, ensino_medio
        etapas = {u.etapa for u in urls}
        assert etapas == {"anos_iniciais", "anos_finais", "ensino_medio"}

    @pytest.mark.asyncio
    async def test_brasil_has_no_etapa(self) -> None:
        urls = await client.gerar_urls_ideb(ano=2023, nivel="brasil")
        assert len(urls) == 1
        assert urls[0].etapa is None

    @pytest.mark.asyncio
    async def test_invalid_year_returns_empty(self) -> None:
        urls = await client.gerar_urls_ideb(ano=9999)
        assert urls == []

    @pytest.mark.asyncio
    async def test_url_contains_download_domain(self) -> None:
        urls = await client.gerar_urls_ideb(ano=2023, nivel="brasil")
        assert "download.inep.gov.br" in urls[0].url


# ---------------------------------------------------------------------------
# listar_microdados
# ---------------------------------------------------------------------------


class TestListarMicrodados:
    @pytest.mark.asyncio
    async def test_returns_all_datasets(self) -> None:
        datasets = await client.listar_microdados()
        codigos = {ds.codigo for ds in datasets}
        assert "censo_escolar" in codigos
        assert "enem" in codigos
        assert "saeb" in codigos

    @pytest.mark.asyncio
    async def test_datasets_have_anos(self) -> None:
        datasets = await client.listar_microdados()
        for ds in datasets:
            assert len(ds.anos_disponiveis) > 0


# ---------------------------------------------------------------------------
# gerar_url_microdados
# ---------------------------------------------------------------------------


class TestGerarUrlMicrodados:
    @pytest.mark.asyncio
    async def test_valid_dataset_and_year(self) -> None:
        url = await client.gerar_url_microdados("enem", 2023)
        assert url is not None
        assert "enem" in url
        assert "2023" in url

    @pytest.mark.asyncio
    async def test_invalid_dataset(self) -> None:
        url = await client.gerar_url_microdados("inexistente", 2023)
        assert url is None

    @pytest.mark.asyncio
    async def test_invalid_year(self) -> None:
        url = await client.gerar_url_microdados("enem", 1900)
        assert url is None


# ---------------------------------------------------------------------------
# listar_indicadores
# ---------------------------------------------------------------------------


class TestListarIndicadores:
    @pytest.mark.asyncio
    async def test_returns_indicators(self) -> None:
        indicadores = await client.listar_indicadores()
        assert len(indicadores) > 0
        codigos = {i.codigo for i in indicadores}
        assert "taxa_distorcao_idade_serie" in codigos
        assert "taxa_rendimento" in codigos
