"""
Security regression tests for HTML escaping, XSS prevention, and URL sanitization.
Ensures that untrusted user, scraped, or AI text and malicious URLs cannot inject executable scripts.
"""

import unittest
from services.ui_utils import safe_html, safe_url, render_card_image

class TestSecurityHtml(unittest.TestCase):

    def test_safe_html_escapes_script_tags(self):
        payload = "<script>alert('XSS')</script>"
        escaped = safe_html(payload)
        self.assertNotIn("<script>", escaped)
        self.assertIn("&lt;script&gt;", escaped)

    def test_safe_html_escapes_event_handlers(self):
        payload = '<img src=x onerror="alert(1)">'
        escaped = safe_html(payload)
        self.assertNotIn("<img", escaped)
        self.assertIn("&lt;img", escaped)

    def test_safe_html_escapes_quotes_and_attributes(self):
        payload = '"><script>alert(document.cookie)</script>'
        escaped = safe_html(payload)
        self.assertNotIn('">', escaped)
        self.assertIn("&quot;&gt;", escaped)

    def test_safe_url_allows_valid_https(self):
        url = "https://www.booking.com/hotel/in/sample.html"
        self.assertEqual(safe_url(url), url)

    def test_safe_url_allows_valid_http(self):
        url = "http://127.0.0.1:8765/goa.html"
        self.assertEqual(safe_url(url), url)

    def test_safe_url_disarms_javascript_scheme(self):
        payload = "javascript:alert(document.domain)"
        self.assertEqual(safe_url(payload), "#")

    def test_safe_url_disarms_data_scheme(self):
        payload = "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg=="
        self.assertEqual(safe_url(payload), "#")

    def test_safe_url_disarms_vbscript(self):
        payload = "vbscript:msgbox(1)"
        self.assertEqual(safe_url(payload), "#")

    def test_render_card_image_sanitizes_attributes(self):
        html_out = render_card_image(
            image_url="https://images.example.com/photo.jpg",
            alt_text='Malicious "><script>alert(1)</script>',
            attribution_text='Photo by <script>evil()</script>',
            attribution_url='javascript:steal()'
        )
        self.assertNotIn("<script>", html_out)
        self.assertNotIn("javascript:steal", html_out)
        self.assertIn("&lt;script&gt;", html_out)
        self.assertIn("https://images.example.com/photo.jpg", html_out)


if __name__ == "__main__":
    unittest.main()

