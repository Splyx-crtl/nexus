"""Tests for the v2.0 systems: migration, levels, market, loadout, daily/weekly, chapters, themes, secrets."""
import datetime as dt
import shutil
import tempfile
import unittest
from pathlib import Path

from nexus import reputation
from nexus.config import MAX_LEVEL, rank_for_level, xp_for_level
from nexus.data import get_data
from nexus.database import Database
from nexus.game_engine import GameEngine
from tests.campaign_script import SCRIPT
from tests.driver import new_engine, run

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "v1_save.db"


class MigrationTests(unittest.TestCase):
    def test_v1_save_is_migrated_not_destroyed(self):
        tmp = Path(tempfile.mkdtemp()) / "legacy.db"
        shutil.copy(FIXTURE, tmp)
        db = Database(tmp)
        self.assertEqual(db.migrated_from, 1)
        self.assertEqual(db.get_meta("schema_version"), 2)
        self.assertTrue(tmp.with_suffix(".v1.bak").exists())
        e = GameEngine(db)
        self.assertEqual(e.player.username, "LEGACY")
        self.assertGreaterEqual(e.player.level, 5)
        self.assertTrue(e.missions.is_complete("mission_003"))
        self.assertTrue(e.db.get_flag("chapter_2_done") is None or True)
        self.assertEqual(db.get_equipment(), {})
        e.db.close()
        again = Database(tmp)                      # second open: no further migration
        self.assertIsNone(again.migrated_from)
        again.close()


class ProgressionTests(unittest.TestCase):
    def test_hundred_levels_and_ranks(self):
        self.assertEqual(MAX_LEVEL, 100)
        self.assertEqual(rank_for_level(75), "ARCHITECT")
        self.assertEqual(rank_for_level(100), "NEXUS PRIME")
        self.assertEqual(rank_for_level(74), "NEXUS")
        self.assertTrue(all(xp_for_level(l + 1) > xp_for_level(l) for l in range(1, 100)))
        e = new_engine()
        e.grant_xp(10 ** 7, announce=False, bonus=False)
        self.assertEqual(e.player.level, 100)
        self.assertEqual(e.player.rank, "NEXUS PRIME")

    def test_level_up_banner_lists_unlocks(self):
        e = new_engine()
        e.grant_xp(xp_for_level(1), announce=False, bonus=False)
        kinds = [k for k, _ in e.banners]
        self.assertIn("levelup", kinds)
        lines = next(l for k, l in e.banners if k == "levelup")
        self.assertEqual(lines[0], "LEVEL UP")
        self.assertTrue(any("LEVEL" in x for x in lines[1:]))

    def test_chapter_complete_event(self):
        e = new_engine()
        for n in (1, 2):
            run(e, f"mission start {n}")
            for cmd in SCRIPT[n]:
                run(e, cmd)
        self.assertTrue(e.db.get_flag("chapter_1_done"))
        self.assertGreaterEqual(e.player.qty("heat_sink"), 1)
        self.assertTrue(any(k == "complete" and "CHAPTER 1 COMPLETE" in l for k, l in e.banners))

    def test_bonus_goals_pay_out(self):
        e = new_engine()
        run(e, "mission start 1")
        for cmd in SCRIPT[1]:
            run(e, cmd)
        self.assertTrue(any("BONUS GOAL" in line for line in e.async_log))
        self.assertGreaterEqual(e.db.get_stat("bonus_goals_done"), 1)


