"""Tests for the DENASUS resources."""

import json

from mcp_brasil.data.denasus import resources


class TestSobreDenasus:
    def test_returns_json(self) -> None:
        result = resources.sobre_denasus()
        data = json.loads(result)
        assert isinstance(data, dict)
        assert "nome" in data
        assert "DENASUS" in data["orgao"]

    def test_has_required_fields(self) -> None:
        result = resources.sobre_denasus()
        data = json.loads(result)
        assert "base_legal" in data
        assert "competencia" in data
        assert "portal" in data


class TestTiposAtividade:
    def test_returns_json(self) -> None:
        result = resources.tipos_atividade()
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) == 5

    def test_contains_known_types(self) -> None:
        result = resources.tipos_atividade()
        data = json.loads(result)
        assert "Auditoria" in data
        assert "Monitoramento" in data
