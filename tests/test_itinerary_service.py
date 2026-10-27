"""
tests/test_itinerary_service.py

Regression tests for destination-aware itinerary fallback logic.

Verifies that when AI generation fails the fallback activities are
geo-appropriate rather than geographically nonsensical (e.g. beach
activities for a Paris or Manali trip).
"""

import unittest
from unittest.mock import patch
from datetime import date

from services import itinerary_service
from models import TripRequest, TripResearchResult, Attraction


def _make_request(destination: str, dep: str = "2025-12-01", ret: str = "2025-12-04") -> TripRequest:
    return TripRequest(
        destination=destination,
        starting_city="Mumbai",
        departure_date=dep,
        return_date=ret,
        travelers=2,
        budget_inr=60_000,
        interests=["sightseeing", "food"],
        travel_style="moderate",
    )


def _empty_research(destination: str) -> TripResearchResult:
    return TripResearchResult(
        destination=destination,
        summary="Research summary for " + destination,
        attractions=[],
        accommodations=[],
        food_experiences=[],
        commute_options=[],
    )


def _rich_research(destination: str, attraction_names: list) -> TripResearchResult:
    return TripResearchResult(
        destination=destination,
        summary="Rich research for " + destination,
        attractions=[
            Attraction(
                name=n,
                description=f"Famous spot in {destination}",
                price_inr=500.0,
                price_display="₹500",
                category="sightseeing",
            )
            for n in attraction_names
        ],
        accommodations=[],
        food_experiences=[],
        commute_options=[],
    )


def _get_algorithmic_text(destination: str, dep: str = "2025-12-01", ret: str = "2025-12-04") -> str:
    """Return all activity text from the algorithmic (non-AI) fallback itinerary."""
    req = _make_request(destination, dep, ret)
    research = _empty_research(destination)
    plans = itinerary_service.generate_algorithmic_itinerary(req, research)
    parts = []
    for day in plans:
        parts += [
            day.morning_activity or "",
            day.afternoon_activity or "",
            day.evening_activity or "",
            day.title or "",
        ]
    return " ".join(parts).lower()


