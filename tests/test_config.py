"""Tests for config.settings — centralized configuration."""

from __future__ import annotations

from config.settings import (
    API_URL_LISTAGEM,
    DATABASE_URL,
    DEFAULT_PAGE_SIZE,
    DEFAULT_TIMEOUT,
    HEADERS,
    MAX_RETRIES,
    OUTPUT_CSV,
    OUTPUT_DIR,
    OUTPUT_JSON,
    OUTPUT_LOGS,
    OUTPUT_XLSX,
    PG_HOST,
    PG_PORT,
    PROJECT_ROOT,
    RETRY_BACKOFF,
    SITUACOES_CONHECIDAS,
    SITUACOES_NEGADAS,
    SITUACOES_TRANSFEREGOV,
    SLEEP_BETWEEN_PAGES,
)


class TestProjectPaths:
    """Verify project path constants."""

    def test_project_root_is_directory(self):
        assert PROJECT_ROOT.is_dir()

    def test_output_dirs_exist(self):
        for d in (OUTPUT_DIR, OUTPUT_XLSX, OUTPUT_CSV, OUTPUT_JSON, OUTPUT_LOGS):
            assert d.exists(), f"{d} should exist"

    def test_output_dirs_are_under_project_root(self):
        for d in (OUTPUT_DIR, OUTPUT_XLSX, OUTPUT_CSV, OUTPUT_JSON, OUTPUT_LOGS):
            assert str(d).startswith(str(PROJECT_ROOT))


class TestAPIConfig:
    """Verify API configuration constants."""

    def test_api_url_is_https(self):
        assert API_URL_LISTAGEM.startswith("https://")

    def test_api_url_contains_listagem(self):
        assert "listagem" in API_URL_LISTAGEM

    def test_headers_has_user_agent(self):
        assert "User-Agent" in HEADERS

    def test_headers_has_accept(self):
        assert "Accept" in HEADERS

    def test_page_size_positive(self):
        assert DEFAULT_PAGE_SIZE > 0

    def test_timeout_positive(self):
        assert DEFAULT_TIMEOUT > 0

    def test_max_retries_positive(self):
        assert MAX_RETRIES > 0

    def test_backoff_greater_than_one(self):
        assert RETRY_BACKOFF > 1.0

    def test_sleep_non_negative(self):
        assert SLEEP_BETWEEN_PAGES >= 0


class TestSituacoes:
    """Verify situation sets are consistent."""

    def test_negadas_is_subset_of_conhecidas(self):
        assert SITUACOES_NEGADAS.issubset(SITUACOES_CONHECIDAS)

    def test_negadas_contains_impedido(self):
        assert "IMPEDIDO" in SITUACOES_NEGADAS

    def test_negadas_contains_reprovado(self):
        assert "REPROVADO" in SITUACOES_NEGADAS

    def test_negadas_contains_cancelado(self):
        assert "CANCELADO" in SITUACOES_NEGADAS

    def test_negadas_contains_nao_cumprou(self):
        assert "NAO_CUMPROU" in SITUACOES_NEGADAS

    def test_transferegov_contains_all_conhecidas(self):
        # SITUACOES_TRANSFEREGOV may have more, but must contain core ones
        core = {"CIENTE", "IMPEDIDO", "CANCELADO", "EM_EXECUCAO", "CONCLUIDO"}
        assert core.issubset(SITUACOES_TRANSFEREGOV)


class TestDatabaseConfig:
    """Verify database configuration defaults."""

    def test_pg_host_default(self):
        # Should be set (either from env or default)
        assert PG_HOST

    def test_pg_port_is_int(self):
        assert isinstance(PG_PORT, int)

    def test_pg_port_valid(self):
        assert 1 <= PG_PORT <= 65535

    def test_database_url_format(self):
        assert DATABASE_URL.startswith("postgresql://")

    def test_database_url_contains_host(self):
        assert PG_HOST in DATABASE_URL
