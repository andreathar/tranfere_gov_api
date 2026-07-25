import asyncio
from typing import Any, Dict, List, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import logging
import os
import contextlib
from dotenv import load_dotenv

log = logging.getLogger(__name__)

class MCPBrasilClient:
    def __init__(self, cache_ttl: int = 3600):
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Any] = {}
        self._session: Optional[ClientSession] = None
        self._exit_stack = contextlib.AsyncExitStack()
        self._lock = asyncio.Lock()

    async def connect(self):
        async with self._lock:
            if self._session:
                return
                
            load_dotenv()
            env = os.environ.copy()
            
            params = StdioServerParameters(
                command="uvx",
                args=["--from", "mcp-brasil", "python", "-m", "mcp_brasil.server"],
                env=env
            )
            # Use AsyncExitStack to properly enter and hold the context managers
            transport = await self._exit_stack.enter_async_context(stdio_client(params))
            read_stream, write_stream = transport
            
            self._session = await self._exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
            await self._session.initialize()
            log.info("MCP Brasil Server initialized successfully.")

    async def close(self):
        await self._exit_stack.aclose()
        self._session = None

    async def call_tool(self, name: str, args: Dict) -> Any:
        if not self._session:
            await self.connect()
            
        # Basic cache
        import json
        cache_key = f"{name}:{json.dumps(args, sort_keys=True)}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        async with self._lock:
            log.info(f"Calling MCP Tool: {name} with args {args}")
            result = await self._session.call_tool(name, args)
        
        text_result = result.content[0].text if result.content else None
        
        self._cache[cache_key] = text_result
        return text_result

    async def call_tools_batch(self, consultas: List[Dict]) -> Any:
        import json
        if not self._session:
            await self.connect()
            
        cache_key = f"executar_lote:{json.dumps(consultas, sort_keys=True)}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        async with self._lock:
            log.info(f"Calling MCP Tool: executar_lote with {len(consultas)} consultas")
            result = await self._session.call_tool("executar_lote", {"consultas": consultas})
            
        text_result = result.content[0].text if result.content else None
        
        try:
            parsed = json.loads(text_result) if text_result else {}
            self._cache[cache_key] = parsed
            return parsed
        except json.JSONDecodeError:
            self._cache[cache_key] = {"result": text_result}
            return {"result": text_result}

# Global singleton client
_mcp_client = MCPBrasilClient()

async def get_saude_resumo(codigo_ibge: str) -> Any:
    """Wrapper for farmacia_popular_buscar_farmacias as an alternative to the broken saude endpoint"""
    import json
    # CNES/DataSUS generally requires the 6-digit IBGE code (without check digit)
    cnes_ibge = str(codigo_ibge)[:6] if len(str(codigo_ibge)) == 7 else str(codigo_ibge)
    res = await _mcp_client.call_tool("farmacia_popular_buscar_farmacias", {"codigo_municipio": cnes_ibge, "limit": 5})
    try:
        return json.loads(res) if res else {}
    except json.JSONDecodeError:
        return {"result": res}

async def buscar_processos_datajud(query: str) -> Any:
    """Wrapper for datajud_buscar_processos with retry for upstream timeouts"""
    import json
    import asyncio
    
    max_retries = 2
    for attempt in range(max_retries + 1):
        res = await _mcp_client.call_tool("datajud_buscar_processos", {"query": query, "tamanho": 3})
        
        # Check if it's the specific timeout message
        if res and "Upstream request timed out" in res and attempt < max_retries:
            log.warning(f"DataJud timed out for query '{query}', retrying {attempt+1}/{max_retries}...")
            await asyncio.sleep(2.0)
            continue
            
        # Check if rate limited
        if res and "Rate limited" in res and attempt < max_retries:
            wait_time = 5.0 * (attempt + 1)
            log.warning(f"DataJud rate limited for query '{query}', waiting {wait_time}s before retry {attempt+1}/{max_retries}...")
            await asyncio.sleep(wait_time)
            continue
            
        try:
            return json.loads(res) if res else {}
        except json.JSONDecodeError:
            return {"result": res}

async def executar_lote(consultas: List[Dict]) -> Any:
    """Wrapper for executar_lote"""
    return await _mcp_client.call_tools_batch(consultas)
