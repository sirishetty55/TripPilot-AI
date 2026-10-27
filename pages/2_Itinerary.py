"""
TripPilot AI — Page 2: Day-by-Day AI Itinerary
Displays structured daily schedules, timing, food experiences, and travel notes.
"""

import streamlit as st
from services.ui_utils import apply_custom_theme, render_hero
from models import TripRequest, TripResearchResult, DayPlan

st.set_page_config(page_title="Itinerary — TripPilot AI", page_icon="📅", layout="wide")
apply_custom_theme()

render_hero("📅 Day-by-Day AI Itinerary", "A realistic, balanced travel schedule grounded in verified research findings.")

req: TripRequest = st.session_state.get("active_trip_request")
res: TripResearchResult = st.session_state.get("active_research_result")
itinerary = st.session_state.get("active_itinerary", [])

if not itinerary or not req:
    st.warning("⚠️ No active itinerary found in this session.")
    st.info("Please start research on the **Home** page to generate a customized travel plan.")
    st.stop()

# Itinerary Summary Banner
col_i1, col_i2, col_i3, col_i4 = st.columns(4)
with col_i1:
    st.metric("Destination", req.destination)
with col_i2:
    st.metric("Duration", f"{len(itinerary)} Days")
with col_i3:
    st.metric("Pace", f"{req.travel_style.capitalize()} style")
with col_i4:
    tot_act_cost = sum(p.estimated_cost_inr for p in itinerary)
    st.metric("Est. Activities Cost", f"₹{tot_act_cost:,.0f}")

st.markdown("---")

# Render Each Day
markdown_export = [f"# {req.destination} {req.num_days}-Day Itinerary\n"]
markdown_export.append(f"**Travelers:** {req.travelers} | **Budget:** ₹{req.budget_inr:,.0f} | **Dates:** {req.departure_date} to {req.return_date}\n\n---\n")

for day in itinerary:
    day: DayPlan
    with st.expander(f"📍 Day {day.day_number}: {day.title} ({day.date_str})", expanded=True):
        col_d1, col_d2 = st.columns([3, 1])
        
        with col_d1:
            st.markdown(f"**🌅 Morning (09:00 AM - 12:30 PM)**")
            st.write(day.morning_activity)
            
            st.markdown(f"**☀️ Afternoon (01:00 PM - 05:00 PM)**")
            st.write(day.afternoon_activity)
            
            st.markdown(f"**🌆 Evening & Night (05:30 PM - 09:30 PM)**")
            st.write(day.evening_activity)

        with col_d2:
            st.markdown("**🍽️ Dining Recommendation**")
            st.info(day.food_recommendations)
            
            st.markdown("**💰 Estimated Daily Cost**")
            st.metric("Daily Out-of-Pocket", f"₹{day.estimated_cost_inr:,.0f}", help="Activities + daily meals for your party")
            
            if day.travel_notes:
                st.markdown("**📝 Travel Notes**")
                st.caption(day.travel_notes)

    # Append to markdown export
    markdown_export.append(f"## Day {day.day_number}: {day.title} ({day.date_str})\n")
    markdown_export.append(f"- **Morning:** {day.morning_activity}\n")
    markdown_export.append(f"- **Afternoon:** {day.afternoon_activity}\n")
    markdown_export.append(f"- **Evening:** {day.evening_activity}\n")
    markdown_export.append(f"- **Food:** {day.food_recommendations}\n")
    markdown_export.append(f"- **Estimated Daily Cost:** ₹{day.estimated_cost_inr:,.0f}\n")
    markdown_export.append(f"- **Travel Notes:** {day.travel_notes}\n\n")

st.markdown("---")
st.subheader("📥 Export Your Itinerary")
st.download_button(
    label="📄 Download Itinerary (Markdown Format)",
    data="".join(markdown_export),
    file_name=f"TripPilot_{req.destination.replace(' ', '_')}_Itinerary.md",
    mime="text/markdown",
    use_container_width=True
)
