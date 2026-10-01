"""Plays all 16 missions headlessly and checks the world logic end to end."""
import unittest

from tests.driver import new_engine, run
from tests.campaign_script import CHOICES, SCRIPT


class CampaignTest(unittest.TestCase):
    def test_full_campaign(self):
        e = new_engine()
        for n in range(1, 17):
            out = run(e, f"mission start {n}")
            self.assertTrue(e.missions.active(), f"mission {n} did not start: {out}")
            for cmd in SCRIPT[n]:
                run(e, cmd)
                e.heat = min(e.heat, 20)   # keep the test about logic, not trace pressure
            if n in CHOICES:
                self.assertTrue(e.missions.progress().get("awaiting_choice"), f"mission {n} not awaiting choice; "
                                f"view={e.missions.objectives_view(e.missions.active()['id'])}")
                run(e, f"choose {CHOICES[n]}")
            self.assertTrue(e.missions.is_complete(f"mission_{n:03d}"),
                            f"mission {n} incomplete: {e.missions.objectives_view(f'mission_{n:03d}')} log={e.async_log[-6:]}")
        self.assertEqual(e.player.ending, "loop")


if __name__ == "__main__":
    unittest.main()
