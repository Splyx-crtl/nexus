"""Unit tests for core systems: puzzles, saves, security, heat/failure, upgrades, events, achievements."""
import random
import tempfile
import unittest
from pathlib import Path

from tests.driver import new_engine, run

from nexus.config import rank_for_level
from nexus.data import get_data
from nexus.database import Database
from nexus.game_engine import GameEngine
from nexus.minigames import AccessPuzzle, EncryptionPuzzle, FirewallPuzzle, RoutingPuzzle, atbash, caesar, vigenere
from nexus.save_system import SaveSystem
from nexus.security import audit_package, looks_like_real_address, safe_filename, sanitize_name, validate_world

ROOT = Path(__file__).resolve().parent.parent


class PuzzleTests(unittest.TestCase):
    def test_firewall_feedback(self):
        p = FirewallPuzzle(6, 4, 6, random.Random(1))
        p.secret = [0, 1, 2, 3]
        self.assertEqual(p.guess([0, 1, 2, 3]), (4, 0))
        self.assertTrue(p.solved)
        p2 = FirewallPuzzle(6, 4, 2, random.Random(1))
        p2.secret = [0, 0, 1, 2]
        self.assertEqual(p2.guess([0, 1, 0, 5]), (1, 2))
        p2.guess([5, 5, 5, 5])
        self.assertTrue(p2.failed)

    def test_ciphers_roundtrip(self):
        text = "HELLO WORLD, 123"
        self.assertEqual(caesar(caesar(text, 7), -7), text)
        self.assertEqual(atbash(atbash(text)), text)
        self.assertEqual(vigenere(vigenere(text, "KEY"), "KEY", decrypt=True), text)
        for kind, key in (("caesar", 9), ("atbash", None), ("vigenere", "ORBIT")):
            puz = EncryptionPuzzle("THE SEED OF NEXUS", kind, key)
            self.assertNotEqual(puz.ciphertext, puz.plain)
            self.assertTrue(puz.check(key))

    def test_routing_always_solvable(self):
        for seed in range(60):
            for diff in (1, 2, 3):
                puz = RoutingPuzzle(seed, diff)
                self.assertTrue(puz.validate(puz.optimal_path)[0], f"seed {seed} diff {diff}")
                self.assertFalse(puz.validate([puz.start])[0])

    def test_access_generator(self):
        for seed in range(4):
            puz = AccessPuzzle.generate(random.Random(seed), 4)
            self.assertEqual(len(puz.code), 4)
            self.assertTrue(puz.clues)

    def test_static_ghost_puzzle_is_unique(self):
        d = range(10)
        found = [(a, b, c, e) for a in d for b in d for c in d for e in d
                 if a + b + c + e == 20 and e > a and e > b and e > c and c < a and c < b
                 and b == a + 4 and all(x % 2 for x in (a, b, c, e))]
        self.assertEqual(found, [(3, 7, 1, 9)])


class SecurityTests(unittest.TestCase):
    def test_real_addresses_are_refused(self):
        for bad in ("8.8.8.8", "192.168.1.1", "google.com", "https://example.org/x", "1.1.1.1:443"):
            self.assertTrue(looks_like_real_address(bad), bad)
        for good in ("10.42.0.7", "echo", "nexus_core"):
            self.assertFalse(looks_like_real_address(good), good)

    def test_world_data_is_sandboxed(self):
        self.assertEqual(validate_world(get_data().servers), [])

    def test_no_network_imports(self):
        self.assertEqual(audit_package(ROOT / "nexus", ROOT / "ui"), [])

    def test_names(self):
        self.assertEqual(sanitize_name("../../evil name!"), "evil_name")
        self.assertNotIn("/", safe_filename("../../x"))

    def test_terminal_refuses_real_hosts(self):
        e = new_engine()
        out = " ".join(run(e, "connect 8.8.8.8"))
        self.assertIn("OUTSIDE SIMULATION", out)
        self.assertIsNone(e.world.current)
        self.assertIn("OUTSIDE SIMULATION", " ".join(run(e, "ping google.com")))


