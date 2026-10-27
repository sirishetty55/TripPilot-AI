"""
Unit tests for TripPilot AI Budget Service.
"""

import unittest
from models import TripRequest, BudgetBreakdown
from services.budget_service import calculate_budget, get_budget_dataframe

class TestBudgetService(unittest.TestCase):

    def setUp(self):
        self.req_balanced = TripRequest(
            destination="Goa",
            departure_date="2026-11-10",
            return_date="2026-11-12",  # 3 days, 2 nights
            travelers=2,
            budget_inr=15000.0,
            accommodation_pref="budget",
            travel_style="balanced"
        )

        self.req_low_budget = TripRequest(
            destination="Goa",
            departure_date="2026-11-10",
            return_date="2026-11-14",  # 5 days, 4 nights
            travelers=4,
            budget_inr=5000.0,         # Very low budget -> should trigger over budget
            accommodation_pref="luxury",
            travel_style="packed"
        )

    def test_budget_calculation_structure(self):
        bgt = calculate_budget(self.req_balanced)
        self.assertIsInstance(bgt, BudgetBreakdown)
        self.assertEqual(bgt.user_budget, 15000.0)
        self.assertGreater(bgt.total_estimated, 0.0)
        self.assertGreater(bgt.accommodation_cost, 0.0)
        self.assertGreater(bgt.food_cost, 0.0)
        self.assertGreater(bgt.transport_cost, 0.0)
        self.assertGreater(bgt.activities_cost, 0.0)
        self.assertGreater(bgt.misc_cost, 0.0)

    def test_budget_within_limit(self):
        bgt = calculate_budget(self.req_balanced)
        self.assertFalse(bgt.is_over_budget)
        self.assertGreaterEqual(bgt.remaining_budget, 0.0)

    def test_over_budget_detection(self):
        bgt = calculate_budget(self.req_low_budget)
        self.assertTrue(bgt.is_over_budget)
        self.assertLess(bgt.remaining_budget, 0.0)

    def test_manual_override(self):
        overrides = {
            "accommodation": 5000.0,
            "food": 3000.0,
            "transport": 1500.0,
            "activities": 1000.0,
            "misc": 500.0
        }
        bgt = calculate_budget(self.req_balanced, overrides=overrides)
        self.assertEqual(bgt.accommodation_cost, 5000.0)
        self.assertEqual(bgt.food_cost, 3000.0)
        self.assertEqual(bgt.total_estimated, 11000.0)
        self.assertEqual(bgt.remaining_budget, 4000.0)

    def test_dataframe_generation(self):
        bgt = calculate_budget(self.req_balanced)
        df = get_budget_dataframe(bgt)
        self.assertEqual(len(df), 5)
        self.assertIn("Category", df.columns)
        self.assertIn("Amount (₹)", df.columns)
        self.assertIn("Share (%)", df.columns)
        self.assertAlmostEqual(df["Share (%)"].sum(), 100.0, delta=1.0)

if __name__ == "__main__":
    unittest.main()
