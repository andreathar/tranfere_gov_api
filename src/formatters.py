"""
formatters — Funções de formatação para BRL, numéricos, porcentagens e acentos.

Substitui as 18+ cópias espalhadas de fmt_brl/fmt_num/fmt_pct/format_brl.
Centraliza strip_accents() para uso em todos os enrichers e dashboards.
"""

from __future__ import annotations

import unicodedata

import pandas as pd


def strip_accents(s: str | None) -> str:
    """Remove acentos de uma string (NFKD decomposition + strip combining).

    Usa o mesmo algoritmo da função f_unaccent() do PostgreSQL (migration 021)
    para consistência entre Python e SQL.

    Args:
        s: String com possíveis acentos (ex: "João", "São Paulo")

    Returns:
        String sem acentos em lowercase (ex: "joao", "sao paulo")
    """
    if s is None:
        return ""
    return (
        "".join(
            c for c in unicodedata.normalize("NFKD", str(s)) if unicodedata.category(c) != "Mn"
        )
        .lower()
        .replace("  ", " ")
        .strip()
    )


def fmt_brl(valor) -> str:
    """Formata valor como R$ brasileiro (ex: R$ 1.234.567,89).

    Aceita float, int, Decimal, None, NaN.
    """
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return "R$ 0"
    try:
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "R$ 0"


def format_brl(value) -> str:
    """Formata valor como R$ brasileiro — retorna '—' para None/NA.

    Variante para uso em relatórios/texto (em vez de 'R$ 0').
    """
    if value is None or pd.isna(value):
        return "—"

    try:
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "—"


def fmt_num(valor) -> str:
    """Formata número com separador de milhar brasileiro (ex: 1.234.567).

    Aceita float, int, None, NaN.
    """
    if valor is None or pd.isna(valor):
        return "0"
    try:
        return f"{int(valor):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"


def fmt_pct(valor) -> str:
    """Formata porcentagem com 1 casa decimal (ex: 45,2%).

    Aceita float, int, None, NaN.
    """
    if valor is None or pd.isna(valor):
        return "0%"
    try:
        return f"{float(valor):.1f}%".replace(".", ",")
    except (ValueError, TypeError):
        return "0%"