class GameplayTests(unittest.TestCase):
    def test_new_game_state(self):
        e = new_engine("ALICE")
        self.assertEqual(e.player.level, 1)
        self.assertEqual(e.player.rank, "SCRIPT KIDDIE")
        self.assertEqual(e.world.discovered(), ["echo"])
        self.assertEqual(e.db.unread_count("mira"), 1)

    def test_rank_progression(self):
        for lvl, rank in ((1, "SCRIPT KIDDIE"), (4, "SCRIPT KIDDIE"), (5, "TECHNICIAN"), (10, "OPERATOR"),
                          (20, "SPECIALIST"), (30, "ELITE"), (50, "NEXUS")):
            self.assertEqual(rank_for_level(lvl), rank)
        e = new_engine()
        e.grant_xp(100000, announce=False)
        self.assertGreaterEqual(e.player.level, 20)
        self.assertEqual(e.player.rank, rank_for_level(e.player.level))

    def test_burn_fails_mission_and_disconnects(self):
        e = new_engine()
        run(e, "mission start 1")
        run(e, "connect echo")
        e.add_heat(500, scale=False)
        self.assertEqual(e.missions.status("mission_001"), "failed")
        self.assertIsNone(e.world.current)
        self.assertEqual(e.player.failed_missions, 1)
        run(e, "mission start 1")          # retry works
        self.assertIsNotNone(e.missions.active())

    def test_time_limit_fails_mission(self):
        e = new_engine()
        for i in range(1, 7):
            e.db.save_mission(f"mission_{i:03d}", "completed", {})
        run(e, "mission start 7")
        for _ in range(500):
            e.missions.tick(1.0)
        self.assertEqual(e.missions.status("mission_007"), "failed")

    def test_bad_password_raises_heat(self):
        e = new_engine()
        for i in range(1, 3):
            e.db.save_mission(f"mission_{i:03d}", "completed", {})
        run(e, "mission start 3")
        run(e, "connect blackvault")
        run(e, "firewall")
        before = e.heat
        out = run(e, "login svc_backup", answers=["wrong"])
        self.assertTrue(any("ACCESS DENIED" in line for line in out))
        self.assertGreater(e.heat, before)
        out = run(e, "login svc_backup", answers=["vault-7-Alpha"])
        self.assertTrue(any("ACCESS GRANTED" in line for line in out))

    def test_firewall_failure_and_bypass_chip(self):
        e = new_engine()
        e.world.discover("blackvault")
        run(e, "connect blackvault")
        out = run(e, "firewall", fail_minigames=True)
        self.assertTrue(any("HELD" in line for line in out))
        self.assertFalse(e.world.is_breached("blackvault"))
        e.grant_item("firewall_bypass_chip")
        run(e, "use firewall_bypass_chip")
        self.assertTrue(e.world.is_breached("blackvault"))
        self.assertEqual(e.player.qty("firewall_bypass_chip"), 0)

    def test_upgrades_and_shop(self):
        e = new_engine()
        e.grant_credits(5000, announce=False)
        run(e, "upgrade 1")
        self.assertEqual(e.player.upgrade_level("terminal_speed"), 1)
        self.assertLess(e.player.anim_factor, 1.0)
        self.assertTrue(any("shop" in line.lower() or "market" in line.lower() for line in run(e, "shop")))
        e.set_flag("shop_open", True)
        run(e, "buy access_token")
        self.assertEqual(e.player.qty("access_token"), 1)
        e.player.add_item("encryption_key")
        self.assertEqual(e.player.add_item("encryption_key"), 0)      # max_qty 1

    def test_access_token_unlocks_login(self):
        e = new_engine()
        e.world.discover("blackvault")
        e.grant_item("access_token")
        run(e, "connect blackvault")
        run(e, "use access_token")        # firewall still active -> refused
        self.assertEqual(e.player.qty("access_token"), 1)
        e.world.set_breached("blackvault")
        run(e, "use access_token")
        self.assertEqual(e.world.role(), 1)
        self.assertEqual(e.player.qty("access_token"), 0)

    def test_contacts_dialogue_and_trust(self):
        e = new_engine()
        out = run(e, "msg mira 2")
        self.assertTrue(any("handler" in line.lower() for line in out))
        self.assertGreater(e.trust("mira"), 40)
        self.assertTrue(any("No open channel" in line for line in run(e, "msg ghost")))

    def test_decode_utility(self):
        e = new_engine()
        out = " ".join(run(e, "decode dmF1bHQtNy1BbHBoYQ=="))
        self.assertIn("vault-7-Alpha", out)

    def test_easter_eggs_and_unknown_command(self):
        e = new_engine()
        run(e, "sudo rm")
        run(e, "42")
        run(e, "hack the planet")
        self.assertGreaterEqual(e.db.get_stat("easter_eggs"), 3)
        self.assertIn("command not found", " ".join(run(e, "frobnicate")))

    def test_events_fire(self):
        e = new_engine()
        e.db.save_mission("mission_002", "completed", {})
        e.db.save_mission("mission_003", "completed", {})
        e.world.discover("blackvault")
        e.world.discover("nexus_grid")
        e.world.set_breached("blackvault")
        for ev in e.data.events:
            e.events.fire(ev["id"])
        self.assertGreater(e.db.get_stat("events_seen"), 5)

    def test_achievements_unlock(self):
        e = new_engine()
        run(e, "connect echo")
        self.assertIn("first_connection", e.db.get_achievements())
        self.assertGreaterEqual(len(e.data.achievements), 20)

    def test_tab_completion(self):
        e = new_engine()
        run(e, "connect echo")
        self.assertIn("cat", e.commands.complete("ca"))
        self.assertIn("readme.txt", e.commands.complete("cat re"))
        self.assertIn("echo", e.commands.complete("connect e"))


class SaveTests(unittest.TestCase):
    def test_save_slots_roundtrip(self):
        tmp = Path(tempfile.mkdtemp())
        saves = SaveSystem(tmp / "p", tmp / "s")
        db = saves.create_profile("SLOTTER")
        db.update_profile(credits=1234, level=7)
        slot = saves.save_slot(db, 2)
        db.update_profile(credits=1)
        db.close()
        self.assertEqual(len(saves.list_profiles()), 1)
        self.assertEqual(saves.list_slots()[0].slot, 2)
        restored = saves.load_slot(slot)
        self.assertEqual(restored.get_profile()["credits"], 1234)
        self.assertEqual(restored.get_profile()["level"], 7)
        restored.close()

    def test_state_survives_reload(self):
        e = new_engine("PERSIST")
        run(e, "mission start 1")
        run(e, "connect echo")
        e.grant_item("data_fragment")
        e.save()
        path = e.db.path
        e.db.close()
        e2 = GameEngine(Database(path))
        self.assertEqual(e2.world.current, "echo")
        self.assertEqual(e2.player.qty("data_fragment"), 1)
        self.assertEqual(e2.missions.active()["id"], "mission_001")


if __name__ == "__main__":
    unittest.main()
