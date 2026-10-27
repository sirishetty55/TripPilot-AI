"""
Integration tests for Playwright MCP Client.
"""

import unittest
from services.mcp_client import PlaywrightMCPClient, is_safe_travel_url
from services.demo_server import start_demo_server, get_demo_page_url

class TestPlaywrightMCPClient(unittest.TestCase):

    def test_safe_travel_url_validation(self):
        # Permitted URLs
        self.assertTrue(is_safe_travel_url("https://en.wikivoyage.org/wiki/Goa"))
        self.assertTrue(is_safe_travel_url("https://en.wikipedia.org/wiki/Goa"))
        self.assertTrue(is_safe_travel_url("http://127.0.0.1:8765/goa.html"))
        self.assertTrue(is_safe_travel_url("https://www.tripadvisor.in/Tourism-g297604-Goa-Vacations.html"))

        # Blocked dangerous URLs
        self.assertFalse(is_safe_travel_url("file:///etc/passwd"))
        self.assertFalse(is_safe_travel_url("file:///C:/Windows/System32"))
        self.assertFalse(is_safe_travel_url("http://192.168.1.1/admin"))
        self.assertFalse(is_safe_travel_url("http://10.0.0.1/secret"))
        self.assertFalse(is_safe_travel_url("ftp://ftp.example.com"))

    def test_mcp_connection_and_tool_discovery(self):
        client = PlaywrightMCPClient()
        result = client.test_connection()
        self.assertTrue(result.get("success"), f"MCP Connection failed: {result.get('error')}")
        self.assertGreater(result.get("tool_count", 0), 10)
        tool_names = [t["name"] for t in result.get("tools", [])]
        self.assertIn("browser_navigate", tool_names)
        self.assertIn("browser_snapshot", tool_names)

    def test_mcp_navigation_on_demo_page(self):
        start_demo_server()
        url = get_demo_page_url("Goa")
        client = PlaywrightMCPClient()
        res = client.navigate_and_snapshot(url)
        self.assertTrue(res.get("success"), f"Navigation failed: {res.get('error')}")
        self.assertIn("snapshot", res)
        self.assertGreater(len(res["snapshot"]), 500)
        self.assertIn("Goa", res["snapshot"])

if __name__ == "__main__":
    unittest.main()
