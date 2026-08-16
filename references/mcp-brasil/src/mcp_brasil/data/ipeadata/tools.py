"""MCP tools for IPEADATA."""

from __future__ import annotations

from mcp_brasil._shared.formatting import markdown_table

from . import client
from .constants import SERIES_POPULARES


async def buscar_serie(termo: str, limite: int = 30) -> str:
    """Busca séries IPEADATA pelo **início** do nome (prefixo exato, case-sensitive).

    Use para descobrir o ``SERCODIGO`` de uma série antes de consultar valores.
    Exemplo: termo='IPCA' retorna apenas séries cujo nome começa com 'IPCA'.

    Limitação da API: IPEADATA OData rejeita ``contains()`` — só ``startswith()``.
    Para buscas amplas, use ``series_populares()`` primeiro.

    Args:
        termo: Prefixo exato do nome da série (case-sensitive).
        limite: Máximo de resultados (padrão 30, máx 100).
    """
    limite = max(1, min(limite, 100))
    series = await client.listar_series(filtro_nome=termo, top=limite)
    if not series:
        return f"Nenhuma série encontrada para '{termo}'."
    rows = [
        (s.SERCODIGO, (s.SERNOME or "—")[:60], s.PERNOME or "—", s.UNINOME or "—") for s in series
    ]
    return f"**{len(series)} séries encontradas**\n\n" + markdown_table(
        ["codigo", "nome", "periodicidade", "unidade"], rows
    )


async def metadados_serie(codigo: str) -> str:
    """Retorna metadados detalhados de uma série IPEADATA.

    Args:
        codigo: SERCODIGO (ex: 'PRECOS12_IPCA12').
    """
    m = await client.metadados_serie(codigo)
    if m is None:
        return f"Série '{codigo}' não encontrada."
    return "\n".join(
        [
            f"**{m.SERNOME}** (`{m.SERCODIGO}`)",
            "",
            f"- **Periodicidade:** {m.PERNOME or '—'}",
            f"- **Unidade:** {m.UNINOME or '—'}",
            f"- **Base:** {m.BASNOME or '—'}",
            f"- **Fonte:** {m.FNTNOME or '—'}",
            f"- **Multiplicador:** {m.MULNOME or '—'}",
            f"- **Atualização:** {m.SERATUALIZACAO or '—'}",
            f"- **Status:** {m.SERSTATUS or '—'}",
            "",
            "**Comentário:**",
            m.SERCOMENTARIO or "—",
        ]
    )


async def valores_serie(codigo: str, limite: int = 60) -> str:
    """Retorna valores históricos de uma série IPEADATA (mais recentes primeiro).

    Args:
        codigo: SERCODIGO.
        limite: Máximo de pontos (padrão 60 ≈ 5 anos mensais, máx 1000).
    """
    limite = max(1, min(limite, 1000))
    valores = await client.valores_serie(codigo, top=limite)
    if not valores:
        return f"Sem valores para série '{codigo}'."
    rows = [
        (
            (v.VALDATA or "")[:10],
            f"{v.VALVALOR:.4f}" if v.VALVALOR is not None else "—",
            v.NIVNOME or "",
            v.TERCODIGO or "",
        )
        for v in valores
    ]
    return (
        f"**{len(valores)} valores para `{codigo}` (mais recentes primeiro)**\n\n"
        + markdown_table(["data", "valor", "nivel", "territorio"], rows)
    )


async def series_populares() -> str:
    """Lista séries IPEADATA de uso mais frequente (catálogo curado, offline)."""
    rows = [(k, v) for k, v in SERIES_POPULARES.items()]
    return "**Séries IPEADATA populares**\n\n" + markdown_table(["codigo", "nome"], rows)


async def ultimo_valor(codigo: str) -> str:
    """Retorna apenas o último valor disponível da série.

    Útil para painéis/dashboards que precisam só do ponto mais recente.

    Args:
        codigo: SERCODIGO.
    """
    valores = await client.valores_serie(codigo, top=1)
    if not valores:
        return f"Sem valores para '{codigo}'."
    v = valores[0]
    return (
        f"**Último valor `{codigo}`**\n\n- Data: {(v.VALDATA or '')[:10]}\n- Valor: {v.VALVALOR}\n"
    )
