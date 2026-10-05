"""German translation, Act I (nexus/campaign/translations/de_act1.py) — every registered mission must still
validate and solve identically once localized (localize() only ever touches display text, never event/match/
solution, so this also proves the translation didn't accidentally change objective counts or break a hint tier)."""
import unittest

from nexus.campaign import translations  # noqa: F401 (registers the translations on import)
from nexus.campaign.content.act1 import ACT1_CHAPTER2, ACT1_HAND_WRITTEN
from nexus.campaign.i18n import TRANSLATIONS, localize
from nexus.campaign.solver import solve
from nexus.campaign.validator import validate_mission

TRANSLATED_MISSIONS = [*ACT1_HAND_WRITTEN, *ACT1_CHAPTER2]
TRANSLATED_IDS = {"act1_m01", "act1_m02", "act1_m03", "act1_m04", "act1_m05", "act1_m06", "act1_m07", "act1_m08",
                  "act1_m09", "act1_m10", "act1_m15", "act1_m16", "act1_m17", "act1_m18", "act1_m19", "act1_m20"}
TITLE_KEPT_IN_ENGLISH = {"act1_m05"}      # "RTFM" — an internet-culture acronym, kept as-is on purpose


class DeAct1(unittest.TestCase):
    def test_every_hand_written_act1_mission_has_a_german_translation(self):
        self.assertEqual({m.id for m in TRANSLATED_MISSIONS}, TRANSLATED_IDS)
        for mid in TRANSLATED_IDS:
            self.assertIn("de", TRANSLATIONS.get(mid, {}), f"{mid} has no German entry")

    def test_localized_missions_still_validate_and_solve(self):
        for m in TRANSLATED_MISSIONS:
            de = localize(m, "de")
            with self.subTest(mission=m.id):
                self.assertEqual(validate_mission(de), [])
                r = solve(de)
                self.assertTrue(r.ok, f"{m.id} (de) failed: {r.missing} {r.error}")

    def test_translation_does_not_change_objective_count(self):
        for m in TRANSLATED_MISSIONS:
            de = localize(m, "de")
            self.assertEqual(len(de.objectives), len(m.objectives), m.id)

    def test_translation_changes_the_displayed_text(self):
        for m in TRANSLATED_MISSIONS:
            de = localize(m, "de")
            with self.subTest(mission=m.id):
                if m.id not in TITLE_KEPT_IN_ENGLISH:
                    self.assertNotEqual(de.title, m.title)
                self.assertNotEqual(de.briefing, m.briefing)
                self.assertNotEqual(de.debrief, m.debrief)
                for eo, go in zip(m.objectives, de.objectives):
                    self.assertNotEqual(go.text, eo.text)

    def test_translation_never_touches_the_solution(self):
        for m in TRANSLATED_MISSIONS:
            de = localize(m, "de")
            self.assertEqual(de.solution, m.solution, m.id)

    def test_translation_never_touches_matching_data(self):
        for m in TRANSLATED_MISSIONS:
            de = localize(m, "de")
            for eo, go in zip(m.objectives, de.objectives):
                self.assertEqual(go.event, eo.event)
                self.assertEqual(go.match, eo.match)


if __name__ == "__main__":
    unittest.main()
