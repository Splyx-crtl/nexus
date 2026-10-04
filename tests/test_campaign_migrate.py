"""A3 (nexus/campaign/migrate.py): archive a 2.x save, start fresh under v3 — no migration of 2.x progress."""
import tempfile
import unittest
from pathlib import Path

from nexus.campaign.migrate import ensure_v3_profile, has_pending_2x_profile
from nexus.campaign.profile import CampaignProfile
from nexus.save_system import SaveSystem


class Migrate(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.saves = SaveSystem(profiles_dir=root / "profiles", slots_dir=root / "slots")
        self.archive_dir = root / "archive_2x"

    def tearDown(self):
        self._tmp.cleanup()

    def test_fresh_install_just_creates_a_v3_profile(self):
        self.assertFalse(has_pending_2x_profile(self.saves))
        db = ensure_v3_profile(self.saves, "newoperator", archive_dir=self.archive_dir)
        self.assertTrue(CampaignProfile.is_v3(db))
        self.assertEqual(db.get_profile()["username"], "newoperator")
        db.close()
        self.assertFalse(self.archive_dir.exists())

    def test_a_2x_profile_gets_archived_and_a_fresh_v3_one_created(self):
        old = self.saves.create_profile("legacyop")
        old.update_profile(level=47, xp=500)
        old_path = old.path
        old.close()

        self.assertTrue(has_pending_2x_profile(self.saves))
        db = ensure_v3_profile(self.saves, "legacyop", archive_dir=self.archive_dir)

        self.assertTrue(CampaignProfile.is_v3(db))
        self.assertEqual(db.get_profile()["level"], 1)           # fresh v3 progress, not migrated
        # a new v3 profile reuses the original filename once the 2.x file has been moved out, so check content,
        # not just path existence: the archived copy still holds the old (level 47) data, untouched.
        archived = list(self.archive_dir.glob("*.db"))
        self.assertEqual(len(archived), 1)
        archived_db = self.saves.open_profile(archived[0])
        self.assertEqual(archived_db.get_profile()["level"], 47)
        self.assertFalse(CampaignProfile.is_v3(archived_db))
        archived_db.close()
        db.close()

    def test_an_existing_v3_profile_is_returned_untouched(self):
        db = ensure_v3_profile(self.saves, "op", archive_dir=self.archive_dir)
        profile = CampaignProfile(db)
        from nexus.campaign.mission import Mission, Objective
        m = Mission(id="m1", number=1, act=1, size="mini", title="t", scenario="x",
                   objectives=[Objective(event="command", match={"name": "ls"})])
        profile.complete_mission(m, [m])
        db.close()

        self.assertFalse(has_pending_2x_profile(self.saves))
        db2 = ensure_v3_profile(self.saves, "ignored-username", archive_dir=self.archive_dir)
        self.assertEqual(db2.get_profile()["username"], "op")
        self.assertEqual(db2.get_profile()["completed_missions"], 1)
        db2.close()
        self.assertFalse(self.archive_dir.exists())

    def test_save_list_shows_the_v3_rank_table_for_a_v3_profile(self):
        """SaveSystem.list_profiles()/_read_info() must not label a v3 profile with a 2.x rank name (the two rank
        tables diverge at the same level numbers, e.g. level 50 is "NEXUS" in 2.x but "NETRUNNER" in v3)."""
        db = ensure_v3_profile(self.saves, "op", archive_dir=self.archive_dir)
        db.update_profile(level=50)
        db.close()
        info = self.saves.latest_profile()
        self.assertEqual(info.rank, "NETRUNNER")

    def test_archiving_does_not_clobber_an_existing_archive_with_the_same_name(self):
        self.archive_dir.mkdir(parents=True)
        old1 = self.saves.create_profile("dup")
        name = old1.path.name
        old1.close()
        (self.archive_dir / name).write_bytes(b"already archived once")

        db = ensure_v3_profile(self.saves, "dup", archive_dir=self.archive_dir)
        db.close()
        archived = sorted(p.name for p in self.archive_dir.glob("*"))
        self.assertEqual(len(archived), 2)


if __name__ == "__main__":
    unittest.main()
