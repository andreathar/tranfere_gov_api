"""Tests for the RENAME resources."""

import json

from mcp_brasil.data.rename import resources


class TestCatalogoRename:
    def test_returns_json(self) -> None:
        result = resources.catalogo_rename()
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) >= 30

    def test_has_required_fields(self) -> None:
        result = resources.catalogo_rename()
        data = json.loads(result)
        for item in data:
            assert "nome" in item
            assert "principio_ativo" in item
            assert "apresentacao" in item
            assert "grupo" in item
            assert "via" in item


class TestGruposTerapeuticos:
    def test_returns_json(self) -> None:
        result = resources.grupos_terapeuticos()
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) == 20

    def test_contains_known_groups(self) -> None:
        result = resources.grupos_terapeuticos()
        data = json.loads(result)
        assert "Antibióticos" in data
        assert "Anti-hipertensivos" in data
