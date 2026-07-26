"""
MCP → OpenAI Tool Bridge.

Converte ferramentas MCP (FastMCP) para o formato OpenAI function calling,
permitindo que modelos LocalAI invoquem tools governamentais e do dashboard.

Uso:
    from src.mcp_tool_bridge import MCPToolBridge

    bridge = MCPToolBridge()

    # Listar tools disponíveis
    tools = bridge.list_tools(category="camara")

    # Executar agentic loop (chat + tool calling automático)
    result = bridge.agent_chat(
        "Quais municípios de Alagoas receberam emendas?",
        max_turns=5,
    )

    # Ou usar diretamente com o LocalAI client
    from src.localai_client import get_localai_client
    client = get_localai_client()
    tools_schema = bridge.to_openai_tools(["camara", "ibge", "transferegov"])
    resp = client.chat("...", tools=tools_schema)
"""

from __future__ import annotations

import inspect
import json
import logging
from typing import Any, Callable

import httpx

from config.settings import (
    LOCALAI_BASE_URL,
    LOCALAI_DEFAULT_MODEL,
    LOCALAI_MAX_RETRIES,
    LOCALAI_TIMEOUT,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Categorias de ferramentas para filtragem
# ---------------------------------------------------------------------------
TOOL_CATEGORIES: dict[str, list[str]] = {
    "transferegov": ["transferegov"],
    "camara": ["camara"],
    "senado": ["senado"],
    "tse": ["tse"],
    "ibge": ["ibge"],
    "siconfi": ["siconfi"],
    "compras": ["compras", "pncp", "contratosgovbr", "dadosabertos"],
    "saude": ["saude", "farmacia_popular", "rename", "denasus", "imunizacao", "opendatasus"],
    "educacao": ["inep", "fnde"],
    "seguranca": ["atlas_violencia", "forum_seguranca", "mj", "sinesp"],
    "ambiental": ["ibama", "inpe"],
    "financeiro": ["bacen", "bcb_olinda", "b3", "bndes", "bps"],
    "judicial": ["datajud", "jurisprudencia", "tcu"],
    "diario_oficial": ["diario_oficial"],
    "dashboard": ["list_registered_charts", "inspect_chart_health", "get_chart_data_summary"],
    "meta": ["listar_features", "recomendar_tools", "planejar_consulta", "executar_lote", "listar_datasets_disponiveis"],
}


class MCPToolBridge:
    """Ponte entre MCP tools e OpenAI function calling."""

    def __init__(self) -> None:
        self._mcp_server = None
        self._tools_cache: list[dict[str, Any]] | None = None
        self._callables: dict[str, Callable] = {}

    # ------------------------------------------------------------------
    # Lazy init do servidor MCP
    # ------------------------------------------------------------------
    def _get_mcp(self):
        """Retorna o servidor MCP (lazy import para evitar circular)."""
        if self._mcp_server is None:
            from mcp_brasil.server import mcp
            self._mcp_server = mcp
        return self._mcp_server

    # ------------------------------------------------------------------
    # Descoberta de tools
    # ------------------------------------------------------------------
    async def discover_tools(self, force: bool = False) -> list[dict[str, Any]]:
        """Descobre tools MCP: meta-tools + curated TransfereGov-relevant tools.

        O mcp-brasil usa BM25 search transform que filtra tools para evitar
        sobrecarregar o LLM com 435+ tools. Usamos as meta-tools (search_tools,
        call_tool) para descoberta dinâmica + um conjunto curado de tools
        mais relevantes para o domínio TransfereGov.
        """
        if self._tools_cache is not None and not force:
            return self._tools_cache

        mcp = self._get_mcp()
        mcp_tools = await mcp.list_tools()
        tools = []

        for ft in mcp_tools:
            mcp_t = ft.to_mcp_tool()
            tags = set()
            if mcp_t.meta and "fastmcp" in (mcp_t.meta or {}):
                tags = set(mcp_t.meta.get("fastmcp", {}).get("tags", []))

            # Determinar categoria
            category = "outros"
            name_lower = mcp_t.name.lower()
            for cat, prefixes in TOOL_CATEGORIES.items():
                if any(name_lower.startswith(p) or p in name_lower for p in prefixes):
                    category = cat
                    break

            tool_def = {
                "name": mcp_t.name,
                "description": (mcp_t.description or "")[:500],
                "input_schema": mcp_t.inputSchema,
                "category": category,
                "tags": list(tags),
            }
            tools.append(tool_def)

        # Adicionar tools curadas do mcp-brasil (via _mcp_server._tool_cache)
        # Estas são as tools que o BM25 transform esconde mas que são registradas
        try:
            srv = mcp._mcp_server
            if hasattr(srv, '_tool_cache') and isinstance(srv._tool_cache, dict):
                for name, ft in srv._tool_cache.items():
                    if any(t["name"] == name for t in tools):
                        continue  # Já temos
                    mcp_t = ft.to_mcp_tool() if hasattr(ft, 'to_mcp_tool') else None
                    if mcp_t:
                        tags = set()
                        if mcp_t.meta and "fastmcp" in (mcp_t.meta or {}):
                            tags = set(mcp_t.meta.get("fastmcp", {}).get("tags", []))
                        category = "outros"
                        name_lower = mcp_t.name.lower()
                        for cat, prefixes in TOOL_CATEGORIES.items():
                            if any(name_lower.startswith(p) or p in name_lower for p in prefixes):
                                category = cat
                                break
                        tools.append({
                            "name": mcp_t.name,
                            "description": (mcp_t.description or "")[:500],
                            "input_schema": mcp_t.inputSchema,
                            "category": category,
                            "tags": list(tags),
                        })
        except Exception as exc:
            logger.debug("Não foi possível acessar _tool_cache: %s", exc)

        self._tools_cache = tools
        logger.info("Descobertas %d tools MCP (meta + cached)", len(tools))
        return tools

    def search_tools_via_mcp(self, query: str) -> list[dict[str, Any]]:
        """Usa a meta-tool search_tools do mcp-brasil para descobrir tools.

        Esta é a forma recomendada pelo mcp-brasil para descobrir tools
        relevantes a partir de uma query em linguagem natural.
        """
        import asyncio
        mcp = self._get_mcp()
        try:
            result = asyncio.get_event_loop().run_until_complete(
                mcp.call_tool("search_tools", {"query": query})
            )
            # Parse o resultado (é texto markdown)
            if hasattr(result, "content") and result.content:
                text = result.content[0].text if result.content else ""
                return [{"name": query, "search_result": text}]
        except Exception as exc:
            logger.warning("search_tools falhou: %s", exc)
        return []

    def list_tools(
        self,
        category: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        """Lista tools disponíveis (sync wrapper)."""
        import asyncio
        tools = asyncio.get_event_loop().run_until_complete(
            self.discover_tools()
        )

        if category:
            tools = [t for t in tools if t["category"] == category]
        if search:
            q = search.lower()
            tools = [
                t for t in tools
                if q in t["name"].lower() or q in t["description"].lower()
            ]
        return tools

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
        """Converte tools MCP para o formato OpenAI function calling.

        Inclui automaticamente as meta-tools search_tools e call_tool
        quando include_meta=True, permitindo que o modelo descubra e
        invoque qualquer uma das 435+ tools do mcp-brasil.

        Args:
            categories: Filtrar por categorias (ex: ["camara", "ibge"])
            max_tools: Limite máximo de tools (LocalAI pode ter limites)
            search: Filtro por texto no nome/descrição
            include_meta: Incluir search_tools/call_tool (recomendado)

        Returns:
            Lista de tools no formato OpenAI:
            [{"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}]
        """
        import asyncio
        tools = asyncio.get_event_loop().run_until_complete(
            self.discover_tools()
        )

        # Converter meta-tools primeiro (sempre incluir)
        openai_tools: list[dict[str, Any]] = []
        meta_names = set()
        if include_meta:
            meta_tools = [t for t in tools if t["category"] == "meta"]
            for t in meta_tools:
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["input_schema"],
                    },
                })
                meta_names.add(t["name"])

        # Filtrar tools por categorias
        filtered = tools
        if categories:
            cat_names = set()
            for cat in categories:
                if cat in TOOL_CATEGORIES:
                    cat_names.update(TOOL_CATEGORIES[cat])
                else:
                    cat_names.add(cat)
            filtered = [
                t for t in tools
                if t["name"] not in meta_names
                and (t["category"] in categories
                     or any(p in t["name"].lower() for p in cat_names))
            ]

        # Filtro por texto
        if search:
            q = search.lower()
            filtered = [
                t for t in filtered
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
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            })

        # Adicionar tools do handler_map (execução direta, sem MCP session)
        # Essas tools NÃO estão no discover_tools() porque o MCP retorna
        # apenas meta-tools via BM25. O handler_map tem acesso direto.
        if not hasattr(self, "_handler_map"):
            self._handler_map = self._build_handler_map()
        for tool_name, handler in self._handler_map.items():
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
            schema = self._function_to_openai_schema(tool_name, handler)
            openai_tools.append(schema)

        logger.info(
            "Convertidas %d tools para OpenAI format (meta=%d, categories=%s, handler_map=%d)",
            len(openai_tools), len(meta_names), categories,
            len([t for t in openai_tools if t["function"]["name"] not in meta_names and t["function"]["name"] not in {x["name"] for x in tools}]),
        )
        return openai_tools

    @staticmethod
    def _function_to_openai_schema(name: str, fn: Callable) -> dict[str, Any]:
        """Converte uma função Python para o formato OpenAI function schema.

        Para wrappers _wrap_no_ctx que usam **kwargs, introspeia o
        __wrapped__ ou a função original para obter os params corretos.
        """
        import inspect

        # Se é um wrapper com **kwargs, tentar usar o __wrapped__
        # que é a função original antes do wrap
        target = getattr(fn, "__wrapped__", fn)
        sig = inspect.signature(target)
        properties = {}
        required = []

        # Tipos de docstrings do MCP-Brasil: extrair descrição dos params
        doc = inspect.getdoc(target) or name
        # Parse Args section se existir
        args_section = {}
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
                    # Stop if we hit Returns/Example/etc
                    if arg_name in ("Returns", "Example", "Examples", "Note", "Notes"):
                        break
                    args_section[arg_name] = arg_desc

        for pname, param in sig.parameters.items():
            if pname in ("ctx", "self", "cls"):
                continue  # Pular ctx e self
            # Mapear tipo Python → JSON Schema type
            annotation = param.annotation
            json_type = "string"
            if annotation in (int, "int", inspect.Parameter.empty):
                # Se vazio ou int, manter string (mais seguro para LLMs)
                if annotation in (int, "int"):
                    json_type = "integer"
            elif annotation in (float, "float"):
                json_type = "number"
            elif annotation in (bool, "bool"):
                json_type = "boolean"

            prop: dict[str, Any] = {"type": json_type}

            # Adicionar descrição do docstring
            if pname in args_section:
                prop["description"] = args_section[pname]

            if param.default is inspect.Parameter.empty:
                required.append(pname)
            else:
                prop["default"] = param.default

            properties[pname] = prop

        # Gerar description do docstring (primeira linha)
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

    # ------------------------------------------------------------------
    # Execução de tools (direto via clientes mcp-brasil)
    # ------------------------------------------------------------------
    def _resolve_handler(self, name: str) -> Callable | None:
        """Resolve o handler de uma tool pelo nome.

        Tenta:
        1. Handlers registrados via register_tool()
        2. Funções Python do mcp-brasil (bypass do MCP session)
        3. Fallback para call_tool MCP (pode falhar sem session)
        """
        # 1. Handlers customizados
        if name in self._callables:
            return self._callables[name]

        # 2. Resolver via importação direta do módulo
        # Mapeamento: nome_da_tool → (módulo, função)
        if not hasattr(self, "_handler_map"):
            self._handler_map = self._build_handler_map()
        if name in self._handler_map:
            return self._handler_map[name]

        return None

    def _build_handler_map(self) -> dict[str, Callable]:
        """Mapeia nomes de tools para funções Python do mcp-brasil."""
        mapping: dict[str, Callable] = {}
        import types

        def _try_import(module_path: str) -> types.ModuleType | None:
            try:
                import importlib
                return importlib.import_module(module_path)
            except (ImportError, ModuleNotFoundError):
                return None

        ibge_tools = _try_import("mcp_brasil.data.ibge.tools")
        camara_tools = _try_import("mcp_brasil.data.camara.tools")
        transferegov_tools = _try_import("mcp_brasil.data.transferegov.tools")
        siconfi_tools = _try_import("mcp_brasil.data.siconfi.tools")
        brasilapi_tools = _try_import("mcp_brasil.data.brasilapi.tools")
        transparencia_tools = _try_import("mcp_brasil.data.transparencia.tools")
        bacen_tools = _try_import("mcp_brasil.data.bacen.tools")
        dou_tools = _try_import("mcp_brasil.data.diario_oficial.tools")
        redator_tools = _try_import("mcp_brasil.agentes.redator.tools")

        _modules = {
            k: v for k, v in {
                "ibge": ibge_tools,
                "camara": camara_tools,
                "transferegov": transferegov_tools,
                "siconfi": siconfi_tools,
                "brasilapi": brasilapi_tools,
                "transparencia": transparencia_tools,
                "bacen": bacen_tools,
                "diario_oficial": dou_tools,
                "redator": redator_tools,
            }.items() if v is not None
        }

        for prefix, mod in _modules.items():
            for attr in dir(mod):
                if attr.startswith("_"):
                    continue
                fn = getattr(mod, attr)
                if not callable(fn) or inspect.isclass(fn):
                    continue
                # Pular constants, strings, etc.
                if not (inspect.isfunction(fn) or inspect.iscoroutinefunction(fn)):
                    continue
                try:
                    wrapped = self._wrap_no_ctx(fn)
                    mapping[f"{prefix}_{attr}"] = wrapped
                except (TypeError, ValueError):
                    pass

        logger.info("Handler map: %d tools mapeados", len(mapping))
        return mapping

    @staticmethod
    def _wrap_no_ctx(fn: Callable) -> Callable:
        """Envolve uma função MCP async para ser chamada sem o parâmetro ctx.

        Cria um mock mínimo do Context para preencher o parâmetro obrigatório.
        """
        import asyncio, inspect

        if not callable(fn):
            raise TypeError(f"{fn} não é chamável")
        if inspect.isclass(fn):
            raise TypeError(f"{fn} é uma classe, não função")

        try:
            sig = inspect.signature(fn)
            has_ctx = "ctx" in sig.parameters
        except (ValueError, TypeError):
            has_ctx = False

        # Mock mínimo do Context do FastMCP
        # Precisa ter métodos async (ctx.info(), ctx.warning() etc.)
        # Usamos _MockCtx ao invés de Context.model_construct() porque
        # o model_construct cria instância incompleta sem _request_context
        _mock_ctx = None
        if has_ctx:
            import types

            class _MockCtx:
                async def info(self, *a, **kw): pass
                async def warning(self, *a, **kw): pass
                async def error(self, *a, **kw): pass
                async def debug(self, *a, **kw): pass
                async def log(self, *a, **kw): pass
                async def report_progress(self, *a, **kw): pass
                session = None
                _request_context = None

            _mock_ctx = _MockCtx()

        async def wrapper(**kwargs):
            if has_ctx:
                kwargs.pop("ctx", None)
                # Injetar mock ctx como keyword arg — funciona para todos os
                # casos (POSITIONAL_OR_KEYWORD, KEYWORD_ONLY, etc.)
                try:
                    ctx_param = sig.parameters["ctx"]
                except KeyError:
                    ctx_param = None

                if ctx_param and ctx_param.kind == inspect.Parameter.POSITIONAL_ONLY:
                    # Raro — ctx como positional only, precisa posicionar
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
                    # POSITIONAL_OR_KEYWORD ou KEYWORD_ONLY — passar como kwarg
                    result = await fn(ctx=_mock_ctx, **kwargs)
            else:
                result = await fn(**kwargs)
            return result

        wrapper.__name__ = getattr(fn, "__name__", str(fn))
        wrapper.__doc__ = getattr(fn, "__doc__", "")
        wrapper.__wrapped__ = fn  # Guardar ref da função original
        return wrapper

    async def execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Executa uma tool pelo nome, usando handler direto ou MCP."""
        # 1. Tentar handler direto (sem session)
        handler = self._resolve_handler(name)
        if handler:
            try:
                import asyncio
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(**arguments)
                else:
                    result = handler(**arguments)
                # Converter resultado para string
                if isinstance(result, str):
                    return result
                if isinstance(result, list):
                    return "\n".join(str(item) for item in result)
                return str(result)
            except Exception as exc:
                error_msg = f"Erro ao executar '{name}': {exc}"
                logger.warning(error_msg)
                return error_msg

        # 2. Fallback: MCP call_tool (pode falhar sem session)
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
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.execute_tool(name, arguments)
        )

    # ------------------------------------------------------------------
    # Tool registration (para tools customizadas do projeto)
    # ------------------------------------------------------------------
    def register_tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable,
        category: str = "local",
    ) -> None:
        """Registra uma tool customizada (não-MCP) no bridge.

        Útil para expor funções Python como tools para o modelo.
        """
        self._callables[name] = handler
        if self._tools_cache is None:
            self._tools_cache = []
        self._tools_cache.append({
            "name": name,
            "description": description,
            "input_schema": parameters,
            "category": category,
            "tags": ["custom"],
        })

    # ------------------------------------------------------------------
    # Agent loop (chat + tool calling)
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
        """Executa agentic loop: chat → tool_calls → execute → repeat.

        Args:
            prompt: Pergunta do usuário
            system: System prompt opcional
            model: Modelo LocalAI a usar
            categories: Filtrar tools por categoria
            max_tools: Máximo de tools a expor
            max_turns: Máximo de iterações tool-calling
            temperature: Temperatura do modelo
            include_meta_tools: Incluir meta-tools (search_tools, recomendar_tools)

        Returns:
            Dict com "response" (texto final), "tool_calls" (lista de calls feitas),
            "turns" (número de iterações)
        """
        tools_schema = self.to_openai_tools(
            categories=categories,
            max_tools=max_tools,
            include_meta=include_meta_tools,
        )
        messages = self._build_messages(prompt, system, tools_schema)
        model = model or LOCALAI_DEFAULT_MODEL

        all_tool_calls: list[dict[str, Any]] = []
        final_response = ""

        for turn in range(max_turns):
            logger.info("Agent turn %d/%d", turn + 1, max_turns)

            # Chamar LocalAI
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 4096,
            }
            if tools_schema:
                payload["tools"] = tools_schema

            data = self._post("/chat/completions", payload)
            choice = data["choices"][0]
            message = choice["message"]

            # Adicionar resposta do assistant às mensagens
            messages.append(message)

            # Verificar se há tool_calls
            tool_calls = message.get("tool_calls", [])
            if not tool_calls:
                final_response = message.get("content", "")
                break

            # Executar cada tool_call
            for tc in tool_calls:
                func = tc["function"]
                tool_name = func["name"]
                try:
                    tool_args = json.loads(func["arguments"])
                except json.JSONDecodeError:
                    tool_args = {}

                logger.info("Executando tool: %s(%s)", tool_name, tool_args)
                result = self.execute_tool_sync(tool_name, tool_args)

                all_tool_calls.append({
                    "tool": tool_name,
                    "arguments": tool_args,
                    "result_preview": result[:200],
                })

                # Adicionar resultado como tool message
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result[:8000],  # Limitar tamanho
                })

                logger.info("Tool %s retornou %d chars", tool_name, len(result))

        return {
            "response": final_response,
            "tool_calls": all_tool_calls,
            "turns": min(turn + 1, max_turns),
            "tools_available": len(tools_schema),
        }

    # ------------------------------------------------------------------
    # Async agent chat
    # ------------------------------------------------------------------
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
        messages = self._build_messages(prompt, system, tools_schema)
        model = model or LOCALAI_DEFAULT_MODEL

        all_tool_calls: list[dict[str, Any]] = []
        final_response = ""

        for turn in range(max_turns):
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 4096,
            }
            if tools_schema:
                payload["tools"] = tools_schema

            data = await self._apost("/chat/completions", payload)
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

                result = await self.execute_tool(tool_name, tool_args)

                all_tool_calls.append({
                    "tool": tool_name,
                    "arguments": tool_args,
                    "result_preview": result[:200],
                })

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result[:8000],
                })

        return {
            "response": final_response,
            "tool_calls": all_tool_calls,
            "turns": min(turn + 1, max_turns),
            "tools_available": len(tools_schema),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _build_messages(
        prompt: str,
        system: str | None = None,
        tools: list[dict] | None = None,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        else:
            # System prompt padrão com contexto das tools disponíveis
            tool_names = [t["function"]["name"] for t in (tools or [])[:20]]
            messages.append({
                "role": "system",
                "content": (
                    "Você é um assistente de IA com acesso a ferramentas de dados "
                    "governamentais brasileiros. Use as ferramentas disponíveis para "
                    "responder perguntas sobre transferências, emendas, municípios, "
                    "finanças públicas e dados abertos.\n\n"
                    f"Ferramentas disponíveis: {', '.join(tool_names)}"
                ),
            })
        messages.append({"role": "user", "content": prompt})
        return messages

    def _post(self, endpoint: str, payload: dict) -> dict:
        """POST com retry."""
        url = f"{LOCALAI_BASE_URL.rstrip('/')}{endpoint}"
        last_exc: Exception | None = None
        for attempt in range(1, LOCALAI_MAX_RETRIES + 1):
            try:
                with httpx.Client(timeout=LOCALAI_TIMEOUT) as client:
                    resp = client.post(url, json=payload)
                    resp.raise_for_status()
                    return resp.json()
            except Exception as exc:
                last_exc = exc
                if attempt < LOCALAI_MAX_RETRIES:
                    import time
                    time.sleep(2 ** attempt)
        raise last_exc  # type: ignore[misc]

    async def _apost(self, endpoint: str, payload: dict) -> dict:
        """POST async com retry."""
        url = f"{LOCALAI_BASE_URL.rstrip('/')}{endpoint}"
        last_exc: Exception | None = None
        for attempt in range(1, LOCALAI_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=LOCALAI_TIMEOUT) as client:
                    resp = await client.post(url, json=payload)
                    resp.raise_for_status()
                    return resp.json()
            except Exception as exc:
                last_exc = exc
                if attempt < LOCALAI_MAX_RETRIES:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
        raise last_exc  # type: ignore[misc]


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
