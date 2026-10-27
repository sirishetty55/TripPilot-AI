"""
tests/test_location_service.py

Regression tests for destination classification in services/location_service.py.

Covers:
- Pudukkottai must NOT be classified as international (substring 'uk' bug).
- Luxembourg must be classified as international (not domestic).
- Known Indian cities/states return country_code 'IN'.
- Known international destinations return correct codes.
- Island detection for Bali, Andaman, Maldives.
- Partial token matching (e.g. "North Goa", "Central Paris").
- Completely unknown locations are marked as UNKNOWN / ambiguous.
"""

import unittest

from services.location_service import LocationService


class TestLocationService(unittest.TestCase):
    """Country-resolution and domestic/international classification."""

    def setUp(self):
        self.svc = LocationService(origin_country_code="IN")

    # ------------------------------------------------------------------
    # Regression: Pudukkottai (contains 'uk' substring)
    # ------------------------------------------------------------------

    def test_pudukkottai_is_domestic_india(self):
        """Pudukkottai must resolve to India (IN), not be classified as UK/international."""
        result = self.svc.resolve(destination="Pudukkottai")
        self.assertEqual(result.country_code, "IN",
                         f"Pudukkottai should be IN, got '{result.country_code}'")
        self.assertFalse(result.is_international,
                         "Pudukkottai must NOT be flagged as international")

    # ------------------------------------------------------------------
    # Regression: Luxembourg must be international
    # ------------------------------------------------------------------

    def test_luxembourg_is_international(self):
        """Luxembourg must be classified as international from an Indian origin."""
        result = self.svc.resolve(destination="Luxembourg")
        self.assertNotEqual(result.country_code, "IN",
                            "Luxembourg must NOT be classified as India")
        self.assertTrue(result.is_international,
                        "Luxembourg must be flagged as international")

    # ------------------------------------------------------------------
    # Well-known Indian cities
    # ------------------------------------------------------------------

    def test_goa_is_domestic(self):
        result = self.svc.resolve("Goa")
        self.assertEqual(result.country_code, "IN")
        self.assertFalse(result.is_international)

    def test_mumbai_is_domestic(self):
        result = self.svc.resolve("Mumbai")
        self.assertEqual(result.country_code, "IN")
        self.assertFalse(result.is_international)

    def test_jaipur_is_domestic(self):
        result = self.svc.resolve("Jaipur")
        self.assertEqual(result.country_code, "IN")
        self.assertFalse(result.is_international)

    def test_manali_is_domestic(self):
        result = self.svc.resolve("Manali")
        self.assertEqual(result.country_code, "IN")
        self.assertFalse(result.is_international)

    def test_bengaluru_is_domestic(self):
        result = self.svc.resolve("Bengaluru")
        self.assertEqual(result.country_code, "IN")
        self.assertFalse(result.is_international)

    # ------------------------------------------------------------------
    # International destinations
    # ------------------------------------------------------------------

    def test_paris_is_international(self):
        result = self.svc.resolve("Paris")
        self.assertNotEqual(result.country_code, "IN")
        self.assertTrue(result.is_international)

    def test_maldives_is_international_island(self):
        result = self.svc.resolve("Maldives")
        self.assertTrue(result.is_international)
        self.assertTrue(result.is_island, "Maldives should be marked as island")

    def test_switzerland_is_international(self):
        result = self.svc.resolve("Switzerland")
        self.assertTrue(result.is_international)

    def test_bali_is_international_island(self):
        result = self.svc.resolve("Bali")
        # Bali is in Indonesia (ID)
        self.assertNotEqual(result.country_code, "IN")
        self.assertTrue(result.is_international)
        self.assertTrue(result.is_island)

    # ------------------------------------------------------------------
    # Domestic island (Andaman — Indian territory, island)
    # ------------------------------------------------------------------

    def test_andaman_is_domestic_island(self):
        result = self.svc.resolve("Andaman")
        self.assertEqual(result.country_code, "IN")
        self.assertFalse(result.is_international)
        self.assertTrue(result.is_island, "Andaman should be marked as island")

    # ------------------------------------------------------------------
    # Partial-token / compound name matching
    # ------------------------------------------------------------------

    def test_north_goa_resolves_to_india(self):
        result = self.svc.resolve("North Goa")
        self.assertEqual(result.country_code, "IN")
        self.assertFalse(result.is_international)

    def test_central_paris_resolves_to_france(self):
        result = self.svc.resolve("Central Paris")
        self.assertNotEqual(result.country_code, "IN")
        self.assertTrue(result.is_international)

    # ------------------------------------------------------------------
    # Completely unknown / ambiguous location
    # ------------------------------------------------------------------

    def test_completely_unknown_location_is_ambiguous(self):
        """An unresolvable destination must return UNKNOWN and is_ambiguous=True."""
        result = self.svc.resolve("FictionalCity99999XYZ")
        self.assertEqual(result.country_code, "UNKNOWN",
                         "Unresolvable location should return UNKNOWN country_code")
        self.assertTrue(result.is_ambiguous,
                        "Unresolvable location should be flagged ambiguous")


if __name__ == "__main__":
    unittest.main()

