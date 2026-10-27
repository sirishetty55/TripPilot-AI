"""
Unit tests for commute route physical feasibility and overland mode filtering.
Ensures that:
- Substring edge-cases like 'Pudukkottai' containing 'uk' remain strictly domestic.
- International destinations like 'Luxembourg' are correctly classified as international.
- Impossible travel modes (e.g., cars/buses from Bengaluru to Switzerland/Europe) are strictly filtered out.
- Domestic island routes (e.g. Andaman) exclude cars and buses.
- Ambiguous / unresolvable inputs are marked as unknown.
"""

import unittest
from services.travel_research import check_route_feasibility, generate_commute_options
from services.location_service import resolve_location, classify_route

class TestCommuteFeasibility(unittest.TestCase):

    def test_pudukkottai_is_classified_as_domestic_not_uk(self):
        """Regression test: Pudukkottai must NOT be classified as international due to substring 'uk'."""
        loc = resolve_location("Pudukkottai")
        self.assertEqual(loc.country_code, "IN")
        self.assertEqual(loc.country_name, "India")

        is_overseas, route_cat = check_route_feasibility("Bengaluru", "Pudukkottai")
        self.assertFalse(is_overseas)
        self.assertEqual(route_cat, "domestic_mainland")

        options = generate_commute_options("Pudukkottai", "Bengaluru")
        modes = [opt.mode.lower() for opt in options]
        # Road trip or train should be viable for Bengaluru to Pudukkottai
        self.assertTrue(any("road" in m or "car" in m or "bus" in m or "train" in m for m in modes))

    def test_luxembourg_is_classified_as_international(self):
        """Regression test: Luxembourg must be correctly classified as international, not domestic."""
        loc = resolve_location("Luxembourg")
        self.assertEqual(loc.country_code, "LU")
        self.assertEqual(loc.country_name, "Luxembourg")

        is_overseas, route_cat = check_route_feasibility("Mumbai", "Luxembourg")
        self.assertTrue(is_overseas)
        self.assertEqual(route_cat, "international")

        options = generate_commute_options("Luxembourg", "Mumbai")
        modes = [opt.mode.lower() for opt in options]
        # Ensure NO car, bus, or road trip from Mumbai to Luxembourg
        for m in modes:
            self.assertNotIn("car", m)
            self.assertNotIn("bus", m)
            self.assertNotIn("road trip", m)
        self.assertTrue(any("flight" in m for m in modes))

    def test_bengaluru_to_switzerland(self):
        """Tests that Bengaluru to Switzerland returns ONLY flights & destination rail, no car/bus."""
        is_overseas, route_cat = check_route_feasibility("Bengaluru", "Switzerland")
        self.assertTrue(is_overseas)
        self.assertEqual(route_cat, "international")

        options = generate_commute_options("Switzerland", "Bengaluru")
        self.assertGreater(len(options), 0)

        # Ensure NO car, road trip, bus or Indian train is present
        modes = [opt.mode.lower() for opt in options]
        for m in modes:
            self.assertNotIn("car", m)
            self.assertNotIn("bus", m)
            self.assertNotIn("road trip", m)

        # Ensure Flight is present
        self.assertTrue(any("flight" in m for m in modes))

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

    def test_domestic_island_route_andaman(self):
        """Tests domestic island route (Bengaluru to Andaman) requires flights/transfers, no cars or buses."""
        is_overseas, route_cat = check_route_feasibility("Bengaluru", "Andaman")
        self.assertTrue(is_overseas)
        self.assertEqual(route_cat, "island")

        options = generate_commute_options("Andaman", "Bengaluru")
        modes = [opt.mode.lower() for opt in options]
        for m in modes:
            self.assertNotIn("car", m)
            self.assertNotIn("bus", m)
            self.assertNotIn("train", m)
        self.assertTrue(any("flight" in m for m in modes))
        self.assertTrue(any("ferry" in m or "transfer" in m for m in modes))

    def test_international_island_route_maldives(self):
        """Tests international island routes return flights and ferry/speedboats, no cars or buses."""
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

    def test_ambiguous_destination_handling(self):
        """Tests unresolvable/ambiguous location is marked as unknown instead of silently guessing."""
        route = classify_route("Delhi", "FictionalCity999")
        self.assertEqual(route.route_category, "unknown")
        self.assertIsNone(route.is_overseas)


if __name__ == "__main__":
    unittest.main()
