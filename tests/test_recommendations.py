"""Tests for minimum accommodation and food recommendations."""

import unittest
from urllib.parse import unquote

from services.travel_research import ensure_minimum_recommendations


class TestMinimumRecommendations(unittest.TestCase):
    def test_empty_lists_receive_three_destination_relevant_suggestions(self):
        stays, food = ensure_minimum_recommendations("Manali", [], [], {"stay": "stay.jpg", "food": "food.jpg"})

        self.assertEqual(len(stays), 3)
        self.assertEqual(len(food), 3)
        self.assertTrue(any("Himachali" in item.name or "Siddu" in item.name for item in food))
        self.assertTrue(all(not item.verified for item in stays + food))
        self.assertTrue(all(item.maps_url.startswith("https://www.google.com/maps/") for item in stays + food))

    def test_existing_recommendations_are_preserved_and_only_supplemented(self):
        from models import Accommodation, FoodExperience

        existing_stay = Accommodation(property_name="Existing Stay", verified=True)
        existing_food = FoodExperience(name="Existing Dish", verified=True)
        stays, food = ensure_minimum_recommendations(
            "Goa", [existing_stay], [existing_food], {"stay": "", "food": ""}
        )

        self.assertEqual(len(stays), 3)
        self.assertEqual(len(food), 3)
        self.assertIs(stays[0], existing_stay)
        self.assertIs(food[0], existing_food)
        self.assertIn("vindaloo", unquote(food[2].maps_url).lower())
        self.assertTrue(all(not item.verified for item in stays[1:] + food[1:]))


if __name__ == "__main__":
    unittest.main()
