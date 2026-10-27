"""
TripPilot AI — Page 3: Budget Planner
Visual expense breakdown, category charts, comparison metrics, and manual cost adjustments.
"""

import streamlit as st
import pandas as pd
from services.ui_utils import apply_custom_theme, render_hero
from services.budget_service import calculate_budget, get_budget_dataframe
from models import TripRequest, TripResearchResult, BudgetBreakdown

st.set_page_config(page_title="Budget Planner — TripPilot AI", page_icon="💰", layout="wide")
apply_custom_theme()

render_hero("💰 Budget Planner & Financial Breakdown", "Transparent, grounded estimates comparing your budget against projected expenses.")

req: TripRequest = st.session_state.get("active_trip_request")
res: TripResearchResult = st.session_state.get("active_research_result")
budget: BudgetBreakdown = st.session_state.get("active_budget")

if not req or not budget:
    st.warning("⚠️ No active budget data found in this session.")
    st.info("Please start research on the **Home** page to calculate your trip budget.")
    st.stop()

# Manual overrides stored in session
if "budget_overrides" not in st.session_state:
    st.session_state["budget_overrides"] = {}

# Recompute if overrides exist
current_overrides = st.session_state["budget_overrides"]
active_budget = calculate_budget(req, res, overrides=current_overrides)
st.session_state["active_budget"] = active_budget

# High-Level KPI Metric Cards
col_b1, col_b2, col_b3, col_b4 = st.columns(4)

with col_b1:
    st.metric("Your Total Budget", f"₹{active_budget.user_budget:,.0f}")

with col_b2:
    st.metric("Estimated Trip Total", f"₹{active_budget.total_estimated:,.0f}")

with col_b3:
    diff = active_budget.remaining_budget
    if diff >= 0:
        st.metric("Remaining Buffer", f"₹{diff:,.0f}", delta=f"Under by ₹{diff:,.0f}", delta_color="normal")
    else:
        st.metric("Over Budget Deficit", f"₹{abs(diff):,.0f}", delta=f"Over by ₹{abs(diff):,.0f}", delta_color="inverse")

with col_b4:
    pct_used = min(100.0, (active_budget.total_estimated / max(1, active_budget.user_budget)) * 100)
    st.metric("Budget Utilization", f"{pct_used:.1f}%")

st.progress(min(1.0, active_budget.total_estimated / max(1, active_budget.user_budget)))

st.markdown("---")

col_left, col_right = st.columns([3, 2])

with col_left:
    st.subheader("📊 Expense Distribution by Category")
    df = get_budget_dataframe(active_budget)
    
    # Display Chart
    chart_data = df.set_index("Category")[["Amount (₹)"]]
    st.bar_chart(chart_data, color="#0d9488")
    
    # Display Table
    st.markdown("#### Itemized Breakdown Table")
    st.dataframe(
        df[["Category", "Amount (₹)", "Share (%)"]].style.format({
            "Amount (₹)": "₹{:,.0f}",
            "Share (%)": "{:.1f}%"
        }),
        use_container_width=True,
        hide_index=True
    )

with col_right:
    st.subheader("✏️ Customize / Override Cost Estimates")
    st.caption("Adjust any category estimate to reflect your personal spending plans:")

    with st.form("budget_override_form"):
        new_accom = st.number_input(
            "🏨 Accommodation (₹)",
            value=float(active_budget.accommodation_cost),
            step=500.0,
            help="Total room cost for all nights"
        )
        new_food = st.number_input(
            "🍽️ Food & Dining (₹)",
            value=float(active_budget.food_cost),
            step=500.0,
            help="All meals for all travelers"
        )
        new_trans = st.number_input(
            "🚕 Local Transport (₹)",
            value=float(active_budget.transport_cost),
            step=250.0,
            help="Scooters, taxis, metro, fuel"
        )
        new_act = st.number_input(
            "🎟️ Activities & Entry Fees (₹)",
            value=float(active_budget.activities_cost),
            step=250.0,
            help="Forts, boat cruises, tickets"
        )
        new_misc = st.number_input(
            "🛡️ Misc Buffer / Souvenirs (₹)",
            value=float(active_budget.misc_cost),
            step=200.0
        )

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            save_overrides = st.form_submit_button("Update Calculations", type="primary", use_container_width=True)
        with col_btn2:
            reset_overrides = st.form_submit_button("Reset to Defaults", use_container_width=True)

    if save_overrides:
        st.session_state["budget_overrides"] = {
            "accommodation": new_accom,
            "food": new_food,
            "transport": new_trans,
            "activities": new_act,
            "misc": new_misc
        }
        st.success("Custom budget estimates applied!")
        st.rerun()

    if reset_overrides:
        st.session_state["budget_overrides"] = {}
        st.info("Reset to default research estimates.")
        st.rerun()

st.markdown("---")
st.subheader("📝 Budget Assumptions & Verified Grounding")
for assumption in active_budget.assumptions:
    st.markdown(f"- {assumption}")

st.caption("Disclaimer: All estimates are advisory projections derived from public listings. Final prices may vary with seasonal surge, peak festival dates, and on-site negotiation.")
