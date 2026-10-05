"""A6: the v3 character editor — name, a short look/appearance description, and the C6 help mode (Guided/Medium/
Hardcore, docs/story/02-acts-and-levels.md §2), asked once on a brand-new v3 profile.

Deliberately minimal on the character side: the player's shell login stays the fixed "operator" account every
mission's scenario data already hard-codes (changing it per player would break 200 missions' worth of
``ssh operator@...``/``/home/operator`` expectations) — this is a display callsign and flavour text, the same
distinction real operators draw between a login name and a handle. ``look`` has no mechanical effect yet; it is
stored for a future avatar/profile-card screen (category D).
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QDialog, QLabel, QLineEdit, QRadioButton, QTextEdit, QVBoxLayout

from nexus.config import COLORS

from .widgets import NeonButton, mono_font

MODES = [
    ("guided", "GUIDED", "Every new command explained in full before first use; hints always available"),
    ("medium", "MEDIUM", "Short unlock notice; tiered hints available on request"),
    ("hardcore", "HARDCORE", "No unlock notices, no hints — real tool behaviour only"),
]


class CharacterDialog(QDialog):
    """Non-blocking by convention: callers connect ``accepted`` (or ``finished``) and call ``show()``, not
    ``exec()`` — keeps this testable headlessly and keeps CampaignWindow's own event loop responsive."""

    created = Signal(str, str, str)      # name, look, mode

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NEXUS // TERMINAL — New Operator")
        self.setMinimumWidth(420)
        self.setStyleSheet(f"QDialog {{ background:{COLORS['bg']}; }}")
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        title = QLabel("WHO ARE YOU GOING TO BE?")
        title.setStyleSheet(f"color:{COLORS['green']}; font-size:16px; font-weight:bold;")
        lay.addWidget(title)

        lay.addWidget(QLabel("Callsign (shown in the UI — your shell login stays 'operator', same as every mission expects):"))
        self.name_input = QLineEdit()
        self.name_input.setFont(mono_font(12))
        self.name_input.setPlaceholderText("Kestrel")
        lay.addWidget(self.name_input)

        lay.addWidget(QLabel("A line or two about them (optional, cosmetic only for now):"))
        self.look_input = QTextEdit()
        self.look_input.setFont(mono_font(11))
        self.look_input.setMaximumHeight(80)
        lay.addWidget(self.look_input)

        lay.addWidget(QLabel("How much help do you want along the way? (changeable later in settings)"))
        self.mode_group = QButtonGroup(self)
        self.mode_buttons: dict[str, QRadioButton] = {}
        for key, label, tip in MODES:
            btn = QRadioButton(f"{label} — {tip}")
            btn.setToolTip(tip)
            self.mode_group.addButton(btn)
            self.mode_buttons[key] = btn
            lay.addWidget(btn)
        self.mode_buttons["guided"].setChecked(True)

        self.ok_btn = NeonButton("[ BEGIN ]", "Start the campaign")
        self.ok_btn.clicked.connect(self._on_ok)
        lay.addWidget(self.ok_btn)
        self.name_input.returnPressed.connect(self._on_ok)

    def _selected_mode(self) -> str:
        return next((key for key, btn in self.mode_buttons.items() if btn.isChecked()), "guided")

    def _on_ok(self) -> None:
        name = self.name_input.text().strip() or "operator"
        look = self.look_input.toPlainText().strip()
        self.created.emit(name, look, self._selected_mode())
        self.accept()
