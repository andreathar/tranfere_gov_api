"""Tests for src.transferegov_extract — pure utility functions."""

from __future__ import annotations

import pandas as pd

from src.transferegov_extract import format_brl, parse_page

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

    def test_nan_returns_dash(self):
        assert format_brl(float("nan")) == "—"

    def test_pandas_na_returns_dash(self):
        assert format_brl(pd.NA) == "—"

    def test_negative_value(self):
        result = format_brl(-1500.50)
        assert "1.500,50" in result
        assert "R$" in result

    def test_string_raises_returns_dash(self):
        # format_brl tries float() on strings — "abc" should fail gracefully
        assert format_brl("abc") == "—"


# ---------------------------------------------------------------------------
# parse_page — API response parsing
# ---------------------------------------------------------------------------


class TestParsePage:
    """Tests for the parse_page helper."""

    def test_none_returns_empty(self):
        records, total = parse_page(None)
        assert records == []
        assert total == 0

    def test_list_response(self):
        data = [{"id": 1}, {"id": 2}]
        records, total = parse_page(data)
        assert records == data
        assert total == 2

    def test_dict_with_listaPlanosAcao(self):
        body = {"total": 42, "listaPlanosAcao": [{"id": 1}]}
        records, total = parse_page(body)
        assert records == [{"id": 1}]
        assert total == 42

    def test_dict_with_data_key(self):
        body = {"total": 10, "data": [{"id": 1}]}
        records, total = parse_page(body)
        assert records == [{"id": 1}]
        assert total == 10

    def test_dict_with_content_key(self):
        body = {"total": 5, "content": [{"id": 1}]}
        records, total = parse_page(body)
        assert records == [{"id": 1}]
        assert total == 5

    def test_dict_with_items_key(self):
        body = {"total": 3, "items": [{"id": 1}]}
        records, total = parse_page(body)
        assert records == [{"id": 1}]
        assert total == 3

    def test_dict_with_no_known_key(self):
        body = {"total": 0, "unknown": [1, 2, 3]}
        records, total = parse_page(body)
        assert records == []
        assert total == 0

    def test_empty_dict(self):
        records, total = parse_page({})
        assert records == []
        assert total == 0

    def test_dict_without_total(self):
        body = {"listaPlanosAcao": [{"id": 1}]}
        records, total = parse_page(body)
        assert records == [{"id": 1}]
        assert total == 0

    def test_unexpected_type_returns_empty(self):
        records, total = parse_page(42)
        assert records == []
        assert total == 0
