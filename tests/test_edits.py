"""Administrator edits, end to end: key -> account -> game save -> server -> admin edit -> player's game -> save on disk.

The first class checks how the game applies an edit to a save; the second runs a real server and drives the whole path with the
game's own online client (what the ONLINE page does, minus the widgets)."""
import json
import os
import socket
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from tests.driver import new_engine
from tests.test_keys import ADMIN, HAVE_SERVER_DEPS, load_server
from tests.test_online import FakeSettings


class EngineAppliesEdits(unittest.TestCase):
    def setUp(self):
        self.e = new_engine("EDITED")

    def test_level_xp_credits_reputation(self):
        e = self.e
        lines = e.apply_admin_edits({"level": 12, "xp": 30, "credits": 4321, "reputation": 66})
        self.assertEqual((e.player.level, e.player.xp, e.player.credits, e.player.reputation), (12, 30, 4321, 66))
        self.assertEqual(len(lines), 3)                                                # level+XP, credits, reputation
        from nexus.config import xp_for_level
        self.assertEqual(int(e.db.get_stat("xp_earned")), sum(xp_for_level(l) for l in range(1, 12)) + 30)    # same total the server computes
        from server.validation import cumulative_xp
        self.assertEqual(int(e.db.get_stat("xp_earned")), cumulative_xp(12) + 30)

    def test_values_are_clamped_to_what_the_game_allows(self):
        e = self.e
        e.apply_admin_edits({"level": 999, "xp": 10**9, "credits": -50, "reputation": 500})
        self.assertEqual((e.player.level, e.player.credits, e.player.reputation), (100, 0, 100))
        self.assertLess(e.player.xp, e.player.xp_needed)

    def test_changes_are_in_the_save_file_after_a_restart(self):
        e = self.e
        e.apply_admin_edits({"level": 8, "xp": 5, "credits": 999})
        path = e.db.path
        e.db.close()
        from nexus.database import Database
        again = Database(path)
        profile = again.get_profile()
        self.assertEqual((profile["level"], profile["xp"], profile["credits"]), (8, 5, 999))
        self.assertGreater(again.get_stat("xp_earned"), 0)
        again.close()

    def test_the_player_is_told(self):
        e = self.e
        seen = []
        e.toast.connect(lambda kind, title, text: seen.append((title, text)))
        e.apply_admin_edits({"credits": 10})
        self.assertEqual(seen[0][0], "ADMIN ADJUSTMENT")
        self.assertIn("Credits", seen[0][1])
        self.assertTrue(any("ADMIN" in n["title"] for n in e.db.get_notifications(5)))

    def test_resets(self):
        e = self.e
        e.db.save_mission("m_done", "completed", {})
        e.player.count_mission(True)
        e.db.add_stat("perfect_missions", 3)
        e.db.set_item("kit", 2)
        e.db.set_upgrade("firewall", 2)
        e.heat = 55.0
        e.apply_admin_edits({"reset": ["missions"]})
        self.assertEqual((e.player.completed_missions, e.db.get_stat("perfect_missions"), e.db.mission_status("m_done")), (0, 0, None))
        self.assertEqual(e.db.item_qty("kit"), 2)                                       # only what was asked for is reset
        e.apply_admin_edits({"reset": ["inventory", "heat"]})
        self.assertEqual((e.db.item_qty("kit"), e.db.get_upgrade("firewall"), e.heat), (0, 0, 0.0))
        self.assertEqual(e.db.get_world("heat"), 0.0)

    def test_a_reset_mission_can_be_played_again(self):
        e = self.e
        first = e.missions.available()[0]
        e.db.save_mission(first["id"], "completed", {})
        e.apply_admin_edits({"reset": ["missions"]})
        self.assertIn(first["id"], [m["id"] for m in e.missions.available()])


