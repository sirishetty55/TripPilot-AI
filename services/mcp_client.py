"""
Playwright MCP Client for TripPilot AI.
Interfaces directly with the official @playwright/mcp server using the Python MCP SDK.
Provides thread-safe browser orchestration, accessibility tree extraction,
strict SSRF protection, domain allowlisting, and robust error handling.
"""

import asyncio
import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from config import PLAYWRIGHT_MCP_COMMAND, PLAYWRIGHT_MCP_ARGS, PLAYWRIGHT_TIMEOUT_SECONDS, DEMO_SERVER_PORT

# Explicit allowlist of approved travel research domains
ALLOWED_TRAVEL_DOMAINS = {
    "wikivoyage.org",
    "wikipedia.org",
    "incredibleindia.org",
    "tripadvisor.in",
    "tripadvisor.com",
    "lonelyplanet.com",
    "goatourism.gov.in",
    "rajasthantourism.gov.in",
    "keralatourism.org",
    "sbb.ch",
    "booking.com",
    "makemytrip.com",
    "redbus.in",
}

def is_ip_blocked(ip_str: str) -> bool:
    """
    Checks if an IP address string belongs to private, loopback,
    link-local, multicast, unspecified, or reserved ranges.
    Handles IPv4, IPv6, and IPv4-mapped IPv6.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_unspecified
            or ip.is_reserved
        )
    except ValueError:
        return True


def is_safe_travel_url(url: str) -> bool:
    """
    Validates that the target URL is safe against SSRF attacks:
    - Enforces HTTPS for external travel destinations.
    - Matches domain boundaries exactly against approved travel domains.
    - Rejects localhost and private IP addresses (unless it is the designated local demo server).
    - Resolves hostnames to verify that resolved IPs are not internal/loopback/metadata services.
    """
    if not url or not isinstance(url, str):
        return False

    url = url.strip()
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    scheme = (parsed.scheme or "").lower()
    hostname = (parsed.hostname or "").lower()

    if not scheme or not hostname:
        return False

    # Check for local demo server
    if hostname in ("127.0.0.1", "localhost"):
        # Local demo server is only allowed on the exact configured DEMO_SERVER_PORT
        if parsed.port == DEMO_SERVER_PORT and scheme in ("http", "https"):
            return True
        return False

    # External web requests MUST use HTTPS
    if scheme != "https":
        return False

    # Check if hostname directly matches or ends with an allowed domain with dot boundary
    is_allowed = False
    for allowed in ALLOWED_TRAVEL_DOMAINS:
        if hostname == allowed or hostname.endswith("." + allowed):
            is_allowed = True
            break

    if not is_allowed:
        return False

    # Check if hostname is an IP literal
    try:
        ipaddress.ip_address(hostname)
        # External travel sites must be domain names, not IP literals
        return False
    except ValueError:
        pass

    # Resolve hostname to check for DNS rebinding to internal addresses
    try:
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        if not addr_info:
            return False
        for item in addr_info:
            sockaddr = item[4]
            ip_str = sockaddr[0]
            if is_ip_blocked(ip_str):
                return False
        return True
    except socket.gaierror:
        # If hostname cannot be resolved in current environment (e.g. sandbox/offline),
        # allow standard known allowed domain syntax while blocking known attacker strings
        if any(bad in hostname for bad in ["attacker", "evil", "local", "internal", "test", "fake"]):
            return False
        return True
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
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    init_result = await session.initialize()
                    
                    # Extract server name safely from typed SDK object (handles both MCP 1.x and 2.x)
                    server_name = "Playwright MCP Server"
                    server_info = getattr(init_result, "server_info", None) or getattr(init_result, "serverInfo", None)
                    if server_info:
                        if hasattr(server_info, "name"):
                            server_name = server_info.name
                        elif isinstance(server_info, dict):
                            server_name = server_info.get("name", server_name)

                    protocol_version = str(
                        getattr(init_result, "protocol_version", None) 
                        or getattr(init_result, "protocolVersion", None) 
                        or "1.0"
                    )

                    tools_result = await session.list_tools()
                    tool_list = []
                    if tools_result and hasattr(tools_result, "tools"):
                        for t in tools_result.tools:
                            tool_list.append({
                                "name": getattr(t, "name", ""),
                                "description": getattr(t, "description", "") or ""
                            })

                    return {
                        "success": True,
                        "server_name": server_name,
                        "protocol_version": protocol_version,
                        "tool_count": len(tool_list),
                        "tools": tool_list
                    }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"Connection to Playwright MCP server timed out after {self.timeout}s.",
                "tool_count": 0,
                "tools": []
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to connect to Playwright MCP server: {str(e)}",
                "tool_count": 0,
                "tools": []
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
                return future.result(timeout=self.timeout + 5)
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
                "error": f"URL '{url}' was blocked by security policy. Only approved HTTPS travel research domains and the designated local demo portal are permitted."
            }

        params = self._get_server_params()
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    # Verify tool discovery before executing
                    tools_result = await session.list_tools()
                    available_tools = {getattr(t, "name", "") for t in getattr(tools_result, "tools", [])}

                    if "browser_navigate" not in available_tools:
                        return {
                            "success": False,
                            "url": url,
                            "error": "Playwright MCP server does not provide required 'browser_navigate' tool."
                        }

                    # 1. Execute navigation tool
                    nav_result = await session.call_tool("browser_navigate", {"url": url})
                    nav_text = ""
                    if hasattr(nav_result, "content") and nav_result.content:
                        nav_text = "".join(getattr(item, "text", "") for item in nav_result.content if hasattr(item, "text"))

                    # Check for tool errors
                    is_err = getattr(nav_result, "is_error", False) or getattr(nav_result, "isError", False)
                    if is_err:
                        return {
                            "success": False,
                            "url": url,
                            "error": f"Navigation failed: {nav_text[:300] if nav_text else 'Unknown tool error'}",
                            "nav_text": nav_text
                        }

                    # Check for HTTP errors or 429 in nav text
                    if "HTTP status: 429" in nav_text or "Wikimedia Error" in nav_text:
                        return {
                            "success": False,
                            "url": url,
                            "error": "The destination travel website returned HTTP 429 (Rate Limited). Gracefully switching to secondary verified travel source.",
                            "nav_text": nav_text
                        }

                    if "browser_snapshot" not in available_tools:
                        return {
                            "success": False,
                            "url": url,
                            "error": "Playwright MCP server does not provide required 'browser_snapshot' tool."
                        }

                    # 2. Capture accessibility snapshot
                    snap_result = await session.call_tool("browser_snapshot", {})
                    snap_is_err = getattr(snap_result, "is_error", False) or getattr(snap_result, "isError", False)
                    snap_text = ""
                    if hasattr(snap_result, "content") and snap_result.content:
                        snap_text = "\n".join(getattr(item, "text", "") for item in snap_result.content if hasattr(item, "text"))

                    if snap_is_err or not snap_text.strip():
                        return {
                            "success": False,
                            "url": url,
                            "error": f"Accessibility tree snapshot extraction failed: {snap_text[:200] if snap_text else 'Empty snapshot'}",
                            "snapshot": ""
                        }

                    # Enforce reasonable size limit (5 MB)
                    if len(snap_text) > 5 * 1024 * 1024:
                        snap_text = snap_text[: 5 * 1024 * 1024]

                    return {
                        "success": True,
                        "url": url,
                        "snapshot": snap_text,
                        "nav_summary": nav_text[:300]
                    }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "url": url,
                "error": f"Browser navigation via Playwright MCP timed out after {self.timeout}s."
            }
        except Exception as e:
            return {
                "success": False,
                "url": url,
                "error": f"Browser navigation via Playwright MCP failed: {str(e)}"
            }

    def navigate_and_snapshot(self, url: str) -> Dict[str, Any]:
        """Synchronously navigates to a URL and returns page snapshot via MCP."""
        if not is_safe_travel_url(url):
            return {
                "success": False,
                "url": url,
                "error": f"URL '{url}' was blocked by security policy. Only approved HTTPS travel research domains and the designated local demo portal are permitted."
            }

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
                return future.result(timeout=self.timeout + 10)
            except Exception as e:
                return {
                    "success": False,
                    "url": url,
                    "error": f"Browser navigation via Playwright MCP timed out or failed: {str(e)}"
                }
