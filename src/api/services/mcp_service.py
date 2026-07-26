import asyncio
import contextlib
import json
import logging
import os
import time
from typing import Any

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

log = logging.getLogger(__name__)


class MCPBrasilClient:
    def __init__(self, cache_ttl: int = 3600):
        self.cache_ttl = cache_ttl
        self._cache: dict[str, Any] = {}  # key -> (value, timestamp)
        self._session: ClientSession | None = None
        self._exit_stack = contextlib.AsyncExitStack()
        self._connect_lock = asyncio.Lock()
        self._call_lock = asyncio.Lock()

    async def connect(self):
        async with self._connect_lock:
            if self._session:
                return

            load_dotenv()
            env = os.environ.copy()

            params = StdioServerParameters(
                command="uvx",
                args=["--from", "mcp-brasil", "python", "-m", "mcp_brasil.server"],
                env=env,
            )
            # Use AsyncExitStack to properly enter and hold the context managers
            transport = await self._exit_stack.enter_async_context(stdio_client(params))
            read_stream, write_stream = transport

            self._session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await self._session.initialize()
            log.info("MCP Brasil Server initialized successfully.")

    async def close(self):
        await self._exit_stack.aclose()
        self._session = None

    def _cache_get(self, key: str) -> Any | None:
        """Busca no cache com TTL. Retorna None se expirado."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        value, ts = entry
        if time.monotonic() - ts > self.cache_ttl:
            del self._cache[key]
            return None
        return value

    def _cache_set(self, key: str, value: Any) -> None:
        """Armazena no cache com timestamp."""
        self._cache[key] = (value, time.monotonic())

    async def call_tool(self, name: str, args: dict) -> Any:
        if not self._session:
            await self.connect()

        cache_key = f"{name}:{json.dumps(args, sort_keys=True)}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        async with self._call_lock:
            # Double-check after acquiring lock
            cached = self._cache_get(cache_key)
            if cached is not None:
                return cached
            log.info("Calling MCP Tool: %s with args %s", name, args)
            result = await self._session.call_tool(name, args)  # type: ignore[union-attr]

        text_result = result.content[0].text if result.content else None  # type: ignore[union-attr]

        self._cache_set(cache_key, text_result)
        return text_result

    async def call_tools_batch(self, consultas: list[dict]) -> Any:
        if not self._session:
            await self.connect()

        cache_key = f"executar_lote:{json.dumps(consultas, sort_keys=True)}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        async with self._call_lock:
            cached = self._cache_get(cache_key)
            if cached is not None:
                return cached
            log.info("Calling MCP Tool: executar_lote with %d consultas", len(consultas))
            result = await self._session.call_tool("executar_lote", {"consultas": consultas})  # type: ignore[union-attr]

        text_result = result.content[0].text if result.content else None  # type: ignore[union-attr]

        try:
            parsed = json.loads(text_result) if text_result else {}
            self._cache_set(cache_key, parsed)
            return parsed
        except json.JSONDecodeError:
            self._cache_set(cache_key, {"result": text_result})
            return {"result": text_result}


# Global singleton client
_mcp_client = MCPBrasilClient()


async def get_saude_resumo(codigo_ibge: str) -> Any:
    """Wrapper for farmacia_popular_buscar_farmacias as an alternative to the broken saude endpoint"""
    import json

    # CNES/DataSUS generally requires the 6-digit IBGE code (without check digit)
    cnes_ibge = str(codigo_ibge)[:6] if len(str(codigo_ibge)) == 7 else str(codigo_ibge)
    res = await _mcp_client.call_tool(
        "farmacia_popular_buscar_farmacias", {"codigo_municipio": cnes_ibge, "limit": 5}
    )
    try:
        return json.loads(res) if res else {}
    except json.JSONDecodeError:
        return {"result": res}


async def buscar_processos_datajud(query: str) -> Any:
    """Wrapper for datajud_buscar_processos with retry for upstream timeouts"""
    import asyncio
    import json

    max_retries = 2
    for attempt in range(max_retries + 1):
        res = await _mcp_client.call_tool(
            "datajud_buscar_processos", {"query": query, "tamanho": 3}
        )

        # Check if it's the specific timeout message
        if res and "Upstream request timed out" in res and attempt < max_retries:
            log.warning(
                "DataJud timed out for query '%s', retrying %d/%d...",
                query,
                attempt + 1,
                max_retries,
            )
            await asyncio.sleep(2.0)
            continue

        # Check if rate limited
        if res and "Rate limited" in res and attempt < max_retries:
            wait_time = 5.0 * (attempt + 1)
            log.warning(
                "DataJud rate limited for query '%s', waiting %.1fs before retry %d/%d...",
                query,
                wait_time,
                attempt + 1,
                max_retries,
            )
            await asyncio.sleep(wait_time)
            continue

        try:
            return json.loads(res) if res else {}
        except json.JSONDecodeError:
            return {"result": res}


async def executar_lote(consultas: list[dict]) -> Any:
    """Wrapper for executar_lote"""
    return await _mcp_client.call_tools_batch(consultas)


async def buscar_diario_perfil(
    nome: str,
    escopo: str = "ambos",
    uf_municipio: str | None = None,
    data_inicio: str | None = None,
    data_fim: str | None = None,
) -> dict:
    """Busca citações de um nome no Diário Oficial (DOU + Querido Diário).

    Returns dict com keys:
      - federal: list de publicações DOU
      - municipal: list de publicações Querido Diário
      - query: termo buscado
      - total: soma de resultados
    """
    import json as _json

    results: dict[str, Any] = {
        "federal": [],
        "municipal": [],
        "query": nome,
        "total": 0,
    }

    # Busca DOU federal
    if escopo in ("ambos", "federal"):
        try:
            dou_args: dict[str, Any] = {"texto": nome, "secao": "DOU-e"}
            if data_inicio:
                dou_args["data_inicio"] = data_inicio
            if data_fim:
                dou_args["data_fim"] = data_fim

            res = await _mcp_client.call_tool("diario_oficial_dou_buscar", dou_args)
            if res:
                parsed = _json.loads(res) if isinstance(res, str) else res
                if isinstance(parsed, list):
                    results["federal"] = parsed[:20]
                elif isinstance(parsed, dict):
                    items = parsed.get("items") or parsed.get("data") or []
                    results["federal"] = (items if isinstance(items, list) else [])[:20]
        except Exception as e:
            log.warning("Erro busca DOU federal para '%s': %s", nome, e)
            results["federal_error"] = str(e)

    # Busca Querido Diário (municipal)
    if escopo in ("ambos", "municipal"):
        try:
            qd_args: dict[str, Any] = {"texto": nome}
            if uf_municipio:
                qd_args["uf"] = uf_municipio

            res = await _mcp_client.call_tool("diario_oficial_buscar_diarios", qd_args)
            if res:
                parsed = _json.loads(res) if isinstance(res, str) else res
                if isinstance(parsed, list):
                    results["municipal"] = parsed[:20]
                elif isinstance(parsed, dict):
                    items = parsed.get("items") or parsed.get("data") or []
                    results["municipal"] = (items if isinstance(items, list) else [])[:20]
        except Exception as e:
            log.warning("Erro busca Querido Diário para '%s': %s", nome, e)
            results["municipal_error"] = str(e)

    results["total"] = len(results["federal"]) + len(results["municipal"])
    return results
