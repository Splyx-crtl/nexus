"""C5 endings logic (nexus/campaign/endings.py)."""
import unittest

from nexus.campaign.endings import ENDINGS, missing_secret_ending_requirements, reachable_endings


class ReachableEndings(unittest.TestCase):
    def test_mains_always_reachable_with_no_clues(self):
        endings = reachable_endings(found_clues=set())
        self.assertEqual({e.id for e in endings}, {"A", "B", "C"})

    def test_secret_ending_needs_all_three_clues_and_the_side_mission(self):
        self.assertEqual({e.id for e in reachable_endings({2, 5}, True)}, {"A", "B", "C"})
        self.assertEqual({e.id for e in reachable_endings({2, 5, 8}, False)}, {"A", "B", "C"})
        self.assertEqual({e.id for e in reachable_endings({2, 5, 8}, True)}, {"A", "B", "C", "D"})

    def test_extra_clues_beyond_the_required_set_do_not_hurt(self):
        endings = reachable_endings({1, 2, 3, 4, 5, 6, 7, 8}, True)
        self.assertIn("D", {e.id for e in endings})

    def test_four_endings_defined_one_secret(self):
        self.assertEqual(set(ENDINGS), {"A", "B", "C", "D"})
        self.assertTrue(ENDINGS["D"].secret)
        self.assertFalse(any(ENDINGS[k].secret for k in ("A", "B", "C")))


class MissingRequirements(unittest.TestCase):
    def test_lists_missing_clues_and_side_mission(self):
        missing = missing_secret_ending_requirements({2}, False)
        self.assertIn("clue 5", missing)
        self.assertIn("clue 8", missing)
        self.assertIn("the second test-operator side-mission", missing)

    def test_empty_when_everything_is_met(self):
        self.assertEqual(missing_secret_ending_requirements({2, 5, 8}, True), [])


if __name__ == "__main__":
    unittest.main()
