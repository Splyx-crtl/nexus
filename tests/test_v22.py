"""v2.2.2: out-of-order play (mission 3 download bug), tutorial mission, performance guards."""
import unittest

import random

from tests.campaign_script import CHOICES, SCRIPT
from tests.driver import new_engine, run


def play_to(e, upto):
    for n in range(1, upto + 1):
        run(e, f"mission start {n}")
        for cmd in SCRIPT[n]:
            run(e, cmd)
            e.heat = min(e.heat, 20)


class OutOfOrderTest(unittest.TestCase):
    """Players do not follow the objective list in order; an early action must not be lost."""

    def _mission3(self, commands):
        e = new_engine()
        play_to(e, 2)
        run(e, "mission start 3")
        for cmd in commands:
            run(e, cmd)
        return e

    def test_download_before_read_still_completes(self):
        e = self._mission3(["connect blackvault", "scan", "firewall", "login svc_backup vault-7-Alpha", "cd /srv/db",
                            "download manifest.txt", "cat manifest.txt"])
        self.assertTrue(e.missions.is_complete("mission_003"))

    def test_download_with_full_path_from_root(self):
        e = self._mission3(["connect blackvault", "firewall", "login svc_backup vault-7-Alpha", "cat /srv/db/manifest.txt",
                            "scan", "download /srv/db/manifest.txt"])
        self.assertTrue(e.missions.is_complete("mission_003"))

    def test_normal_order_unchanged(self):
        e = self._mission3(SCRIPT[3])
        self.assertTrue(e.missions.is_complete("mission_003"))

    def test_one_action_counts_once(self):
        e = self._mission3(["connect blackvault", "scan", "firewall", "login svc_backup vault-7-Alpha", "cd /srv/db",
                            "cat manifest.txt"])
        self.assertFalse(e.missions.is_complete("mission_003"))        # the download is still missing
        done = e.missions.progress()["done"]
        self.assertIn("read", done)
        self.assertNotIn("dl", done)

    def test_hint_names_the_download(self):
        e = self._mission3(["connect blackvault", "scan", "firewall", "login svc_backup vault-7-Alpha", "cd /srv/db", "cat manifest.txt"])
        self.assertIn("download manifest.txt", e.missions.hint())


TUTORIAL = ["help", "connect echo", "scan", "ls", "cd training", "cat lesson.txt", "ls -a", "cat .keycard",
            "download field_notes.dat", "hint", "disconnect"]


class TutorialTest(unittest.TestCase):
    def test_tutorial_is_a_normal_mission_zero(self):
        e = new_engine()
        m = e.missions.by_number(0)
        self.assertEqual(m["id"], "mission_000")
        self.assertTrue(m["tutorial"])
        self.assertEqual(e.missions.status("mission_000"), "available")

    def test_tutorial_walkthrough_hands_over_to_mission_1(self):
        e = new_engine()
        out = run(e, "mission start 0")
        self.assertTrue(any("BOOT CAMP" in line for line in out))
        for cmd in TUTORIAL:
            self.assertTrue(e.missions.active(), f"tutorial ended early before {cmd!r}")
            self.assertEqual(e.missions.active()["id"], "mission_000")
            run(e, cmd)
        self.assertTrue(e.missions.is_complete("mission_000"))
        self.assertEqual(e.missions.active()["id"], "mission_001", "mission 1 must start right after the tutorial")
        self.assertTrue(e.db.get_flag("tutorial_done"))
        self.assertTrue(any("MISSION 001" in line for line in e.async_log), "briefing of mission 1 is printed")

    def test_tutorial_does_not_count_as_a_mission(self):
        e = new_engine()
        run(e, "mission start 0")
        for cmd in TUTORIAL:
            run(e, cmd)
        self.assertEqual(e.player.completed_missions, 0)
        self.assertEqual(int(e.db.get_stat("missions_completed")), 0)

    def test_training_files_only_exist_during_the_tutorial(self):
        e = new_engine()
        run(e, "connect echo")
        self.assertNotIn("training", " ".join(run(e, "ls")))
        run(e, "disconnect")
        run(e, "mission start 0")
        run(e, "connect echo")
        self.assertIn("training", " ".join(run(e, "ls")))

    def test_every_step_has_a_working_hint(self):
        e = new_engine()
        run(e, "mission start 0")
        for cmd in TUTORIAL[:-1]:
            self.assertTrue(e.missions.hint())
            run(e, cmd)

    def test_skipping_the_tutorial_is_possible(self):
        e = new_engine()
        run(e, "mission start 0")
        run(e, "mission abort")
        run(e, "mission start 1")
        self.assertEqual(e.missions.active()["id"], "mission_001")

    def test_steps_in_the_wrong_order_are_not_lost(self):
        e = new_engine()
        run(e, "mission start 0")
        for cmd in ["connect echo", "cd training", "download field_notes.dat", "cat .keycard", "cat lesson.txt",
                    "help", "scan", "ls", "hint", "disconnect"]:
            run(e, cmd)
        self.assertTrue(e.missions.is_complete("mission_000"))


class RealisticRunTest(unittest.TestCase):
    """Tutorial -> missions 1..6 the way a person plays: no heat cheating, time passing, mistakes in the mini-games and
    random world events firing in between. Every mission must still be completable."""

    FIREWALL_MISSIONS = (3, 6)

    def _play(self, seed):
        e = new_engine(seed=seed)
        e.set_flag("x", True)
        rng = random.Random(seed)
        e.events.rng = rng

        def step(cmd, **kw):
            run(e, cmd, **kw)
            e.tick(2.0)                                   # time passes: heat decays, mission clock runs
            if rng.random() < 0.5:
                e.events.fire_random()                    # world events: must never break a mission

        run(e, "mission start 0")
        for cmd in TUTORIAL:
            step(cmd)
        self.assertTrue(e.missions.is_complete("mission_000"), f"seed {seed}: tutorial")
        self.assertEqual(e.missions.active()["id"], "mission_001", f"seed {seed}: hand-over")
        for n in range(1, 7):
            if not e.missions.active():
                run(e, f"mission start {n}")
            self.assertEqual(e.missions.active()["number"], n)
            for cmd in SCRIPT[n]:
                if cmd == "firewall":
                    step(cmd, fail_minigames=True)        # a mistake first ...
                    e.heat = min(e.heat, 60)
                run_cmd = cmd
                step(run_cmd)
            if n in CHOICES:
                step(f"choose {CHOICES[n]}")
            self.assertTrue(e.missions.is_complete(f"mission_{n:03d}"),
                            f"seed {seed}: mission {n} incomplete: {e.missions.objectives_view(f'mission_{n:03d}')}")
        return e

    def test_complete_run_many_seeds(self):
        for seed in range(40):
            self._play(seed)

    def test_events_never_rearm_or_hide_what_the_mission_needs(self):
        e = new_engine(seed=3)
        play_to(e, 2)
        run(e, "mission start 3")
        run(e, "connect blackvault")
        run(e, "firewall")
        for _ in range(200):
            e.events.fire_random()
        self.assertTrue(e.world.is_breached("blackvault"), "firewall of the mission server was re-armed by an event")
        self.assertTrue(e.world.is_online("blackvault"))


if __name__ == "__main__":
    unittest.main()
