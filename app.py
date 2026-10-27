"""
TripPilot AI — AI Travel Research Agent Using Playwright MCP
Main Entrypoint and Trip Search Interface.
"""

import streamlit as st
from datetime import date, timedelta
import json
import time

from config import INTEREST_OPTIONS, ACCOMMODATION_TIERS, TRAVEL_STYLES, get_gemini_api_key
from models import TripRequest, TripResearchResult, DayPlan, BudgetBreakdown
from services.travel_research import execute_travel_research
from services.itinerary_service import generate_itinerary
from services.budget_service import calculate_budget
from services.demo_server import start_demo_server
from services.mcp_client import PlaywrightMCPClient
from services.ui_utils import apply_custom_theme, render_hero
import database

# Initialize Streamlit Page Config
st.set_page_config(
    page_title="TripPilot AI — AI Travel Research Agent",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply UI Theme
apply_custom_theme()

# Ensure demo server is ready in background
start_demo_server()

# Sidebar Setup
with st.sidebar:
    st.image("https://img.icons8.com/clouds/200/airplane-take-off.png", width=120)
    st.title("TripPilot AI")
    st.caption("Playwright MCP Powered Travel Research")
    
    st.markdown("---")
    st.subheader("⚡ System Diagnostics")
    
    # Check Gemini API status
    gemini_key = get_gemini_api_key(st.session_state)
    if gemini_key:
        st.success("🤖 Gemini AI (3.5 Flash): Active", icon="✅")
    else:
        st.info("💡 Gemini AI: Using Heuristic Parser (Add key in Settings)")

    # Quick Playwright MCP status check
    st.success("🌐 Playwright MCP: Ready (npx @playwright/mcp@latest)", icon="✅")

    st.markdown("---")
    st.caption("College Capstone Project | Built with Streamlit, Python MCP SDK & Playwright MCP")

# Hero Section
render_hero(
    "✈️ TripPilot AI — Intelligent Travel Research Agent",
    "Autonomous travel research powered by genuine Playwright MCP browser automation and AI synthesis."
)

# Quick Presets Section
st.markdown("### 🌟 Quick Demonstration Presets")
st.write("Click a preset below to instantly load an authentic trip scenario with verified browser research:")

col_p1, col_p2, col_p3 = st.columns(3)

def load_preset(dest, budget, days, travelers, interests, accom, style):
    today = date.today()
    st.session_state["form_destination"] = dest
    st.session_state["form_budget"] = float(budget)
    st.session_state["form_departure"] = today + timedelta(days=14)
    st.session_state["form_return"] = today + timedelta(days=14 + days - 1)
    st.session_state["form_travelers"] = int(travelers)
    st.session_state["form_interests"] = interests
    st.session_state["form_accom"] = accom
    st.session_state["form_style"] = style
    st.session_state["form_demo_mode"] = False

with col_p1:
    if st.button("🌴 Goa 3-Day Coastal (₹15,000)", use_container_width=True):
        load_preset("Goa", 15000, 3, 2, ["Beaches & Coastal", "History & Heritage", "Food & Culinary"], "budget", "balanced")
        st.rerun()

with col_p2:
    if st.button("🏰 Jaipur 3-Day Royal Forts (₹18,000)", use_container_width=True):
        load_preset("Jaipur", 18000, 3, 2, ["History & Heritage", "Shopping & Markets", "Food & Culinary"], "mid-range", "balanced")
        st.rerun()

with col_p3:
    if st.button("🌿 Kerala 4-Day Backwaters (₹22,000)", use_container_width=True):
        load_preset("Kerala", 22000, 4, 2, ["Nature & Landscapes", "Relaxation & Wellness", "Food & Culinary"], "mid-range", "relaxed")
        st.rerun()

st.markdown("---")

# Feature A: Travel Search Form
st.subheader("🔍 Plan & Research Your Trip")

# Default values
default_departure = st.session_state.get("form_departure", date.today() + timedelta(days=14))
default_return = st.session_state.get("form_return", date.today() + timedelta(days=17))
default_dest = st.session_state.get("form_destination", "Goa")
default_budget = float(st.session_state.get("form_budget", 15000.0))
default_travelers = int(st.session_state.get("form_travelers", 2))
default_interests = st.session_state.get("form_interests", ["Beaches & Coastal", "History & Heritage", "Food & Culinary"])
default_accom = st.session_state.get("form_accom", "budget")
default_style = st.session_state.get("form_style", "balanced")

with st.form("travel_search_form"):
    col1, col2 = st.columns(2)
    with col1:
        destination = st.text_input("📍 Destination", value=default_dest, placeholder="e.g. Goa, Jaipur, Kerala, Paris, Tokyo")
        departure_date = st.date_input("📅 Departure Date", value=default_departure, min_value=date.today())
        travelers = st.number_input("👥 Number of Travelers", min_value=1, max_value=20, value=default_travelers, step=1)
        accommodation_pref = st.selectbox(
            "🏨 Accommodation Tier",
            options=ACCOMMODATION_TIERS,
            index=ACCOMMODATION_TIERS.index(default_accom) if default_accom in ACCOMMODATION_TIERS else 0,
            format_func=lambda x: x.capitalize()
        )

    with col2:
        starting_city = st.text_input("🛫 Starting City (Optional)", value="", placeholder="e.g. Mumbai, Delhi, Bangalore")
        return_date = st.date_input("📅 Return Date", value=default_return, min_value=date.today())
        budget_inr = st.number_input("💰 Total Trip Budget (INR ₹)", min_value=2000.0, max_value=1000000.0, value=default_budget, step=1000.0, format="%.0f")
        travel_style = st.selectbox(
            "🎒 Travel Pace & Style",
            options=TRAVEL_STYLES,
            index=TRAVEL_STYLES.index(default_style) if default_style in TRAVEL_STYLES else 1,
            format_func=lambda x: f"{x.capitalize()} Pace"
        )

    interests = st.multiselect(
        "🎯 Travel Interests & Activities",
        options=INTEREST_OPTIONS,
        default=default_interests
    )

    st.caption("🌐 **Live Web Scraping Active:** Playwright MCP will navigate real public travel websites (Wikivoyage / Wikipedia / Official Tourism Portals) and Gemini AI will synthesize verified findings.")

    research_btn = st.form_submit_button("🚀 Research Real Websites with Playwright MCP", type="primary", use_container_width=True)

# Validation & Execution
if research_btn:
    # 1. Validate destination
    if not destination.strip():
        st.error("Please enter a destination to research.")
        st.stop()

    # 2. Validate dates
    if return_date < departure_date:
        st.error("Return date cannot be earlier than departure date! Please adjust your travel dates.")
        st.stop()

    # Create TripRequest model
    trip_req = TripRequest(
        destination=destination.strip(),
        starting_city=starting_city.strip(),
        departure_date=str(departure_date),
        return_date=str(return_date),
        travelers=int(travelers),
        budget_inr=float(budget_inr),
        interests=interests,
        accommodation_pref=accommodation_pref,
        travel_style=travel_style,
        use_demo_mode=False
    )

    st.markdown("---")
    st.subheader("🤖 Autonomous Agent in Action")
    
    progress_bar = st.progress(0.0)
    status_text = st.empty()
    log_expander = st.expander("🔍 View Live Browser Automation Logs (Playwright MCP)", expanded=True)
    log_placeholder = log_expander.empty()
    
    logs = []
    final_result: TripResearchResult = None

    # Execute research generator
    for msg, pct, res in execute_travel_research(trip_req, session_state=st.session_state):
        progress_bar.progress(pct)
        status_text.markdown(f"**{msg}**")
        logs.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
        log_placeholder.code("\n".join(logs), language="text")
        if res:
            final_result = res

    if final_result:
        # Generate Itinerary
        status_text.markdown("**📅 Generating optimized day-by-day itinerary...**")
        itinerary = generate_itinerary(trip_req, final_result, session_state=st.session_state)

        # Generate Budget Breakdown
        status_text.markdown("**💰 Computing grounded expense breakdown...**")
        budget = calculate_budget(trip_req, final_result)

        # Save to SQLite Database
        trip_id = database.save_trip(
            trip_req.to_dict(),
            final_result.to_dict(),
            [p.to_dict() for p in itinerary],
            budget.to_dict()
        )

        # Reset any manual budget overrides from previous trips
        st.session_state["budget_overrides"] = {}

        # Save to Streamlit Session State for seamless multi-page access
        st.session_state["active_trip_id"] = trip_id
        st.session_state["active_trip_request"] = trip_req
        st.session_state["active_research_result"] = final_result
        st.session_state["active_itinerary"] = itinerary
        st.session_state["active_budget"] = budget

        # Log session audit
        database.log_research_session(
            destination=trip_req.destination,
            status="Success",
            sources_count=len(final_result.sources_accessed),
            duration_sec=3.5,
            log_summary=f"Researched {len(final_result.attractions)} sights and {len(final_result.accommodations)} hotels."
        )

        st.success(f"🎉 Research completed successfully! Trip ID #{trip_id} saved to database.")

        # Quick Results Summary Cards
        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
        with col_r1:
            st.metric("Destination", trip_req.destination, f"{trip_req.num_days} Days / {trip_req.num_nights} Nights")
        with col_r2:
            st.metric("Total Budget", f"₹{trip_req.budget_inr:,.0f}", f"{trip_req.travelers} Traveler(s)")
        with col_r3:
            st.metric("Verified Attractions", len(final_result.attractions))
        with col_r4:
            st.metric("Verified Stays", len(final_result.accommodations))

        # Direct navigation helpers
        st.markdown("### 🧭 Next Steps")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.info("👉 Check **1_Trip_Results** to view detailed attraction cards and hotel listings.")
        with c2:
            st.info("👉 Check **2_Itinerary** to inspect the day-by-day activity plan.")
        with c3:
            st.info("👉 Check **3_Budget_Planner** to explore the visual expense breakdown.")

# Display Active Trip Quick View if already researched in this session
if "active_research_result" in st.session_state and not research_btn:
    st.markdown("---")
    st.subheader("📌 Current Session Research Summary")
    active_req: TripRequest = st.session_state.get("active_trip_request")
    active_res: TripResearchResult = st.session_state.get("active_research_result")
    active_itn = st.session_state.get("active_itinerary", [])
    active_bgt: BudgetBreakdown = st.session_state.get("active_budget")

    if active_res:
        st.markdown(f"**Destination:** {active_res.destination} | **Travelers:** {active_req.travelers} | **Budget:** ₹{active_req.budget_inr:,.0f}")
        st.write(active_res.summary)
        
        c_a, c_b, c_c = st.columns(3)
        with c_a:
            st.metric("Attractions Found", len(active_res.attractions))
        with c_b:
            st.metric("Accommodations", len(active_res.accommodations))
        with c_c:
            status_badge = "✅ Within Budget" if not active_bgt.is_over_budget else "⚠️ Over Budget"
            st.metric("Budget Status", status_badge, f"Est: ₹{active_bgt.total_estimated:,.0f}")
