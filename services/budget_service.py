"""
Budget Planner Service for TripPilot AI.
Calculates transparent expense breakdowns across accommodation, dining,
transit, and activities, and compares against the traveler's total budget.
"""

import math
from typing import Dict, Any, List, Optional
import pandas as pd
from models import TripRequest, TripResearchResult, BudgetBreakdown

def calculate_budget(
    trip_req: TripRequest,
    research: Optional[TripResearchResult] = None,
    overrides: Optional[Dict[str, float]] = None
) -> BudgetBreakdown:
    """
    Computes a grounded budget breakdown with clear assumptions.
    Allows manual override of specific category totals.
    """
    overrides = overrides or {}
    
    num_days = max(1, trip_req.num_days)
    num_nights = max(1, trip_req.num_nights)
    travelers = max(1, trip_req.travelers)
    rooms_needed = math.ceil(travelers / 2)
    
    # 1. Accommodation Calculation
    # Check if verified stays were extracted from research
    nightly_rate = 1500.0
    if research and research.accommodations:
        matching = [
            h for h in research.accommodations 
            if trip_req.accommodation_pref.lower() in (h.property_type.lower() + h.description.lower())
        ]
        if matching:
            nightly_rate = matching[0].price_per_night_inr
        else:
            nightly_rate = research.accommodations[0].price_per_night_inr
    else:
        # Default baseline per room per night
        if trip_req.accommodation_pref == "budget":
            nightly_rate = 1400.0
        elif trip_req.accommodation_pref == "mid-range":
            nightly_rate = 3200.0
        else: # luxury
            nightly_rate = 7500.0

    raw_accommodation = nightly_rate * num_nights * rooms_needed
    accommodation_cost = overrides.get("accommodation", raw_accommodation)

    # 2. Food & Dining Calculation
    daily_food_per_person = 650.0
    if trip_req.travel_style == "relaxed":
        daily_food_per_person = 550.0
    elif trip_req.travel_style == "balanced":
        daily_food_per_person = 800.0
    elif trip_req.travel_style == "packed":
        daily_food_per_person = 1100.0

    raw_food = daily_food_per_person * num_days * travelers
    food_cost = overrides.get("food", raw_food)

    # 3. Local Transportation Calculation
    daily_transport = 600.0
    if trip_req.travel_style == "relaxed":
        daily_transport = 400.0  # e.g. Rented scooter or short taxi
    elif trip_req.travel_style == "balanced":
        daily_transport = 750.0  # Mix of scooter / shared cab
    elif trip_req.travel_style == "packed":
        daily_transport = 1200.0 # Full day cab hire for extensive sightseeing

    raw_transport = daily_transport * num_days
    transport_cost = overrides.get("transport", raw_transport)

    # 4. Activities and Tickets Calculation
    raw_activities = 0.0
    if research and research.attractions:
        # Sum entry fees of top attractions for each traveler
        sample_fees = sum(a.price_inr for a in research.attractions[:4])
        raw_activities = sample_fees * travelers
    if raw_activities <= 0:
        raw_activities = 350.0 * num_days * travelers

    activities_cost = overrides.get("activities", raw_activities)

    # 5. Miscellaneous Buffer (emergency, local shopping, tips, laundry)
    subtotal = accommodation_cost + food_cost + transport_cost + activities_cost
    raw_misc = round(subtotal * 0.08, -1)
    misc_cost = overrides.get("misc", raw_misc)

    total_estimated = accommodation_cost + food_cost + transport_cost + activities_cost + misc_cost
    remaining_budget = trip_req.budget_inr - total_estimated
    is_over_budget = remaining_budget < 0

    assumptions = [
        f"Accommodation: {num_nights} nights at ₹{nightly_rate:,.0f}/room/night for {rooms_needed} room(s).",
        f"Dining: ₹{daily_food_per_person:,.0f}/person/day for {travelers} traveler(s) over {num_days} days.",
        f"Transit: ₹{daily_transport:,.0f}/day average local transit ({trip_req.travel_style} travel style).",
        f"Activities: Calculated from researched attraction entry fees and standard excursions.",
        f"Contingency: ~8% reserve buffer for unexpected transit or emergency needs."
    ]

    return BudgetBreakdown(
        user_budget=float(trip_req.budget_inr),
        accommodation_cost=float(accommodation_cost),
        food_cost=float(food_cost),
        transport_cost=float(transport_cost),
        activities_cost=float(activities_cost),
        misc_cost=float(misc_cost),
        total_estimated=float(total_estimated),
        remaining_budget=float(remaining_budget),
        is_over_budget=is_over_budget,
        assumptions=assumptions
    )

def get_budget_dataframe(budget: BudgetBreakdown) -> pd.DataFrame:
    """Creates a Pandas DataFrame for Streamlit bar and pie charts."""
    data = [
        {"Category": "🏨 Accommodation", "Amount (₹)": budget.accommodation_cost, "Share": (budget.accommodation_cost / max(1, budget.total_estimated)) * 100},
        {"Category": "🍽️ Food & Dining", "Amount (₹)": budget.food_cost, "Share": (budget.food_cost / max(1, budget.total_estimated)) * 100},
        {"Category": "🚕 Local Transport", "Amount (₹)": budget.transport_cost, "Share": (budget.transport_cost / max(1, budget.total_estimated)) * 100},
        {"Category": "🎟️ Activities & Tickets", "Amount (₹)": budget.activities_cost, "Share": (budget.activities_cost / max(1, budget.total_estimated)) * 100},
        {"Category": "🛡️ Misc Buffer", "Amount (₹)": budget.misc_cost, "Share": (budget.misc_cost / max(1, budget.total_estimated)) * 100},
    ]
    df = pd.DataFrame(data)
    df["Share (%)"] = df["Share"].round(1)
    return df
