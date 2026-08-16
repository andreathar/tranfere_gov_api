"""Tests for the SPU-Imoveis resources."""

from __future__ import annotations

import json

import pytest
from fastmcp import Client

from mcp_brasil.data.spu_imoveis.resources import (
    catalogo_orgaos,
    info_api,
    schema_csv,
)
from mcp_brasil.data.spu_imoveis.server import mcp


def test_schema_csv_lists_columns() -> None:
    data = json.loads(schema_csv())
    names = {c["name"] for c in data["columns"]}
    assert "orgao_superior_sigla" in names
    assert "municipio_cod_ibge" in names
    assert "valor_imovel" in names


def test_catalogo_orgaos_not_empty() -> None:
    data = json.loads(catalogo_orgaos())
    assert "MEC" in data["orgaos_superiores_frequentes"]
    assert "MD" in data["orgaos_superiores_frequentes"]


def test_info_api_has_source() -> None:
    data = json.loads(info_api())
    assert "Raio-X" in data["fonte"]
    assert data["auth"].startswith("Sem ")


@pytest.mark.asyncio
async def test_resources_registered_on_server() -> None:
    async with Client(mcp) as c:
        resources = await c.list_resources()
        uris = {str(r.uri) for r in resources}
        assert "data://schema" in uris
        assert "data://orgaos" in uris
        assert "data://info" in uris
