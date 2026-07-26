"""
Tests for src.deputado_followup — followup de emendas por deputado.

Tests pure formatting functions and SQL query structure.
Uses mocks for DB-dependent functions.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.deputado_followup import (
    SQL_COMPARACAO_PARTIDO,
    SQL_DETALHE_EMENDA,
    SQL_EMENDAS,
    SQL_MUNICIPIOS,
    SQL_PERFIL,
    SQL_RESUMO,
    format_brl,
    print_section,
    print_table,
)

# ---------------------------------------------------------------------------
# format_brl — Brazilian currency formatting
# ---------------------------------------------------------------------------


class TestFormatBrl:
    """Tests for the format_brl helper."""

    def test_integer_value(self):
        assert format_brl(1000) == "R$ 1.000,00"

    def test_float_value(self):
        assert format_brl(1234.56) == "R$ 1.234,56"

    def test_zero(self):
        assert format_brl(0) == "R$ 0,00"

    def test_large_number(self):
        assert format_brl(1000000) == "R$ 1.000.000,00"

    def test_none_returns_dash(self):
        assert format_brl(None) == "—"

    def test_negative_value(self):
        result = format_brl(-1500.50)
        assert "1.500,50" in result
        assert "R$" in result

    def test_billion_value(self):
        result = format_brl(6779708728.64)
        assert "6.779.708.728,64" in result

    def test_small_decimal(self):
        assert format_brl(0.50) == "R$ 0,50"


# ---------------------------------------------------------------------------
# print_section
# ---------------------------------------------------------------------------


class TestPrintSection:
    """Tests for print_section output."""

    def test_prints_title(self, capsys):
        print_section("TESTE")
        output = capsys.readouterr().out
        assert "TESTE" in output

    def test_prints_equals_separator(self, capsys):
        print_section("T", width=20)
        output = capsys.readouterr().out
        assert "=" * 20 in output


# ---------------------------------------------------------------------------
# print_table
# ---------------------------------------------------------------------------


class TestPrintTable:
    """Tests for print_table output formatting."""

    def test_empty_rows(self, capsys):
        print_table([], ["col1", "col2"])
        output = capsys.readouterr().out
        assert "Nenhum resultado" in output

    def test_single_row(self, capsys):
        print_table([("A", 100)], ["nome", "valor"])
        output = capsys.readouterr().out
        assert "A" in output
        assert "1" in output

    def test_none_values(self, capsys):
        print_table([(None, "OK")], ["nulo", "status"])
        output = capsys.readouterr().out
        assert "—" in output
        assert "OK" in output

    def test_brl_column(self, capsys):
        print_table([("X", 1234.56)], ["nome", "valor"], brl_cols={1})
        output = capsys.readouterr().out
        assert "1.234,56" in output

    def test_record_count(self, capsys):
        print_table([("a",), ("b",), ("c",)], ["x"])
        output = capsys.readouterr().out
        assert "3 registros" in output


# ---------------------------------------------------------------------------
# SQL queries — structure validation
# ---------------------------------------------------------------------------


class TestSQLQueries:
    """Verify SQL queries are well-formed."""

    def test_perfil_has_limit(self):
        assert "LIMIT 1" in SQL_PERFIL

    def test_perfil_ilike(self):
        assert "ILIKE" in SQL_PERFIL

    def test_resumo_groups_by_parlamentar(self):
        assert "GROUP BY" in SQL_RESUMO

    def test_resumo_counts_negados(self):
        assert "REPROVADO" in SQL_RESUMO
        assert "IMPEDIDO" in SQL_RESUMO

    def test_emendas_groups_by_emenda(self):
        assert "emenda_codigo" in SQL_EMENDAS

    def test_municipios_joins_beneficiarios(self):
        assert "JOIN beneficiarios" in SQL_MUNICIPIOS

    def test_detalhe_emenda_filters_by_both(self):
        assert "ILIKE" in SQL_DETALHE_EMENDA
        assert "emenda_codigo = %s" in SQL_DETALHE_EMENDA

    def test_comparacao_uses_ranking_view(self):
        assert "v_ranking_parlamentares_enriquecido" in SQL_COMPARACAO_PARTIDO


# ---------------------------------------------------------------------------
# buscar_deputados — mock DB
# ---------------------------------------------------------------------------


class TestBuscarDeputados:
    """Tests for buscar_deputados with mocked DB."""

    @patch("src.deputado_followup.get_connection")
    def test_returns_deputado_list(self, mock_conn):
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [
            ("AFONSO FLORENCE", "PT", "BA"),
        ]
        mock_conn.return_value.cursor.return_value = mock_cur

        from src.deputado_followup import buscar_deputados

        result = buscar_deputados(mock_conn.return_value, "AFONSO")
        assert len(result) == 1
        assert result[0][0] == "AFONSO FLORENCE"

    @patch("src.deputado_followup.get_connection")
    def test_empty_result(self, mock_conn):
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = []
        mock_conn.return_value.cursor.return_value = mock_cur

        from src.deputado_followup import buscar_deputados

        result = buscar_deputados(mock_conn.return_value, "ZZZZZ")
        assert result == []


# ---------------------------------------------------------------------------
# mostrar_perfil — mock DB
# ---------------------------------------------------------------------------


class TestMostrarPerfil:
    """Tests for mostrar_perfil with mocked DB."""

    @patch("src.deputado_followup.get_connection")
    def test_found_returns_true(self, mock_conn, capsys):
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (
            "AFONSO FLORENCE",
            "PT",
            "BA",
            "Ativo",
            "Superior",
            "6199999",
            "dep@test.com",
            "http://photo.jpg",
            None,
            "Salvador",
        )
        # mock description for column names
        mock_cur.description = [
            (name,)
            for name in [
                "nome",
                "sigla_partido",
                "uf",
                "situacao",
                "escolaridade",
                "gabinete_telefone",
                "gabinete_email",
                "url_foto",
                "data_nascimento",
                "municipio_nascimento",
            ]
        ]
        mock_conn.return_value.cursor.return_value = mock_cur

        from src.deputado_followup import mostrar_perfil

        result = mostrar_perfil(mock_conn.return_value, "AFONSO FLORENCE")
        assert result is True
        output = capsys.readouterr().out
        assert "AFONSO FLORENCE" in output

    @patch("src.deputado_followup.get_connection")
    def test_not_found_returns_false(self, mock_conn):
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_conn.return_value.cursor.return_value = mock_cur

        from src.deputado_followup import mostrar_perfil

        result = mostrar_perfil(mock_conn.return_value, "ZZZZZ")
        assert result is False


# ---------------------------------------------------------------------------
# mostrar_resumo — mock DB
# ---------------------------------------------------------------------------


class TestMostrarResumo:
    """Tests for mostrar_resumo with mocked DB."""

    @patch("src.deputado_followup.get_connection")
    def test_displays_summary(self, mock_conn, capsys):
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (
            "CORONEL ULYSSES",
            24,
            15,
            20,
            16154822.99,
            673117.62,
            5,
            14,
            5,
        )
        mock_conn.return_value.cursor.return_value = mock_cur

        from src.deputado_followup import mostrar_resumo

        mostrar_resumo(mock_conn.return_value, "CORONEL ULYSSES")
        output = capsys.readouterr().out
        assert "CORONEL ULYSSES" in output
        assert "24" in output
        assert "15" in output  # emendas
        assert "R$" in output
