"""
AI Itinerary Service for TripPilot AI.
Synthesizes day-by-day practical travel itineraries based on research findings,
traveler interests, dates, and budget using Gemini AI or structured algorithmic generation.
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from models import TripRequest, TripResearchResult, DayPlan
from config import get_gemini_api_key, GEMINI_MODEL

def generate_algorithmic_itinerary(trip_req: TripRequest, research: TripResearchResult) -> List[DayPlan]:
    """
    Creates a balanced, realistic day-by-day itinerary grouped logically
    by geographical areas and traveler interests when AI API is offline.
    """
    plans: List[DayPlan] = []
    num_days = trip_req.num_days
    
    try:
        start_date = datetime.strptime(trip_req.departure_date, "%Y-%m-%d").date()
    except Exception:
        start_date = datetime.now().date()

    attractions = research.attractions[:]
    foods = research.food_experiences[:]
    
    # Helper to pick next attraction or fallback
    def get_attr(index: int, default_name: str, default_desc: str) -> Dict[str, Any]:
        if index < len(attractions):
            a = attractions[index]
            return {"name": a.name, "desc": a.description, "cost": a.price_inr}
        return {"name": default_name, "desc": default_desc, "cost": 0.0}

    # Helper to pick next food or fallback
    def get_food(index: int, default_text: str) -> str:
        if index < len(foods):
            f = foods[index]
            return f"{f.name} ({f.cuisine_type}) - {f.description} [Est: {f.price_range_inr}]"
        return default_text

    for i in range(num_days):
        current_date = start_date + timedelta(days=i)
        day_num = i + 1
        date_str = current_date.strftime("%a, %b %d, %Y")

        if day_num == 1:
            title = f"Arrival, Colonial Heritage & Coastal Sunset"
            morning = f"Arrive in {trip_req.destination}, check in at your accommodation, and settle in. Grab a refreshing welcome coconut or coffee."
            a1 = get_attr(0, f"Central Heritage District", f"Explore scenic colonial streets and historic quarters.")
            afternoon = f"Visit {a1['name']}. {a1['desc']}"
            a2 = get_attr(1, f"Scenic Sunset Promenade", f"Stroll along the coast and witness the sunset over the sea.")
            evening = f"Explore {a2['name']}. {a2['desc']} followed by beachside stroll."
            food = get_food(0, "Local coastal café for traditional lunch and fresh fruit juices.")
            day_cost = (a1['cost'] + a2['cost']) * trip_req.travelers + (500 * trip_req.travelers)
            notes = "Keep local taxi fare or scooter rental deposit ready. Wear walking shoes."

        elif day_num == 2:
            title = f"Fortresses, Coastal Views & Vibrant Local Markets"
            a3 = get_attr(1, f"Historic Fort Vista", f"Morning exploration of cliffside fortifications.")
            morning = f"Morning trip to {a3['name']}. {a3['desc']}"
            a4 = get_attr(2, f"Coastline Leisure & Beach Shacks", f"Relax on the sands, try water activities or chilled refreshments.")
            afternoon = f"Head to {a4['name']}. {a4['desc']}"
            evening = "Explore the vibrant evening souvenir market or enjoy live music at a local beach shack."
            food = get_food(1, "Famous family restaurant serving authentic regional curries and seafood.")
            day_cost = (a3['cost'] + a4['cost']) * trip_req.travelers + (650 * trip_req.travelers)
            notes = "Apply sunscreen and carry bottled water. Moderate walking on fort ramparts."

        elif day_num == 3:
            title = f"Nature Excursion, Local Dining & Relaxation"
            a5 = get_attr(3, f"Scenic Sanctuary / Falls", f"Visit natural springs or lush tropical reserves.")
            morning = f"Excursion to {a5['name']}. {a5['desc']}"
            afternoon = "Enjoy a leisurely lunch at a historic riverside restaurant and sample traditional desserts."
            evening = "Relaxed evening walk, shopping for local spices, artisanal souvenirs, and packing."
            food = get_food(2, "Riverside dining featuring coastal thalis and regional dessert.")
            day_cost = (a5['cost']) * trip_req.travelers + (700 * trip_req.travelers)
            notes = "Book jeep safari or transfers early in the morning to beat the afternoon heat."

        else:
            # Days 4 and beyond
            title = f"Hidden Gems, Watersports & Leisure"
            a_idx = (i * 2) % max(1, len(attractions))
            a_next = get_attr(a_idx, f"Offbeat Coastal Village", f"Explore peaceful palm-fringed backstreets.")
            morning = f"Explore {a_next['name']} and participate in optional water sports or cycling."
            afternoon = "Relaxed afternoon café hop and art gallery or spice plantation tour."
            evening = "Sunset cruise along the river followed by dinner at a beachfront bistro."
            food = "Local bistro serving fusion coastal delicacies and wood-fired delicacies."
            day_cost = 600 * trip_req.travelers
            notes = "Enjoy a leisurely pace without rushing between distant transit hubs."

        plans.append(DayPlan(
            day_number=day_num,
            date_str=date_str,
            title=title,
            morning_activity=morning,
            afternoon_activity=afternoon,
            evening_activity=evening,
            food_recommendations=food,
            estimated_cost_inr=float(day_cost),
            travel_notes=notes
        ))

    return plans

def generate_gemini_itinerary(
    trip_req: TripRequest,
    research: TripResearchResult,
    session_state=None
) -> Optional[List[DayPlan]]:
    """
    Uses Gemini API to synthesize an intelligent day-by-day itinerary
    closely aligning verified attractions with the user's travel style and dates.
    """
    api_key = get_gemini_api_key(session_state)
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        attraction_summary = "\n".join(
            f"- {a.name} (Category: {a.category}, Cost: {a.price_display}, Location: {a.location})"
            for a in research.attractions[:8]
        )
        food_summary = "\n".join(
            f"- {f.name} ({f.cuisine_type}, Cost: {f.price_range_inr}, Loc: {f.location})"
            for f in research.food_experiences[:5]
        )

        prompt = f"""
