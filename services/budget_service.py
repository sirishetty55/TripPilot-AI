"""
Budget Planner Service for TripPilot AI.
Calculates transparent expense breakdowns across accommodation, dining,
intercity transit, local transit, and activities, comparing against total budget.
Handles same-day trips (zero hotel cost), hotel tier matching, per-person metrics,
and transparent assumptions.
"""

import math
import re
from typing import Dict, Any, List, Optional
import pandas as pd
from models import TripRequest, TripResearchResult, BudgetBreakdown

def _extract_estimated_fare_per_person(fare_str: str) -> float:
    """Extracts a numeric fare estimate in INR from a commute fare description."""
    if not fare_str:
        return 0.0
    # Search for numbers after rupee symbol or currency
    matches = re.findall(r'[₹Rs\. ]*([0-9]+(?:,[0-9]+)*)', fare_str)
    if matches:
        nums = []
        for m in matches:
            clean_num = m.replace(",", "").strip()
            if clean_num.isdigit():
                val = float(clean_num)
                # Ignore small numbers that might be durations (e.g. 3-day)
                if val >= 200:
                    nums.append(val)
        if nums:
            # Average min and max if a range was provided
            return sum(nums) / len(nums)
    return 0.0


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
    num_nights = max(0, trip_req.num_nights)  # Same-day trip has 0 nights
    travelers = max(1, trip_req.travelers)
    rooms_needed = math.ceil(travelers / 2) if num_nights > 0 else 0
    
    # 1. Accommodation Calculation
    nightly_rate = 0.0
    is_stay_verified = False
    
    if num_nights == 0:
        # Same-day trip: No hotel stay required
        raw_accommodation = 0.0
        nightly_rate = 0.0
    else:
        # Default tier baselines
        tier_pref = trip_req.accommodation_pref.lower()
        if tier_pref == "budget":
            default_rate = 1400.0
        elif tier_pref == "mid-range":
            default_rate = 3200.0
        else:  # luxury
            default_rate = 7500.0

        nightly_rate = default_rate

        # If research accommodations are available, pick one matching the requested tier
        if research and research.accommodations:
            tier_matches = []
            for h in research.accommodations:
                price = getattr(h, "price_per_night_inr", 0.0)
                ptype = getattr(h, "property_type", "").lower()
                desc = getattr(h, "description", "").lower()
                combined = f"{ptype} {desc}"

                if tier_pref == "budget" and (price <= 2200 or "hostel" in combined or "budget" in combined or "guesthouse" in combined):
                    tier_matches.append(h)
                elif tier_pref == "mid-range" and (2000 <= price <= 6000 or "hotel" in combined or "resort" in combined):
                    tier_matches.append(h)
                elif tier_pref == "luxury" and (price >= 5500 or "luxury" in combined or "5-star" in combined or "palace" in combined):
                    tier_matches.append(h)

            if tier_matches:
                selected_stay = tier_matches[0]
                nightly_rate = selected_stay.price_per_night_inr
                is_stay_verified = getattr(selected_stay, "verified", False)
            elif research.accommodations:
                # If tier wasn't directly matched, scale appropriately rather than picking mismatched rate
                first_stay = research.accommodations[0]
                if tier_pref == "budget":
                    nightly_rate = min(first_stay.price_per_night_inr, 2000.0)
                elif tier_pref == "luxury":
                    nightly_rate = max(first_stay.price_per_night_inr, 6500.0)
                else:
                    nightly_rate = first_stay.price_per_night_inr
                is_stay_verified = getattr(first_stay, "verified", False)

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

    # 3. Intercity Transit Calculation (Flights / Long-distance trains from starting city)
    raw_transit = 0.0
    transit_mode = "Local"
    if trip_req.starting_city.strip() and research and getattr(research, "commute_options", None):
        options = research.commute_options
        if options:
            top_opt = options[0]
            transit_mode = getattr(top_opt, "mode", "Transit")
            fare_est = _extract_estimated_fare_per_person(getattr(top_opt, "estimated_cost_inr", ""))
            if fare_est > 0:
                raw_transit = fare_est * travelers

    transit_cost = overrides.get("transit", raw_transit)

    # 4. Local Transportation Calculation (Within destination city)
    daily_local_transport = 600.0
    if trip_req.travel_style == "relaxed":
        daily_local_transport = 400.0
    elif trip_req.travel_style == "balanced":
        daily_local_transport = 750.0
    elif trip_req.travel_style == "packed":
        daily_local_transport = 1200.0

    raw_transport = daily_local_transport * num_days
    transport_cost = overrides.get("transport", raw_transport)

    # 5. Activities and Tickets Calculation
    raw_activities = 0.0
    priced_activities_count = 0
    if research and research.attractions:
        for a in research.attractions:
            if a.price_inr > 0:
                raw_activities += a.price_inr
                priced_activities_count += 1
        raw_activities = raw_activities * travelers
        
    if raw_activities <= 0 or priced_activities_count == 0:
        # Standard nominal buffer for entry tickets
        raw_activities = 350.0 * num_days * travelers

    activities_cost = overrides.get("activities", raw_activities)

    # 6. Miscellaneous Contingency Buffer (~8%)
    subtotal = accommodation_cost + food_cost + transport_cost + activities_cost + transit_cost
    raw_misc = round(subtotal * 0.08, -1)
    misc_cost = overrides.get("misc", raw_misc)

    total_estimated = accommodation_cost + food_cost + transport_cost + activities_cost + transit_cost + misc_cost
    remaining_budget = trip_req.budget_inr - total_estimated
    is_over_budget = remaining_budget < 0
    per_person_total = total_estimated / max(1, travelers)

    # Grounded Assumptions Documentation
    assumptions = []
    if num_nights == 0:
        assumptions.append("Same-day trip: No overnight accommodation cost required.")
    else:
        status_tag = "verified listing rate" if is_stay_verified else f"{trip_req.accommodation_pref} tier estimate"
        assumptions.append(f"Accommodation: {num_nights} night(s) at ₹{nightly_rate:,.0f}/room/night for {rooms_needed} room(s) ({status_tag}).")

    assumptions.append(f"Dining: ₹{daily_food_per_person:,.0f}/person/day for {travelers} traveler(s) across {num_days} day(s).")
    
    if transit_cost > 0:
        assumptions.append(f"Intercity Transit: ₹{transit_cost:,.0f} estimated travel connecting {trip_req.starting_city} and {trip_req.destination} ({transit_mode}).")

    assumptions.append(f"Local Transit: ₹{daily_local_transport:,.0f}/day destination city travel ({trip_req.travel_style} pace).")
    assumptions.append(f"Activities: Entry fees and excursions estimated at ₹{activities_cost / travelers:,.0f}/person.")
    assumptions.append("Contingency: ~8% reserve buffer for emergency or unexpected expenses.")

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
        transit_cost=float(transit_cost),
        per_person_total=float(per_person_total),
        assumptions=assumptions
    )

