"""Tests for CPF, CNPJ, and CEP validators."""

import pytest

from mcp_brasil._shared.validators import (
    format_cep,
    format_cnpj,
    format_cpf,
    validate_cep,
    validate_cnpj,
    validate_cpf,
)

# ---------------------------------------------------------------------------
# CPF
# ---------------------------------------------------------------------------


class TestValidateCPF:
    def test_valid_cpf(self) -> None:
        assert validate_cpf("529.982.247-25") is True

    def test_valid_cpf_digits_only(self) -> None:
        assert validate_cpf("52998224725") is True

    def test_invalid_cpf_wrong_digits(self) -> None:
        assert validate_cpf("529.982.247-26") is False

    def test_invalid_cpf_all_same(self) -> None:
        assert validate_cpf("111.111.111-11") is False
        assert validate_cpf("000.000.000-00") is False

    def test_invalid_cpf_too_short(self) -> None:
        assert validate_cpf("123456") is False

    def test_invalid_cpf_too_long(self) -> None:
        assert validate_cpf("123456789012") is False

    def test_another_valid_cpf(self) -> None:
        assert validate_cpf("111.444.777-35") is True

    def test_classic_valid_cpf(self) -> None:
        assert validate_cpf("123.456.789-09") is True


class TestFormatCPF:
    def test_formats_digits(self) -> None:
        assert format_cpf("52998224725") == "529.982.247-25"

    def test_formats_already_formatted(self) -> None:
        assert format_cpf("529.982.247-25") == "529.982.247-25"

    def test_raises_wrong_length(self) -> None:
        with pytest.raises(ValueError, match="11 digits"):
            format_cpf("123")


# ---------------------------------------------------------------------------
# CNPJ
# ---------------------------------------------------------------------------


class TestValidateCNPJ:
    def test_valid_cnpj(self) -> None:
        assert validate_cnpj("11.222.333/0001-81") is True

    def test_valid_cnpj_digits_only(self) -> None:
        assert validate_cnpj("11222333000181") is True

    def test_invalid_cnpj_wrong_digits(self) -> None:
        assert validate_cnpj("11.222.333/0001-82") is False

    def test_invalid_cnpj_all_same(self) -> None:
        assert validate_cnpj("11111111111111") is False

    def test_invalid_cnpj_too_short(self) -> None:
        assert validate_cnpj("123456") is False

    def test_invalid_cnpj_too_long(self) -> None:
        assert validate_cnpj("123456789012345") is False

    def test_another_valid_cnpj(self) -> None:
        assert validate_cnpj("00.394.460/0001-41") is True


class TestFormatCNPJ:
    def test_formats_digits(self) -> None:
        assert format_cnpj("11222333000181") == "11.222.333/0001-81"

    def test_formats_already_formatted(self) -> None:
        assert format_cnpj("11.222.333/0001-81") == "11.222.333/0001-81"

    def test_raises_wrong_length(self) -> None:
        with pytest.raises(ValueError, match="14 digits"):
            format_cnpj("123")


# ---------------------------------------------------------------------------
# CEP
# ---------------------------------------------------------------------------


class TestValidateCEP:
    def test_valid_cep(self) -> None:
        assert validate_cep("01001-000") is True

    def test_valid_cep_digits_only(self) -> None:
        assert validate_cep("01001000") is True

    def test_invalid_cep_all_zeros(self) -> None:
        assert validate_cep("00000-000") is False

    def test_invalid_cep_too_short(self) -> None:
        assert validate_cep("01001") is False

    def test_invalid_cep_too_long(self) -> None:
        assert validate_cep("010010001") is False


class TestFormatCEP:
    def test_formats_digits(self) -> None:
        assert format_cep("01001000") == "01001-000"

    def test_formats_already_formatted(self) -> None:
        assert format_cep("01001-000") == "01001-000"

    def test_raises_wrong_length(self) -> None:
        with pytest.raises(ValueError, match="8 digits"):
            format_cep("123")
