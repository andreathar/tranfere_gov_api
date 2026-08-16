"""Tests for tabua_mares resources."""

from __future__ import annotations

import json

from mcp_brasil.data.tabua_mares.resources import estados_costeiros


def test_estados_costeiros_returns_valid_json() -> None:
    result = estados_costeiros()
    data = json.loads(result)
    assert isinstance(data, list)
    assert len(data) == 17


def test_estados_costeiros_has_expected_fields() -> None:
    data = json.loads(estados_costeiros())
    for estado in data:
        assert "sigla" in estado
        assert "nome" in estado
        assert len(estado["sigla"]) == 2


def test_estados_costeiros_sorted() -> None:
    data = json.loads(estados_costeiros())
    siglas = [e["sigla"] for e in data]
    assert siglas == sorted(siglas)
