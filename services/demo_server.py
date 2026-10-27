"""
Local demo HTTP server for TripPilot AI.
Serves static travel guides for live presentations and offline testing
ensuring 100% reliable Playwright MCP browser automation.
"""

import http.server
import socketserver
import threading
import time
import socket
from pathlib import Path
from config import BASE_DIR, DEMO_SERVER_PORT, DEMO_SERVER_HOST, DEMO_SERVER_URL

DEMO_DIR = BASE_DIR / "static" / "demo_pages"
_server_instance = None
_server_thread = None

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DEMO_DIR), **kwargs)

    def log_message(self, format, *args):
        # Suppress noisy standard HTTP access logs
        pass

def is_port_in_use(port: int, host: str = DEMO_SERVER_HOST) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0

def start_demo_server() -> bool:
    """Starts the demo static HTTP server in a background daemon thread."""
    global _server_instance, _server_thread

    if is_port_in_use(DEMO_SERVER_PORT, DEMO_SERVER_HOST):
        return True

    try:
        DEMO_DIR.mkdir(parents=True, exist_ok=True)
        # Allow immediate socket reuse
        socketserver.TCPServer.allow_reuse_address = True
        _server_instance = socketserver.TCPServer((DEMO_SERVER_HOST, DEMO_SERVER_PORT), QuietHandler)
        _server_thread = threading.Thread(target=_server_instance.serve_forever, daemon=True)
        _server_thread.start()
        time.sleep(0.3)
        return True
    except Exception as e:
        print(f"Warning: Could not start demo server on port {DEMO_SERVER_PORT}: {e}")
        return False

def get_demo_page_url(destination: str) -> str:
    """Returns local test URL for given destination."""
    dest_clean = destination.strip().lower()
    if "goa" in dest_clean:
        filename = "goa.html"
    elif "jaipur" in dest_clean:
        filename = "jaipur.html"
    elif "kerala" in dest_clean or "kochi" in dest_clean or "alleppey" in dest_clean:
        filename = "kerala.html"
    else:
        filename = "goa.html"  # Default fallback demo page
    
    start_demo_server()
    return f"{DEMO_SERVER_URL}/{filename}"

def is_demo_server_running() -> bool:
    return is_port_in_use(DEMO_SERVER_PORT, DEMO_SERVER_HOST)
