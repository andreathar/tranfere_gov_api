"""Formatting helpers for LLM-friendly output.

Provides functions to format data as Markdown tables,
formatted numbers (BRL currency, percentages), and lists.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    """Format data as a Markdown table.

    Args:
        headers: Column headers.
        rows: List of rows (each row is a sequence of values).

    Returns:
        Markdown-formatted table string.
    """
    if not rows:
        return "Nenhum resultado encontrado."

    header_line = "| " + " | ".join(str(h) for h in headers) + " |"
    separator = "| " + " | ".join("---" for _ in headers) + " |"
    body_lines = ["| " + " | ".join(str(v) for v in row) + " |" for row in rows]

    return "\n".join([header_line, separator, *body_lines])


def format_brl(value: float) -> str:
    """Format a number as Brazilian Real currency.

    Args:
        value: Numeric value.

    Returns:
        Formatted string like "R$ 1.234,56".
    """
    formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def format_number_br(value: float, decimals: int = 2) -> str:
    """Format a number with Brazilian locale (dot as thousands, comma as decimal).

    Args:
        value: Numeric value.
        decimals: Number of decimal places.

    Returns:
        Formatted string like "1.234,56".
    """
    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def format_percent(value: float, decimals: int = 2) -> str:
    """Format a number as percentage.

    Args:
        value: Numeric value (e.g., 0.05 for 5%).

    Returns:
        Formatted string like "5,00%".
    """
    return f"{format_number_br(value * 100, decimals)}%"


def parse_brl_number(value: Any) -> float | None:
    """Parse a Brazilian-formatted number string into a float.

    Handles strings like "348.600,00" (dot=thousands, comma=decimal).
    Passes through int/float values unchanged.

    Args:
        value: Raw value from API (string, int, float, or None).

    Returns:
        Parsed float or None if unparseable.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace(".", "").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def truncate_list(items: Sequence[str], max_items: int = 50) -> str:
    """Join items with newlines, truncating if too many.

    Args:
        items: List of strings.
        max_items: Maximum items to show before truncating.

    Returns:
        Joined string with truncation notice if needed.
    """
    if len(items) <= max_items:
        return "\n".join(items)

    shown = items[:max_items]
    remaining = len(items) - max_items
    return "\n".join(shown) + f"\n\n... e mais {remaining} resultados."
