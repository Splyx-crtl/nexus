"""Plays every one of the 52 missions headlessly: 16 story missions + 36 generated side/secret missions."""
import json
import unittest
from pathlib import Path

from tests.campaign_script import CHOICES, SCRIPT
from tests.driver import new_engine, run

ROOT = Path(__file__).resolve().parent


def play_main(e, upto=16):
    for n in range(1, upto + 1):
        run(e, f"mission start {n}")
        assert e.missions.active(), f"mission {n} did not start"
        for cmd in SCRIPT[n]:
            run(e, cmd)
            e.heat = min(e.heat, 20)
        if n in CHOICES:
            run(e, f"choose {CHOICES[n]}")
        assert e.missions.is_complete(f"mission_{n:03d}"), f"story mission {n} incomplete"


class AllMissionsTest(unittest.TestCase):
    def test_all_52_missions(self):
        scripts = json.loads((ROOT / "side_scripts.json").read_text(encoding="utf-8"))
        e = new_engine("PLAYER")
        play_main(e)
        e.player._set(level=100)                       # level gates are tested separately
        e.player.add_reputation(100)
        for item in ("ghost_token", "black_key", "quantum_decryptor", "nexus_core"):
            e.player.add_item(item)
        e.grant_credits(1000, announce=False)
        done = 16
        for mid in sorted(scripts):
            script = scripts[mid]
            number = int(mid.split("_")[1])
            self.assertEqual(e.missions.lock_reason(e.missions.by_id[mid]), "", f"{mid} locked: {e.missions.lock_reason(e.missions.by_id[mid])}")
            out = run(e, f"mission start {number}")
            self.assertTrue(e.missions.active(), f"{mid} did not start: {out[-3:]}")
            for cmd in script["commands"]:
                run(e, cmd)
                e.heat = 0
                e.missions.sync_states()
            if script["choice"]:
                self.assertTrue(e.missions.progress().get("awaiting_choice"), f"{mid} not awaiting choice: {e.missions.objectives_view(mid)}")
                run(e, "choose 1")
            self.assertTrue(e.missions.is_complete(mid), f"{mid} incomplete: {e.missions.objectives_view(mid)}")
            for path in list(e.local.files()):
                if path.startswith("downloads/"):
                    e.db.delete_local_file(path)          # players clean up their storage between jobs
            done += 1
        self.assertEqual(done, 52)
        self.assertEqual(sum(1 for m in e.data.missions if e.missions.is_complete(m["id"])), 52)
        self.assertTrue(e.db.get_flag("specter_done") and e.db.get_flag("void_done"))
        for n in range(1, 7):
            self.assertTrue(e.db.get_flag(f"chapter_{n}_done"), f"chapter {n} flag")


if __name__ == "__main__":
    unittest.main()
