"""Shared lifespan for mcp-brasil — creates/closes an httpx.AsyncClient.

The HTTP client is available in tools via ctx.lifespan_context["http_client"].

Usage:
    from mcp_brasil._shared.lifespan import http_lifespan

    mcp = FastMCP("mcp-brasil", lifespan=http_lifespan)
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan

from mcp_brasil.settings import HTTP_TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)


@lifespan
async def http_lifespan(server: FastMCP[Any]) -> AsyncIterator[dict[str, Any] | None]:
    """Create a shared httpx.AsyncClient on startup, close on shutdown."""
    logger.info("Starting shared HTTP client")
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(HTTP_TIMEOUT),
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
        follow_redirects=True,
    )
    try:
        yield {"http_client": client}
    finally:
        await client.aclose()
        logger.info("Shared HTTP client closed")
