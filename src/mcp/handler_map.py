"""
Mapeamento de tools MCP para funções Python executáveis.

Inclui:
- build_handler_map: importa módulos mcp-brasil e mapeia funções
- wrap_no_ctx: envolve funções async MCP para chamada sem Context
- resolve_handler: resolve nome → callable
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


def build_handler_map() -> dict[str, Callable]:
    """Mapeia nomes de tools para funções Python do mcp-brasil.

    Importa módulos de tools do mcp-brasil e cria um dicionário
    {prefixo_nome: handler_wrapado} para execução direta sem session MCP.
    """
    import importlib
    import types

    mapping: dict[str, Callable] = {}

    def _try_import(module_path: str) -> types.ModuleType | None:
        try:
            return importlib.import_module(module_path)
        except (ImportError, ModuleNotFoundError):
            return None

    _modules_raw = {
        "ibge": "mcp_brasil.data.ibge.tools",
        "camara": "mcp_brasil.data.camara.tools",
        "transferegov": "mcp_brasil.data.transferegov.tools",
        "siconfi": "mcp_brasil.data.siconfi.tools",
        "brasilapi": "mcp_brasil.data.brasilapi.tools",
        "transparencia": "mcp_brasil.data.transparencia.tools",
        "bacen": "mcp_brasil.data.bacen.tools",
        "diario_oficial": "mcp_brasil.data.diario_oficial.tools",
        "redator": "mcp_brasil.agentes.redator.tools",
    }

    modules = {
        prefix: mod
        for prefix, path in _modules_raw.items()
        if (mod := _try_import(path)) is not None
    }

    for prefix, mod in modules.items():
        for attr in dir(mod):
            if attr.startswith("_"):
                continue
            fn = getattr(mod, attr)
            if not callable(fn) or inspect.isclass(fn):
                continue
            if not (inspect.isfunction(fn) or inspect.iscoroutinefunction(fn)):
                continue
            try:
                wrapped = wrap_no_ctx(fn)
                mapping[f"{prefix}_{attr}"] = wrapped
            except (TypeError, ValueError):
                pass

    logger.info("Handler map: %d tools mapeados", len(mapping))
    return mapping


def wrap_no_ctx(fn: Callable) -> Callable:
    """Envolve uma função MCP async para ser chamada sem o parâmetro ctx.

    Cria um mock mínimo do Context do FastMCP para preencher o parâmetro
    obrigatório quando a tool é chamada diretamente (sem session MCP).
    """
    if not callable(fn):
        raise TypeError(f"{fn} não é chamável")
    if inspect.isclass(fn):
        raise TypeError(f"{fn} é uma classe, não função")

    try:
        sig = inspect.signature(fn)
        has_ctx = "ctx" in sig.parameters
    except (ValueError, TypeError):
        sig = inspect.Signature()  # vazio — has_ctx será False
        has_ctx = False

    # Mock mínimo do Context do FastMCP
    _mock_ctx = None
    if has_ctx:
        class _MockCtx:
            async def info(self, *a, **kw):
                pass

            async def warning(self, *a, **kw):
                pass

            async def error(self, *a, **kw):
                pass

            async def debug(self, *a, **kw):
                pass

            async def log(self, *a, **kw):
                pass

            async def report_progress(self, *a, **kw):
                pass

            session = None
            _request_context = None

        _mock_ctx = _MockCtx()

    async def wrapper(**kwargs):
        if has_ctx:
            kwargs.pop("ctx", None)
            try:
                ctx_param = sig.parameters["ctx"]
            except KeyError:
                ctx_param = None

            if ctx_param and ctx_param.kind == inspect.Parameter.POSITIONAL_ONLY:
                params = list(sig.parameters.keys())
                ctx_idx = params.index("ctx")
                pos_args = []
                for p in params[:ctx_idx]:
                    if p in kwargs:
                        pos_args.append(kwargs.pop(p))
                    else:
                        pos_args.append(None)
                result = await fn(*pos_args, _mock_ctx, **kwargs)
            else:
                result = await fn(ctx=_mock_ctx, **kwargs)
        else:
            result = await fn(**kwargs)
        return result

    wrapper.__name__ = getattr(fn, "__name__", str(fn))  # type: ignore[attr-defined]
    wrapper.__doc__ = getattr(fn, "__doc__", "")  # type: ignore[attr-defined]
    wrapper.__wrapped__ = fn  # type: ignore[attr-defined]
    return wrapper


def resolve_handler(
    name: str,
    callables: dict[str, Callable],
    handler_map: dict[str, Callable],
) -> Callable | None:
    """Resolve o handler de uma tool pelo nome.

    Tenta:
    1. Handlers registrados via register_tool() (callables)
    2. Funções Python do mcp-brasil (handler_map)
    3. Retorna None (caller deve usar MCP call_tool como fallback)
    """
    if name in callables:
        return callables[name]
    if name in handler_map:
        return handler_map[name]
    return None
