"""Testes para o parser de valores monetários (R$) do QC multi-analista.

Regressão do fix 2026-07-31: parse_brl_token não tratava formatos mistos
(US milhar + BR decimal) nem milhar BR sem decimal, gerando falsos positivos
de "invenção" no taxa_invencao_rs (penalizava dossiers corretos).
"""

import pytest

from src.analysts.base import coletar_valores_rs, parse_brl_token, taxa_invencao_rs

# Type helpers usados nas anotações das funções de teste
# (pytest/mypy: funções de teste devem ter retorno anotado)


@pytest.mark.parametrize(
    "raw, esperado",
    [
        # Formatos canônicos (não podem quebrar)
        ("1.234.567,89", 1234567.89),  # BR clássico
        ("1,234,567.89", 1234567.89),  # US clássico
        ("5.400.000,0", 5400000.0),  # BR sem 2 casas
        ("1234567", 1234567.0),  # inteiro puro
        ("123,45", 123.45),  # vírgula única decimal
        ("1.234", 1.234),  # 1 ponto = decimal (mantém comportamento)
        ("40,443,658.00", 40443658.0),  # US real (chunk)
        # Formatos que motivaram o fix
        ("40,443,658,00", 40443658.0),  # misto US milhar + BR decimal
        ("40.443.658", 40443658.0),  # BR milhar sem decimal
        ("5,444,39", 5444.39),  # per-capita BR (2 vírgulas)
        ("1,234,567", 1234567.0),  # US milhar sem decimal
    ],
)
def test_parse_brl_token(raw: str, esperado: float) -> None:
    assert parse_brl_token(raw) == pytest.approx(esperado)


def test_parse_brl_token_invalidos() -> None:
    assert parse_brl_token("abc") is None
    assert parse_brl_token("") is None
    assert parse_brl_token("12a,34") is None


def test_coletar_valores_rs() -> None:
    texto = "Custo R$ 1.234,56 e outro R$ 40,443,658,00 no total."
    vals = coletar_valores_rs(texto)
    assert vals == pytest.approx([1234.56, 40443658.0])


def test_taxa_invencao_mesmo_valor_formatos_diferentes() -> None:
    """Chunk US e output misto representam o MESMO valor -> nao e invencao."""
    chunk = "[EMENDA] ... R$ 40,443,658.00 (12 emenda(s))"
    out = "| ... | R$ 40,443,658,00 |"
    assert taxa_invencao_rs(out, chunk) == 0.0


def test_taxa_invencao_detecta_fabricacao() -> None:
    """Valor que nao existe no chunk deve ser detectado como invencao."""
    chunk = "[EMENDA] ... R$ 1.000,00 ..."
    out = "| R$ 40,443,658,00 |"
    assert taxa_invencao_rs(out, chunk) == 1.0


def test_taxa_invencao_sem_r_no_output() -> None:
    assert taxa_invencao_rs("sem valores monetarios", "[EMENDA] R$ 1.000,00") == 0.0


def test_taxa_invencao_sem_r_no_chunk() -> None:
    """Sem valores no chunk, nao ha como acusar invencao."""
    assert taxa_invencao_rs("R$ 5.000,00", "[EMENDA] sem valores") == 0.0


def test_briefing_fallback_nao_e_considerado_valido() -> None:
    from src.analysts.preparer import PromptPreparer

    fallback = PromptPreparer._build_fallback(["[EMENDA] R$ 1.000,00"])

    assert fallback.raw_fallback is True
    assert fallback.validation_pass is False
    assert fallback.is_useful is False
