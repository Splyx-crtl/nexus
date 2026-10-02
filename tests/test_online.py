"""Online service tests: runs the real server (dev login) on localhost and drives it with the game's client."""
import importlib.util
import os
import socket
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

HAVE_SERVER_DEPS = all(importlib.util.find_spec(m) for m in ("fastapi", "uvicorn", "httpx"))


class FakeSettings:
    def __init__(self, **values):
        self.values = {"online_enabled": True, "online_token": "", **values}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        self.values[key] = value


class ValidationTests(unittest.TestCase):
    def test_validation_rules(self):
        from server.validation import Rejected, cumulative_xp, validate
        ok = {"level": 5, "xp_total": cumulative_xp(5) + 10, "missions": 4, "credits_earned": 5000, "perfect": 2, "playtime": 600, "ng_plus": 0, "rank": "TECHNICIAN"}
        self.assertEqual(validate(ok, None, None)["level"], 5)
        bad_cases = [
            {**ok, "level": 101}, {**ok, "level": 0}, {**ok, "xp_total": 1}, {**ok, "perfect": 99}, {**ok, "missions": -1}, {"level": "x"},
        ]
        for bad in bad_cases:
            with self.assertRaises(Rejected, msg=str(bad)):
                validate(bad, None, None)
        with self.assertRaises(Rejected):                       # going backwards
            validate({**ok, "missions": 2}, {**ok, "xp_total": ok["xp_total"]}, 60)
        with self.assertRaises(Rejected):                       # too fast
            validate(ok, dict(ok), 3)
        with self.assertRaises(Rejected):                       # implausible XP jump
            validate({**ok, "xp_total": ok["xp_total"] + 10_000_000, "level": 5}, dict(ok), 60)


@unittest.skipUnless(HAVE_SERVER_DEPS, "server dependencies (fastapi, uvicorn, httpx) not installed")
class OnlineIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import uvicorn
        os.environ["NEXUS_DB"] = str(Path(tempfile.mkdtemp()) / "online.db")
        os.environ["NEXUS_DEV_LOGIN"] = "1"
        import server.app as srv
        importlib.reload(srv)
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        cls.port = s.getsockname()[1]
        s.close()
        cls.server = uvicorn.Server(uvicorn.Config(srv.app, host="127.0.0.1", port=cls.port, log_level="error"))
        cls.thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.thread.start()
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{cls.port}/health", timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        cls.url = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.should_exit = True
        cls.thread.join(5)

    def login(self, name):
        from nexus.online import OnlineClient
        settings = FakeSettings()
        client = OnlineClient(settings, self.url)
        state, url = client.new_login(dev_name=name)
        urllib.request.urlopen(url, timeout=5).read()               # the "browser" completes the login
        self.assertTrue(client.poll_login(state))
        self.assertFalse(client.poll_login(state))                  # the token is handed out only once
        self.assertTrue(settings.values["online_token"])
        return client

    @staticmethod
    def score(level, missions, credits):
        from server.validation import cumulative_xp
        return {"level": level, "xp_total": cumulative_xp(level) + 50, "missions": missions, "credits_earned": credits, "perfect": 1,
                "playtime": 600, "ng_plus": 0, "rank": "OPERATOR"}

    def test_full_flow(self):
        from nexus.online import OnlineError
        alice, bob = self.login("Alice"), self.login("Bob")
        self.assertEqual(alice.me()["name"], "Alice")
        alice.submit_scores(self.score(5, 4, 5000))
        bob.submit_scores(self.score(9, 8, 9000))
        with self.assertRaises(OnlineError):                         # second submission inside the rate window
            alice.submit_scores(self.score(6, 5, 6000))
        board = alice.leaderboard("level")
        self.assertEqual([e["name"] for e in board["entries"][:2]], ["Bob", "Alice"])
        self.assertEqual(board["me"]["position"], 2)
        self.assertEqual(alice.leaderboard("missions")["entries"][0]["value"], 8)
        self.assertIn("weekly_xp", alice.leaderboard("weekly")["entries"][0] | {"weekly_xp": 0})
        with self.assertRaises(OnlineError) as cm:
            bob.submit_scores({**self.score(100, 1, 1), "xp_total": 5})
        self.assertIn("XP", str(cm.exception))

        # friends + presence
        self.assertEqual(alice.friend_request("bob")["status"], "pending")
        with self.assertRaises(OnlineError):
            alice.friend_request("bob")
        with self.assertRaises(OnlineError):
            alice.friend_request("nobody-here")
        self.assertEqual(bob.friends()["incoming"][0]["name"], "Alice")
        bob.friend_respond("Alice", True)
        bob.presence("Mission 007 · LOCKDOWN")
        friend = alice.friends()["friends"][0]
        self.assertEqual((friend["name"], friend["online"], friend["status"], friend["level"]), ("Bob", True, "Mission 007 · LOCKDOWN", 9))

        # privacy: hidden from leaderboards and presence
        bob.set_share(False)
        self.assertNotIn("Bob", [e["name"] for e in alice.leaderboard("level")["entries"]])
        self.assertFalse(alice.friends()["friends"][0]["online"])

        # deletion removes everything
        bob.delete_account()
        self.assertEqual(alice.friends()["friends"], [])
        self.assertEqual(bob.settings.values["online_token"], "")
        alice.logout()
        self.assertEqual(alice.settings.values["online_token"], "")

    def test_auth_required_and_safety_rules(self):
        from nexus.online import OnlineClient, OnlineError
        anon = OnlineClient(FakeSettings(), self.url)
        with self.assertRaises(OnlineError):
            anon.me()
        stale = FakeSettings(online_token="not-a-real-token")
        with self.assertRaises(OnlineError):
            OnlineClient(stale, self.url).me()
        self.assertEqual(stale.values["online_token"], "")           # dead token is cleared
        with self.assertRaises(OnlineError):
            OnlineClient(FakeSettings(online_token="x"), "http://evil.example.com").me()   # plain HTTP to a remote host is refused
        self.assertFalse(OnlineClient(FakeSettings(), "").configured)
        with self.assertRaises(OnlineError):
            OnlineClient(FakeSettings(), "").me()

    def test_game_snapshot_contains_only_numbers(self):
        from nexus.online import presence_text, snapshot
        from tests.driver import new_engine
        e = new_engine("PRIVATE_NAME")
        snap = snapshot(e)
        self.assertEqual(set(snap), {"level", "xp_total", "missions", "credits_earned", "perfect", "playtime", "ng_plus", "rank", "details"})
        self.assertEqual(set(snap["details"]), {"credits", "reputation", "heat", "achievements", "unlocks", "stats"})
        self.assertNotIn("PRIVATE_NAME", str(snap))
        self.assertIn("menus", presence_text(e))


if __name__ == "__main__":
    unittest.main()
