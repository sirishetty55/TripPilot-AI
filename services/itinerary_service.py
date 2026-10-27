"""
AI Itinerary Service for TripPilot AI.
Synthesizes day-by-day practical travel itineraries grounded in verified research findings,
traveler interests, dates, and budget using Gemini AI or destination-aware algorithmic scheduling.
Avoids geographically inappropriate generic activities (e.g. no beach shacks in Paris or Manali).
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from models import TripRequest, TripResearchResult, DayPlan
from config import get_gemini_api_key, GEMINI_MODEL
from services.location_service import resolve_location

def _get_destination_theme(destination: str) -> Dict[str, Any]:
    """Identifies destination characteristics to generate geographically accurate fallback themes."""
    loc_info = resolve_location(destination)
    d_lower = destination.lower()
    
    # Mountain / Alpine / Hill Station
    if any(k in d_lower for k in ["manali", "shimla", "munnar", "kullu", "spiti", "ladakh", "leh", "kashmir", "srinagar", "gulmarg", "darjeeling", "gangtok", "ooty", "kodaikanal", "switzerland", "alps", "zermatt", "interlaken", "grindelwald", "chamonix", "innsbruck"]):
        return {
            "type": "mountain",
            "morning_1": f"Arrive in {loc_info.canonical_name}, take in the mountain air, and visit a scenic panoramic viewpoint.",
            "afternoon_1": f"Stroll through the central town square and explore traditional craft shops and local cafes.",
            "evening_1": f"Enjoy sunset over the valley followed by hot regional cuisine and mountain tea.",
            "dining_1": "Local mountain cafe featuring traditional warm stews and regional specialties.",
            "morning_2": f"Morning excursion to natural scenic trails, viewpoints, or historical temples/churches.",
            "afternoon_2": f"Visit local heritage museum or botanical gardens, taking in panoramic vistas.",
            "evening_2": f"Evening walk through the local bazaar for artisanal handicrafts and woolens.",
            "dining_2": "Traditional family-run restaurant serving regional dinner.",
            "notes": "Carry warm layers and comfortable walking shoes for uneven mountain paths."
        }
    
    # Coastal / Beach / Islands
    if loc_info.is_island or any(k in d_lower for k in ["goa", "kerala", "beach", "maldives", "andaman", "phuket", "bali", "santorini", "hawaii", "mauritius", "lakshadweep", "gokarna", "pondicherry"]):
        return {
            "type": "coastal",
            "morning_1": f"Arrive in {loc_info.canonical_name}, settle in, and take a refreshing walk along the coastal promenade.",
            "afternoon_1": f"Visit scenic coastal viewpoints or historical colonial quarters.",
            "evening_1": f"Sunset viewing along the coast followed by relaxed dinner.",
            "dining_1": "Coastal restaurant serving fresh traditional regional curries and refreshing drinks.",
            "morning_2": f"Morning visit to historic fortifications or scenic shoreline reserves.",
            "afternoon_2": f"Relaxed coastal exploration or leisurely boat ride.",
            "evening_2": f"Evening walk through local beachside markets and cafes.",
            "dining_2": "Authentic regional coastal restaurant known for traditional recipes.",
            "notes": "Carry sunscreen, sunglasses, and light breathable clothing."
        }
        
    # International City / Metropolis
    if loc_info.country_code not in ("IN", "UNKNOWN"):
        return {
            "type": "metropolis",
            "morning_1": f"Arrive in {loc_info.canonical_name}, obtain a transit pass, and explore the historic city center.",
            "afternoon_1": f"Visit an iconic cultural landmark, cathedral, or municipal museum in central {loc_info.canonical_name}.",
            "evening_1": f"Stroll through historic cobblestone streets or riverfront promenade.",
            "dining_1": f"Classic {loc_info.country_name} bistro or cafe serving traditional regional specialties.",
            "morning_2": f"Morning visit to world-renowned art galleries, historic plazas, or observation towers.",
            "afternoon_2": f"Explore historic neighborhoods, bookshops, and botanical public gardens.",
            "evening_2": f"Evening stroll through the cultural quarter with illuminated monument vistas.",
            "dining_2": "Celebrated local dining spot offering seasonal regional tasting menus.",
            "notes": "Validate museum time-slots in advance and use urban metro/public transit."
        }
        
    # Heritage / Cultural / Inland India (Jaipur, Varanasi, Agra, Delhi, etc.)
    return {
        "type": "heritage",
        "morning_1": f"Arrive in {loc_info.canonical_name}, settle in, and begin exploring the historic heritage district.",
        "afternoon_1": f"Visit prominent historical monuments, palaces, or architectural landmarks.",
        "evening_1": f"Evening walk through traditional bazaars and vibrant street markets.",
        "dining_1": "Iconic heritage restaurant renowned for traditional regional thalis and sweets.",
        "morning_2": f"Morning exploration of historic forts, museums, or spiritual heritage sites.",
        "afternoon_2": f"Visit artisan workshops, craft emporiums, or royal gardens.",
        "evening_2": f"Witness cultural performances or scenic city lights from an elevated viewpoint.",
        "dining_2": "Traditional dining venue serving local delicacies and time-honored recipes.",
        "notes": "Wear comfortable shoes for walking through historic courtyards and carry drinking water."
    }

def generate_algorithmic_itinerary(trip_req: TripRequest, research: TripResearchResult) -> List[DayPlan]:
    """
    Creates a balanced, realistic, destination-aware day-by-day itinerary
    closely grounded in researched attractions when AI generation is offline.
    """
    plans: List[DayPlan] = []
    num_days = max(1, trip_req.num_days)
    is_sameday = (trip_req.num_nights == 0)
    
    try:
        start_date = datetime.strptime(trip_req.departure_date, "%Y-%m-%d").date()
    except Exception:
        start_date = datetime.now().date()

    attractions = research.attractions[:] if research else []
    foods = research.food_experiences[:] if research else []
    theme = _get_destination_theme(trip_req.destination)

    def get_attr(index: int, default_name: str, default_desc: str) -> Dict[str, Any]:
        if index < len(attractions):
            a = attractions[index]
            return {"name": a.name, "desc": a.description, "cost": a.price_inr}
        return {"name": default_name, "desc": default_desc, "cost": 0.0}

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
            title = f"Arrival & Discovery in {trip_req.destination}"
            if is_sameday:
                morning = f"Arrive early in {trip_req.destination}. Begin sightseeing promptly. {theme['morning_1']}"
            else:
                morning = f"Arrive in {trip_req.destination}, check in at your accommodation, and refresh. {theme['morning_1']}"
            
            a1 = get_attr(0, f"Central {trip_req.destination} Landmarks", theme['afternoon_1'])
            afternoon = f"Visit {a1['name']}. {a1['desc']}"
            
            a2 = get_attr(1, f"Scenic Promenade & Viewpoint", theme['evening_1'])
            evening = f"Explore {a2['name']}. {a2['desc']}"
            food = get_food(0, theme['dining_1'])
            day_cost = (a1['cost'] + a2['cost']) * trip_req.travelers + (550 * trip_req.travelers)
            notes = theme['notes']

        elif day_num == 2:
            title = f"Historic Architecture & Cultural Immersion"
            a3 = get_attr(1, f"Iconic Monument Vista", theme['morning_2'])
            morning = f"Morning visit to {a3['name']}. {a3['desc']}"
            
            a4 = get_attr(2, f"Artisan District & Local Markets", theme['afternoon_2'])
            afternoon = f"Head to {a4['name']}. {a4['desc']}"
            evening = theme['evening_2']
            food = get_food(1, theme['dining_2'])
            day_cost = (a3['cost'] + a4['cost']) * trip_req.travelers + (650 * trip_req.travelers)
            notes = "Start early to avoid peak mid-day crowds at top landmarks."

        elif day_num == 3:
            title = f"Scenic Excursion & Culinary Highlights"
            a5 = get_attr(3, f"Regional Excursion / Heritage Site", "Explore notable historic landmarks or natural sanctuaries.")
            morning = f"Excursion to {a5['name']}. {a5['desc']}"
            afternoon = "Enjoy a leisurely lunch at a local cafe and explore surrounding artisan quarters."
            evening = "Relaxed evening walk, shopping for regional mementos, spices, or souvenirs."
            food = get_food(2, "Authentic regional restaurant featuring traditional tasting dishes.")
            day_cost = (a5['cost']) * trip_req.travelers + (700 * trip_req.travelers)
            notes = "Confirm local opening hours for cultural venues and ticket counters."

        else:
            # Day 4 and beyond
            title = f"Hidden Gems & Local Exploration (Day {day_num})"
            a_idx = (i * 2) % max(1, len(attractions))
            a_next = get_attr(a_idx, f"Offbeat Neighborhood in {trip_req.destination}", "Explore tranquil side streets and historic architecture.")
            morning = f"Explore {a_next['name']} and discover local parks or cultural workshops."
            afternoon = "Relaxed afternoon cafe hop, art gallery tour, or regional market visit."
            evening = "Sunset vista from a scenic overlook followed by dinner at a popular local restaurant."
            food = "Local bistro serving traditional recipes and seasonal dishes."
            day_cost = 650 * trip_req.travelers
            notes = "Enjoy a flexible schedule aligned with your personal travel pace."

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
    grounded in verified attractions and destination context.
    Omits unsupported parameters for Gemini 3 / reasoning models.
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
You are the AI Travel Specialist for TripPilot AI.
Create a realistic, day-by-day travel itinerary for {trip_req.destination}.

Trip Parameters:
- Total Days: {trip_req.num_days} day(s)
- Total Nights: {trip_req.num_nights} night(s)
- Dates: {trip_req.departure_date} to {trip_req.return_date}
- Number of Travelers: {trip_req.travelers}
- Total Budget: ₹{trip_req.budget_inr:,.0f} INR
- Travel Style: {trip_req.travel_style}
- Interests: {', '.join(trip_req.interests)}

Verified Research Findings:
Attractions:
{attraction_summary if attraction_summary else 'Use verified landmarks in ' + trip_req.destination}

Food & Dining:
{food_summary if food_summary else 'Use authentic dishes in ' + trip_req.destination}

Requirements:
1. Destination Authenticity: Strictly suggest activities and places that belong to {trip_req.destination}. Never suggest beach or coastal activities for landlocked or mountain destinations.
2. Group nearby sights logically to minimize unnecessary intra-city transit.
3. If this is a same-day trip (0 nights), do not suggest checking into or sleeping at a hotel.
4. Return an array of {trip_req.num_days} JSON day plans matching the schema below:

[
  {{
    "day_number": 1,
    "date_str": "Day 1",
    "title": "Theme for Day 1",
    "morning_activity": "Detailed morning activity",
    "afternoon_activity": "Detailed afternoon activity",
    "evening_activity": "Detailed evening activity",
    "food_recommendations": "Specific restaurant and dish suggestions",
    "estimated_cost_inr": 850.0,
    "travel_notes": "Practical timing or transit tips"
  }}
]
"""
        # Configure Gemini: Gemini 3-series and reasoning models do not take temperature
        model_lower = GEMINI_MODEL.lower()
        if "gemini-3" in model_lower or "gemini-2.5" in model_lower or "thinking" in model_lower:
            gen_config = types.GenerateContentConfig(response_mime_type="application/json")
        else:
            gen_config = types.GenerateContentConfig(temperature=0.3, response_mime_type="application/json")

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=gen_config
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
        print(f"Gemini Itinerary generation note: {e}")
        return None

def generate_itinerary(
    trip_req: TripRequest,
    research: TripResearchResult,
    session_state=None
) -> List[DayPlan]:
    """Generates itinerary using pre-synthesized AI plan if available, otherwise Gemini or algorithmic."""
    # Fast path: If pre-synthesized during research pass and covers the full trip duration
    if hasattr(research, "itinerary_plans") and research.itinerary_plans and len(research.itinerary_plans) >= trip_req.num_days:
        return research.itinerary_plans

    ai_itinerary = generate_gemini_itinerary(trip_req, research, session_state=session_state)
    if ai_itinerary:
        return ai_itinerary
    return generate_algorithmic_itinerary(trip_req, research)
