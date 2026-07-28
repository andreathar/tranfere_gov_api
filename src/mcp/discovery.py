"""
Descoberta e listagem de tools MCP.

Fornece:
- discover_tools_async: descobre tools via MCP server (meta + cached)
- search_tools_via_mcp: busca tools por query em linguagem natural
- list_tools_sync: wrapper síncrono para listagem com filtros
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.mcp.categories import TOOL_CATEGORIES

logger = logging.getLogger(__name__)


def _get_mcp():
    """Retorna o servidor MCP (lazy import para evitar circular)."""
    from mcp_brasil.server import mcp

    return mcp


def _categorize_tool(name: str) -> str:
    """Determina a categoria de uma tool pelo nome."""
    name_lower = name.lower()
    for cat, prefixes in TOOL_CATEGORIES.items():
        if any(name_lower.startswith(p) or p in name_lower for p in prefixes):
            return cat
    return "outros"


def _mcp_tool_to_dict(mcp_t: Any) -> dict[str, Any]:
    """Converte um MCP tool object para dict padronizado."""
    tags: set[str] = set()
    if mcp_t.meta and "fastmcp" in (mcp_t.meta or {}):
        tags = set(mcp_t.meta.get("fastmcp", {}).get("tags", []))

    return {
        "name": mcp_t.name,
        "description": (mcp_t.description or "")[:500],
        "input_schema": mcp_t.inputSchema,
        "category": _categorize_tool(mcp_t.name),
        "tags": list(tags),
    }


async def discover_tools_async(force: bool = False) -> list[dict[str, Any]]:
    """Descobre tools MCP: meta-tools + curated TransfereGov-relevant tools.

    Cacheia resultado para evitar múltiplas chamadas async.
    Pass force=True para forçar redescoberta.
    """
    mcp = _get_mcp()
    mcp_tools = await mcp.list_tools()
    tools: list[dict[str, Any]] = []

    for ft in mcp_tools:
        mcp_t = ft.to_mcp_tool()
        tools.append(_mcp_tool_to_dict(mcp_t))

    # Adicionar tools curadas do mcp-brasil (via _tool_cache)
    try:
        srv = mcp._mcp_server
        if hasattr(srv, "_tool_cache") and isinstance(srv._tool_cache, dict):
            existing_names = {t["name"] for t in tools}
            for name, ft in srv._tool_cache.items():
                if name in existing_names:
                    continue
                mcp_t = ft.to_mcp_tool() if hasattr(ft, "to_mcp_tool") else None
                if mcp_t:
                    tools.append(_mcp_tool_to_dict(mcp_t))
    except Exception as exc:
        logger.debug("Não foi possível acessar _tool_cache: %s", exc)

    logger.info("Descobertas %d tools MCP (meta + cached)", len(tools))
    return tools


def _run_async(coro):
    """Executa uma coroutine async de forma segura.

    Funciona tanto em contextos com event loop ativo quanto sem.
    Substitui asyncio.get_event_loop().run_until_complete() deprecado.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Já estamos dentro de um event loop (ex: FastAPI, Jupyter).
        # Não podemos bloquear — usar thread.
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


async def search_tools_via_mcp_async(query: str) -> list[dict[str, Any]]:
    """Usa a meta-tool search_tools do mcp-brasil para descobrir tools."""
    mcp = _get_mcp()
    try:
        result = await mcp.call_tool("search_tools", {"query": query})
        if hasattr(result, "content") and result.content:
            text = result.content[0].text if result.content else ""
            return [{"name": query, "search_result": text}]
    except Exception as exc:
        logger.warning("search_tools falhou: %s", exc)
    return []


def search_tools_via_mcp(query: str) -> list[dict[str, Any]]:
    """Wrapper síncrono de search_tools_via_mcp_async."""
    return _run_async(search_tools_via_mcp_async(query))


def list_tools_sync(
    tools_cache: list[dict[str, Any]] | None,
    category: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """Lista tools disponíveis com filtros (wrapper síncrono).

    Se tools_cache é None, executa discover_tools_async.
    """
    tools = _run_async(discover_tools_async()) if tools_cache is None else tools_cache

    if category:
        tools = [t for t in tools if t["category"] == category]
    if search:
        q = search.lower()
        tools = [
            t for t in tools
            if q in t["name"].lower() or q in t["description"].lower()
        ]
    return tools