class TestItineraryFallback(unittest.TestCase):
    """Ensure algorithmic fallback itineraries are geographically appropriate."""

    # ------------------------------------------------------------------
    # Paris — no beach/coastal activities
    # ------------------------------------------------------------------

    def test_paris_fallback_contains_no_beach_activities(self):
        """Paris fallback must NOT suggest beach, coastal, or surf activities."""
        text = _get_algorithmic_text("Paris")
        # The Paris theme goes through the 'metropolis' branch — no coastal keywords expected.
        beach_terms = ["surf ", "surfing", "snorkel", "coral reef"]
        offenders = [t for t in beach_terms if t in text]
        self.assertEqual(offenders, [], f"Paris itinerary contains coastal activity keywords: {offenders}\n\nFull text:\n{text}")

    def test_paris_fallback_not_beach_theme(self):
        """The algorithmic theme for Paris must be 'metropolis', not 'coastal'."""
        from services.itinerary_service import _get_destination_theme
        theme = _get_destination_theme("Paris")
        self.assertNotEqual(theme["type"], "coastal",
                            f"Paris should NOT get a coastal theme, got: {theme['type']}")
        self.assertEqual(theme["type"], "metropolis",
                         f"Paris should get a metropolis theme, got: {theme['type']}")

    # ------------------------------------------------------------------
    # Manali — mountain theme
    # ------------------------------------------------------------------

    def test_manali_fallback_contains_no_beach_activities(self):
        """Manali fallback must NOT suggest beach or coastal activities."""
        text = _get_algorithmic_text("Manali")
        beach_terms = ["surf ", "snorkel", "coral reef"]
        offenders = [t for t in beach_terms if t in text]
        self.assertEqual(offenders, [], f"Manali itinerary contains coastal activity keywords: {offenders}\n\nFull text:\n{text}")

    def test_manali_gets_mountain_theme(self):
        """The algorithmic theme for Manali must be 'mountain'."""
        from services.itinerary_service import _get_destination_theme
        theme = _get_destination_theme("Manali")
        self.assertEqual(theme["type"], "mountain",
                         f"Manali should get a mountain theme, got: {theme['type']}")

    # ------------------------------------------------------------------
    # Goa — coastal theme (sanity check that coastal is still used where appropriate)
    # ------------------------------------------------------------------

    def test_goa_gets_coastal_theme(self):
        """Goa should correctly get a coastal theme (not metropolitan or mountain)."""
        from services.itinerary_service import _get_destination_theme
        theme = _get_destination_theme("Goa")
        self.assertEqual(theme["type"], "coastal",
                         f"Goa should get a coastal theme, got: {theme['type']}")

    # ------------------------------------------------------------------
    # Same-day trip — single day plan only
    # ------------------------------------------------------------------

    def test_sameday_trip_produces_one_day_plan(self):
        """Same-day trip (dep == ret) should produce exactly 1 day plan."""
        req = _make_request("Delhi", dep="2025-12-05", ret="2025-12-05")
        research = _empty_research("Delhi")
        plans = itinerary_service.generate_algorithmic_itinerary(req, research)
        self.assertEqual(len(plans), 1, f"Same-day trip must produce 1 day plan, got {len(plans)}")

    # ------------------------------------------------------------------
    # Fallback structure — valid DayPlan objects
    # ------------------------------------------------------------------

    def test_empty_research_produces_valid_fallback_structure(self):
        """Even with no research data, fallback must return valid DayPlan objects."""
        req = _make_request("Agra", dep="2025-12-05", ret="2025-12-07")
        research = _empty_research("Agra")
        plans = itinerary_service.generate_algorithmic_itinerary(req, research)
        self.assertGreaterEqual(len(plans), 1)
        for day in plans:
            self.assertTrue(hasattr(day, "morning_activity"), "DayPlan must have morning_activity")
            self.assertTrue(hasattr(day, "afternoon_activity"), "DayPlan must have afternoon_activity")
            self.assertTrue(hasattr(day, "evening_activity"), "DayPlan must have evening_activity")
            self.assertIsNotNone(day.day_number, "DayPlan.day_number must not be None")

    # ------------------------------------------------------------------
    # Uses research attractions when available
    # ------------------------------------------------------------------

    def test_itinerary_uses_provided_research_attractions(self):
        """When rich research is provided, fallback itinerary references at least some attractions."""
        req = _make_request("Jaipur", dep="2025-12-05", ret="2025-12-07")
        research = _rich_research("Jaipur", ["Hawa Mahal", "Amber Fort", "City Palace"])
        plans = itinerary_service.generate_algorithmic_itinerary(req, research)
        text = " ".join([
            (p.morning_activity or "") + (p.afternoon_activity or "") + (p.evening_activity or "")
            for p in plans
        ]).lower()
        known = ["hawa mahal", "amber fort", "city palace"]
        hits = [k for k in known if k in text]
        self.assertGreater(len(hits), 0,
                           f"Jaipur fallback ignores provided attraction data.\nText: {text}")

    # ------------------------------------------------------------------
    # generate_itinerary falls back to algorithmic when Gemini unavailable
    # ------------------------------------------------------------------

    def test_generate_itinerary_falls_back_to_algorithmic(self):
        """generate_itinerary() must fall back to the algorithmic path when Gemini has no API key."""
        req = _make_request("Udaipur")
        research = _empty_research("Udaipur")
        # Patch get_gemini_api_key to return empty string (no key configured).
        with patch("services.itinerary_service.get_gemini_api_key", return_value=""):
            plans = itinerary_service.generate_itinerary(req, research)
        self.assertGreater(len(plans), 0, "generate_itinerary must return plans even without Gemini API key")
        for day in plans:
            self.assertIsNotNone(day.morning_activity)


if __name__ == "__main__":
    unittest.main()

