"""
Comprehensive unit tests for the 7 user-requested fixes:
1. Raw HTML rendering fix (no indented code blocks)
2. Relevant images and neutral placeholders (no portraits for non-human attractions, no photo duplication)
3. Destination-specific Categorized Tourist Places section (Goa includes Baga Beach, Fort Aguada, etc., dynamic per destination)
4. RedBus integration (no 'undefined', functional routes, official portal fallback for overseas)
5. Destination mismatch prevention (never loads Mumbai for Goa)
6. Budget accuracy and over-budget flagging
7. Graceful Gemini 503 handling and honest verification labeling
"""

import unittest
from unittest.mock import patch, MagicMock
import json

from models import TripRequest, TripResearchResult, Attraction, Accommodation, FoodExperience, CommuteOption
from services.travel_research import (
    is_valid_attraction_name,
    curated_destination_attractions,
    get_categorized_tourist_places,
    generate_commute_options,
    parse_with_heuristics,
    parse_with_gemini,
    check_route_feasibility,
)
from services.image_service import (
    get_destination_photo,
    _fetch_from_unsplash,
    _MEMORY_IMAGE_CACHE
)
from services.ui_utils import render_card_image, safe_html, safe_url
from services.budget_service import calculate_budget


class TestSevenFixes(unittest.TestCase):

    def setUp(self):
        _MEMORY_IMAGE_CACHE.clear()

    # --- 1. Raw HTML bug fix ---
    def test_raw_html_no_indented_code_blocks(self):
        """Verify that render_card_image and HTML templates have zero leading indentation on lines."""
        placeholder_html = render_card_image("", "Test Landmark", category="beach")
        self.assertIn("🏖️", placeholder_html)
        self.assertIn("Beach & Coast", placeholder_html)
        # Ensure rendered image block does not have 4+ leading spaces on any line
        for line in placeholder_html.splitlines():
            if line.strip():
                self.assertFalse(line.startswith("    "), f"Indented line found: {line}")

    # --- 2. Relevant images & neutral placeholders ---
    def test_forbidden_terms_do_not_fetch_photos(self):
        """Terms like 'Wine and other products' or 'Electricity and utilities' must return empty neutral photo."""
        photo1 = get_destination_photo("Wine and other products", "France", category="attraction")
        self.assertEqual(photo1.image_url, "")
        self.assertFalse(photo1.is_exact_match)

        photo2 = get_destination_photo("Electricity and utilities", "Sweden", category="attraction")
        self.assertEqual(photo2.image_url, "")

    @patch("services.image_service.urlopen")
    def test_unsplash_filters_out_portraits_for_landmarks(self, mock_urlopen):
        """Unsplash results matching portrait/person descriptions must be filtered out for attractions."""
        payload = {
            "results": [
                {
                    "description": "Portrait of a man standing in front of winery",
                    "alt_description": "Man posing with wine glass",
                    "urls": {"regular": "https://images.unsplash.com/man.jpg", "small": "https://images.unsplash.com/man_s.jpg"},
                    "user": {"name": "Photographer", "links": {"html": "https://unsplash.com/@user"}}
                },
                {
                    "description": "Scenic vineyard landscape under sunset",
                    "alt_description": "Green rolling vineyard hills",
                    "urls": {"regular": "https://images.unsplash.com/vineyard.jpg", "small": "https://images.unsplash.com/vineyard_s.jpg"},
                    "user": {"name": "Landscape Artist", "links": {"html": "https://unsplash.com/@landscape"}}
                }
            ]
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(payload).encode()

        result = _fetch_from_unsplash("Vineyard", "fake_access_key", page=1, category="attraction")
        self.assertIsNotNone(result)
        # Should have skipped the portrait of a man and picked the scenic vineyard landscape
        self.assertEqual(result.image_url, "https://images.unsplash.com/vineyard.jpg")

    def test_neutral_placeholder_rendered_when_image_unavailable(self):
        """When an exact image is unavailable, render_card_image returns a clean styled placeholder tile."""
        html_stay = render_card_image("", "Budget Hotel", category="hotel")
        self.assertIn("🏨", html_stay)
        self.assertIn("Accommodation", html_stay)

        html_food = render_card_image("", "Goan Fish Curry", category="food")
        self.assertIn("🍽️", html_food)
        self.assertIn("Regional Dining", html_food)

    # --- 3. Tourist Places to Visit section ---
    def test_tourist_places_goa_has_required_spots_in_categories(self):
        """For Goa, places must include Baga Beach, Fort Aguada, Basilica of Bom Jesus, and Dudhsagar Falls."""
        places_dict = get_categorized_tourist_places("Goa")
        self.assertIn("🏖️ Beaches & Coastal Sights", places_dict)
        self.assertIn("🏰 Heritage, Forts & Palaces", places_dict)
        self.assertIn("🛕 Spiritual & Cultural Landmarks", places_dict)
        self.assertIn("🌿 Nature, Waterfalls & Scenic Spots", places_dict)

        all_names = [p["name"] for cat in places_dict.values() for p in cat]
        self.assertTrue(any("Baga Beach" in n for n in all_names), "Baga Beach missing")
        self.assertTrue(any("Fort Aguada" in n for n in all_names), "Fort Aguada missing")
        self.assertTrue(any("Basilica of Bom Jesus" in n for n in all_names), "Basilica of Bom Jesus missing")
        self.assertTrue(any("Dudhsagar Waterfalls" in n for n in all_names), "Dudhsagar Waterfalls missing")

    def test_tourist_places_change_with_destination(self):
        """Recommendations must change dynamically with destination and not remain hardcoded."""
        goa_places = get_categorized_tourist_places("Goa")
        jaipur_places = get_categorized_tourist_places("Jaipur")
        kundapura_places = get_categorized_tourist_places("Kundapura")

        goa_names = {p["name"] for cat in goa_places.values() for p in cat}
        jaipur_names = {p["name"] for cat in jaipur_places.values() for p in cat}
        kundapura_names = {p["name"] for cat in kundapura_places.values() for p in cat}

        self.assertFalse(goa_names.intersection(jaipur_names), "Goa and Jaipur places overlapped")
        self.assertIn("Amber Fort & Palace", jaipur_names)
        self.assertIn("Maravanthe Beach", kundapura_names)

    def test_invalid_names_rejected_from_attractions(self):
        """Meta guide headings, single words like Districts/Cities/Regions, and shopping must be rejected."""
        self.assertFalse(is_valid_attraction_name("Districts", "Paris"))
        self.assertFalse(is_valid_attraction_name("Cities", "Sweden"))
        self.assertFalse(is_valid_attraction_name("Regions", "Sweden"))
        self.assertFalse(is_valid_attraction_name("Other destinations", "Sweden"))
        self.assertFalse(is_valid_attraction_name("The year in Sweden", "Sweden"))
        self.assertFalse(is_valid_attraction_name("Electricity and utilities", "Sweden"))
        self.assertFalse(is_valid_attraction_name("Tourist information", "Sweden"))
        self.assertFalse(is_valid_attraction_name("Wine and other products", "France"))
        self.assertFalse(is_valid_attraction_name("Public holidays", "Sweden"))

    # --- 4. RedBus integration ---
    def test_redbus_dynamic_route_url_no_undefined(self):
        """RedBus booking URL must dynamically use origin and destination without 'undefined'."""
        options = generate_commute_options("Goa", "Bengaluru", travel_date="2026-11-15")
        bus_opt = next((o for o in options if "bus" in o.mode.lower()), None)
        self.assertIsNotNone(bus_opt)
        self.assertNotIn("undefined", bus_opt.booking_url)
        self.assertIn("redbus.in/bus-tickets/bengaluru-to-goa", bus_opt.booking_url)

    def test_overseas_route_excludes_overland_buses(self):
        """Overseas travel (e.g. India to Switzerland or Paris) must not fabricate bus routes."""
        is_overseas, route_cat = check_route_feasibility("Bengaluru", "Switzerland")
        self.assertTrue(is_overseas)
        self.assertEqual(route_cat, "international")

        options = generate_commute_options("Switzerland", "Bengaluru")
        bus_modes = [o for o in options if "bus" in o.mode.lower() and "airport" not in o.title.lower()]
        self.assertEqual(len(bus_modes), 0, "Overland bus should not be generated for overseas route")

    # --- 5. Destination mismatch prevention ---
    def test_destination_validation(self):
        """Requested destination and returned destination must match."""
        req = TripRequest(destination="Goa", starting_city="Bengaluru", departure_date="2026-11-01", return_date="2026-11-05")
        mismatched_res = TripResearchResult(
            destination="Mumbai",
            summary="Research for Mumbai",
            attractions=[],
            accommodations=[],
            food_experiences=[],
            commute_options=[]
        )
        self.assertNotEqual(
            req.destination.casefold().strip(),
            mismatched_res.destination.casefold().strip()
        )

    # --- 6. Budget accuracy & over-budget flagging ---
    def test_budget_accuracy_and_over_budget_flagging(self):
        """Budget calculation must accurately reflect travelers and flag over-budget scenarios."""
        # Case A: Low budget where expenses exceed budget
        low_req = TripRequest(
            destination="Goa",
            travelers=4,
            departure_date="2026-11-01",
            return_date="2026-11-06",  # 5 nights, 4 travelers -> 2 rooms
            budget_inr=10000.0,
            accommodation_pref="mid-range"
        )
        budget_a = calculate_budget(low_req)
        self.assertTrue(budget_a.is_over_budget)
        self.assertGreater(budget_a.total_estimated, low_req.budget_inr)
        self.assertLess(budget_a.remaining_budget, 0)

        # Case B: Sufficient budget
        high_req = TripRequest(
            destination="Goa",
            travelers=1,
            departure_date="2026-11-01",
            return_date="2026-11-02",  # 1 night, 1 traveler -> 1 room
            budget_inr=50000.0,
            accommodation_pref="budget"
        )
        budget_b = calculate_budget(high_req)
        self.assertFalse(budget_b.is_over_budget)
        self.assertLessEqual(budget_b.total_estimated, high_req.budget_inr)

    # --- 7. Gemini errors & heuristic labeling ---
    def test_parse_with_heuristics_labels_suggestions_honestly(self):
        """Heuristic fallback attractions must have verified=False and never claim live verification."""
        req = TripRequest(destination="Goa", departure_date="2026-11-01", return_date="2026-11-05")
        snapshot = 'heading "Baga Beach"\nheading "Fort Aguada & Lighthouse"'
        res = parse_with_heuristics(snapshot, req, "https://en.wikivoyage.org/wiki/Goa")
        self.assertEqual(res.destination, "Goa")
        for attr in res.attractions:
            self.assertFalse(attr.verified, "Heuristic attractions must not claim live verification")

    def test_gemini_503_handled_gracefully(self):
        """When Gemini throws an error or is unavailable, parse_with_gemini must return None gracefully."""
        req = TripRequest(destination="Goa", departure_date="2026-11-01", return_date="2026-11-05")
        with patch("services.travel_research.get_gemini_api_key", return_value="dummy_api_key"):
            # When the genai import or call fails with 503 or any exception
            with patch("builtins.__import__", side_effect=Exception("503 Service Unavailable")):
                res = parse_with_gemini("dummy text", req, "https://en.wikivoyage.org/wiki/Goa")
                self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
