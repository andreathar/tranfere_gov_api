"""MCP tools for IBAMA."""

from __future__ import annotations

from typing import Any

from mcp_brasil._shared.formatting import markdown_table

from . import client
from .constants import DATASETS_CHAVE


async def listar_datasets_ibama(filtro: str | None = None, limite: int = 50) -> str:
    """Lista datasets do portal IBAMA.

    Args:
        filtro: Substring de filtro.
        limite: Máximo (padrão 50, máx 500).
    """
    limite = max(1, min(limite, 500))
    nomes = await client.listar_datasets()
    if filtro:
        f = filtro.lower()
        nomes = [n for n in nomes if f in n.lower()]
    if not nomes:
        return "Nenhum dataset encontrado."
    mostrados = nomes[:limite]
    return f"**{len(nomes)} datasets (exibindo {len(mostrados)})**\n\n" + "\n".join(
        f"- `{n}`" for n in mostrados
    )


async def buscar_datasets_ibama(termo: str, limite: int = 20) -> str:
    """Busca datasets IBAMA por palavra-chave.

    Args:
        termo: Palavra-chave (ex: 'infração', 'multa', 'desmatamento').
        limite: Máximo (padrão 20, máx 100).
    """
    limite = max(1, min(limite, 100))
    data = await client.buscar_datasets(termo, limite)
    results = data.get("results") or []
    count = data.get("count", len(results))
    if not results:
        return f"Nenhum dataset para '{termo}'."
    rows: list[tuple[Any, ...]] = []
    for p in results[:limite]:
        rows.append(
            (
                p.get("name") or "",
                (p.get("title") or "")[:60],
                len(p.get("resources") or []),
            )
        )
    return f"**{count} datasets para '{termo}' (exibindo {len(rows)})**\n\n" + markdown_table(
        ["package", "título", "nº recursos"], rows
    )


async def detalhe_dataset_ibama(package_id: str) -> str:
    """Detalhe de um dataset IBAMA + URLs para download.

    Args:
        package_id: Nome do package (ex: 'fiscalizacao-auto-de-infracao').
    """
    d = await client.detalhe_dataset(package_id)
    if not d:
        return f"Dataset '{package_id}' não encontrado."
    title = d.get("title") or package_id
    notes = d.get("notes") or ""
    resources = d.get("resources") or []
    lines = [
        f"**{title}** (`{package_id}`)",
        "",
        (notes[:800] + "…") if len(notes) > 800 else notes,
        "",
    ]
    if resources:
        lines.append(f"**{len(resources)} recursos:**\n")
        rows = [
            (r.get("name") or "—", r.get("format") or "—", r.get("url") or "")
            for r in resources[:50]
        ]
        lines.append(markdown_table(["nome", "formato", "url"], rows))
    return "\n".join(lines)


async def datasets_chave_ibama() -> str:
    """Datasets IBAMA mais usados (curadoria)."""
    rows = [(k, v) for k, v in DATASETS_CHAVE.items()]
    return "**Datasets-chave do IBAMA**\n\n" + markdown_table(["package", "descrição"], rows)
