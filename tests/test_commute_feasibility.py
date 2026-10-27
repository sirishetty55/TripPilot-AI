"""
Unit tests for commute route physical feasibility and overland mode filtering.
Ensures that impossible travel modes (e.g., cars/buses from Bengaluru to Switzerland)
are strictly filtered out.
"""

import unittest
from services.travel_research import check_route_feasibility, generate_commute_options

class TestCommuteFeasibility(unittest.TestCase):

    def test_bengaluru_to_switzerland(self):
        """Tests that Bengaluru to Switzerland returns ONLY flights & destination rail, no car/bus."""
        is_overseas, route_cat = check_route_feasibility("Bengaluru", "Switzerland")
        self.assertTrue(is_overseas)
        self.assertEqual(route_cat, "international")

        options = generate_commute_options("Switzerland", "Bengaluru")
        self.assertGreater(len(options), 0)

        # Ensure NO car, road trip, bus or Indian train is present
        modes = [opt.mode.lower() for opt in options]
        titles = [opt.title.lower() for opt in options]

        for m in modes:
            self.assertNotIn("car", m)
            self.assertNotIn("bus", m)
            self.assertNotIn("road trip", m)

        # Ensure Flight is present
        self.assertTrue(any("flight" in m for m in modes))

    def test_fuzzy_spelling_swirzerland(self):
        """Tests user typo 'swirzerland' is handled as international."""
        is_overseas, route_cat = check_route_feasibility("Bengaluru", "swirzerland")
        self.assertTrue(is_overseas)
        self.assertEqual(route_cat, "international")

        options = generate_commute_options("swirzerland", "Bengaluru")
        modes = [opt.mode.lower() for opt in options]
        for m in modes:
            self.assertNotIn("car", m)
            self.assertNotIn("bus", m)

    def test_domestic_mainland_mumbai_to_goa(self):
        """Tests domestic mainland routes retain multi-modal options (flight, train, bus, car)."""
        is_overseas, route_cat = check_route_feasibility("Mumbai", "Goa")
        self.assertFalse(is_overseas)
        self.assertEqual(route_cat, "domestic_mainland")

        options = generate_commute_options("Goa", "Mumbai")
        modes = [opt.mode.lower() for opt in options]
        self.assertTrue(any("flight" in m for m in modes))
        self.assertTrue(any("train" in m for m in modes))
        self.assertTrue(any("bus" in m for m in modes))
        self.assertTrue(any("road" in m or "car" in m for m in modes))

    def test_island_route_maldives(self):
        """Tests island routes return flights and ferry/speedboats, no cars or buses."""
        is_overseas, route_cat = check_route_feasibility("Delhi", "Maldives")
        self.assertTrue(is_overseas)
        self.assertEqual(route_cat, "island")

        options = generate_commute_options("Maldives", "Delhi")
        modes = [opt.mode.lower() for opt in options]
        for m in modes:
            self.assertNotIn("car", m)
            self.assertNotIn("bus", m)
            self.assertNotIn("train", m)
        self.assertTrue(any("flight" in m for m in modes))
        self.assertTrue(any("ferry" in m or "transfer" in m for m in modes))

if __name__ == "__main__":
    unittest.main()
