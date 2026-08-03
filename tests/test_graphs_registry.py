"""Tests for src.graphs.registry — sistema de registro de gráficos."""

from __future__ import annotations

import plotly.graph_objects as go

from src.graphs.registry import CHART_REGISTRY, ChartSpec, register_chart

# ---------------------------------------------------------------------------
# register_chart decorator
# ---------------------------------------------------------------------------


class TestRegisterChart:
    """Testes para o decorador @register_chart."""

    def test_registra_chart_no_chart_registry(self):
        """Decorar uma função deve adicionar um ChartSpec ao CHART_REGISTRY."""

        @register_chart(
            id="test_meu_grafico",
            title="Meu Grafico",
            description="Descricao do grafico de teste",
            category="Teste",
        )
        def meu_grafico() -> go.Figure:
            return go.Figure()

        assert "test_meu_grafico" in CHART_REGISTRY
        spec = CHART_REGISTRY["test_meu_grafico"]
        assert isinstance(spec, ChartSpec)
        assert spec.title == "Meu Grafico"
        assert spec.description == "Descricao do grafico de teste"
        assert spec.category == "Teste"

    def test_funcao_permanece_chamavel(self):
        """Decorador nao deve alterar o comportamento da funcao chamavel."""

        @register_chart(
            id="test_soma",
            title="Soma",
            description="Soma dois numeros",
        )  # pyright: ignore
        def soma(a: int, b: int) -> int:
            return a + b

        assert soma(2, 3) == 5

    def test_chart_registry_contem_chartspecs(self):
        """CHART_REGISTRY deve conter apenas ChartSpec como valores."""
        for nome, spec in CHART_REGISTRY.items():
            assert isinstance(spec, ChartSpec), f"{nome} nao e ChartSpec"
            assert callable(spec.builder), f"{nome}.builder nao e chamavel"

    def test_chart_registry_chaves_sao_strings(self):
        """Todas as chaves do CHART_REGISTRY devem ser strings."""
        for nome in CHART_REGISTRY:
            assert isinstance(nome, str)

    def test_chart_registry_nao_vazio(self):
        """CHART_REGISTRY deve ter pelo menos um ChartSpec registrado."""
        assert len(CHART_REGISTRY) > 0

    def test_registra_duas_funcoes(self):
        """Registrar dois charts deve manter ambos no registry."""

        @register_chart(
            id="test_grafico_a",
            title="Grafico A",
            description="Primeiro grafico",
        )
        def grafico_a() -> go.Figure:
            return go.Figure()

        @register_chart(
            id="test_grafico_b",
            title="Grafico B",
            description="Segundo grafico",
        )
        def grafico_b() -> go.Figure:
            return go.Figure()

        assert "test_grafico_a" in CHART_REGISTRY
        assert "test_grafico_b" in CHART_REGISTRY
        assert CHART_REGISTRY["test_grafico_a"].title == "Grafico A"
        assert CHART_REGISTRY["test_grafico_b"].title == "Grafico B"
