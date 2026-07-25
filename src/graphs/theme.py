"""
Dark Slate theme and shared constants for all charts.
"""

from __future__ import annotations

import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# DESIGN TOKENS
# ---------------------------------------------------------------------------
THEME_CARD_BG = "#1e293b"
THEME_TEXT = "#f8fafc"
THEME_GRID = "#334155"

# All Brazilian UFs + "TODOS" selector
TODAS_UFS = [
    "TODOS", "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ",
    "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]

# Situation color map
CORES_SITUACAO = {
    "CIENTE": "#3b82f6",
    "IMPEDIDO": "#ef4444",
    "IMPEDIDO_REJEICAO_PLANO_TRABALHO": "#f97316",
    "REPROVADO": "#a855f7",
    "CANCELADO": "#64748b",
    "EM_EXECUCAO": "#22c55e",
    "CONCLUIDO": "#10b981",
    "NAO_CUMPROU": "#475569",
}


def aplicar_tema(fig: go.Figure, titulo: str, altura: int = 450) -> go.Figure:
    """Apply the Dark Slate theme to a Plotly figure."""
    fig.update_layout(
        title={
            "text": f"<b>{titulo}</b>",
            "y": 0.95, "x": 0.02, "xanchor": "left",
            "font": {"size": 16, "color": THEME_TEXT},
        },
        paper_bgcolor=THEME_CARD_BG,
        plot_bgcolor=THEME_CARD_BG,
        font={"family": "Inter, sans-serif", "color": THEME_TEXT},
        height=altura,
        margin=dict(l=40, r=40, t=60, b=40),
        legend=dict(
            bgcolor="rgba(15, 23, 42, 0.7)",
            bordercolor="#475569", borderwidth=1,
            font=dict(color=THEME_TEXT, size=11),
        ),
    )
    fig.update_xaxes(gridcolor=THEME_GRID, zerolinecolor=THEME_GRID, tickfont=dict(color=THEME_TEXT))
    fig.update_yaxes(gridcolor=THEME_GRID, zerolinecolor=THEME_GRID, tickfont=dict(color=THEME_TEXT))
    return fig
