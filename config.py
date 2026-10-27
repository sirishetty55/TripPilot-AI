"""
Configuration settings for TripPilot AI.
Loads settings from .env file or environment variables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory of Project
BASE_DIR = Path(__file__).resolve().parent

# Load .env file
ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE)

# Gemini AI Configuration
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL

# Playwright MCP Configuration
LOCAL_MCP_CLI = BASE_DIR / "node_modules" / "@playwright" / "mcp" / "cli.js"
if LOCAL_MCP_CLI.exists():
    PLAYWRIGHT_MCP_COMMAND = "node"
    PLAYWRIGHT_MCP_ARGS = [
        str(LOCAL_MCP_CLI),
        "--headless",
        "--image-responses", "omit",
        "--block-service-workers",
        "--timeout-settle", "150",
        "--user-agent",
        "TripPilotAI/1.0 (Educational Travel Assistant; contact@trippilot.edu) Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ]
else:
    PLAYWRIGHT_MCP_COMMAND = os.getenv("PLAYWRIGHT_MCP_COMMAND", "npx").strip()
    PLAYWRIGHT_MCP_ARGS = [
        "-y",
        "@playwright/mcp@latest",
        "--headless",
        "--image-responses", "omit",
        "--block-service-workers",
        "--timeout-settle", "150",
        "--user-agent",
        "TripPilotAI/1.0 (Educational Travel Assistant; contact@trippilot.edu) Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ]
PLAYWRIGHT_TIMEOUT_SECONDS = int(os.getenv("PLAYWRIGHT_TIMEOUT_SECONDS", "30"))

# Database Configuration
DATABASE_PATH = BASE_DIR / os.getenv("DATABASE_PATH", "trippilot.db")

# Demo Server Configuration
DEMO_SERVER_PORT = int(os.getenv("DEMO_SERVER_PORT", "8765"))
DEMO_SERVER_HOST = "127.0.0.1"
DEMO_SERVER_URL = f"http://{DEMO_SERVER_HOST}:{DEMO_SERVER_PORT}"

# Supported Travel Categories
INTEREST_OPTIONS = [
    "Nature & Landscapes",
    "Beaches & Coastal",
    "Adventure & Outdoors",
    "History & Heritage",
    "Shopping & Markets",
    "Food & Culinary",
    "Nightlife & Social",
    "Relaxation & Wellness"
]

ACCOMMODATION_TIERS = ["budget", "mid-range", "luxury"]
TRAVEL_STYLES = ["relaxed", "balanced", "packed"]

def get_gemini_api_key(session_state=None) -> str:
    """
    Returns active Gemini API key from session state if set by user in UI,
    otherwise falls back to environment variable or .env file.
    """
    if session_state and hasattr(session_state, "get"):
        ui_key = session_state.get("custom_gemini_api_key", "").strip()
        if ui_key:
            return ui_key
    # Also reload from env in case user updated .env
    return os.getenv("GEMINI_API_KEY", GEMINI_API_KEY).strip()
