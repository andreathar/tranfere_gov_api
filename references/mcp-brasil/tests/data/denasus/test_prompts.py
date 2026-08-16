"""Tests for the DENASUS prompts."""

from mcp_brasil.data.denasus.prompts import analise_auditoria_municipal


class TestAnaliseAuditoriaMunicipal:
    def test_includes_municipio(self) -> None:
        result = analise_auditoria_municipal("Teresina", "PI")
        assert "Teresina" in result

    def test_includes_uf(self) -> None:
        result = analise_auditoria_municipal("São Paulo", "SP")
        assert "SP" in result

    def test_includes_tool_names(self) -> None:
        result = analise_auditoria_municipal("Rio", "RJ")
        assert "verificar_municipio" in result
        assert "buscar_auditorias" in result
        assert "listar_relatorios_anuais" in result
        assert "informacoes_sna" in result
