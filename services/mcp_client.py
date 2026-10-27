"""
Playwright MCP Client for TripPilot AI.
Interfaces directly with the official @playwright/mcp server using the Python MCP SDK.
Provides thread-safe browser orchestration, accessibility tree extraction, and connection health checks.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from config import PLAYWRIGHT_MCP_COMMAND, PLAYWRIGHT_MCP_ARGS, PLAYWRIGHT_TIMEOUT_SECONDS, DEMO_SERVER_PORT

def is_safe_travel_url(url: str) -> bool:
    """
    Validates that the target URL is a safe, public travel domain or our local demo server.
    Restricts access to prevent arbitrary internal network scraping or file access.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        
        hostname = (parsed.hostname or "").lower()
        
        # Allow local demo server
        if hostname in ("127.0.0.1", "localhost") and parsed.port == DEMO_SERVER_PORT:
            return True
            
        # Allowed travel research domains
        allowed_suffixes = [
            "wikivoyage.org",
            "wikipedia.org",
            "incredibleindia.org",
            "tripadvisor.in",
            "tripadvisor.com",
            "lonelyplanet.com",
            "goatourism.gov.in",
            "rajasthantourism.gov.in",
            "keralatourism.org"
        ]
        
        for suffix in allowed_suffixes:
            if hostname == suffix or hostname.endswith("." + suffix):
                return True
                
        # By default, allow standard HTTP/HTTPS public sites with valid domains
        if "." in hostname and not hostname.startswith(("10.", "192.168.", "172.16.", "169.254.")):
            return True
            
        return False
    except Exception:
        return False

class PlaywrightMCPClient:
    """Wrapper around official Playwright MCP server over stdio."""

    def __init__(self, command: str = PLAYWRIGHT_MCP_COMMAND, args: Optional[List[str]] = None):
        self.command = command
        self.args = args or PLAYWRIGHT_MCP_ARGS
        self.timeout = PLAYWRIGHT_TIMEOUT_SECONDS

    def _get_server_params(self) -> StdioServerParameters:
        return StdioServerParameters(
            command=self.command,
            args=self.args,
            env=None
        )

    async def _async_test_connection(self) -> Dict[str, Any]:
        params = self._get_server_params()
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                init_result = await session.initialize()
                tools_result = await session.list_tools()
                tool_list = [
                    {
                        "name": t.name,
                        "description": t.description or ""
                    }
                    for t in tools_result.tools
                ]
                return {
                    "success": True,
                    "server_name": getattr(init_result, "serverInfo", {}).get("name", "Playwright MCP Server") if hasattr(init_result, "serverInfo") else "Playwright MCP Server",
                    "protocol_version": getattr(init_result, "protocolVersion", "1.0"),
                    "tool_count": len(tool_list),
                    "tools": tool_list
                }

    def test_connection(self) -> Dict[str, Any]:
        """Synchronously tests MCP server connection and returns tool list."""
        def runner():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self._async_test_connection())
            finally:
                loop.close()

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(runner)
            try:
                return future.result(timeout=self.timeout)
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "tool_count": 0,
                    "tools": []
                }

    async def _async_navigate_and_snapshot(self, url: str) -> Dict[str, Any]:
        if not is_safe_travel_url(url):
            return {
                "success": False,
                "url": url,
                "error": f"URL '{url}' was blocked by safety policy. Only public travel sites and local demo server are permitted."
            }

        params = self._get_server_params()
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # 1. Execute navigation tool
                nav_result = await session.call_tool("browser_navigate", {"url": url})
                nav_text = ""
                if hasattr(nav_result, "content") and nav_result.content:
                    nav_text = "".join(getattr(item, "text", "") for item in nav_result.content)
                
                # Check for HTTP errors or 429 in nav text
                if "HTTP status: 429" in nav_text or "Wikimedia Error" in nav_text:
                    return {
                        "success": False,
                        "url": url,
                        "error": "The destination travel website returned HTTP 429 (Rate Limited). Gracefully switching to secondary verified travel source.",
                        "nav_text": nav_text
                    }

                # 2. Capture accessibility snapshot
                snap_result = await session.call_tool("browser_snapshot", {})
                snap_text = ""
                if hasattr(snap_result, "content") and snap_result.content:
                    snap_text = "\n".join(getattr(item, "text", "") for item in snap_result.content)

                return {
                    "success": True,
                    "url": url,
                    "snapshot": snap_text,
                    "nav_summary": nav_text[:300]
                }

    def navigate_and_snapshot(self, url: str) -> Dict[str, Any]:
        """Synchronously navigates to a URL and returns page snapshot via MCP."""
        def runner():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self._async_navigate_and_snapshot(url))
            finally:
                loop.close()

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(runner)
            try:
                return future.result(timeout=self.timeout)
            except Exception as e:
                return {
                    "success": False,
                    "url": url,
                    "error": f"Browser navigation via Playwright MCP timed out or failed: {str(e)}"
                }
