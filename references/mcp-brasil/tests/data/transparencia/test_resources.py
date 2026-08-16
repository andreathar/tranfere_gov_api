"""Tests for Transparência resources — static reference data."""

import json

import pytest

from mcp_brasil.data.transparencia.resources import bases_sancoes, endpoints_disponiveis, info_api


class TestEndpointsDisponiveis:
    def test_returns_valid_json(self) -> None:
        data = json.loads(endpoints_disponiveis())
        assert isinstance(data, list)

    def test_has_endpoints(self) -> None:
        data = json.loads(endpoints_disponiveis())
        assert len(data) >= 9

    def test_each_endpoint_has_required_fields(self) -> None:
        data = json.loads(endpoints_disponiveis())
        for ep in data:
            assert "endpoint" in ep
            assert "descricao" in ep
            assert "parametros" in ep

    def test_contains_contratos_and_sancoes(self) -> None:
        data = json.loads(endpoints_disponiveis())
        endpoints = {ep["endpoint"] for ep in data}
        assert "contratos" in endpoints
        assert any("sancoes" in ep or "ceaf" in ep for ep in endpoints)


class TestBasesSancoes:
    def test_returns_valid_json(self) -> None:
        data = json.loads(bases_sancoes())
        assert isinstance(data, list)

    def test_has_4_bases(self) -> None:
        data = json.loads(bases_sancoes())
        assert len(data) == 4

    def test_bases_have_required_fields(self) -> None:
        data = json.loads(bases_sancoes())
        for base in data:
            assert "sigla" in base
            assert "nome" in base
            assert "url" in base

    def test_contains_ceis_and_cnep(self) -> None:
        data = json.loads(bases_sancoes())
        siglas = {b["sigla"] for b in data}
        assert "CEIS" in siglas
        assert "CNEP" in siglas


class TestInfoApi:
    def test_returns_valid_json(self) -> None:
        data = json.loads(info_api())
        assert isinstance(data, dict)

    def test_has_required_fields(self) -> None:
        data = json.loads(info_api())
        assert "nome" in data
        assert "url_base" in data
        assert "autenticacao" in data
        assert "limites" in data

    def test_auth_info(self) -> None:
        data = json.loads(info_api())
        auth = data["autenticacao"]
        assert auth["header"] == "chave-api-dados"


class TestResourcesIntegration:
    @pytest.mark.asyncio
    async def test_resources_accessible_via_client(self) -> None:
        from fastmcp import Client

        from mcp_brasil.data.transparencia.server import mcp

        async with Client(mcp) as c:
            resources = await c.list_resources()
            uris = {str(r.uri) for r in resources}
            assert "data://endpoints" in uris
            assert "data://bases-sancoes" in uris
            assert "data://info-api" in uris

    @pytest.mark.asyncio
    async def test_read_endpoints_resource(self) -> None:
        from fastmcp import Client

        from mcp_brasil.data.transparencia.server import mcp

        async with Client(mcp) as c:
            contents = await c.read_resource("data://endpoints")
            text = contents[0].text if hasattr(contents[0], "text") else str(contents[0])
            assert "contratos" in text
