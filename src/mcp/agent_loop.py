"""
Agentic loop: chat → tool_calls → execução → repetição.

Usa LocalAIClient para chamadas HTTP (elimina duplicação do HTTP client
que existia no MCPToolBridge original).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from config.settings import LOCALAI_DEFAULT_MODEL

logger = logging.getLogger(__name__)


def build_messages(
    prompt: str,
    system: str | None = None,
    tools: list[dict] | None = None,
) -> list[dict[str, Any]]:
    """Monta lista de messages para o chat completion."""
    messages: list[dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})
    else:
        tool_names = [t["function"]["name"] for t in (tools or [])[:20]]
        messages.append(
            {
                "role": "system",
                "content": (
                    "Você é um assistente de IA com acesso a ferramentas de dados "
                    "governamentais brasileiros. Use as ferramentas disponíveis para "
                    "responder perguntas sobre transferências, emendas, municípios, "
                    "finanças públicas e dados abertos.\n\n"
                    f"Ferramentas disponíveis: {', '.join(tool_names)}"
                ),
            }
        )
    messages.append({"role": "user", "content": prompt})
    return messages


def agent_chat_sync(
    prompt: str,
    *,
    system: str | None = None,
    model: str | None = None,
    tools_schema: list[dict[str, Any]],
    execute_tool_fn,
    max_turns: int = 5,
    temperature: float = 0.3,
) -> dict[str, Any]:
    """Agentic loop síncrono: chat → tool_calls → execute → repeat.

    Args:
        execute_tool_fn: callable(name, args) -> str — executa uma tool

    Returns:
        {"response": str, "tool_calls": list, "turns": int, "tools_available": int}
    """
    from src.localai_client import LocalAIClient

    client = LocalAIClient()
    messages = build_messages(prompt, system, tools_schema)
    model = model or LOCALAI_DEFAULT_MODEL

    all_tool_calls: list[dict[str, Any]] = []
    final_response = ""
    turn = 0

    for turn in range(max_turns):
        logger.info("Agent turn %d/%d", turn + 1, max_turns)

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4096,
        }
        if tools_schema:
            payload["tools"] = tools_schema

        data = client._post("/chat/completions", payload)  # noqa: SLF001
        choice = data["choices"][0]
        message = choice["message"]

        messages.append(message)

        tool_calls = message.get("tool_calls", [])
        if not tool_calls:
            final_response = message.get("content", "")
            break

        for tc in tool_calls:
            func = tc["function"]
            tool_name = func["name"]
            try:
                tool_args = json.loads(func["arguments"])
            except json.JSONDecodeError:
                tool_args = {}

            logger.info("Executando tool: %s(%s)", tool_name, tool_args)
            result = execute_tool_fn(tool_name, tool_args)

            all_tool_calls.append(
                {
                    "tool": tool_name,
                    "arguments": tool_args,
                    "result_preview": result[:200],
                }
            )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result[:8000],
                }
            )

            logger.info("Tool %s retornou %d chars", tool_name, len(result))

    return {
        "response": final_response,
        "tool_calls": all_tool_calls,
        "turns": min(turn + 1, max_turns),
        "tools_available": len(tools_schema),
    }


async def agent_chat_async(
    prompt: str,
    *,
    system: str | None = None,
    model: str | None = None,
    tools_schema: list[dict[str, Any]],
    execute_tool_fn,
    max_turns: int = 5,
    temperature: float = 0.3,
) -> dict[str, Any]:
    """Agentic loop async: chat → tool_calls → execute → repeat.

    Args:
        execute_tool_fn: async callable(name, args) -> str
    """
    from src.localai_client import LocalAIClient

    client = LocalAIClient()
    messages = build_messages(prompt, system, tools_schema)
    model = model or LOCALAI_DEFAULT_MODEL

    all_tool_calls: list[dict[str, Any]] = []
    final_response = ""
    _turn = 0

    for _turn in range(max_turns):
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4096,
        }
        if tools_schema:
            payload["tools"] = tools_schema

        data = await client._apost("/chat/completions", payload)  # noqa: SLF001
        choice = data["choices"][0]
        message = choice["message"]

        messages.append(message)

        tool_calls = message.get("tool_calls", [])
        if not tool_calls:
            final_response = message.get("content", "")
            break

        for tc in tool_calls:
            func = tc["function"]
            tool_name = func["name"]
            try:
                tool_args = json.loads(func["arguments"])
            except json.JSONDecodeError:
                tool_args = {}

            result = await execute_tool_fn(tool_name, tool_args)

            all_tool_calls.append(
                {
                    "tool": tool_name,
                    "arguments": tool_args,
                    "result_preview": result[:200],
                }
            )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result[:8000],
                }
            )

    return {
        "response": final_response,
        "tool_calls": all_tool_calls,
        "turns": min(_turn + 1, max_turns),
        "tools_available": len(tools_schema),
    }
