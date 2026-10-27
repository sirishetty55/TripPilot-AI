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

        self.assertEqual([item.name for item in result.attractions], ["Hadimba Devi Temple"])
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


if __name__ == "__main__":
    unittest.main()
