"""2.4.0: weekly community challenge, Discord winner announcement, friends bar data, music library."""
import importlib
import importlib.util
import os
import socket
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

from tests import test_online as _online

HAVE_SERVER_DEPS = _online.HAVE_SERVER_DEPS


@unittest.skipUnless(HAVE_SERVER_DEPS, "server dependencies (fastapi, uvicorn, httpx) not installed")
class WeeklyChallenge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import uvicorn
        os.environ["NEXUS_DB"] = str(Path(tempfile.mkdtemp()) / "weekly.db")
        os.environ["NEXUS_DEV_LOGIN"] = "1"
        os.environ.pop("DISCORD_GUILD_ID", None)
        import server.app as srv
        importlib.reload(srv)
        cls.srv = srv
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

    login = _online.OnlineIntegration.login
    score = staticmethod(_online.OnlineIntegration.score)

    def test_the_challenge_rotates_by_week(self):
        srv = self.srv
        seen = {srv.challenge_for(f"2026-W{w:02d}")[0] for w in range(1, 9)}
        self.assertEqual(seen, {"xp", "missions", "credits", "perfect"})
        self.assertEqual(srv.challenge_for("2026-W10"), srv.challenge_for("2026-W10"))

    def test_progress_counts_from_the_start_of_the_week(self):
        carol = self.login("Carol")
        dave = self.login("Dave")
        srv = self.srv
        metric = srv.challenge_for(srv.week_key())[0]
        carol.submit_scores(self.score(5, 4, 5000))
        dave.submit_scores(self.score(5, 4, 5000))
        first = carol.challenge()
        self.assertEqual(first["metric"], metric)
        self.assertEqual(first["me"]["value"], 0)                   # the first submission is the baseline
        # Dave plays more: patch his stored current numbers like a later submission would
        with srv.db() as conn:
            uid = conn.execute("SELECT id FROM users WHERE name='Dave'").fetchone()["id"]
            conn.execute("UPDATE week_results SET xp=xp+700, missions=missions+3, credits=credits+900, perfect=perfect+2 "
                         "WHERE user_id=? AND week=?", (uid, srv.week_key()))
        board = carol.challenge()
        self.assertEqual(board["entries"][0]["name"], "Dave")
        self.assertGreater(board["entries"][0]["value"], 0)
        self.assertEqual(board["me"]["position"], 2)
        self.assertEqual(board["community_total"], board["entries"][0]["value"])
        self.assertGreater(board["ends_in"], 0)
        self.assertLessEqual(board["ends_in"], 7 * 86400)

    def test_hidden_players_are_not_listed(self):
        erin = self.login("Erin")
        erin.submit_scores(self.score(5, 4, 5000))
        erin.set_share(False)
        self.assertNotIn("Erin", [e["name"] for e in erin.challenge()["entries"]])

    def test_winner_is_announced_once_to_discord(self):
        srv = self.srv
        sent = []
        original = (srv.send_webhook, srv.DISCORD_WEBHOOK_URL)
        srv.send_webhook, srv.DISCORD_WEBHOOK_URL = sent.append, "https://example.invalid/hook"
        try:
            frank = self.login("Frank")
            frank.submit_scores(self.score(5, 4, 5000))             # makes sure the user exists
            week = srv.previous_week()
            metric = srv.challenge_for(week)[0]
            with srv.db() as conn:
                uid = conn.execute("SELECT id FROM users WHERE name='Frank'").fetchone()["id"]
                conn.execute("DELETE FROM announcements")
                conn.execute("INSERT OR REPLACE INTO week_results VALUES(?,?,0,0,0,0,500,5,5000,3)", (week, uid))
            frank.challenge()
            frank.challenge()
            self.assertEqual(len(sent), 1)
            self.assertIn("Frank", sent[0])
            self.assertIn(week, sent[0])
            self.assertNotIn("@", sent[0])
            self.assertIn(metric, sent[0])
        finally:
            srv.send_webhook, srv.DISCORD_WEBHOOK_URL = original

    def test_no_announcement_without_webhook(self):
        srv = self.srv
        sent = []
        original = srv.send_webhook
        srv.send_webhook = sent.append
        try:
            self.assertEqual(srv.DISCORD_WEBHOOK_URL, "")
            self.login("Gina").challenge()
            self.assertEqual(sent, [])
        finally:
            srv.send_webhook = original


class MusicLibrary(unittest.TestCase):
    TRACKS = ("menu", "terminal", "tension")

    def test_every_track_exists_and_is_a_clean_loop(self):
        import struct
        import wave
        from nexus.audio import MUSIC
        from nexus.config import MUSIC_DIR
        self.assertEqual(set(MUSIC), set(self.TRACKS))
        for name in self.TRACKS:
            with wave.open(str(MUSIC_DIR / f"{name}.wav")) as wf:
                self.assertEqual((wf.getnchannels(), wf.getsampwidth()), (1, 2))
                frames = wf.getnframes()
                data = struct.unpack(f"<{frames}h", wf.readframes(frames))
            self.assertGreater(frames / wf.getframerate(), 20, name)                 # long enough not to feel repetitive
            self.assertLess(abs(data[0] - data[-1]) / 32768, 0.05, f"{name}: audible click at the loop point")
            peak = max(abs(v) for v in data) / 32768
            self.assertTrue(0.3 < peak < 0.999, f"{name}: peak {peak}")             # not silent, not clipping
            rms = (sum(v * v for v in data[::50]) / len(data[::50])) ** 0.5 / 32768
            self.assertGreater(rms, 0.05, f"{name}: too quiet")

    def test_the_manager_is_safe_without_audio(self):
        from nexus.audio import SoundManager
        os.environ["NEXUS_NO_AUDIO"] = "1"
        sm = SoundManager(_online.FakeSettings(volume_master=80, volume_music=70, volume_sfx=80, typing_sound=True))
        sm.set_music("tension")
        sm.play("levelup")
        sm.apply_volumes()
        sm.stop_ambient()

    def test_new_effects_are_synthesised(self):
        from nexus.audio import _build_sounds
        built = _build_sounds()
        for name in ("levelup", "purchase", "friend"):
            self.assertGreater(len(built[name]), 1000, name)
        self.assertNotIn("ambient", built)

    def test_the_music_ships_with_the_game(self):
        text = (Path(__file__).resolve().parent.parent / "build_exe.bat").read_text(encoding="utf-8", errors="ignore")
        self.assertIn('--add-data "assets;assets"', text)


if __name__ == "__main__":
    unittest.main()
