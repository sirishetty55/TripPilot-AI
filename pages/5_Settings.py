"""
TripPilot AI — Page 5: Settings & MCP Connection Diagnostics
Manage Gemini API credentials, test the Playwright MCP connection, and inspect system audit logs.
"""

import streamlit as st
import os
from services.ui_utils import apply_custom_theme, render_hero
from services.mcp_client import PlaywrightMCPClient
from services.demo_server import start_demo_server, is_demo_server_running, DEMO_SERVER_URL
from config import get_gemini_api_key, GEMINI_MODEL, PLAYWRIGHT_MCP_COMMAND, PLAYWRIGHT_MCP_ARGS
import database

st.set_page_config(page_title="Settings — TripPilot AI", page_icon="⚙️", layout="wide")
apply_custom_theme()

render_hero("⚙️ Settings & System Diagnostics", "Configure AI providers and test live Playwright MCP server connectivity.")

tab_mcp, tab_ai, tab_demo, tab_logs = st.tabs([
    "🌐 Playwright MCP Status",
    "🤖 AI Provider Configuration",
    "🔬 Local Demo Server",
    "📋 Research Audit Logs"
])

# 1. Playwright MCP Server Diagnostics
with tab_mcp:
    st.subheader("Playwright MCP (Model Context Protocol) Connection")
    st.write("TripPilot AI uses the official `@playwright/mcp` server over stdio to control browser sessions.")

    st.markdown(f"""
    - **Command:** `{PLAYWRIGHT_MCP_COMMAND}`
    - **Arguments:** `{' '.join(PLAYWRIGHT_MCP_ARGS)}`
    """)

    if st.button("🧪 Test MCP Connection Now", type="primary", use_container_width=True):
        with st.spinner("Connecting to Playwright MCP server via Python MCP SDK..."):
            client = PlaywrightMCPClient()
            result = client.test_connection()
            
            if result.get("success"):
                st.success(f"✅ Successfully connected to **{result.get('server_name')}**!")
                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    st.metric("Protocol Version", result.get("protocol_version", "1.0"))
                with col_m2:
                    st.metric("Available Tools Discovered", result.get("tool_count", 0))

                st.markdown("#### Discovered MCP Browser Tools:")
                tool_data = [{"Tool Name": t["name"], "Description": t["description"]} for t in result.get("tools", [])]
                st.dataframe(tool_data, use_container_width=True, hide_index=True)
            else:
                st.error(f"❌ Connection failed: {result.get('error')}")
                st.info("Ensure Node.js is installed (`node -v`) and `npx` is available on your system path.")

# 2. AI Provider Configuration
with tab_ai:
    st.subheader("Gemini AI API Configuration")
    st.write("TripPilot AI uses Google Gemini to synthesize messy browser research snapshots into structured, verified itineraries.")

    current_key = get_gemini_api_key(st.session_state)
    masked_key = f"••••••••••••••••{current_key[-4:]}" if len(current_key) > 8 else ("(Not configured)" if not current_key else "••••")

    st.write(f"**Current Status:** {'✅ Configured' if current_key else '⚠️ Not set (Using Heuristic Parser)'}")
    st.write(f"**Active Model:** `{GEMINI_MODEL}`")

    with st.form("api_key_form"):
        new_key = st.text_input(
            "Enter Gemini API Key",
            type="password",
            placeholder="AIzaSy...",
            help="Get a free key at https://aistudio.google.com/"
        )
        save_key_btn = st.form_submit_button("Save API Key for Session", type="primary")

    if save_key_btn:
        if new_key.strip():
            st.session_state["custom_gemini_api_key"] = new_key.strip()
            st.success("Gemini API key saved for this active session!")
            st.rerun()
        else:
            st.error("Please enter a valid key.")

# 3. Local Demo Server Status
with tab_demo:
    st.subheader("Local Demo Travel Portal")
    st.write("A built-in static HTTP server provides guaranteed, rate-limit-free travel guides for live presentations.")

    server_running = is_demo_server_running()
    st.write(f"**Server Status:** {'🟢 Running' if server_running else '🔴 Stopped'}")
    st.write(f"**Base URL:** `{DEMO_SERVER_URL}`")

    if not server_running:
        if st.button("Start Local Demo Server"):
            start_demo_server()
            st.success("Demo server started on localhost:8765")
            st.rerun()

    st.markdown("#### Available Sample Travel Guides:")
    st.markdown(f"""
    - [🌴 Goa Coastal Guide]({DEMO_SERVER_URL}/goa.html)
    - [🏰 Jaipur Pink City Guide]({DEMO_SERVER_URL}/jaipur.html)
    - [🌿 Kerala Backwaters Guide]({DEMO_SERVER_URL}/kerala.html)
    """)

# 4. Audit Logs
with tab_logs:
    st.subheader("Recent MCP Research Sessions")
    logs = database.get_recent_research_logs(15)
    if not logs:
        st.info("No research sessions recorded in SQLite yet.")
    else:
        st.dataframe(logs, use_container_width=True, hide_index=True)
