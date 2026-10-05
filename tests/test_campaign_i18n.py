"""Mission-content translation overlay (nexus/campaign/i18n.py)."""
import unittest

from nexus.campaign.i18n import TRANSLATIONS, localize, register
from nexus.campaign.mission import Mission, Objective


def _m() -> Mission:
    return Mission(
        id="t_m1", number=1, act=1, size="mini", title="First Light", scenario="x",
        briefing=["NEXUS: Hello."], debrief=["NEXUS: Done."],
        objectives=[
            Objective(event="command", match={"name": "ls"}, text="List the folder", hints=["a", "b", "c"]),
            Objective(event="command", match={"name": "cat"}, text="Read the file", hints=["x"]),
        ],
        solution=["ls", "cat welcome.txt"],
    )


class Localize(unittest.TestCase):
    def setUp(self):
        # TRANSLATIONS is a shared, process-global registry (real translation blocks like translations/de_act1.py
        # register into it once, at import time) — save and restore it instead of clearing it outright, so this
        # test doesn't wipe out real translations for any test that runs later in the same process.
        self._saved = dict(TRANSLATIONS)
        TRANSLATIONS.clear()

    def tearDown(self):
        TRANSLATIONS.clear()
        TRANSLATIONS.update(self._saved)

    def test_english_is_always_the_identity(self):
        m = _m()
        self.assertIs(localize(m, "en"), m)

    def test_no_registration_falls_back_to_english_untouched(self):
        m = _m()
        out = localize(m, "de")
        self.assertEqual(out.title, m.title)
        self.assertEqual(out.briefing, m.briefing)

    def test_full_translation_overrides_everything_registered(self):
        register("t_m1", "de", title="Erstes Licht", briefing=["NEXUS: Hallo."], debrief=["NEXUS: Fertig."],
                 objectives=[{"text": "Ordner auflisten", "hints": ["a-de", "b-de", "c-de"]},
                            {"text": "Datei lesen", "hints": ["x-de"]}])
        out = localize(_m(), "de")
        self.assertEqual(out.title, "Erstes Licht")
        self.assertEqual(out.briefing, ["NEXUS: Hallo."])
        self.assertEqual(out.debrief, ["NEXUS: Fertig."])
        self.assertEqual(out.objectives[0].text, "Ordner auflisten")
        self.assertEqual(out.objectives[0].hints, ["a-de", "b-de", "c-de"])
        self.assertEqual(out.objectives[1].text, "Datei lesen")

    def test_partial_objective_translation_falls_back_per_entry(self):
        register("t_m1", "de", title="Erstes Licht", objectives=[{"text": "Ordner auflisten"}, None])
        out = localize(_m(), "de")
        self.assertEqual(out.title, "Erstes Licht")
        self.assertEqual(out.objectives[0].text, "Ordner auflisten")
        self.assertEqual(out.objectives[0].hints, ["a", "b", "c"])          # hints omitted -> English hints kept
        self.assertEqual(out.objectives[1].text, "Read the file")           # entry is None -> fully English

    def test_fewer_translated_objectives_than_real_ones_is_safe(self):
        register("t_m1", "de", objectives=[{"text": "Ordner auflisten"}])
        out = localize(_m(), "de")
        self.assertEqual(out.objectives[0].text, "Ordner auflisten")
        self.assertEqual(out.objectives[1].text, "Read the file")

    def test_solution_is_never_translated(self):
        register("t_m1", "de", title="Erstes Licht")
        out = localize(_m(), "de")
        self.assertEqual(out.solution, ["ls", "cat welcome.txt"])

    def test_missing_mission_id_falls_back_to_english(self):
        register("some_other_mission", "de", title="Anders")
        out = localize(_m(), "de")
        self.assertEqual(out.title, "First Light")

    def test_localize_does_not_mutate_the_original(self):
        register("t_m1", "de", title="Erstes Licht")
        original = _m()
        localize(original, "de")
        self.assertEqual(original.title, "First Light")


if __name__ == "__main__":
    unittest.main()