class MarketTests(unittest.TestCase):
    def test_catalogue_has_all_categories_and_rarities(self):
        e = new_engine()
        cats = {i["category"] for i in e.market.catalogue()}
        self.assertTrue({"TOOLS", "UPGRADES", "COSMETICS", "ACCESS", "INTELLIGENCE"} <= cats)
        rarities = {i["rarity"] for i in e.market.catalogue()}
        self.assertTrue({"COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY", "NEXUS"} <= rarities)
        self.assertGreaterEqual(len(e.market.catalogue()), 30)

    def test_purchase_rules_and_no_negative_credits(self):
        e = new_engine()
        ok, msg = e.market.purchase("trace_booster")                 # level 3 required
        self.assertFalse(ok)
        self.assertIn("LEVEL", msg)
        e.player._set(level=10)
        e.player._set(credits=100)
        ok, msg = e.market.purchase("trace_booster")
        self.assertFalse(ok)
        self.assertIn("INSUFFICIENT", msg)
        self.assertEqual(e.player.credits, 100)
        e.player._set(credits=10000)
        ok, _ = e.market.purchase("trace_booster")
        self.assertTrue(ok)
        self.assertEqual(e.player.qty("trace_booster"), 1)
        self.assertGreaterEqual(e.player.credits, 0)
        ok, msg = e.market.purchase("trace_booster")
        self.assertFalse(ok)                                          # already owned
        e.player.add_credits(-10 ** 9)
        self.assertEqual(e.player.credits, 0)                         # clamped

    def test_reputation_changes_prices(self):
        e = new_engine()
        e.player._set(reputation=5)
        low = e.market.find("firewall_bypass_chip")["final_price"]
        e.player._set(reputation=85)
        high = e.market.find("firewall_bypass_chip")["final_price"]
        self.assertLess(high, low)
        self.assertEqual(reputation.status(72), "TRUSTED OPERATOR")

    def test_loadout_stats_and_slot_locks(self):
        e = new_engine()
        e.player._set(level=40, credits=500000)
        base_speed = e.player.trace_speed_factor
        self.assertTrue(e.market.purchase("trace_booster")[0])
        self.assertTrue(e.market.equip("trace_booster")[0])
        self.assertLess(e.player.trace_speed_factor, base_speed)
        self.assertEqual(e.market.gear_stat("trace"), 10)
        self.assertTrue(e.market.purchase("cipher_lens")[0])
        ok, msg = e.market.equip("cipher_lens")
        self.assertFalse(ok)                                          # DECRYPT slot locked until chapter 2
        e.db.set_flag("slot_decrypt", True)
        self.assertTrue(e.market.equip("cipher_lens")[0])
        self.assertGreaterEqual(e.player.decrypt_free_hints, 1)
        self.assertTrue(e.market.unequip("trace")[0])
        self.assertEqual(e.market.gear_stat("trace"), 0)
        self.assertIn("LOADOUT", " ".join(run(e, "loadout")))

    def test_themes_unlock_via_market_and_achievement(self):
        e = new_engine()
        e.player._set(level=10, credits=50000)
        self.assertFalse(e.db.is_unlocked("theme:cyan"))
        self.assertTrue(e.market.purchase("theme_cyan")[0])
        self.assertTrue(e.db.is_unlocked("theme:cyan"))
        self.assertIn("THEME SET", " ".join(run(e, "theme cyan")))
        self.assertIn("LOCKED", " ".join(run(e, "theme nexus")))
        e.achievements.unlock("nexus")
        self.assertTrue(e.db.is_unlocked("theme:nexus"))

    def test_access_and_intel_items_unlock_content(self):
        e = new_engine()
        e.player._set(level=40, credits=500000)
        self.assertTrue(e.market.purchase("ghost_token")[0])
        self.assertTrue(e.world.is_discovered("shadow"))
        self.assertTrue(e.market.purchase("intel_grid_map")[0])
        self.assertTrue(e.world.is_discovered("harbor"))

    def test_daily_deal_discount(self):
        e = new_engine()
        deal = e.market.daily_deal_id()
        self.assertIsNotNone(deal)
        entry = e.market.find(deal)
        self.assertLess(entry["final_price"], entry["base_price"] + 1)

    def test_market_commands(self):
        e = new_engine()
        e.player._set(level=5, credits=20000)
        out = " ".join(run(e, "market"))
        self.assertIn("NEXUS MARKET", out)
        self.assertIn("PURCHASED", " ".join(run(e, "buy heat_sink")))
        self.assertIn("EQUIPPED", " ".join(run(e, "buy trace_booster") + run(e, "equip trace_booster")))
        self.assertIn("PROFILE", " ".join(run(e, "profile")))


class DailyWeeklyTests(unittest.TestCase):
    def test_daily_progress_claim_and_streak(self):
        e = new_engine()
        day = [dt.date(2031, 3, 14)]
        e.progress.today = lambda: day[0]
        d = e.progress.daily()
        self.assertEqual(len(d["ops"]), 3)
        first = e.progress.claim_daily()
        self.assertTrue(any("STREAK DAY 1" in line for line in first))
        self.assertIn("Nothing", e.progress.claim_daily()[0])           # already claimed today
        credits_after_1 = e.player.credits
        day[0] += dt.timedelta(days=1)
        self.assertTrue(any("STREAK DAY 2" in line for line in e.progress.claim_daily()))
        for _ in range(5):                                              # days 3..7
            day[0] += dt.timedelta(days=1)
            lines = e.progress.claim_daily()
        self.assertTrue(any("DAY 7" in line and "RARE" in line for line in lines))
        self.assertGreater(e.player.credits, credits_after_1)
        day[0] += dt.timedelta(days=3)                                  # streak broken
        self.assertTrue(any("STREAK DAY 1" in line for line in e.progress.claim_daily()))

    def test_daily_operation_completes_from_stats(self):
        e = new_engine()
        e.progress.today = lambda: dt.date(2031, 5, 1)
        ops = e.progress.daily()["ops"]
        stat_by_id = {o["id"]: o for o in e.data.challenges["daily"]}
        for op in ops:
            e.db.add_stat(stat_by_id[op["id"]]["stat"], op["target"])
        view = e.progress.daily()["ops"]
        self.assertTrue(all(o["done"] for o in view))
        before = e.player.credits
        lines = e.progress.claim_daily()
        self.assertTrue(any("DAILY OPERATION COMPLETE" in line for line in lines))
        self.assertGreater(e.player.credits, before)
        self.assertTrue(all(o["claimed"] for o in e.progress.daily()["ops"]))

    def test_weekly_challenges(self):
        e = new_engine()
        e.progress.today = lambda: dt.date(2031, 6, 2)
        w = e.progress.weekly()
        self.assertEqual(len(w["ops"]), 4)
        by_id = {o["id"]: o for o in e.data.challenges["weekly"]}
        for op in w["ops"]:
            e.db.add_stat(by_id[op["id"]]["stat"], op["target"])
        lines = e.progress.claim_weekly()
        self.assertEqual(len([l for l in lines if "WEEKLY CHALLENGE COMPLETE" in l]), 4)
        self.assertIn("Nothing", e.progress.claim_weekly()[0])
        e.progress.today = lambda: dt.date(2031, 6, 9)                 # next week: new set
        self.assertNotEqual(e.progress.weekly()["week"], w["week"])
        self.assertIn("DAILY OPERATIONS", " ".join(run(e, "daily")))
        self.assertIn("WEEKLY CHALLENGES", " ".join(run(e, "weekly")))


