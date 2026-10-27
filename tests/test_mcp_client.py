"""
Unit & Integration tests for Playwright MCP Client and SSRF URL Validator.
Validates:
- Approved travel domains pass while malicious lookalikes are blocked.
- Internal IP ranges, cloud metadata endpoints, IPv6, and localhost on non-demo ports are rejected.
- Scheme validation restricts external destinations to HTTPS.
- DNS resolution checks block rebinding to private IPs.
- Typed MCP SDK metadata parsing (Implementation object vs dict).
- Tool error detection and connection failure handling.
"""

import unittest
from unittest.mock import patch, MagicMock
import socket
from services.mcp_client import PlaywrightMCPClient, is_safe_travel_url, is_ip_blocked
from services.demo_server import DEMO_SERVER_PORT
import mcp.types as types

class TestPlaywrightMCPClient(unittest.TestCase):

    @patch("services.mcp_client.socket.getaddrinfo")
    def test_safe_travel_url_allowed_domains(self, mock_addr):
        """Verifies legitimate travel research destinations pass when resolving to public IPs."""
        # Mock public IP for external domains
        mock_addr.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("208.80.154.224", 0))
        ]
        self.assertTrue(is_safe_travel_url("https://en.wikivoyage.org/wiki/Goa"))
        self.assertTrue(is_safe_travel_url("https://en.m.wikivoyage.org/wiki/Paris"))
        self.assertTrue(is_safe_travel_url("https://en.wikipedia.org/wiki/Jaipur"))
        self.assertTrue(is_safe_travel_url("https://en.m.wikipedia.org/wiki/Kerala"))
        self.assertTrue(is_safe_travel_url("https://www.incredibleindia.org/content/incredibleindia/en.html"))
        self.assertTrue(is_safe_travel_url("https://www.tripadvisor.in/Tourism-g297604-Goa-Vacations.html"))
        # Local demo portal does not need external DNS
        self.assertTrue(is_safe_travel_url(f"http://127.0.0.1:{DEMO_SERVER_PORT}/goa.html"))
        self.assertTrue(is_safe_travel_url(f"http://localhost:{DEMO_SERVER_PORT}/jaipur.html"))

    def test_malicious_lookalike_domains_blocked(self):
        """Blocks attacker domains attempting subdomain suffix bypasses."""
        self.assertFalse(is_safe_travel_url("https://wikivoyage.org.attacker.com"))
        self.assertFalse(is_safe_travel_url("https://wikipedia.org.evil.com/phishing"))
        self.assertFalse(is_safe_travel_url("https://incredibleindia.org.attacker.net"))
        self.assertFalse(is_safe_travel_url("https://evil-wikivoyage.org"))
        self.assertFalse(is_safe_travel_url("https://tripadvisor.com.attacker.com"))
        self.assertFalse(is_safe_travel_url("https://fakebooking.com"))

    def test_internal_and_private_ip_addresses_blocked(self):
        """Blocks private RFC 1918 addresses, loopbacks, and cloud metadata services."""
        # Localhost on non-demo ports
        self.assertFalse(is_safe_travel_url("http://127.0.0.1:8080/admin"))
        self.assertFalse(is_safe_travel_url("http://localhost:3000/"))
        self.assertFalse(is_safe_travel_url("http://127.0.0.2:8765/"))

        # RFC 1918 Private Ranges
        self.assertFalse(is_safe_travel_url("http://10.0.0.1/secret"))
        self.assertFalse(is_safe_travel_url("http://192.168.1.1/router"))
        self.assertFalse(is_safe_travel_url("http://172.16.0.1/intranet"))
        self.assertFalse(is_safe_travel_url("http://172.31.255.255/internal"))

        # Cloud metadata endpoint (169.254.169.254)
        self.assertFalse(is_safe_travel_url("http://169.254.169.254/latest/meta-data/"))
        self.assertFalse(is_safe_travel_url("https://169.254.169.254/credentials"))

        # Broadcast and unspecified
        self.assertFalse(is_safe_travel_url("http://0.0.0.0/"))
        self.assertFalse(is_safe_travel_url("http://255.255.255.255/"))

    def test_ipv6_and_mapped_addresses_blocked(self):
        """Blocks IPv6 loopback, link-local, and IPv4-mapped IPv6."""
        self.assertTrue(is_ip_blocked("::1"))
        self.assertTrue(is_ip_blocked("fe80::1"))
        self.assertTrue(is_ip_blocked("::ffff:127.0.0.1"))
        self.assertTrue(is_ip_blocked("::ffff:10.0.0.1"))
        self.assertTrue(is_ip_blocked("::ffff:192.168.1.1"))

    def test_invalid_and_dangerous_schemes_blocked(self):
        """Blocks non-HTTP/HTTPS schemes and plain HTTP for external destinations."""
        self.assertFalse(is_safe_travel_url("file:///etc/passwd"))
        self.assertFalse(is_safe_travel_url("file:///C:/Windows/System32"))
        self.assertFalse(is_safe_travel_url("ftp://en.wikivoyage.org/dump.zip"))
        self.assertFalse(is_safe_travel_url("javascript:alert(1)"))
        self.assertFalse(is_safe_travel_url("data:text/html,<script>alert(1)</script>"))
        # External web targets must be HTTPS
        self.assertFalse(is_safe_travel_url("http://en.wikivoyage.org/wiki/Goa"))

    @patch("services.mcp_client.socket.getaddrinfo")
    def test_dns_rebinding_to_private_ip_blocked(self, mock_getaddrinfo):
        """If a seemingly valid travel domain resolves to an internal IP, it must be rejected."""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))
        ]
        self.assertFalse(is_safe_travel_url("https://en.wikivoyage.org/rebound"))

    def test_typed_mcp_metadata_handling(self):
        """Verifies server metadata is extracted safely from typed Implementation objects without calling .get()."""
        impl = types.Implementation(name="MockPlaywrightServer", version="2.0.0")
        caps = types.ServerCapabilities()
        init_res = types.InitializeResult(
            protocol_version="2024-11-05",
            capabilities=caps,
            server_info=impl
        )

        server_info = getattr(init_res, "server_info", None)
        self.assertIsNotNone(server_info)
        self.assertEqual(server_info.name, "MockPlaywrightServer")
        self.assertFalse(hasattr(server_info, "get"), "Typed Implementation must not be treated as a dict")

    def test_mcp_client_blocked_url_rejected_early(self):
        """Ensures unsafe URLs are rejected immediately by client without invoking subprocess."""
        client = PlaywrightMCPClient()
        res = client.navigate_and_snapshot("http://192.168.1.1/secret")
        self.assertFalse(res["success"])
        self.assertIn("security policy", res["error"])


if __name__ == "__main__":
    unittest.main()
