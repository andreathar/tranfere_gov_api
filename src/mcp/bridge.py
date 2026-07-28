"""
MCPToolBridge — orquestra discovery, schema, handlers e agent loop.

Esta é a classe pública que mantém a mesma API do mcp_tool_bridge original
mas delega para módulos focados. Eliminou o HTTP client duplicado
(o agent loop agora usa LocalAIClient).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from src.mcp.agent_loop import agent_chat_async, agent_chat_sync
from src.mcp.categories import TOOL_CATEGORIES
from src.mcp.discovery import (
    discover_tools_async,
    list_tools_sync,
    search_tools_via_mcp,
)
from src.mcp.handler_map import build_handler_map, resolve_handler
from src.mcp.schema import function_to_openai_schema

logger = logging.getLogger(__name__)


class MCPToolBridge:
    """Ponte entre MCP tools e OpenAI function calling."""

    def __init__(self) -> None:
        self._mcp_server = None
        self._tools_cache: list[dict[str, Any]] | None = None
        self._callables: dict[str, Callable] = {}
        self._handler_map: dict[str, Callable] | None = None

    # ------------------------------------------------------------------
    # Lazy init do servidor MCP
    # ------------------------------------------------------------------

    def _get_mcp(self):
        """Retorna o servidor MCP (lazy import para evitar circular)."""
        if self._mcp_server is None:
            from mcp_brasil.server import mcp

            self._mcp_server = mcp
        return self._mcp_server

    def _ensure_handler_map(self) -> dict[str, Callable]:
        if self._handler_map is None:
            self._handler_map = build_handler_map()
        return self._handler_map

    # ------------------------------------------------------------------
    # Descoberta de tools
    # ------------------------------------------------------------------

    async def discover_tools(self, force: bool = False) -> list[dict[str, Any]]:
        """Descobre tools MCP: meta-tools + curated TransfereGov-relevant tools."""
        if self._tools_cache is not None and not force:
            return self._tools_cache
        self._tools_cache = await discover_tools_async(force=force)
        return self._tools_cache

    def search_tools_via_mcp(self, query: str) -> list[dict[str, Any]]:
        """Usa a meta-tool search_tools do mcp-brasil para descobrir tools."""
        return search_tools_via_mcp(query)

    def list_tools(
        self,
        category: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        """Lista tools disponíveis (sync wrapper)."""
        return list_tools_sync(self._tools_cache, category=category, search=search)

    # ------------------------------------------------------------------
    # Conversão para OpenAI function calling format
    # ------------------------------------------------------------------

    def to_openai_tools(
        self,
        categories: list[str] | None = None,
        max_tools: int = 50,
        search: str | None = None,
        include_meta: bool = True,
    ) -> list[dict[str, Any]]:
        """Converte tools MCP para o formato OpenAI function calling."""
        tools = list_tools_sync(self._tools_cache)

        # Converter meta-tools primeiro (sempre incluir)
        openai_tools: list[dict[str, Any]] = []
        meta_names: set[str] = set()
        if include_meta:
            meta_tools = [t for t in tools if t["category"] == "meta"]
            for t in meta_tools:
                openai_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": t["name"],
                            "description": t["description"],
                            "parameters": t["input_schema"],
                        },
                    }
                )
                meta_names.add(t["name"])

        # Filtrar tools por categorias
        filtered = tools
        if categories:
            cat_names: set[str] = set()
            for cat in categories:
                if cat in TOOL_CATEGORIES:
                    cat_names.update(TOOL_CATEGORIES[cat])
                else:
                    cat_names.add(cat)
            filtered = [
                t
                for t in tools
                if t["name"] not in meta_names
                and (t["category"] in categories or any(p in t["name"].lower() for p in cat_names))
            ]

        # Filtro por texto
        if search:
            q = search.lower()
            filtered = [
                t
                for t in filtered
                if t["name"] not in meta_names
                and (q in t["name"].lower() or q in t["description"].lower())
            ]

        # Remover duplicatas e meta já incluídas
        seen = meta_names.copy()
        for t in filtered:
            if t["name"] in seen:
                continue
            seen.add(t["name"])
            if len(openai_tools) >= max_tools:
                break
            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["input_schema"],
                    },
                }
            )

        # Adicionar tools do handler_map (execução direta, sem MCP session)
        handler_map = self._ensure_handler_map()
        for tool_name, handler in handler_map.items():
            if tool_name in seen:
                continue
            if categories:
                cat_match = False
                for cat in categories:
                    prefixes = TOOL_CATEGORIES.get(cat, [cat])
                    if any(tool_name.startswith(p + "_") for p in prefixes):
                        cat_match = True
                        break
                if not cat_match:
                    continue
            seen.add(tool_name)
            if len(openai_tools) >= max_tools:
                break
            schema = function_to_openai_schema(tool_name, handler)
            openai_tools.append(schema)

        logger.info(
            "Convertidas %d tools para OpenAI format (meta=%d, categories=%s)",
            len(openai_tools), len(meta_names), categories,
        )
        return openai_tools

    # ------------------------------------------------------------------
    # Execução de tools
    # ------------------------------------------------------------------

    async def execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Executa uma tool pelo nome, usando handler direto ou MCP."""
        handler = resolve_handler(name, self._callables, self._ensure_handler_map())
        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(**arguments)
                else:
                    result = handler(**arguments)
                if isinstance(result, str):
                    return result
                if isinstance(result, list):
                    return "\n".join(str(item) for item in result)
                return str(result)
            except Exception as exc:
                error_msg = f"Erro ao executar '{name}': {exc}"
                logger.warning(error_msg)
                return error_msg

        # Fallback: MCP call_tool
        mcp = self._get_mcp()
        try:
            result = await mcp.call_tool(name, arguments)
            if hasattr(result, "content") and result.content:
                parts = []
                for item in result.content:
                    if hasattr(item, "text"):
                        parts.append(item.text)
                    else:
                        parts.append(str(item))
                return "\n".join(parts)
            return str(result)
        except Exception as exc:
            error_msg = f"Tool '{name}' não encontrada ou sem session: {exc}"
            logger.error(error_msg)
            return error_msg

    def execute_tool_sync(self, name: str, arguments: dict[str, Any]) -> str:
        """Versão sync da execução de tool."""
        from src.mcp.discovery import _run_async

        return _run_async(self.execute_tool(name, arguments))

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable,
        category: str = "local",
    ) -> None:
        """Registra uma tool customizada (não-MCP) no bridge."""
        self._callables[name] = handler
        if self._tools_cache is None:
            self._tools_cache = []
        self._tools_cache.append(
            {
                "name": name,
                "description": description,
                "input_schema": parameters,
                "category": category,
                "tags": ["custom"],
            }
        )

    # ------------------------------------------------------------------
    # Agent loop
    # ------------------------------------------------------------------

    def agent_chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        categories: list[str] | None = None,
        max_tools: int = 30,
        max_turns: int = 5,
        temperature: float = 0.3,
        include_meta_tools: bool = True,
    ) -> dict[str, Any]:
        """Executa agentic loop: chat → tool_calls → execute → repeat."""
        tools_schema = self.to_openai_tools(
            categories=categories,
            max_tools=max_tools,
            include_meta=include_meta_tools,
        )
        return agent_chat_sync(
            prompt,
            system=system,
            model=model,
            tools_schema=tools_schema,
            execute_tool_fn=self.execute_tool_sync,
            max_turns=max_turns,
            temperature=temperature,
        )

    async def aagent_chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        categories: list[str] | None = None,
        max_tools: int = 30,
        max_turns: int = 5,
        temperature: float = 0.3,
        include_meta_tools: bool = True,
    ) -> dict[str, Any]:
        """Versão async do agent chat."""
        tools_schema = self.to_openai_tools(
            categories=categories,
            max_tools=max_tools,
            include_meta=include_meta_tools,
        )
        return await agent_chat_async(
            prompt,
            system=system,
            model=model,
            tools_schema=tools_schema,
            execute_tool_fn=self.execute_tool,
            max_turns=max_turns,
            temperature=temperature,
        )


# ---------------------------------------------------------------------------
# Instância global
# ---------------------------------------------------------------------------
_bridge: MCPToolBridge | None = None


def get_mcp_bridge() -> MCPToolBridge:
    """Retorna instância singleton do bridge."""
    global _bridge
    if _bridge is None:
        _bridge = MCPToolBridge()
    return _bridge