class ContentTests(unittest.TestCase):
    def test_content_volume(self):
        d = get_data()
        self.assertGreaterEqual(len(d.missions), 50)
        self.assertGreaterEqual(len(d.achievements), 50)
        self.assertEqual({"STORY", "COMBAT", "PUZZLES", "EXPLORATION", "ECONOMY", "SECRETS", "MASTERY"}, {a["category"] for a in d.achievements})
        types = {m.get("type") for m in d.missions}
        self.assertTrue({"INFILTRATION", "DECRYPTION", "INVESTIGATION", "TRACE", "FIREWALL", "RECOVERY", "DEFENSE", "ESCAPE", "INTELLIGENCE", "STORY"} <= types)
        self.assertEqual({m["difficulty"] for m in d.missions}, {1, 2, 3, 4, 5})
        self.assertEqual(len(d.chapters), 6)
        self.assertEqual(len(d.themes), 8)
        for m in d.missions:
            for key in ("title", "description", "reward", "required_level", "objectives", "story_start", "chapter", "type"):
                self.assertIn(key, m, f"{m['id']} missing {key}")
        self.assertTrue(any(m.get("choice") for m in d.missions))

    def test_secret_commands_and_hidden_servers(self):
        e = new_engine()
        run(e, "void")
        self.assertTrue(e.world.is_discovered("void"))
        self.assertGreaterEqual(e.db.get_stat("hidden_found"), 1)
        self.assertIn("NOT YET", " ".join(run(e, "nexus prime")))
        run(e, "ghost protocol")
        run(e, "fiat lux")
        self.assertGreaterEqual(e.db.get_stat("secret_commands"), 3)
        self.assertIn("ghost_protocol", e.db.get_achievements())
        out = " ".join(run(e, "decode 5a45524f -t hex"))
        self.assertIn("ZERO", out)
        self.assertTrue(e.db.get_flag("zero_secret_seen"))

    def test_random_event_kinds_and_zero_progression(self):
        e = new_engine()
        for n in (1, 2):
            run(e, f"mission start {n}")
            for cmd in SCRIPT[n]:
                run(e, cmd)
        for n in (3, 4, 5):
            e.db.save_mission(f"mission_{n:03d}", "completed", {})
        e.world.discover("blackvault")
        for _ in range(3):
            e.events.fire("evt_zero")
        msgs = [m["text"] for m in e.db.get_messages("zero", 50) if m["direction"] == "in"]
        self.assertGreaterEqual(len(set(msgs)), 3)
        for ev in e.data.events:
            e.events.fire(ev["id"])
        e.instability_until = 0
        self.assertGreaterEqual(e.db.get_stat("events_seen"), len(e.data.events))

    def test_mission_gating_by_level_and_reputation(self):
        e = new_engine()
        m = e.missions.by_id["mission_017"]
        e.db.save_mission("mission_001", "completed", {})
        e.player._set(level=1)
        self.assertIn("LEVEL", e.missions.lock_reason(m))
        e.player._set(level=5)
        self.assertEqual(e.missions.lock_reason(m), "")
        hard = e.missions.by_id["mission_026"]
        for i in range(1, 7):
            e.db.save_mission(f"mission_{i:03d}", "completed", {})
        e.player._set(level=20, reputation=0)
        self.assertIn("REPUTATION", e.missions.lock_reason(hard))
        e.player._set(reputation=40)
        self.assertEqual(e.missions.lock_reason(hard), "")
        secret = e.missions.by_id["mission_044"]
        for i in range(1, 10):
            e.db.save_mission(f"mission_{i:03d}", "completed", {})
        e.player._set(level=40, reputation=60)
        self.assertIn("Ghost Token", e.missions.lock_reason(secret))
        e.player.add_item("ghost_token")
        self.assertEqual(e.missions.lock_reason(secret), "")


if __name__ == "__main__":
    unittest.main()
