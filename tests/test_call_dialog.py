"""E2: the speaker-prefix parser (ui/call_dialog.py's parse_speaker) - pure logic, no Qt. The actual dialog
(timers, buttons, ducking) is exercised in tests/ui_campaign_window.py, which needs a real QApplication."""
import unittest

from ui.call_dialog import DEFAULT_SPEAKER_COLOR, SPEAKER_COLORS, parse_speaker


class ParseSpeakerTests(unittest.TestCase):
    def test_a_recognized_speaker_prefix_splits_cleanly(self):
        self.assertEqual(parse_speaker("NEXUS: Something happened."), ("NEXUS", "Something happened."))
        self.assertEqual(parse_speaker("MIRA: Keep going."), ("MIRA", "Keep going."))

    def test_leading_and_trailing_whitespace_is_tolerated(self):
        self.assertEqual(parse_speaker("  ZERO: ...I don't love any of those words.  "), ("ZERO", "...I don't love any of those words."))

    def test_a_line_without_a_speaker_prefix_passes_through_unchanged(self):
        self.assertEqual(parse_speaker("Just narration, no speaker."), (None, "Just narration, no speaker."))

    def test_lowercase_prefix_is_not_mistaken_for_a_speaker(self):
        # avoids mistaking a stray "note: ..." or similar for a character name
        self.assertEqual(parse_speaker("note: this is not a speaker line"), (None, "note: this is not a speaker line"))

    def test_a_colon_inside_the_text_does_not_confuse_the_split(self):
        self.assertEqual(parse_speaker("NEXUS: Ratio is 3:1, worth noting."), ("NEXUS", "Ratio is 3:1, worth noting."))

    def test_the_three_named_characters_have_distinct_colors(self):
        colors = {SPEAKER_COLORS["NEXUS"], SPEAKER_COLORS["MIRA"], SPEAKER_COLORS["ZERO"], DEFAULT_SPEAKER_COLOR}
        self.assertEqual(len(colors), 4, "every speaker color (incl. the default) must be visually distinct")


if __name__ == "__main__":
    unittest.main()
