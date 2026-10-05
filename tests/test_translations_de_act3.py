"""German translation, Act III (nexus/campaign/translations/de_act3.py) — every registered mission must still
validate and solve identically once localized (localize() only ever touches display text, never event/match/
solution, so this also proves the translation didn't accidentally change objective counts or break a hint tier)."""
import unittest

from nexus.campaign import translations  # noqa: F401 (registers the translations on import)
from nexus.campaign.content.act3 import ACT3
from nexus.campaign.i18n import TRANSLATIONS, localize
from nexus.campaign.solver import solve
from nexus.campaign.validator import validate_mission

TRANSLATED_MISSIONS = ACT3
TRANSLATED_IDS = {f"act3_m{n}" for n in range(46, 71)}


class DeAct3(unittest.TestCase):
    def test_every_act3_mission_has_a_german_translation(self):
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
