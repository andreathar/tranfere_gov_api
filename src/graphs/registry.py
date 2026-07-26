"""
Registry infrastructure for chart management.

Provides the CHART_REGISTRY dict and the @register_chart decorator.
All chart modules register themselves by importing and using these.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import plotly.graph_objects as go


@dataclass
class ControlSpec:
    """Interactive filter control for a chart."""

    id: str
    label: str
    options: list[str]
    default: str


@dataclass
class ChartSpec:
    """Complete specification for a registered chart."""

    id: str
    title: str
    description: str
    category: str
    builder: Callable[..., go.Figure]
    controls: list[ControlSpec] = field(default_factory=list)


# Global registry — populated by @register_chart decorators
CHART_REGISTRY: dict[str, ChartSpec] = {}


def register_chart(
    id: str,
    title: str,
    description: str,
    category: str = "Geral",
    controls: list[ControlSpec] | None = None,
):
    """
    Decorator to register a Plotly chart builder.

    Charts registered this way are automatically:
      1. Added to the Dash web interface.
      2. Exposed as MCP tools at /_mcp for AI agents.
      3. Styled with the default Dark Slate theme.
    """

    def decorator(fn: Callable[..., go.Figure]):
        spec = ChartSpec(
            id=id,
            title=title,
            description=description,
            category=category,
            builder=fn,
            controls=controls or [],
        )
        CHART_REGISTRY[id] = spec
        return fn

    return decorator
