"""E2: a call-style presentation for key story beats - accept/decline, subtitles revealed over time (skippable),
a per-speaker visual filter, and music ducking while it's open.

Real voice audio (E1) is still blocked on installing Piper and picking a licensed voice - nothing in this module
plays speech. It plays a ring tone and times the subtitle reveal the way a real call's pacing would feel, so the
mechanism is ready to carry real audio the moment E1 unblocks, without anything here needing to change.

Deliberately NOT wired into every story-tagged mission automatically: ~50 of the 200 missions carry the "story"
tag, and popping a modal-feeling dialog for a quarter of the campaign would be a real pacing regression over the
existing inline terminal text players already know. CampaignWindow offers this only when the player has opted in
(the "call_scenes" setting, off by default) and only for story beats - see its own call site for the exact rule.
"""
from __future__ import annotations

import re

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout

from nexus.config import COLORS

from .widgets import NeonButton, mono_font

SPEAKER_RE = re.compile(r"^([A-Z][A-Za-z0-9 ]{1,20}):\s*(.*)$")

# Established per-role accent colors elsewhere in the app (green=NEXUS/ok, cyan=MIRA/info, red=ZERO/danger);
# anyone else (Oduya, Reyes, the player's own echoed decisions, ...) gets the neutral amber used for story text.
SPEAKER_COLORS = {"NEXUS": COLORS["green"], "MIRA": COLORS["cyan"], "ZERO": COLORS["red"]}
DEFAULT_SPEAKER_COLOR = COLORS["amber"]

MS_PER_CHAR = 35       # subtitle pacing: roughly reading speed, not a race
MIN_LINE_MS = 1400
MAX_LINE_MS = 5000
AUTOCLOSE_DELAY_MS = 1200


def parse_speaker(line: str) -> tuple[str | None, str]:
    """'NEXUS: Something happened' -> ('NEXUS', 'Something happened'); no match -> (None, line)."""
    m = SPEAKER_RE.match(line.strip())
    return (m.group(1), m.group(2)) if m else (None, line)


class CallDialog(QDialog):
    answered = Signal()
    declined = Signal()
    finished = Signal()

    def __init__(self, lines: list[str], sound=None, parent=None):
        super().__init__(parent)
        self.lines = [parse_speaker(l) for l in lines]
        self.sound = sound
        self._index = 0
        self._answered = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance)

        self.setWindowTitle("Incoming Call")
        self.resize(480, 260)
        self.setStyleSheet(f"QDialog {{ background:{COLORS['bg']}; border:2px solid {COLORS['border']}; }}")

        lay = QVBoxLayout(self)
        self.speaker_label = QLabel("INCOMING CALL")
        self.speaker_label.setFont(mono_font(16, bold=True))
        lay.addWidget(self.speaker_label)

        self.subtitle = QLabel("")
        self.subtitle.setWordWrap(True)
        self.subtitle.setFont(mono_font(13))
        self.subtitle.setMinimumHeight(110)
        lay.addWidget(self.subtitle, 1)

        row = QHBoxLayout()
        self.accept_btn = NeonButton("[ ACCEPT ]", "Take the call")
        self.accept_btn.clicked.connect(self._accept)
        self.decline_btn = NeonButton("[ DECLINE ]", "Let it go to nothing - you can still read it later", "danger")
        self.decline_btn.clicked.connect(self._decline)
        row.addWidget(self.accept_btn)
        row.addWidget(self.decline_btn)
        lay.addLayout(row)

        if self.sound is not None:
            self.sound.play("connect")
            self.sound.set_duck(0.3)

    # ------------------------------------------------------------------ flow
    def _accept(self) -> None:
        if self._answered:
            return
        self._answered = True
        self.answered.emit()
        self.accept_btn.hide()
        self.decline_btn.setText("[ SKIP ]")
        self.decline_btn.setToolTip("Skip to the end of the call")
        try:
            self.decline_btn.clicked.disconnect()
        except TypeError:
            pass
        self.decline_btn.clicked.connect(self._skip_to_end)
        self._show_line()

    def _decline(self) -> None:
        self.declined.emit()
        self._end_call()
        self.reject()

    def _skip_to_end(self) -> None:
        self._timer.stop()
        self._index = len(self.lines)
        self._end_call()
        self.finished.emit()
        self.accept()

    def _show_line(self) -> None:
        if self._index >= len(self.lines):
            self._end_call()
            self.finished.emit()
            QTimer.singleShot(AUTOCLOSE_DELAY_MS, self.accept)
            return
        speaker, text = self.lines[self._index]
        color = SPEAKER_COLORS.get((speaker or "").upper(), DEFAULT_SPEAKER_COLOR)
        self.speaker_label.setText(speaker or "UNKNOWN")
        self.speaker_label.setStyleSheet(f"color:{color};")
        self.subtitle.setText(text)
        self.subtitle.setStyleSheet(f"color:{COLORS['text']}; border-left: 3px solid {color}; padding-left: 8px;")
        ms = max(MIN_LINE_MS, min(MAX_LINE_MS, len(text) * MS_PER_CHAR))
        self._index += 1
        self._timer.start(ms)

    def _advance(self) -> None:
        self._show_line()

    def _end_call(self) -> None:
        self._timer.stop()
        if self.sound is not None:
            self.sound.set_duck(1.0)

    def keyPressEvent(self, ev) -> None:
        from PySide6.QtCore import Qt
        if self._answered and ev.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._timer.stop()
            self._show_line()          # skip to the next line immediately
            return
        super().keyPressEvent(ev)

    def closeEvent(self, ev) -> None:
        self._end_call()
        super().closeEvent(ev)
