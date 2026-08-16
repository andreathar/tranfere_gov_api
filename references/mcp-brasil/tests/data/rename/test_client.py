"""Tests for the RENAME client (static data functions)."""

from mcp_brasil.data.rename import client
from mcp_brasil.data.rename.schemas import MedicamentoRename

# ---------------------------------------------------------------------------
# buscar_medicamento
# ---------------------------------------------------------------------------


class TestBuscarMedicamento:
    def test_finds_by_name(self) -> None:
        result = client.buscar_medicamento("paracetamol")
        assert len(result) >= 1
        assert all(isinstance(m, MedicamentoRename) for m in result)
        assert any("Paracetamol" in m.nome for m in result)

    def test_finds_by_principio_ativo(self) -> None:
        result = client.buscar_medicamento("dipirona sódica")
        assert len(result) >= 1
        assert any("Dipirona" in m.principio_ativo for m in result)

    def test_case_insensitive(self) -> None:
        lower = client.buscar_medicamento("ibuprofeno")
        upper = client.buscar_medicamento("IBUPROFENO")
        assert len(lower) == len(upper)

    def test_no_match(self) -> None:
        result = client.buscar_medicamento("medicamento_inexistente_xyz")
        assert result == []

    def test_partial_match(self) -> None:
        result = client.buscar_medicamento("insulin")
        assert len(result) >= 1
        assert all("Insulin" in m.nome or "Insulin" in m.principio_ativo for m in result)


# ---------------------------------------------------------------------------
# listar_por_grupo
# ---------------------------------------------------------------------------


class TestListarPorGrupo:
    def test_finds_antibioticos(self) -> None:
        result = client.listar_por_grupo("Antibióticos")
        assert len(result) >= 1
        assert all(m.grupo == "Antibióticos" for m in result)

    def test_partial_match(self) -> None:
        result = client.listar_por_grupo("anti-hiper")
        assert len(result) >= 1
        assert all("Anti-hipertensivos" in m.grupo for m in result)

    def test_no_match(self) -> None:
        result = client.listar_por_grupo("grupo_inexistente")
        assert result == []


# ---------------------------------------------------------------------------
# verificar_disponibilidade_sus
# ---------------------------------------------------------------------------


class TestVerificarDisponibilidadeSus:
    def test_delegates_to_buscar(self) -> None:
        result = client.verificar_disponibilidade_sus("paracetamol")
        expected = client.buscar_medicamento("paracetamol")
        assert len(result) == len(expected)

    def test_no_match(self) -> None:
        result = client.verificar_disponibilidade_sus("inexistente")
        assert result == []


# ---------------------------------------------------------------------------
# listar_grupos
# ---------------------------------------------------------------------------


class TestListarGrupos:
    def test_returns_all_groups(self) -> None:
        result = client.listar_grupos()
        assert len(result) == 20
        assert "Antibióticos" in result
        assert "Anti-hipertensivos" in result
        assert "Antidiabéticos" in result

    def test_returns_strings(self) -> None:
        result = client.listar_grupos()
        assert all(isinstance(g, str) for g in result)


# ---------------------------------------------------------------------------
# listar_todos
# ---------------------------------------------------------------------------


class TestListarTodos:
    def test_returns_all_medications(self) -> None:
        result = client.listar_todos()
        assert len(result) >= 30
        assert all(isinstance(m, MedicamentoRename) for m in result)

    def test_has_multiple_groups(self) -> None:
        result = client.listar_todos()
        groups = {m.grupo for m in result}
        assert len(groups) >= 5


# ---------------------------------------------------------------------------
# _parse_medicamento
# ---------------------------------------------------------------------------


class TestParseMedicamento:
    def test_parses_all_fields(self) -> None:
        raw = {
            "nome": "Test",
            "principio_ativo": "Active",
            "apresentacao": "Comprimido 500mg",
            "grupo": "Antibióticos",
            "via": "Oral",
            "disponivel_ubs": True,
        }
        result = client._parse_medicamento(raw)
        assert result.nome == "Test"
        assert result.principio_ativo == "Active"
        assert result.apresentacao == "Comprimido 500mg"
        assert result.grupo == "Antibióticos"
        assert result.via == "Oral"
        assert result.disponivel_ubs is True

    def test_defaults_disponivel_ubs_to_true(self) -> None:
        raw = {
            "nome": "Test",
            "principio_ativo": "Active",
            "apresentacao": "Comp",
            "grupo": "G",
            "via": "Oral",
        }
        result = client._parse_medicamento(raw)
        assert result.disponivel_ubs is True
