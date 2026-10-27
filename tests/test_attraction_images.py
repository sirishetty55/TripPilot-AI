"""Tests for destination-specific attraction photos."""

import json
import sqlite3
import unittest
from unittest.mock import patch

from models import TripRequest
from services.travel_research import parse_with_heuristics
from services.image_service import _MEMORY_IMAGE_CACHE
from config import DATABASE_PATH


class TestAttractionImages(unittest.TestCase):
    def setUp(self):
        _MEMORY_IMAGE_CACHE.clear()
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            conn.cursor().execute("DELETE FROM image_cache")
            conn.commit()
            conn.close()
        except Exception:
            pass

    @patch("services.image_service.urlopen")
    def test_heuristic_parser_uses_real_place_thumbnails_and_skips_overview_headings(self, mock_urlopen):
        payload = {
            "query": {
                "pages": {
                    "42": {
                        "title": "Hadimba Devi Temple",
                        "thumbnail": {"source": "https://upload.wikimedia.org/hadimba.jpg"},
                        "original": {"source": "https://upload.wikimedia.org/hadimba.jpg"},
                    }
                }
            }
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(payload).encode()
        request = TripRequest(
            destination="Manali",
            departure_date="2026-11-01",
            return_date="2026-11-03",
        )
        snapshot = '\n'.join([
            'heading "Manali"',
            'heading "Understand"',
            'heading "Weather"',
            'heading "Hadimba Devi Temple"',
        ])

        result = parse_with_heuristics(snapshot, request, "https://en.wikivoyage.org/wiki/Manali")

        # The heuristic parser should keep "Hadimba Devi Temple" (valid attraction)
        # AND supplement with curated Manali sights (minimum 4 attractions enforced)
        attraction_names = [item.name for item in result.attractions]
        self.assertIn("Hadimba Devi Temple", attraction_names)
        # Should have at least 4 attractions total (curated supplements added)
        self.assertGreaterEqual(len(result.attractions), 4)
        self.assertEqual(result.attractions[0].image_url, "https://upload.wikimedia.org/hadimba.jpg")

    @patch("services.image_service.urlopen", side_effect=OSError("offline"))
    def test_missing_image_does_not_fall_back_to_unrelated_stock_photo(self, _mock_urlopen):
        request = TripRequest(
            destination="Manali",
            departure_date="2026-11-01",
            return_date="2026-11-03",
        )
        result = parse_with_heuristics(
            'heading "Hadimba Devi Temple"', request, "https://en.wikivoyage.org/wiki/Manali"
        )

        self.assertEqual(result.attractions[0].image_url, "")

    @patch("services.image_service.urlopen", side_effect=OSError("offline"))
    def test_electricity_and_guide_sections_are_rejected_and_replaced_with_real_sights(self, _mock_urlopen):
        """Ensures guide meta headings (Electricity, Regions, etc.) are rejected and real tourist sights are used."""
        request = TripRequest(
            destination="Sweden",
            departure_date="2026-11-01",
            return_date="2026-11-05",
        )
        snapshot = "\n".join([
            'heading "Regions"',
            'heading "Cities"',
            'heading "Other destinations"',
            'heading "The year in Sweden"',
            'heading "Electricity and utilities"',
            'heading "Tourist information"',
        ])
        result = parse_with_heuristics(snapshot, request, "https://en.wikivoyage.org/wiki/Sweden")

        attraction_names = [item.name for item in result.attractions]
        # None of the generic headings should appear as attractions
        self.assertNotIn("Regions", attraction_names)
        self.assertNotIn("Cities", attraction_names)
        self.assertNotIn("Other destinations", attraction_names)
        self.assertNotIn("The year in Sweden", attraction_names)
        self.assertNotIn("Electricity and utilities", attraction_names)
        self.assertNotIn("Tourist information", attraction_names)

        # Real tourist attractions must be returned instead
        self.assertTrue(len(attraction_names) >= 3, "Must provide real tourist attractions")
        self.assertTrue(any("Vasa" in name or "Gamla Stan" in name or "Palace" in name for name in attraction_names))

    def test_is_valid_attraction_name_filters_guide_meta_and_accepts_real_sights(self):
        from services.travel_research import is_valid_attraction_name
        # Guide sections & meta terms must be rejected
        self.assertFalse(is_valid_attraction_name("Regions", "Sweden"))
        self.assertFalse(is_valid_attraction_name("Cities", "Sweden"))
        self.assertFalse(is_valid_attraction_name("Other destinations", "Sweden"))
        self.assertFalse(is_valid_attraction_name("Electricity and utilities", "Sweden"))
        self.assertFalse(is_valid_attraction_name("The year in Sweden", "Sweden"))
        self.assertFalse(is_valid_attraction_name("Tourist information", "Sweden"))
        self.assertFalse(is_valid_attraction_name("Districts", "Paris"))
        self.assertFalse(is_valid_attraction_name("Public holidays", "France"))
        self.assertFalse(is_valid_attraction_name("Name", "Goa"))
        self.assertFalse(is_valid_attraction_name("People", "Goa"))
        self.assertFalse(is_valid_attraction_name("See", "Jaipur"))
        self.assertFalse(is_valid_attraction_name("Eat", "Jaipur"))
        self.assertFalse(is_valid_attraction_name("Drink", "Jaipur"))
        self.assertFalse(is_valid_attraction_name("Sleep", "Jaipur"))

        # Real attractions and landmarks must be accepted
        self.assertTrue(is_valid_attraction_name("Vasa Museum", "Sweden"))
        self.assertTrue(is_valid_attraction_name("Eiffel Tower", "Paris"))
        self.assertTrue(is_valid_attraction_name("Louvre Museum", "Paris"))
        self.assertTrue(is_valid_attraction_name("Kodi Beach", "Kundapura"))
        self.assertTrue(is_valid_attraction_name("Maravanthe Beach", "Kundapura"))
        self.assertTrue(is_valid_attraction_name("Amber Fort & Palace", "Jaipur"))
        self.assertTrue(is_valid_attraction_name("Basilica of Bom Jesus", "Goa"))
        self.assertTrue(is_valid_attraction_name("Hadimba Devi Temple", "Manali"))

    def test_bengaluru_to_kundapura_transit_accuracy_and_redbus_no_undefined(self):
        from services.travel_research import generate_commute_options
        options = generate_commute_options("Kundapura", "Bengaluru", travel_date="2026-11-15")
        
        # Must have options
        self.assertTrue(len(options) >= 3)

        train_opts = [o for o in options if "train" in o.mode.lower()]
        self.assertTrue(len(train_opts) >= 1)
        # Must NOT claim a Vande Bharat train operates
        self.assertNotIn("vande bharat train", train_opts[0].title.lower())
        self.assertIn("do not assume a vande bharat operates", train_opts[0].details.lower())

        bus_opts = [o for o in options if "bus" in o.mode.lower()]
        self.assertTrue(len(bus_opts) >= 1)
        # RedBus booking url must NOT contain 'undefined'
        self.assertNotIn("undefined", bus_opts[0].booking_url.lower())
        self.assertTrue("redbus.in" in bus_opts[0].booking_url or "google.com" in bus_opts[0].booking_url)


if __name__ == "__main__":
    unittest.main()
