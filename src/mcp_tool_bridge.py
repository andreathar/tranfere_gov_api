"""
Backward-compat shim — importa de src.mcp.

Este arquivo existe para manter compatibilidade com imports antigos:
    from src.mcp_tool_bridge import MCPToolBridge, get_mcp_bridge

Novos código devem usar:
    from src.mcp import MCPToolBridge, get_mcp_bridge
"""

from src.mcp.bridge import MCPToolBridge, get_mcp_bridge  # noqa: F401
from src.mcp.categories import TOOL_CATEGORIES  # noqa: F401

__all__ = ["MCPToolBridge", "get_mcp_bridge", "TOOL_CATEGORIES"]
