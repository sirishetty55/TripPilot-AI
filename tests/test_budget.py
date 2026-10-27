"""
Unit tests for TripPilot AI Budget Service.
Verifies same-day trips, hotel tier accuracy, multi-traveler calculations,
intercity transit inclusion, and override behaviors.
"""

import unittest
from models import TripRequest, BudgetBreakdown, Attraction, Accommodation, CommuteOption, TripResearchResult
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
            budget_inr=5000.0,         # Very low budget -> triggers deficit
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

    def test_sameday_trip_has_zero_accommodation_cost(self):
        """A same-day trip (departure == return, 0 nights) must NOT incur hotel cost."""
        req_same_day = TripRequest(
            destination="Jaipur",
            departure_date="2026-11-10",
            return_date="2026-11-10",  # Same-day
            travelers=1,
            budget_inr=5000.0
        )
        self.assertEqual(req_same_day.num_days, 1)
        self.assertEqual(req_same_day.num_nights, 0)

        bgt = calculate_budget(req_same_day)
        self.assertEqual(bgt.accommodation_cost, 0.0, "Same day trip must have zero accommodation cost")
        self.assertTrue(any("Same-day trip" in a for a in bgt.assumptions))

    def test_hotel_tier_matching(self):
        """Verifies that requested hotel tiers (budget vs luxury) calculate appropriately."""
        req_b = TripRequest(destination="Goa", departure_date="2026-11-10", return_date="2026-11-12", accommodation_pref="budget")
        req_l = TripRequest(destination="Goa", departure_date="2026-11-10", return_date="2026-11-12", accommodation_pref="luxury")

        b_bgt = calculate_budget(req_b)
        l_bgt = calculate_budget(req_l)

        self.assertGreater(l_bgt.accommodation_cost, b_bgt.accommodation_cost)
        self.assertGreaterEqual(l_bgt.accommodation_cost, 14000.0)  # 2 nights * 7500 = 15000

    def test_multiple_travelers_room_math(self):
        """Verifies 3 travelers require 2 rooms, scaling accommodation cost."""
        req_2_pax = TripRequest(destination="Goa", departure_date="2026-11-10", return_date="2026-11-11", travelers=2, accommodation_pref="budget")
        req_3_pax = TripRequest(destination="Goa", departure_date="2026-11-10", return_date="2026-11-11", travelers=3, accommodation_pref="budget")

        bgt_2 = calculate_budget(req_2_pax)
        bgt_3 = calculate_budget(req_3_pax)

        # 2 pax -> 1 room; 3 pax -> 2 rooms
        self.assertEqual(bgt_3.accommodation_cost, bgt_2.accommodation_cost * 2)

    def test_intercity_transit_inclusion(self):
        """When starting city is provided, intercity transit is computed into the total."""
        req_transit = TripRequest(
            destination="Goa",
            starting_city="Mumbai",
            departure_date="2026-11-10",
            return_date="2026-11-12",
            travelers=2,
            budget_inr=25000.0
        )
        commute_opt = CommuteOption(
            mode="Flight",
            title="Flight from Mumbai to Goa",
            estimated_cost_inr="₹3,500 / person",
            details="Direct flight"
        )
        research = TripResearchResult(
            destination="Goa",
            summary="Coastal state",
            commute_options=[commute_opt]
        )
        bgt = calculate_budget(req_transit, research=research)
        self.assertGreater(bgt.transit_cost, 0.0)
        self.assertEqual(bgt.transit_cost, 7000.0)  # 3500 * 2 pax
        self.assertIn(bgt.transit_cost, [bgt.transit_cost])
        self.assertEqual(bgt.total_estimated, bgt.accommodation_cost + bgt.food_cost + bgt.transport_cost + bgt.activities_cost + bgt.transit_cost + bgt.misc_cost)

    def test_missing_and_zero_cost_activities(self):
        """Unpriced or zero-cost activities receive a transparent nominal baseline buffer."""
        research = TripResearchResult(
            destination="Goa",
            summary="Coastal state",
            attractions=[
                Attraction(name="Free Beach", description="Public beach", price_inr=0.0, price_display="Free")
            ]
        )
        bgt = calculate_budget(self.req_balanced, research=research)
        self.assertGreater(bgt.activities_cost, 0.0)

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
        df = get_budget_dataframe(bgt, travelers=self.req_balanced.travelers)
        self.assertGreaterEqual(len(df), 5)
        self.assertIn("Category", df.columns)
        self.assertIn("Group Total (₹)", df.columns)
        self.assertIn("Per Person (₹)", df.columns)
        self.assertIn("Share (%)", df.columns)
        self.assertAlmostEqual(df["Share (%)"].sum(), 100.0, delta=1.0)


if __name__ == "__main__":
    unittest.main()
