"""Tests for the RENAME prompts."""

from mcp_brasil.data.rename.prompts import consulta_medicamento_sus


class TestConsultaMedicamentoSus:
    def test_includes_nome(self) -> None:
        result = consulta_medicamento_sus("losartana")
        assert "losartana" in result

    def test_includes_tool_names(self) -> None:
        result = consulta_medicamento_sus("metformina")
        assert "verificar_disponibilidade_sus" in result
        assert "buscar_medicamento_rename" in result

    def test_includes_instructions(self) -> None:
        result = consulta_medicamento_sus("insulina")
        assert "assistente" in result.lower()
        assert "RENAME" in result or "SUS" in result
