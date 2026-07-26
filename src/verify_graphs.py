#!/usr/bin/env python3
"""
TransfereGov — Suite de Verificação Integrativa de Gráficos (Plotly + Dash + MCP).

Verifica se todos os gráficos registrados em `CHART_REGISTRY` funcionam sem erros
e contêm dados válidos e não-nulos para exibição web e MCP.

Uso:
    python3 src/verify_graphs.py
"""

import logging
import sys
import time
from typing import Any

import plotly.graph_objects as go

from src.graph_factory import CHART_REGISTRY

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("verify_graphs")

def verify_single_chart(chart_id: str, spec: Any) -> tuple[bool, int, int, float, str]:
    """
    Testa um único gráfico e calcula métricas de saúde.
    
    Retorna: (is_ok, num_traces, total_data_points, elapsed_ms, error_msg)
    """
    start_time = time.time()
    try:
        fig = spec.builder()
        elapsed_ms = (time.time() - start_time) * 1000

        if not isinstance(fig, go.Figure):
            return False, 0, 0, elapsed_ms, "O retorno não é um objeto plotly.graph_objects.Figure"

        num_traces = len(fig.data)
        total_data_points = 0

        for trace in fig.data:
            x_len = len(trace.x) if hasattr(trace, 'x') and trace.x is not None else 0
            y_len = len(trace.y) if hasattr(trace, 'y') and trace.y is not None else 0
            val_len = len(trace.values) if hasattr(trace, 'values') and trace.values is not None else 0
            z_len = len(trace.z) if hasattr(trace, 'z') and trace.z is not None else 0
            loc_len = len(trace.locations) if hasattr(trace, 'locations') and trace.locations is not None else 0
            r_len = len(trace.r) if hasattr(trace, 'r') and trace.r is not None else 0  # Scatterpolar/radar
            link_len = len(trace.link.value) if hasattr(trace, 'link') and trace.link and hasattr(trace.link, 'value') and trace.link.value is not None else 0
            pts = max(x_len, y_len, val_len, z_len, loc_len, link_len, r_len)
            total_data_points += pts


        if total_data_points == 0:
            return False, num_traces, 0, elapsed_ms, "Gráfico sem pontos de dados (Plot vazio)"

        return True, num_traces, total_data_points, elapsed_ms, ""

    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return False, 0, 0, elapsed_ms, str(e)


def run_verification_suite() -> bool:
    """Executa a suite completa de verificação em todos os gráficos do sistema."""
    print("=" * 80)
    print(" 🛡️  TRANSFEREGOV — SUITE DE VERIFICAÇÃO DE SAÚDE DOS GRÁFICOS (31 CHARTS)")
    print("=" * 80)

    total_charts = len(CHART_REGISTRY)
    passed_count = 0
    failed_count = 0
    results: list[dict[str, Any]] = []

    print(f"{'STATUS':<12} | {'ID DO GRÁFICO':<35} | {'TRACES':<7} | {'PONTOS':<8} | {'TEMPO':<8}")
    print("-" * 80)

    for chart_id, spec in CHART_REGISTRY.items():
        is_ok, num_traces, total_pts, elapsed_ms, error_msg = verify_single_chart(chart_id, spec)

        if is_ok:
            passed_count += 1
            status_str = "✅ APTO"
        else:
            failed_count += 1
            status_str = "❌ FALHA"

        print(f"{status_str:<12} | {chart_id:<35} | {num_traces:<7} | {total_pts:<8} | {elapsed_ms:>6.1f}ms")
        if not is_ok and error_msg:
            print(f"   ↳ ⚠️ MOTIVO DA FALHA: {error_msg}")

        results.append({
            "id": chart_id,
            "title": spec.title,
            "category": spec.category,
            "is_ok": is_ok,
            "traces": num_traces,
            "points": total_pts,
            "time_ms": elapsed_ms,
            "error": error_msg
        })

    print("=" * 80)
    print(f"📊 RESUMO DE EXECUÇÃO: {passed_count}/{total_charts} Gráficos Operacionais ({passed_count/total_charts*100:.1f}%)")
    print("=" * 80)

    if failed_count > 0:
        print(f"❌ ATENÇÃO: {failed_count} gráfico(s) falharam no teste de dados!")
        return False
    else:
        print("🎉 TODOS OS GRÁFICOS PASSARAM NO TESTE DE DADOS E FUNCIONAMENTO!")
        return True


if __name__ == "__main__":
    success = run_verification_suite()
    sys.exit(0 if success else 1)
