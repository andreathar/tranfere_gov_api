"""
TransfereGov Graphs Package.

Módulos organizados por domínio para cada grupo de gráficos.
O registro global CHART_REGISTRY é populado automaticamente via
decoradores @register_chart em cada módulo ao importar este package.

Uso:
    from src.graphs import CHART_REGISTRY, aplicar_tema, register_chart
"""

# Importar registry e tema (infraestrutura)
import src.graphs.analitico  # noqa: F401, E501
import src.graphs.arrecadacao  # noqa: F401, E501
import src.graphs.economia_cruzada  # noqa: F401, E501
import src.graphs.economico  # noqa: F401, E501
import src.graphs.financas  # noqa: F401, E501
import src.graphs.fiscal  # noqa: F401, E501
import src.graphs.geoespacial  # noqa: F401, E501
import src.graphs.hierarquico  # noqa: F401, E501
import src.graphs.impacto_social  # noqa: F401, E501

# Importar todos os módulos de gráficos para executar os @register_chart.
# Cada módulo, ao ser importado, registra seus gráficos no CHART_REGISTRY.
import src.graphs.parlamentar  # noqa: F401, E501
import src.graphs.prefeitos  # noqa: F401, E501
import src.graphs.radar_diario  # noqa: F401, E501
import src.graphs.intel_proposicoes  # noqa: F401, E501
import src.graphs.siconfi  # noqa: F401, E501
import src.graphs.socioeconomico  # noqa: F401, E501
from src.graphs.registry import (
    CHART_REGISTRY,
    ChartSpec,
    ControlSpec,
    register_chart,
)
from src.graphs.theme import CORES_SITUACAO, THEME_CARD_BG, TODAS_UFS, aplicar_tema

__all__ = [
    "CHART_REGISTRY",
    "ChartSpec",
    "ControlSpec",
    "register_chart",
    "aplicar_tema",
    "CORES_SITUACAO",
    "TODAS_UFS",
    "THEME_CARD_BG",
]
