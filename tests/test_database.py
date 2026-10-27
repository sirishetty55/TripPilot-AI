"""
Unit tests for TripPilot AI SQLite Database Module.
Enforces strict test isolation using dedicated temporary databases,
ensuring the application's production database is never modified during tests.
"""

import unittest
import os
import shutil
import tempfile
import sqlite3
from models import TripRequest, TripResearchResult, DayPlan, BudgetBreakdown, Attraction, Accommodation
import database
from config import DATABASE_PATH as PROD_DATABASE_PATH

class TestDatabaseModule(unittest.TestCase):

    def setUp(self):
        # Create isolated temporary directory and database file
        self.temp_dir = tempfile.mkdtemp(prefix="trippilot_test_")
        self.temp_db_path = os.path.join(self.temp_dir, "test_trippilot.db")
        
        # Save original database path and patch to isolated temp db
        self.orig_db_path = database.DATABASE_PATH
        database.DATABASE_PATH = self.temp_db_path
        
        # Initialize isolated schema
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
            sources_accessed=[{"url": "https://en.wikivoyage.org/wiki/Goa", "title": "Goa Guide", "status": "Navigated via Playwright MCP"}]
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

    def tearDown(self):
        # Restore original database path
        database.DATABASE_PATH = self.orig_db_path
        # Remove temporary directory and test database
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_retrieve_trip_isolated(self):
        trip_id = database.save_trip(
            self.sample_req.to_dict(),
            self.sample_res.to_dict(),
            [p.to_dict() for p in self.sample_itn],
            self.sample_bgt.to_dict()
        )
        self.assertIsInstance(trip_id, int)
        self.assertGreater(trip_id, 0)

        # Retrieve all from isolated db
        all_trips = database.get_all_trips()
        self.assertEqual(len(all_trips), 1)
        self.assertEqual(all_trips[0]["id"], trip_id)

        # Retrieve specific trip
        loaded = database.get_trip_by_id(trip_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["destination"], "Goa")
        self.assertEqual(loaded["travelers"], 2)
        self.assertEqual(loaded["trip_request"]["destination"], "Goa")
        self.assertEqual(len(loaded["research_result"]["attractions"]), 1)
        self.assertEqual(loaded["research_result"]["attractions"][0]["name"], "Fort Aguada")

        # Cleanup in isolated db
        deleted = database.delete_trip(trip_id)
        self.assertTrue(deleted)
        self.assertIsNone(database.get_trip_by_id(trip_id))
        self.assertEqual(len(database.get_all_trips()), 0)

    def test_audit_logs_deterministic(self):
        """Ensures audit-log tests are deterministic, independent, and start with 0 records."""
        initial_logs = database.get_recent_research_logs(10)
        self.assertEqual(len(initial_logs), 0, "Isolated test database must start with zero audit logs")

        database.log_research_session("Jaipur", "Success", 2, 4.25, "Test audit log entry")
        logs = database.get_recent_research_logs(10)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["destination"], "Jaipur")
        self.assertEqual(logs[0]["status"], "Success")
        self.assertEqual(logs[0]["sources_count"], 2)

    def test_production_database_remains_unmodified(self):
        """Regression test confirming the configured production database is not modified."""
        prod_path = str(PROD_DATABASE_PATH)
        if not os.path.exists(prod_path):
            self.skipTest("Production database does not exist on disk yet.")

        # Record initial row count and mtime of production database
        conn = sqlite3.connect(prod_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM saved_trips")
        initial_trip_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM research_logs")
        initial_log_count = cursor.fetchone()[0]
        conn.close()
        initial_mtime = os.path.getmtime(prod_path)

        # Execute operations on the isolated test database
        for i in range(3):
            database.save_trip(
                self.sample_req.to_dict(),
                self.sample_res.to_dict(),
                [p.to_dict() for p in self.sample_itn],
                self.sample_bgt.to_dict()
            )
            database.log_research_session(f"Dest_{i}", "Success", 1, 1.0, f"Log {i}")

        # Verify test db accumulated 3 trips and 3 logs
        self.assertEqual(len(database.get_all_trips()), 3)
        self.assertEqual(len(database.get_recent_research_logs(10)), 3)

        # Verify production database row counts and mtime are completely untouched
        conn = sqlite3.connect(prod_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM saved_trips")
        final_trip_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM research_logs")
        final_log_count = cursor.fetchone()[0]
        conn.close()

        self.assertEqual(initial_trip_count, final_trip_count, "Production saved_trips count was modified by test!")
        self.assertEqual(initial_log_count, final_log_count, "Production research_logs count was modified by test!")
        self.assertEqual(initial_mtime, os.path.getmtime(prod_path), "Production database file was touched by test!")


if __name__ == "__main__":
    unittest.main()
