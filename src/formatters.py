"""
formatters — Funções de formatação para BRL, numéricos e porcentagens.

Substitui as 18+ cópias espalhadas de fmt_brl/fmt_num/fmt_pct/format_brl.
"""

from __future__ import annotations

import pandas as pd


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
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return "0"
    return f"{int(valor):,}".replace(",", ".")


def fmt_pct(valor) -> str:
    """Formata porcentagem com 1 casa decimal (ex: 45,2%).

    Aceita float, int, None, NaN.
    """
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return "0%"
    return f"{valor:.1f}%"
