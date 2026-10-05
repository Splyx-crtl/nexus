"""C6: the command lexicon — look up anything you've unlocked, any time, not just the first time you use it
(that's Guided mode's automatic lesson, nexus/campaign/profile.py's has_seen_lesson()/mark_lesson_seen()). Only
unlocked commands are listed (matches the "something new every level" progression — no spoilers for tools you
don't have yet), across all three shell families (bash/PowerShell/cmd) in one searchable reference.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

from nexus.config import COLORS
from nexus.shell.registry import specs

from .widgets import mono_font

FAMILY_LABEL = {"bash": "bash", "ps": "PowerShell", "cmd": "cmd.exe"}
_ROLE_LESSON = int(Qt.ItemDataRole.UserRole)
_ROLE_HEADING = int(Qt.ItemDataRole.UserRole) + 1
_ROLE_SUMMARY = int(Qt.ItemDataRole.UserRole) + 2


class LexiconDialog(QDialog):
    """Non-blocking by the same convention as the other campaign dialogs: call ``show()``, not ``exec()``."""

    def __init__(self, level: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Command Lexicon")
        self.resize(760, 560)
        self.setStyleSheet(f"QDialog {{ background:{COLORS['bg']}; }}")
        lay = QVBoxLayout(self)

        title = QLabel(f"EVERYTHING YOU'VE UNLOCKED (LEVEL {level})")
        title.setStyleSheet(f"color:{COLORS['green']}; font-size:14px; font-weight:bold;")
        lay.addWidget(title)

        self.search = QLineEdit()
        self.search.setFont(mono_font(11))
        self.search.setPlaceholderText("Search by name or what it does...")
        self.search.textChanged.connect(self._refilter)
        lay.addWidget(self.search)

        body = QHBoxLayout()
        self.list = QListWidget()
        self.list.setFont(mono_font(11))
        self.list.setMinimumWidth(260)
        self.list.setMaximumWidth(320)
        self.list.currentItemChanged.connect(self._on_select)
        body.addWidget(self.list)

        self.detail = QLabel("Select a command to see what it does.")
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet(f"color:{COLORS['text']};")
        self.detail.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        body.addWidget(self.detail, 1)
        lay.addLayout(body, 1)

        self._entries: list[tuple[str, str, str, str]] = []     # (display_name, family_label, summary, lesson)
        for family in ("bash", "ps", "cmd"):
            for spec in specs(family):
                if spec.level > level or not spec.lesson:
                    continue
                self._entries.append((spec.name, FAMILY_LABEL[family], spec.summary, spec.lesson))
        self._entries.sort(key=lambda e: (e[1], e[0]))
        self._populate(self._entries)

    def _populate(self, entries: list[tuple[str, str, str, str]]) -> None:
        self.list.clear()
        for name, family, summary, lesson in entries:
            item = QListWidgetItem(f"{name}  [{family}]")
            item.setData(_ROLE_LESSON, lesson)
            item.setData(_ROLE_SUMMARY, summary)
            item.setData(_ROLE_HEADING, f"{name} ({family})")
            self.list.addItem(item)

    def _refilter(self, text: str) -> None:
        text = text.lower().strip()
        if not text:
            self._populate(self._entries)
            return
        matches = [e for e in self._entries if text in e[0].lower() or text in e[2].lower() or text in e[3].lower()]
        self._populate(matches)

    def _on_select(self, item: QListWidgetItem | None, _prev=None) -> None:
        if item is None:
            self.detail.setText("Select a command to see what it does.")
            return
        heading = item.data(_ROLE_HEADING)
        summary = item.data(_ROLE_SUMMARY)
        lesson = item.data(_ROLE_LESSON)
        self.detail.setText(f"{heading}\n{summary}\n\n{lesson}")