def get_budget_dataframe(budget: BudgetBreakdown, travelers: int = 1) -> pd.DataFrame:
    """Creates an itemized Pandas DataFrame for UI charts and tables."""
    travelers = max(1, travelers)
    data = []
    
    if budget.transit_cost > 0:
        data.append({
            "Category": "✈️ Intercity Transit",
            "Group Total (₹)": budget.transit_cost,
            "Per Person (₹)": budget.transit_cost / travelers,
            "Share": (budget.transit_cost / max(1, budget.total_estimated)) * 100
        })

    data.extend([
        {
            "Category": "🏨 Accommodation",
            "Group Total (₹)": budget.accommodation_cost,
            "Per Person (₹)": budget.accommodation_cost / travelers,
            "Share": (budget.accommodation_cost / max(1, budget.total_estimated)) * 100
        },
        {
            "Category": "🍽️ Food & Dining",
            "Group Total (₹)": budget.food_cost,
            "Per Person (₹)": budget.food_cost / travelers,
            "Share": (budget.food_cost / max(1, budget.total_estimated)) * 100
        },
        {
            "Category": "🚕 Local Transport",
            "Group Total (₹)": budget.transport_cost,
            "Per Person (₹)": budget.transport_cost / travelers,
            "Share": (budget.transport_cost / max(1, budget.total_estimated)) * 100
        },
        {
            "Category": "🎟️ Activities & Tickets",
            "Group Total (₹)": budget.activities_cost,
            "Per Person (₹)": budget.activities_cost / travelers,
            "Share": (budget.activities_cost / max(1, budget.total_estimated)) * 100
        },
        {
            "Category": "🛡️ Contingency Buffer",
            "Group Total (₹)": budget.misc_cost,
            "Per Person (₹)": budget.misc_cost / travelers,
            "Share": (budget.misc_cost / max(1, budget.total_estimated)) * 100
        },
    ])
    
    df = pd.DataFrame(data)
    df["Share (%)"] = df["Share"].round(1)
    df["Amount (₹)"] = df["Group Total (₹)"]
    return df
