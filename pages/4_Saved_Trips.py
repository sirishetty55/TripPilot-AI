"""
TripPilot AI — Page 4: Saved Trips & History
Persistent SQLite trip storage allowing users to reload, review, and delete previous research.
"""

import streamlit as st
import json
from services.ui_utils import apply_custom_theme, render_hero
from models import TripRequest, TripResearchResult, DayPlan, BudgetBreakdown
import database

st.set_page_config(page_title="Saved Trips — TripPilot AI", page_icon="📁", layout="wide")
apply_custom_theme()

render_hero("📁 Saved Trips & Research History", "Review and reload your past trips stored securely in SQLite.")

# Fetch all trips from SQLite
trips = database.get_all_trips()

if not trips:
    st.info("No saved trips found in the SQLite database yet.")
    st.write("Go to the **Home** page and click **'Research My Trip'** to create your first saved research session.")
    st.stop()

st.write(f"Found **{len(trips)}** saved trip(s) in your local database:")

for item in trips:
    trip_id = item["id"]
    dest = item["destination"]
    dep = item["departure_date"]
    ret = item["return_date"]
    travelers = item["travelers"]
    budget = item["budget_inr"]
    created_at = item["created_at"]

    with st.container():
        st.markdown(f"""
        <div class="travel-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h3 style="margin: 0; color: #0f766e;">#{trip_id} &bull; {dest}</h3>
                <span class="badge-price">₹{budget:,.0f} Budget</span>
            </div>
            <div style="font-size: 14px; color: inherit; opacity: 0.88; margin: 8px 0;">
                📅 <strong>Travel Dates:</strong> {dep} to {ret} &nbsp;|&nbsp; 
                👥 <strong>Travelers:</strong> {travelers} &nbsp;|&nbsp;
                🕒 <strong>Researched On:</strong> {created_at}
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_b1, col_b2, col_b3 = st.columns([2, 2, 4])
        with col_b1:
            if st.button(f"📂 Reopen Trip #{trip_id}", key=f"open_{trip_id}", use_container_width=True):
                full_trip = database.get_trip_by_id(trip_id)
                if full_trip:
                    st.session_state["active_trip_id"] = trip_id
                    st.session_state["active_trip_request"] = TripRequest.from_dict(full_trip["trip_request"])
                    st.session_state["active_research_result"] = TripResearchResult.from_dict(full_trip["research_result"])
                    st.session_state["active_itinerary"] = [DayPlan.from_dict(p) for p in full_trip["itinerary"]]
                    st.session_state["active_budget"] = BudgetBreakdown.from_dict(full_trip["budget"])
                    st.success(f"Trip #{trip_id} ({dest}) loaded as active session!")
                    st.info("👉 Check **1_Trip_Results**, **2_Itinerary**, or **3_Budget_Planner** to inspect this trip.")

        with col_b2:
            if st.button(f"🗑️ Delete Trip #{trip_id}", key=f"del_{trip_id}", type="secondary", use_container_width=True):
                database.delete_trip(trip_id)
                st.warning(f"Trip #{trip_id} deleted.")
                st.rerun()

        with col_b3:
            full_trip = database.get_trip_by_id(trip_id)
            if full_trip:
                st.download_button(
                    label=f"💾 Export JSON (#{trip_id})",
                    data=json.dumps(full_trip, indent=2),
                    file_name=f"Trip_{trip_id}_{dest}.json",
                    mime="application/json",
                    key=f"dl_{trip_id}"
                )

        st.markdown("<br>", unsafe_allow_html=True)
