herdr"""
Conversão de funções Python → schema OpenAI function calling.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any


def function_to_openai_schema(name: str, fn: Callable) -> dict[str, Any]:
    """Converte uma função Python para o formato OpenAI function schema.

    Para wrappers _wrap_no_ctx que usam **kwargs, introspeia o
    __wrapped__ ou a função original para obter os params corretos.
    """
    # Se é um wrapper com **kwargs, tentar usar o __wrapped__
    # que é a função original antes do wrap
    target = getattr(fn, "__wrapped__", fn)
    sig = inspect.signature(target)
    properties: dict[str, Any] = {}
    required: list[str] = []

    # Tipos de docstrings do MCP-Brasil: extrair descrição dos params
    doc = inspect.getdoc(target) or name
    # Parse Args section se existir
    args_section: dict[str, str] = {}
    if "Args:" in doc:
        in_args = False
        for line in doc.split("\n"):
            stripped = line.strip()
            if stripped == "Args:":
                in_args = True
                continue
            if in_args and ":" in stripped:
                parts = stripped.split(":", 1)
                arg_name = parts[0].strip()
                arg_desc = parts[1].strip()
                if arg_name in ("Returns", "Example", "Examples", "Note", "Notes"):
                    break
                args_section[arg_name] = arg_desc

    for pname, param in sig.parameters.items():
        if pname in ("ctx", "self", "cls"):
            continue
        # Mapear tipo Python → JSON Schema type
        annotation = param.annotation
        json_type = "string"
        if annotation in (int, "int", inspect.Parameter.empty):
            if annotation in (int, "int"):
                json_type = "integer"
        elif annotation in (float, "float"):
            json_type = "number"
        elif annotation in (bool, "bool"):
            json_type = "boolean"

        prop: dict[str, Any] = {"type": json_type}
        if pname in args_section:
            prop["description"] = args_section[pname]
        if param.default is inspect.Parameter.empty:
            required.append(pname)
        else:
            prop["default"] = param.default

        properties[pname] = prop

    description = doc.split("\n")[0].strip() if doc else name

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }
