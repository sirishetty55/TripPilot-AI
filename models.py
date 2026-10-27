"""
Data models and schemas for TripPilot AI.
Includes serialization helpers for SQLite persistence and Streamlit UI consumption.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from urllib.parse import quote_plus

@dataclass
class TripRequest:
    destination: str
    departure_date: str  # YYYY-MM-DD
    return_date: str     # YYYY-MM-DD
    travelers: int = 1
    budget_inr: float = 15000.0
    starting_city: str = ""
    interests: List[str] = field(default_factory=lambda: ["Beaches & Coastal", "History & Heritage", "Food & Culinary"])
    accommodation_pref: str = "budget"  # budget, mid-range, luxury
    travel_style: str = "balanced"      # relaxed, balanced, packed
    use_demo_mode: bool = False

    @property
    def num_days(self) -> int:
        try:
            d1 = datetime.strptime(self.departure_date, "%Y-%m-%d").date()
            d2 = datetime.strptime(self.return_date, "%Y-%m-%d").date()
            if d2 < d1:
                return 1
            diff = (d2 - d1).days + 1
            return max(1, diff)
        except Exception:
            return 3

    @property
    def num_nights(self) -> int:
        try:
            d1 = datetime.strptime(self.departure_date, "%Y-%m-%d").date()
            d2 = datetime.strptime(self.return_date, "%Y-%m-%d").date()
            if d2 <= d1:
                return 0
            return (d2 - d1).days
        except Exception:
            return max(0, self.num_days - 1)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["num_days"] = self.num_days
        d["num_nights"] = self.num_nights
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TripRequest":
        clean = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**clean)


@dataclass
class CommuteOption:
    mode: str  # Flight, Train, Bus, Drive / Road Trip
    title: str
    duration: str = "Flexible"
    estimated_cost_inr: str = "Check fares"
    details: str = ""
    booking_url: str = ""
    source_url: str = ""
    icon: str = "🚆"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CommuteOption":
        clean = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**clean)


@dataclass
class Attraction:
    name: str
    description: str
    category: str = "Sightseeing"
    price_inr: float = 0.0
    price_display: str = "Free"
    opening_hours: str = "Check local schedule"
    location: str = "Central"
    verified: bool = True
    source_url: str = ""
    maps_url: str = ""
    image_url: str = ""
    attribution_text: str = ""
    attribution_url: str = ""

    def __post_init__(self):
        if not self.maps_url and self.name:
            self.maps_url = f"https://www.google.com/maps/search/?api=1&query={quote_plus(self.name + ' ' + self.location)}"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Attraction":
        clean = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**clean)


@dataclass
class Accommodation:
    property_name: str
    property_type: str = "Hotel"
    price_per_night_inr: float = 1500.0
    price_display: str = "₹1,500 / night"
    pricing_period: str = "per night"
    rating: str = "4.2 / 5"
    location: str = "Main area"
    description: str = "Comfortable verified stay"
    verified: bool = True
    source_url: str = ""
    booking_url: str = ""
    maps_url: str = ""
    image_url: str = ""
    attribution_text: str = ""
    attribution_url: str = ""

    def __post_init__(self):
        query = quote_plus(f"{self.property_name} {self.location}")
        if not self.maps_url and self.property_name:
            self.maps_url = f"https://www.google.com/maps/search/?api=1&query={query}"
        if not self.booking_url and self.property_name:
            # Direct deep-link to real booking search on Booking.com / Goibibo
            self.booking_url = f"https://www.booking.com/searchresults.html?ss={query}"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Accommodation":
        clean = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**clean)


@dataclass
class FoodExperience:
    name: str
    cuisine_type: str = "Regional Cuisine"
    price_range_inr: str = "₹400 - ₹800 for two"
    location: str = "Local market"
    description: str = "Traditional local specialty"
    verified: bool = True
    source_url: str = ""
    maps_url: str = ""
    image_url: str = ""
    attribution_text: str = ""
    attribution_url: str = ""

    def __post_init__(self):
        if not self.maps_url and self.name:
            self.maps_url = f"https://www.google.com/maps/search/?api=1&query={quote_plus(self.name + ' restaurant ' + self.location)}"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FoodExperience":
        clean = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**clean)


@dataclass
class DayPlan:
    day_number: int
    date_str: str
    title: str = ""
    morning_activity: str = ""
    afternoon_activity: str = ""
    evening_activity: str = ""
    food_recommendations: str = ""
    estimated_cost_inr: float = 0.0
    travel_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DayPlan":
        clean = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**clean)


@dataclass
class BudgetBreakdown:
    user_budget: float
    accommodation_cost: float
    food_cost: float
    transport_cost: float
    activities_cost: float
    misc_cost: float
    total_estimated: float
    remaining_budget: float
    is_over_budget: bool
    transit_cost: float = 0.0
    per_person_total: float = 0.0
    assumptions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BudgetBreakdown":
        clean = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**clean)


@dataclass
class TripResearchResult:
    destination: str
    summary: str
    attractions: List[Attraction] = field(default_factory=list)
    accommodations: List[Accommodation] = field(default_factory=list)
    food_experiences: List[FoodExperience] = field(default_factory=list)
    commute_options: List[CommuteOption] = field(default_factory=list)
    neighborhoods: List[str] = field(default_factory=list)
    travel_tips: List[str] = field(default_factory=list)
    best_recommendation: Dict[str, Any] = field(default_factory=dict)
    sources_accessed: List[Dict[str, Any]] = field(default_factory=list)
    research_timestamp: str = ""
    is_demo_data: bool = False
    execution_logs: List[str] = field(default_factory=list)
    itinerary_plans: List[DayPlan] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "destination": self.destination,
            "summary": self.summary,
            "attractions": [a.to_dict() for a in self.attractions],
            "accommodations": [h.to_dict() for h in self.accommodations],
            "food_experiences": [f.to_dict() for f in self.food_experiences],
            "commute_options": [c.to_dict() for c in self.commute_options],
            "neighborhoods": self.neighborhoods,
            "travel_tips": self.travel_tips,
            "best_recommendation": self.best_recommendation,
            "sources_accessed": self.sources_accessed,
            "research_timestamp": self.research_timestamp,
            "is_demo_data": self.is_demo_data,
            "execution_logs": self.execution_logs,
            "itinerary_plans": [p.to_dict() for p in self.itinerary_plans]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TripResearchResult":
        return cls(
            destination=data.get("destination", ""),
            summary=data.get("summary", ""),
            attractions=[Attraction.from_dict(a) for a in data.get("attractions", [])],
            accommodations=[Accommodation.from_dict(h) for h in data.get("accommodations", [])],
            food_experiences=[FoodExperience.from_dict(f) for f in data.get("food_experiences", [])],
            commute_options=[CommuteOption.from_dict(c) for c in data.get("commute_options", [])],
            neighborhoods=data.get("neighborhoods", []),
            travel_tips=data.get("travel_tips", []),
            best_recommendation=data.get("best_recommendation", {}),
            sources_accessed=data.get("sources_accessed", []),
            research_timestamp=data.get("research_timestamp", ""),
            is_demo_data=data.get("is_demo_data", False),
            execution_logs=data.get("execution_logs", []),
            itinerary_plans=[DayPlan.from_dict(p) for p in data.get("itinerary_plans", [])]
        )
