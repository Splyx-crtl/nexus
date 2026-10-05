"""A6: the v3 character editor — name and a short look/appearance description, asked once on a brand-new v3 profile.
Deliberately minimal: the player's shell login stays the fixed "operator" account every mission's scenario data
already hard-codes (changing it per player would break 200 missions' worth of ``ssh operator@...``/``/home/operator``
expectations) — this is a display callsign and flavour text, the same distinction real operators draw between a
login name and a handle. ``look`` has no mechanical effect yet; it is stored for a future avatar/profile-card screen
(category D).
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QTextEdit, QVBoxLayout

from nexus.config import COLORS

from .widgets import NeonButton, mono_font


class CharacterDialog(QDialog):
    """Non-blocking by convention: callers connect ``accepted`` (or ``finished``) and call ``show()``, not
    ``exec()`` — keeps this testable headlessly and keeps CampaignWindow's own event loop responsive."""

    created = Signal(str, str)      # name, look

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

        self.ok_btn = NeonButton("[ BEGIN ]", "Start the campaign")
        self.ok_btn.clicked.connect(self._on_ok)
        lay.addWidget(self.ok_btn)
        self.name_input.returnPressed.connect(self._on_ok)

    def _on_ok(self) -> None:
        name = self.name_input.text().strip() or "operator"
        look = self.look_input.toPlainText().strip()
        self.created.emit(name, look)
        self.accept()
