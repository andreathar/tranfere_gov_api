"""
Pacote MCP — Descoberta, conversão e execução de tools MCP.

Re-exports para backward compat com src.mcp_tool_bridge:
    from src.mcp import MCPToolBridge, get_mcp_bridge, TOOL_CATEGORIES
"""

from src.mcp.bridge import MCPToolBridge, get_mcp_bridge
from src.mcp.categories import TOOL_CATEGORIES

__all__ = ["MCPToolBridge", "get_mcp_bridge", "TOOL_CATEGORIES"]
