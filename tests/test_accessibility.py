"""D3 accessibility: reduced motion, showcase mode and the colorblind-safe/mono themes. Pure logic only - the
actual widget wiring (ScanlineOverlay, MainMenu, CampaignWindow) is exercised in tests/ui_flow.py and
tests/ui_campaign_window.py, which need a real QApplication."""
import unittest

from nexus import config
from nexus.config import DEFAULT_SETTINGS, mask_name, set_showcase_mode, showcase_mode
from nexus.data import get_data

PALETTE_KEYS = {"bg", "bg_alt", "panel", "panel_hi", "border", "green", "green_dim", "cyan", "cyan_dim", "red",
                 "amber", "text", "dim", "white", "purple"}


class ShowcaseModeTests(unittest.TestCase):
    def tearDown(self):
        set_showcase_mode(False)       # module-level global: never leak state into other tests

    def test_default_settings_include_the_new_keys(self):
        self.assertIn("reduced_motion", DEFAULT_SETTINGS)
        self.assertIn("showcase_mode", DEFAULT_SETTINGS)
        self.assertFalse(DEFAULT_SETTINGS["reduced_motion"])
        self.assertFalse(DEFAULT_SETTINGS["showcase_mode"])

    def test_showcase_mode_off_by_default(self):
        self.assertFalse(showcase_mode())
        self.assertEqual(mask_name("TOTO"), "TOTO")

    def test_showcase_mode_masks_the_name(self):
        set_showcase_mode(True)
        self.assertTrue(showcase_mode())
        self.assertEqual(mask_name("TOTO"), "OPERATOR")
        set_showcase_mode(False)
        self.assertEqual(mask_name("TOTO"), "TOTO")

    def test_config_module_object_reflects_the_same_state(self):
        config.set_showcase_mode(True)
        self.assertTrue(config.showcase_mode())


class ThemeTests(unittest.TestCase):
    def test_ten_themes_total(self):
        self.assertEqual(len(get_data().themes), 10)

    def test_colorblind_safe_and_mono_themes_exist_and_are_free(self):
        by_id = {t["id"]: t for t in get_data().themes}
        for theme_id in ("colorblind", "mono"):
            self.assertIn(theme_id, by_id)
            self.assertTrue(by_id[theme_id].get("free"), f"{theme_id} should be free (accessibility, not a reward)")
            self.assertEqual(set(by_id[theme_id]["palette"].keys()), PALETTE_KEYS)

    def test_colorblind_theme_avoids_pure_red_green(self):
        palette = next(t for t in get_data().themes if t["id"] == "colorblind")["palette"]
        self.assertNotEqual(palette["green"].lower(), "#00ff00")
        self.assertNotEqual(palette["red"].lower(), "#ff0000")


if __name__ == "__main__":
    unittest.main()
