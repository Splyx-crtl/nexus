"""F1 "daily challenge with seed" (nexus/campaign/daily.py): a deterministic, same-for-everyone endless op keyed
by calendar date. Pure logic here; tests/ui_campaign_window.py exercises the actual CampaignWindow button."""
import unittest
from datetime import date

from nexus.campaign.daily import daily_mission_id, daily_seed
from nexus.campaign.endless import generate_endless_mission
from nexus.campaign.solver import solve
from nexus.campaign.validator import validate_mission


class DailySeedTests(unittest.TestCase):
    def test_same_date_same_seed(self):
        d = date(2026, 10, 5)
        self.assertEqual(daily_seed(d), daily_seed(d))

    def test_different_dates_different_seeds(self):
        self.assertNotEqual(daily_seed(date(2026, 10, 5)), daily_seed(date(2026, 10, 6)))

    def test_mission_id_includes_the_date(self):
        self.assertEqual(daily_mission_id(date(2026, 10, 5)), "daily_2026-10-05")

    def test_today_defaults_without_a_date_argument(self):
        # just confirms it doesn't blow up and produces a deterministic value for "right now"
        self.assertEqual(daily_seed(), daily_seed())

    def test_the_generated_daily_mission_is_itself_solvable(self):
        d = date(2026, 10, 5)
        m = generate_endless_mission(daily_mission_id(d), 200, 9, daily_seed(d))
        self.assertEqual(validate_mission(m), [])
        r = solve(m)
        self.assertTrue(r.ok, f"daily mission for {d} failed: {r.missing} {r.error}")


if __name__ == "__main__":
    unittest.main()
