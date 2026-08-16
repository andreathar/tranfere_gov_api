"""Tests for Senado resources — static reference data."""

import json

import pytest

from mcp_brasil.data.senado.resources import comissoes_permanentes, info_api, tipos_materia


class TestTiposMateria:
    def test_returns_valid_json(self) -> None:
        data = json.loads(tipos_materia())
        assert isinstance(data, list)

    def test_has_types(self) -> None:
        data = json.loads(tipos_materia())
        assert len(data) >= 10

    def test_each_type_has_required_fields(self) -> None:
        data = json.loads(tipos_materia())
        for t in data:
            assert "sigla" in t
            assert "descricao" in t

    def test_contains_pec_and_pls(self) -> None:
        data = json.loads(tipos_materia())
        siglas = {t["sigla"] for t in data}
        assert "PEC" in siglas
        assert "PLS" in siglas


class TestInfoApi:
    def test_returns_valid_json(self) -> None:
        data = json.loads(info_api())
        assert isinstance(data, dict)

    def test_has_required_fields(self) -> None:
        data = json.loads(info_api())
        assert "nome" in data
        assert "url_base" in data
        assert "autenticacao" in data

    def test_no_auth_required(self) -> None:
        data = json.loads(info_api())
        assert "Não requer" in data["autenticacao"]


class TestComissoesPermanentes:
    def test_returns_valid_json(self) -> None:
        data = json.loads(comissoes_permanentes())
        assert isinstance(data, list)

    def test_has_comissoes(self) -> None:
        data = json.loads(comissoes_permanentes())
        assert len(data) >= 10

    def test_each_comissao_has_required_fields(self) -> None:
        data = json.loads(comissoes_permanentes())
        for c in data:
            assert "sigla" in c
            assert "nome" in c

    def test_contains_ccj(self) -> None:
        data = json.loads(comissoes_permanentes())
        siglas = {c["sigla"] for c in data}
        assert "CCJ" in siglas


class TestResourcesIntegration:
    @pytest.mark.asyncio
    async def test_resources_accessible_via_client(self) -> None:
        from fastmcp import Client

        from mcp_brasil.data.senado.server import mcp

        async with Client(mcp) as c:
            resources = await c.list_resources()
            uris = {str(r.uri) for r in resources}
            assert "data://tipos-materia" in uris
            assert "data://info-api" in uris
            assert "data://comissoes-permanentes" in uris

    @pytest.mark.asyncio
    async def test_read_tipos_materia_resource(self) -> None:
        from fastmcp import Client

        from mcp_brasil.data.senado.server import mcp

        async with Client(mcp) as c:
            contents = await c.read_resource("data://tipos-materia")
            text = contents[0].text if hasattr(contents[0], "text") else str(contents[0])
            assert "PEC" in text
