"""Tests for src.schemas — Pydantic validation of PlanoAcao."""

from __future__ import annotations

import pytest

from src.schemas import PlanoAcaoSchema, validate_records

# ---------------------------------------------------------------------------
# PlanoAcaoSchema — construction & validation
# ---------------------------------------------------------------------------

class TestPlanoAcaoSchema:
    """Unit tests for the PlanoAcaoSchema model."""

    MINIMAL_VALID = {"planoAcaoId": 1}

    def test_minimal_valid_record(self):
        plano = PlanoAcaoSchema.model_validate(self.MINIMAL_VALID)
        assert plano.planoAcaoId == 1
        assert plano.planoAcaoSituacao == ""
        assert plano.valorTotal == 0.0

    def test_missing_plano_acao_id_raises(self):
        with pytest.raises(Exception, match="Field required"):
            PlanoAcaoSchema.model_validate({})

    def test_uf_normalized_to_upper(self):
        plano = PlanoAcaoSchema.model_validate(
            {**self.MINIMAL_VALID, "uf": "  al  "}
        )
        assert plano.uf == "AL"

    def test_uf_none_becomes_empty(self):
        plano = PlanoAcaoSchema.model_validate(
            {**self.MINIMAL_VALID, "uf": None}
        )
        assert plano.uf == ""

    def test_valor_custeio_from_string(self):
        plano = PlanoAcaoSchema.model_validate(
            {**self.MINIMAL_VALID, "valorCusteio": "1.234,56"}
        )
        assert plano.valorCusteio == pytest.approx(1234.56)

    def test_valor_investimento_from_string_brl(self):
        plano = PlanoAcaoSchema.model_validate(
            {**self.MINIMAL_VALID, "valorInvestimento": "10.000,00"}
        )
        assert plano.valorInvestimento == pytest.approx(10000.0)

    def test_valor_none_defaults_to_zero(self):
        plano = PlanoAcaoSchema.model_validate(
            {**self.MINIMAL_VALID, "valorTotal": None}
        )
        assert plano.valorTotal == 0.0

    def test_valor_invalid_string_defaults_to_zero(self):
        plano = PlanoAcaoSchema.model_validate(
            {**self.MINIMAL_VALID, "valorCusteio": "abc"}
        )
        assert plano.valorCusteio == 0.0

    def test_extra_fields_ignored(self):
        plano = PlanoAcaoSchema.model_validate(
            {**self.MINIMAL_VALID, "unknownField": "value", "another": 42}
        )
        assert plano.planoAcaoId == 1

    def test_is_negado_true(self):
        for sit in ("REPROVADO", "IMPEDIDO", "CANCELADO", "NAO_CUMPROU"):
            plano = PlanoAcaoSchema.model_validate(
                {**self.MINIMAL_VALID, "planoAcaoSituacao": sit}
            )
            assert plano.is_negado is True, f"Expected is_negado for {sit}"

    def test_is_negado_false(self):
        for sit in ("CIENTE", "APROVADO", "EM_EXECUCAO", "CONCLUIDO"):
            plano = PlanoAcaoSchema.model_validate(
                {**self.MINIMAL_VALID, "planoAcaoSituacao": sit}
            )
            assert plano.is_negado is False, f"Expected NOT is_negado for {sit}"

    def test_valor_total_real_sum(self):
        plano = PlanoAcaoSchema.model_validate(
            {**self.MINIMAL_VALID, "valorCusteio": 100.0, "valorInvestimento": 200.0}
        )
        assert plano.valor_total_real == pytest.approx(300.0)

    def test_full_record(self):
        data = {
            "planoAcaoId": 12345,
            "planoAcaoCodigo": "202600012345",
            "planoAcaoSituacao": "EM_EXECUCAO",
            "objetoId": 301,
            "objetoDescricao": "Cemitérios",
            "programaId": 25,
            "beneficiarioId": 9858,
            "beneficiarioNome": "Município de Teste",
            "beneficiarioCnpj": "12345678000190",
            "uf": "AL",
            "valorCusteio": 50000.0,
            "valorInvestimento": 100000.0,
            "valorTotal": 150000.0,
        }
        plano = PlanoAcaoSchema.model_validate(data)
        assert plano.planoAcaoId == 12345
        assert plano.uf == "AL"
        assert plano.valor_total_real == pytest.approx(150000.0)
        assert plano.is_negado is False


# ---------------------------------------------------------------------------
# validate_records — batch validation
# ---------------------------------------------------------------------------

class TestValidateRecords:
    """Tests for the validate_records helper."""

    def test_valid_records_returned(self):
        records = [
            {"planoAcaoId": 1, "uf": "SP"},
            {"planoAcaoId": 2, "uf": "RJ"},
        ]
        validos, erros = validate_records(records)
        assert len(validos) == 2
        assert len(erros) == 0

    def test_invalid_record_skipped_in_non_strict(self):
        records = [
            {"planoAcaoId": 1},
            {"no_id_field": True},  # missing required field
            {"planoAcaoId": 3},
        ]
        validos, erros = validate_records(records, strict=False)
        assert len(validos) == 2
        assert len(erros) == 1
        assert "Registro 1" in erros[0]

    def test_strict_mode_raises_on_invalid(self):
        records = [
            {"planoAcaoId": 1},
            {"bad": "record"},
        ]
        with pytest.raises(ValueError, match="Registro 1"):
            validate_records(records, strict=True)

    def test_empty_list(self):
        validos, erros = validate_records([])
        assert validos == []
        assert erros == []

    def test_all_invalid(self):
        records = [{"bad": 1}, {"bad": 2}]
        validos, erros = validate_records(records)
        assert len(validos) == 0
        assert len(erros) == 2
