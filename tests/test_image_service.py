"""
Unit tests for Destination Image Service.
Verifies:
- Dynamic real photograph retrieval.
- Landmark-specific vs destination-level resolution.
- Two-tier caching behavior (in-memory + SQLite).
- Safe fallback when offline (never fabricating fake URLs).
- Proper alt text and attribution metadata.
"""

import json
import unittest
from unittest.mock import patch, MagicMock
from services.image_service import get_destination_photo, _MEMORY_IMAGE_CACHE, DestinationPhoto

class TestImageService(unittest.TestCase):

    def setUp(self):
        _MEMORY_IMAGE_CACHE.clear()

    @patch("services.image_service.urlopen")
    def test_landmark_photo_retrieval(self, mock_urlopen):
        """Tests fetching landmark photograph with full attribution."""
        payload = {
            "query": {
                "pages": {
                    "101": {
                        "title": "Eiffel Tower",
                        "thumbnail": {"source": "https://upload.wikimedia.org/eiffel_thumb.jpg"},
                        "original": {"source": "https://upload.wikimedia.org/eiffel_orig.jpg"},
                        "fullurl": "https://en.wikipedia.org/wiki/Eiffel_Tower"
                    }
                }
            }
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(payload).encode()

        photo = get_destination_photo("Eiffel Tower", "Paris", category="attraction")
        self.assertIsInstance(photo, DestinationPhoto)
        self.assertEqual(photo.image_url, "https://upload.wikimedia.org/eiffel_orig.jpg")
        self.assertEqual(photo.thumb_url, "https://upload.wikimedia.org/eiffel_thumb.jpg")
        self.assertIn("Eiffel Tower", photo.alt_text)
        self.assertIn("Wikimedia Commons", photo.attribution_text)
        self.assertEqual(photo.provider, "Wikimedia Commons")
        self.assertTrue(photo.is_exact_match)

    @patch("services.image_service.urlopen")
    def test_caching_avoids_repeated_network_calls(self, mock_urlopen):
        """Tests that a second request for the same landmark is served directly from cache."""
        payload = {
            "query": {
                "pages": {
                    "202": {
                        "title": "Amber Fort",
                        "thumbnail": {"source": "https://upload.wikimedia.org/amber.jpg"}
                    }
                }
            }
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(payload).encode()

        photo1 = get_destination_photo("Amber Fort", "Jaipur")
        self.assertEqual(mock_urlopen.call_count, 1)

        photo2 = get_destination_photo("Amber Fort", "Jaipur")
        self.assertEqual(mock_urlopen.call_count, 1, "Second call must be served from cache without network invocation")
        self.assertEqual(photo1.image_url, photo2.image_url)

    @patch("services.image_service.urlopen", side_effect=OSError("Network unreachable"))
    def test_offline_failure_returns_honest_empty_image(self, mock_urlopen):
        """When provider API is offline or unreachable, returns empty string instead of fabricating image URLs."""
        photo = get_destination_photo("Random Remote Place", "Unknown Dest")
        self.assertEqual(photo.image_url, "")
        self.assertEqual(photo.thumb_url, "")
        self.assertFalse(photo.is_exact_match)

    @patch("services.image_service.urlopen")
    def test_destination_level_fallback_when_landmark_not_found(self, mock_urlopen):
        """If exact landmark is not found, falls back to destination-level city photograph without fabricating."""
        empty_payload = {"query": {"pages": {}}}
        city_payload = {
            "query": {
                "pages": {
                    "303": {
                        "title": "Zurich",
                        "thumbnail": {"source": "https://upload.wikimedia.org/zurich_city.jpg"},
                        "original": {"source": "https://upload.wikimedia.org/zurich_city.jpg"}
                    }
                }
            }
        }
        # First call (landmark) returns empty; second call (city) returns city photo
        mock_urlopen.return_value.__enter__.return_value.read.side_effect = [
            json.dumps(empty_payload).encode(),
            json.dumps(city_payload).encode()
        ]

        photo = get_destination_photo("Unlisted Boutique Stay", "Zurich", category="hotel")
        self.assertEqual(photo.image_url, "https://upload.wikimedia.org/zurich_city.jpg")
        self.assertFalse(photo.is_exact_match, "Fallback destination photograph must not be marked as exact match")
        self.assertIn("Zurich", photo.alt_text)


if __name__ == "__main__":
    unittest.main()

