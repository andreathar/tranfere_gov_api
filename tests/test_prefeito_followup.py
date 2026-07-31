"""
Tests for src.prefeito_followup — CLI de Inteligência de Prefeitos.

Tests pure formatting functions and DB-dependent functions with mocks.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.prefeito_followup import buscar_prefeitos, mostrar_perfil_prefeito, mostrar_ranking_prefeitos

# ---------------------------------------------------------------------------
# buscar_prefeitos — mock DB
# ---------------------------------------------------------------------------


class TestBuscarPrefeitos:
    """Tests for buscar_prefeitos with mocked DB."""

    @patch("src.prefeito_followup.get_connection")
    def test_returns_prefeito_list(self, mock_conn):
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [
            (2700300, "Maceió", "AL", "JOÃO HENRIQUE", "PP", 5000000.0),
        ]
        mock_conn.return_value.cursor.return_value = mock_cur

        result = buscar_prefeitos("Maceió")
        assert len(result) == 1
        assert result[0][1] == "Maceió"
        assert result[0][3] == "JOÃO HENRIQUE"

    @patch("src.prefeito_followup.get_connection")
    def test_empty_result(self, mock_conn):
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = []
        mock_conn.return_value.cursor.return_value = mock_cur

        result = buscar_prefeitos("ZZZZZ")
        assert result == []

    @patch("src.prefeito_followup.get_connection")
    def test_search_calls_ilike_both_columns(self, mock_conn):
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = []
        mock_conn.return_value.cursor.return_value = mock_cur

        buscar_prefeitos("Amapá")
        called_sql = mock_cur.execute.call_args[0][0]
        assert "UPPER(municipio_nome) LIKE" in called_sql
        assert "UPPER(prefeito_nome) LIKE" in called_sql

    @patch("src.prefeito_followup.get_connection")
    def test_closes_connection(self, mock_conn):
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = []
        mock_conn.return_value.cursor.return_value = mock_cur

        buscar_prefeitos("Teste")
        mock_conn.return_value.close.assert_called_once()


# ---------------------------------------------------------------------------
# mostrar_perfil_prefeito — mock DB
# ---------------------------------------------------------------------------


class TestMostrarPerfilPrefeito:
    """Tests for mostrar_perfil_prefeito with mocked DB."""

    @patch("src.prefeito_followup.get_connection")
    def test_found_returns_true(self, mock_conn, capsys):
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (
            2700300,  # municipio_id
            "Maceió",  # municipio_nome
            "AL",  # uf
            "JOÃO HENRIQUE",  # prefeito_nome
            "PP",  # prefeito_partido
            2024,  # ano_eleicao
            "ELEITO",  # situacao_candidatura
            None,  # coligacao
            "Nordeste",  # ibge_regiao
            957916,  # ibge_populacao
            0.721,  # ibge_idhm
            2500000.0,  # siconfi_receitas_correntes
            2200000.0,  # siconfi_despesas_correntes
            65.5,  # siconfi_autonomia_fiscal_pct
            50,  # total_emendas_recebidas
            15000000.0,  # valor_total_emendas
            12000000.0,  # valor_emendas_aprovadas
            3000000.0,  # valor_emendas_impedidas
            15.66,  # emendas_per_capita
        )
        mock_conn.return_value.cursor.return_value = mock_cur

        result = mostrar_perfil_prefeito("Maceió")
        assert result is True
        output = capsys.readouterr().out
        assert "Maceió" in output
        assert "JOÃO HENRIQUE" in output
        assert "PP" in output
        assert "R$" in output
        assert "Nordeste" in output

    @patch("src.prefeito_followup.get_connection")
    def test_not_found_returns_false(self, mock_conn):
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_conn.return_value.cursor.return_value = mock_cur

        result = mostrar_perfil_prefeito("ZZZZZ")
        assert result is False

    @patch("src.prefeito_followup.get_connection")
    def test_displays_top_deputados(self, mock_conn, capsys):
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (
            2700300,
            "Maceió",
            "AL",
            "JOÃO HENRIQUE",
            "PP",
            2024,
            "ELEITO",
            None,
            "Nordeste",
            957916,
            0.721,
            2500000.0,
            2200000.0,
            65.5,
            50,
            15000000.0,
            12000000.0,
            3000000.0,
            15.66,
        )
        # Source query order: deputados(3) → licitacoes(7) → ganhadores(4)
        mock_cur.fetchall.side_effect = [
            [("Deputado A", 10, 5000000.0)],
            [("123/2024", "Pregão", "Obra", 500000.0, "Homologado", "Construtora Y", None)],
            [("Empresa X", "12.345.678/0001-90", 5, 2000000.0)],
        ]
        mock_conn.return_value.cursor.return_value = mock_cur

        mostrar_perfil_prefeito("Maceió")
        output = capsys.readouterr().out
        assert "Deputado A" in output
        assert "TOP DEPUTADOS" in output or "PARCEIROS" in output

    @patch("src.prefeito_followup.get_connection")
    def test_displays_top_fornecedores(self, mock_conn, capsys):
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (
            2700300,
            "Maceió",
            "AL",
            "JOÃO HENRIQUE",
            "PP",
            2024,
            "ELEITO",
            None,
            "Nordeste",
            957916,
            0.721,
            2500000.0,
            2200000.0,
            65.5,
            50,
            15000000.0,
            12000000.0,
            3000000.0,
            15.66,
        )
        mock_cur.fetchall.side_effect = [
            [("Deputado A", 10, 5000000.0)],
            [("123/2024", "Pregão", "Obra", 500000.0, "Homologado", "Construtora Y", None)],
            [("Empresa X", "12.345.678/0001-90", 5, 2000000.0)],
        ]
        mock_conn.return_value.cursor.return_value = mock_cur

        mostrar_perfil_prefeito("Maceió")
        output = capsys.readouterr().out
        assert "Empresa X" in output
        assert "12.345.678/0001-90" in output

    @patch("src.prefeito_followup.get_connection")
    def test_displays_licitacoes(self, mock_conn, capsys):
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (
            2700300,
            "Maceió",
            "AL",
            "JOÃO HENRIQUE",
            "PP",
            2024,
            "ELEITO",
            None,
            "Nordeste",
            957916,
            0.721,
            2500000.0,
            2200000.0,
            65.5,
            50,
            15000000.0,
            12000000.0,
            3000000.0,
            15.66,
        )
        mock_cur.fetchall.side_effect = [
            [],  # deputados (empty)
            [  # licitacoes — 7 cols
                ("123/2024", "Pregão", "Obra", 500000.0, "Homologado", "Construtora Y", None),
            ],
            [],  # ganhadores (empty)
        ]
        mock_conn.return_value.cursor.return_value = mock_cur

        mostrar_perfil_prefeito("Maceió")
        output = capsys.readouterr().out
        assert "123/2024" in output
        assert "Pregão" in output
        assert "Construtora Y" in output

    @patch("src.prefeito_followup.get_connection")
    def test_closes_connection(self, mock_conn):
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_conn.return_value.cursor.return_value = mock_cur

        mostrar_perfil_prefeito("ZZZZZ")
        mock_conn.return_value.close.assert_called_once()


# ---------------------------------------------------------------------------
# mostrar_ranking_prefeitos — mock DB
# ---------------------------------------------------------------------------


class TestMostrarRankingPrefeitos:
    """Tests for mostrar_ranking_prefeitos with mocked DB."""

    @patch("src.prefeito_followup.get_connection")
    def test_displays_ranking(self, mock_conn, capsys):
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [
            ("Maceió", "AL", "JOÃO HENRIQUE", "PP", 957916, 15000000.0, 15.66),
            ("Rio Largo", "AL", "FÁBIO", "MDB", 50000, 3000000.0, 60.0),
        ]
        mock_conn.return_value.cursor.return_value = mock_cur

        mostrar_ranking_prefeitos(limit=2)
        output = capsys.readouterr().out
        assert "Maceió" in output
        assert "Rio Largo" in output
        assert "JOÃO HENRIQUE" in output
        assert "R$" in output
        assert "TOP 2" in output

    @patch("src.prefeito_followup.get_connection")
    def test_default_limit(self, mock_conn, capsys):
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = []
        mock_conn.return_value.cursor.return_value = mock_cur

        mostrar_ranking_prefeitos()
        called_sql = mock_cur.execute.call_args[0][0]
        assert "LIMIT" in called_sql.upper()
        # Default limit is 15
        assert 15 == mock_cur.execute.call_args[0][1][0]

    @patch("src.prefeito_followup.get_connection")
    def test_empty_ranking(self, mock_conn, capsys):
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = []
        mock_conn.return_value.cursor.return_value = mock_cur

        mostrar_ranking_prefeitos()
        output = capsys.readouterr().out
        # Still shows header even if empty
        assert "RANKING" in output
