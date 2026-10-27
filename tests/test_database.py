"""
Unit tests for TripPilot AI SQLite Database Module.
"""

import unittest
import os
from models import TripRequest, TripResearchResult, DayPlan, BudgetBreakdown, Attraction, Accommodation
import database

class TestDatabaseModule(unittest.TestCase):

    def setUp(self):
        database.init_db()
        self.sample_req = TripRequest(
            destination="Goa",
            departure_date="2026-11-10",
            return_date="2026-11-12",
            travelers=2,
            budget_inr=15000.0
        )
        self.sample_res = TripResearchResult(
            destination="Goa",
            summary="Beautiful coastal beaches and Portuguese forts.",
            attractions=[
                Attraction(name="Fort Aguada", description="17th century fort", price_inr=50.0)
            ],
            accommodations=[
                Accommodation(property_name="Zostel Goa", price_per_night_inr=1100.0)
            ],
            sources_accessed=[{"url": "http://127.0.0.1:8765/goa.html", "title": "Goa Guide", "status": "OK"}]
        )
        self.sample_itn = [
            DayPlan(day_number=1, date_str="Day 1", title="Arrival", morning_activity="Check in")
        ]
        self.sample_bgt = BudgetBreakdown(
            user_budget=15000.0,
            accommodation_cost=2200.0,
            food_cost=3600.0,
            transport_cost=1500.0,
            activities_cost=100.0,
            misc_cost=500.0,
            total_estimated=7900.0,
            remaining_budget=7100.0,
            is_over_budget=False
        )

    def test_save_and_retrieve_trip(self):
        trip_id = database.save_trip(
            self.sample_req.to_dict(),
            self.sample_res.to_dict(),
            [p.to_dict() for p in self.sample_itn],
            self.sample_bgt.to_dict()
        )
        self.assertIsInstance(trip_id, int)
        self.assertGreater(trip_id, 0)

        # Retrieve all
        all_trips = database.get_all_trips()
        self.assertTrue(any(t["id"] == trip_id for t in all_trips))

        # Retrieve specific trip
        loaded = database.get_trip_by_id(trip_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["destination"], "Goa")
        self.assertEqual(loaded["travelers"], 2)
        self.assertEqual(loaded["trip_request"]["destination"], "Goa")
        self.assertEqual(len(loaded["research_result"]["attractions"]), 1)
        self.assertEqual(loaded["research_result"]["attractions"][0]["name"], "Fort Aguada")

        # Cleanup
        deleted = database.delete_trip(trip_id)
        self.assertTrue(deleted)
        self.assertIsNone(database.get_trip_by_id(trip_id))

    def test_audit_logs(self):
        database.log_research_session("Jaipur", "Success", 2, 4.25, "Test audit log entry")
        logs = database.get_recent_research_logs(5)
        self.assertGreater(len(logs), 0)
        self.assertEqual(logs[0]["destination"], "Jaipur")

if __name__ == "__main__":
    unittest.main()
