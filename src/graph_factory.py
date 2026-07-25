#!/usr/bin/env python3
"""
TransfereGov — Graph Factory (backward-compat shim).

Este módulo é um shim de compatibilidade que redireciona todos os imports
para o novo pacote `src.graphs`, onde os gráficos estão organizados por
domínio em módulos separados (parlamentar, fiscal, siconfi, etc.).

Arquivo original: ~1889 linhas (monolito com 31 gráficos).
Arquivo atual: shim de 15 linhas que preserva 100% da API pública.

Para adicionar novos gráficos, crie um módulo em src/graphs/ e use
o decorador @register_chart — ele será importado automaticamente.
"""

# Re-exportar infraestrutura pública (tokens, decorator, registry, dataclasses)
from src.graphs import (  # noqa: F401
    CHART_REGISTRY,
    ChartSpec,
    ControlSpec,
    CORES_SITUACAO,
    TODAS_UFS,
    THEME_CARD_BG,
    aplicar_tema,
    register_chart,
)