You are the AI Travel Planner for TripPilot AI.
Create a realistic, day-by-day travel itinerary for {trip_req.destination}.

Trip Parameters:
- Total Days: {trip_req.num_days} days
- Dates: {trip_req.departure_date} to {trip_req.return_date}
- Number of Travelers: {trip_req.travelers}
- Total Budget: ₹{trip_req.budget_inr:,.0f} INR
- Travel Style: {trip_req.travel_style}
- Interests: {', '.join(trip_req.interests)}

Verified Research Findings from Browser Automation:
Attractions:
{attraction_summary}

Food & Dining:
{food_summary}

Requirements:
1. Avoid unrealistic schedules and excessive travel between attractions.
2. Group nearby sights logically (e.g. North Goa on one day, South Goa on another).
3. Do not invent confirmed bookings. Use verified prices from research where available.
4. Return an array of {trip_req.num_days} JSON day plans matching the schema below:

[
  {{
    "day_number": 1,
    "date_str": "Day 1 - YYYY-MM-DD",
    "title": "Theme for Day 1",
    "morning_activity": "Detailed morning plan",
    "afternoon_activity": "Detailed afternoon plan",
    "evening_activity": "Detailed evening plan",
    "food_recommendations": "Specific restaurant and dish suggestions",
    "estimated_cost_inr": 850.0,
    "travel_notes": "Practical transportation and timing advice"
  }}
]
"""
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                response_mime_type="application/json"
            )
        )
        
        if response and response.text:
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            data = json.loads(text.strip())
            if isinstance(data, list) and len(data) > 0:
                return [DayPlan.from_dict(d) for d in data]
    except Exception as e:
        print(f"Gemini Itinerary fallback due to: {e}")
        return None

def generate_itinerary(
    trip_req: TripRequest,
    research: TripResearchResult,
    session_state=None
) -> List[DayPlan]:
    """Generates itinerary using pre-synthesized AI plan if available, otherwise Gemini or algorithmic."""
    # Fast path: If already synthesized during unified research pass, return immediately (0.0s)
    if hasattr(research, "itinerary_plans") and research.itinerary_plans and len(research.itinerary_plans) >= trip_req.num_days:
        return research.itinerary_plans

    ai_itinerary = generate_gemini_itinerary(trip_req, research, session_state=session_state)
    if ai_itinerary:
        return ai_itinerary
    return generate_algorithmic_itinerary(trip_req, research)
