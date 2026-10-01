"""Tests for v2.1: contracts, difficulty, New Game+, credits/about."""
import random
import unittest

from nexus import version
from nexus.contracts import tier_for_level
from nexus.database import Database
from nexus.game_engine import GameEngine
from tests.campaign_script import CHOICES, SCRIPT
from tests.driver import new_engine, run
from tests.test_missions_all import play_main


def prepared(level=30):
    e = new_engine("TOTO")
    for n in (1, 2, 3):
        run(e, f"mission start {n}")
        for cmd in SCRIPT[n]:
            run(e, cmd)
    e.player._set(level=level, reputation=50)
    return e


class ContractTests(unittest.TestCase):
    def test_locked_before_mission_3(self):
        e = new_engine()
        self.assertIn("unlock", " ".join(run(e, "contract")))

    def test_endless_contracts_all_types_and_tiers(self):
        for level in (5, 15, 30, 55, 80):
            e = prepared(level)
            seen = set()
            for seed in range(8):
                ok, msg = e.contracts.generate(random.Random(seed * 7 + level))
                self.assertTrue(ok, msg)
                run(e, "contract start")
                self.assertEqual(e.missions.active()["id"], e.contracts.mission_id())
                for cmd in e.contracts.script():
                    run(e, cmd)
                    e.heat = 0
                    e.missions.sync_states()
                self.assertTrue(e.missions.is_complete(e.contracts.mission_id()), e.contracts.spec())
                seen.add(e.contracts.spec()["type"])
                for path in list(e.local.files()):
                    e.db.delete_local_file(path)
            self.assertGreaterEqual(len(seen), 3)
            self.assertEqual(int(e.db.get_stat("contracts_done")), 8)

    def test_tier_scales_with_level_and_reward(self):
        self.assertEqual([tier_for_level(l) for l in (1, 10, 25, 45, 70)], [1, 2, 3, 4, 5])
        low, high = prepared(5), prepared(80)
        low.contracts.generate(random.Random(1))
        high.contracts.generate(random.Random(1))
        self.assertGreater(high.missions.by_id[high.contracts.mission_id()]["reward"]["xp"],
                           low.missions.by_id[low.contracts.mission_id()]["reward"]["xp"])

    def test_contract_survives_reload_and_is_hidden_from_mission_list(self):
        e = prepared()
        e.contracts.generate(random.Random(3))
        mid = e.contracts.mission_id()
        e.save()
        path = e.db.path
        e.db.close()
        e2 = GameEngine(Database(path))
        self.assertEqual(e2.contracts.mission_id(), mid)
        self.assertIn(mid, e2.missions.by_id)
        self.assertNotIn("CONTRACT", " ".join(run(e2, "missions")))
        self.assertTrue(all(not m.get("contract") for m in e2.missions.available()))
        run(e2, "contract start")
        self.assertEqual(e2.missions.active()["id"], mid)
        self.assertFalse(e2.contracts.generate()[0])                    # cannot reroll while active


class DifficultyAndNewGamePlus(unittest.TestCase):
    def test_difficulty_changes_heat_and_rewards(self):
        e = new_engine()
        e.set_difficulty("easy")
        e.heat = 0
        e.add_heat(10)
        easy_heat = e.heat
        e.set_difficulty("hard")
        e.heat = 0
        e.add_heat(10)
        self.assertGreater(e.heat, easy_heat)
        self.assertLess(e.DIFFICULTY["easy"]["reward"], e.DIFFICULTY["hard"]["reward"])
        self.assertIn("HARD", " ".join(run(e, "difficulty hard")))
        self.assertIn("usage", " ".join(run(e, "difficulty banana")))

    def test_new_game_plus_keeps_progress_and_resets_story(self):
        e = new_engine("NG")
        self.assertIn("Finish the campaign", " ".join(run(e, "newgameplus")))
        play_main(e)
        e.grant_item("heat_sink", 1, announce=False)
        e.player._set(level=40, credits=12345)
        self.assertTrue(e.db.get_flag("campaign_complete"))
        self.assertIn("Cancelled", " ".join(run(e, "newgameplus", answers=["no"])))
        out = " ".join(run(e, "newgameplus", answers=["YES"]))
        self.assertIn("NEW GAME+ 1", out)
        self.assertEqual(e.ng_plus, 1)
        self.assertGreater(e.reward_mult, 1.0)
        self.assertEqual(e.player.level, 40)
        self.assertEqual(e.player.credits, 12345)
        self.assertGreaterEqual(e.player.qty("heat_sink"), 1)
        self.assertFalse(e.missions.is_complete("mission_001"))
        self.assertEqual(e.missions.status("mission_001"), "available")
        self.assertEqual(e.world.discovered(), ["echo"])
        self.assertTrue(len(e.db.get_achievements()) > 5)
        self.assertIn("loop", e.db.get_world("endings", []))            # endings stay discovered
        run(e, "mission start 1")
        for cmd in SCRIPT[1]:
            run(e, cmd)
        self.assertTrue(e.missions.is_complete("mission_001"))


class CreditsAndLinks(unittest.TestCase):
    def test_author_and_links(self):
        self.assertEqual(version.AUTHOR, "Toto")
        self.assertTrue(hasattr(version, "DISCORD_URL"))
        self.assertTrue(version.VERSION.startswith("2."))
        self.assertIn("Toto", " ".join(run(new_engine(), "about")))

    def test_contrast_theme_and_tips_defaults(self):
        from nexus.config import DEFAULT_SETTINGS
        from nexus.data import get_data
        themes = {t["id"]: t for t in get_data().themes}
        self.assertTrue(themes["contrast"].get("free"))
        self.assertEqual(DEFAULT_SETTINGS["seen_tips"], [])


if __name__ == "__main__":
    unittest.main()
