"""A2 (nexus/campaign/profile.py): the v3 save adapter built on the existing generic SQLite tables."""
import tempfile
import unittest
from pathlib import Path

from nexus.campaign.mission import Mission, Objective
from nexus.campaign.profile import CampaignProfile
from nexus.campaign.progression import MAX_LEVEL
from nexus.database import Database


def _m(id_, number, requires=(), tags=(), reward_xp=50) -> Mission:
    return Mission(id=id_, number=number, act=1, size="mini", title=id_, scenario="x",
                   objectives=[Objective(event="command", match={"name": "ls"})],
                   requires=list(requires), tags=list(tags), reward_xp=reward_xp)


class ProfileBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self._tmp.name) / "p.db")
        self.profile = CampaignProfile.init_v3(self.db, "operator")
        self.missions = [
            _m("m1", 1, tags=["clue:2"]),
            _m("m2", 2, requires=["m1"]),
            _m("m3", 3, requires=["m2"], tags=["clue:5"]),
            _m("m4", 4, requires=["m3"], tags=["secret-ending-track"]),
            _m("m5", 5, requires=["m4"], tags=["clue:8"]),
        ]

    def tearDown(self):
        self.db.close()
        self._tmp.cleanup()


class Identity(ProfileBase):
    def test_init_v3_sets_the_flag(self):
        self.assertTrue(CampaignProfile.is_v3(self.db))

    def test_fresh_profile_is_not_v3(self):
        db2 = Database(Path(self._tmp.name) / "p2.db")
        db2.create_profile("someone")
        self.assertFalse(CampaignProfile.is_v3(db2))
        db2.close()

    def test_initial_level_is_one(self):
        self.assertEqual(self.profile.level, 1)
        self.assertEqual(self.profile.xp, 0)


class Progress(ProfileBase):
    def test_next_mission_is_the_first_one_initially(self):
        self.assertEqual(self.profile.next_mission(self.missions).id, "m1")

    def test_next_mission_respects_requires(self):
        self.profile.complete_mission(self.missions[0], self.missions)
        self.assertEqual(self.profile.next_mission(self.missions).id, "m2")

    def test_completing_advances_level_to_next_mission_number(self):
        self.profile.complete_mission(self.missions[0], self.missions)
        self.assertEqual(self.profile.level, 2)

    def test_level_reaches_max_once_campaign_is_done(self):
        for m in self.missions:
            self.profile.complete_mission(m, self.missions)
        self.assertIsNone(self.profile.next_mission(self.missions))
        self.assertEqual(self.profile.level, MAX_LEVEL)
        self.assertTrue(self.profile.is_campaign_complete(self.missions))

    def test_xp_accumulates(self):
        self.profile.complete_mission(self.missions[0], self.missions)
        self.profile.complete_mission(self.missions[1], self.missions)
        self.assertEqual(self.profile.xp, 100)

    def test_completing_twice_is_a_no_op(self):
        self.profile.complete_mission(self.missions[0], self.missions)
        self.profile.complete_mission(self.missions[0], self.missions)
        self.assertEqual(self.profile.xp, 50)
        self.assertEqual(self.profile.completed_count, 1)

    def test_is_unlocked_checks_requires_regardless_of_order(self):
        self.assertTrue(self.profile.is_unlocked(self.missions[0]))
        self.assertFalse(self.profile.is_unlocked(self.missions[1]))
        self.profile.complete_mission(self.missions[0], self.missions)
        self.assertTrue(self.profile.is_unlocked(self.missions[1]))


class CluesAndEndings(ProfileBase):
    def test_found_clues_only_counts_completed_missions(self):
        self.assertEqual(self.profile.found_clues(self.missions), set())
        self.profile.complete_mission(self.missions[0], self.missions)
        self.assertEqual(self.profile.found_clues(self.missions), {2})

    def test_secret_ending_needs_the_track_mission_completed(self):
        self.assertFalse(self.profile.secret_ending_unlocked(self.missions))
        for m in self.missions[:4]:
            self.profile.complete_mission(m, self.missions)
        self.assertTrue(self.profile.secret_ending_unlocked(self.missions))

    def test_reachable_endings_gates_the_secret_one(self):
        ids = {e.id for e in self.profile.reachable_endings(self.missions)}
        self.assertEqual(ids, {"A", "B", "C"})
        for m in self.missions:
            self.profile.complete_mission(m, self.missions)
        ids = {e.id for e in self.profile.reachable_endings(self.missions)}
        self.assertEqual(ids, {"A", "B", "C", "D"})

    def test_set_and_read_ending(self):
        self.profile.set_ending("C")
        self.assertEqual(self.db.get_profile()["ending"], "C")


class DecisionsModeCharacter(ProfileBase):
    def test_record_and_read_a_decision(self):
        self.assertIsNone(self.profile.get_decision("decision:1"))
        self.profile.record_decision("decision:1", "helped Reyes", mission_id="act2_m35")
        self.assertEqual(self.profile.get_decision("decision:1"), "helped Reyes")

    def test_mode_defaults_to_guided(self):
        self.assertEqual(self.profile.get_mode(), "guided")
        self.profile.set_mode("hardcore")
        self.assertEqual(self.profile.get_mode(), "hardcore")

    def test_character_round_trips(self):
        self.assertEqual(self.profile.get_character(), {"name": "", "look": ""})
        self.profile.set_character("Kestrel", "short dark hair, old jacket")
        self.assertEqual(self.profile.get_character(), {"name": "Kestrel", "look": "short dark hair, old jacket"})


if __name__ == "__main__":
    unittest.main()