@unittest.skipUnless(HAVE_SERVER_DEPS, "server dependencies (fastapi, uvicorn, httpx) not installed")
class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import uvicorn
        cls.dir = tempfile.mkdtemp()
        cls.db = Path(cls.dir) / "online.db"
        cls.srv = load_server(cls.db)
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        cls.port = s.getsockname()[1]
        s.close()
        cls.server = uvicorn.Server(uvicorn.Config(cls.srv.app, host="127.0.0.1", port=cls.port, log_level="error"))
        cls.thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.port}"
        for _ in range(100):
            try:
                urllib.request.urlopen(cls.url + "/health", timeout=1)
                break
            except OSError:
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.should_exit = True
        cls.thread.join(5)

    def admin(self, method, path, payload=None):
        request = urllib.request.Request(self.url + path, data=json.dumps(payload).encode() if payload is not None else None, method=method,
                                         headers={**ADMIN, "Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(request, timeout=5).read())

    def make_client(self):
        from nexus.online import OnlineClient
        return OnlineClient(FakeSettings(), self.url)

    def login(self, client, key, name):
        state, url = client.new_login(dev_name=name)
        client.begin_login(state, key)                                  # the key is checked BEFORE the browser step
        urllib.request.urlopen(url, timeout=5).read()
        self.assertTrue(client.poll_login(state))

    def refused_login(self, client, key, name) -> str:
        """A login the server turns down: returns the reason the player is shown."""
        from nexus.online import OnlineError
        state, url = client.new_login(dev_name=name)
        client.begin_login(state, key)
        try:
            urllib.request.urlopen(url, timeout=5).read()
        except urllib.error.HTTPError as exc:                          # the "browser" page says no
            exc.close()
        with self.assertRaises(OnlineError) as cm:
            client.poll_login(state)
        return str(cm.exception)

    def test_the_whole_path(self):
        from nexus.online import OnlineError, snapshot
        # 1. no key, no account
        client = self.make_client()
        with self.assertRaises(OnlineError) as cm:
            client.begin_login("a" * 32, "")
        self.assertEqual(cm.exception.status, 403)
        with self.assertRaises(OnlineError):
            client.begin_login("b" * 32, "NX-AAAAA-BBBBB-CCCCC")
        self.assertEqual(sqlite3.connect(self.db).execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)

        # 2. valid key -> registration -> account
        key = self.admin("POST", "/admin/keys", {"label": "e2e", "count": 1})["keys"][0]["key"]
        self.login(client, key, "Eddie")
        self.assertEqual(client.me()["name"], "Eddie")
        self.assertIn("already been used", self.refused_login(self.make_client(), key, "Imposter"))      # the key is now taken

        # 3. game -> save numbers -> server
        engine = new_engine("EDDIE")
        engine.player.add_xp(500)
        engine.player.add_credits(2500)
        engine.db.add_stat("xp_earned", 500)
        engine.db.add_stat("credits_earned", 2500)
        self.assertEqual(client.submit_scores(snapshot(engine))["edits"], [])
        players = self.admin("GET", "/admin/players?search=eddie")["players"]
        self.assertEqual(len(players), 1)
        pid = players[0]["id"]
        self.assertEqual((players[0]["level"], players[0]["credits"]), (engine.player.level, engine.player.credits))
        detail = self.admin("GET", f"/admin/players/{pid}")
        self.assertEqual(detail["name"], "Eddie")
        self.assertEqual(detail["key"]["label"], "e2e")

        # 4. admin edits -> the game's next sync receives it, applies it to the save, confirms
        self.admin("POST", f"/admin/players/{pid}/edit", {"level": 9, "xp": 12, "credits": 777, "reason": "e2e"})
        con = sqlite3.connect(self.db)
        con.execute("UPDATE scores SET updated_at = updated_at - 100")
        con.commit()
        con.close()
        answer = client.submit_scores(snapshot(engine))                   # the game still has its old numbers
        self.assertTrue(answer["ignored"])
        for edit in answer["edits"]:
            engine.apply_admin_edits(edit["ops"])
            client.ack_edit(edit["id"])
        self.assertEqual((engine.player.level, engine.player.xp, engine.player.credits), (9, 12, 777))

        # 5. the new numbers are accepted and match what the admin sees
        con = sqlite3.connect(self.db)
        con.execute("UPDATE scores SET updated_at = updated_at - 100")
        con.commit()
        con.close()
        self.assertEqual(client.submit_scores(snapshot(engine))["edits"], [])
        detail = self.admin("GET", f"/admin/players/{pid}")
        self.assertEqual((detail["level"], detail["credits"], detail["pending_edits"]), (9, 777, []))

        # 6. persistence: the save on disk and the server database after a restart
        path = engine.db.path
        engine.db.close()
        from nexus.database import Database
        reopened = Database(path).get_profile()
        self.assertEqual((reopened["level"], reopened["credits"]), (9, 777))
        from fastapi.testclient import TestClient
        restarted = TestClient(load_server(self.db).app)
        again = restarted.get(f"/admin/players/{pid}", headers=ADMIN).json()
        self.assertEqual((again["level"], again["credits"], again["audit"][0]["action"]), (9, 777, "player.edit"))

        # 7. deactivating the account stops the running game and the next login
        self.admin("POST", f"/admin/players/{pid}/status", {"status": "disabled", "reason": "e2e done"})
        with self.assertRaises(OnlineError) as cm:
            client.me()
        self.assertIn("deactivated", str(cm.exception))
        self.assertIn("deactivated", self.refused_login(self.make_client(), key, "Eddie"))
        self.admin("POST", f"/admin/players/{pid}/status", {"status": "active"})
        self.login(self.make_client(), key, "Eddie")


if __name__ == "__main__":
    unittest.main()
