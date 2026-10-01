"""Small modal dialogs: new operation, load/save, pause menu, confirmation."""
from __future__ import annotations

import getpass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from nexus.config import COLORS
from nexus.save_system import SLOT_COUNT, SaveInfo, SaveSystem
from nexus.security import sanitize_name

from .widgets import NeonButton, hline


class NeonDialog(QDialog):
    def __init__(self, title: str, parent=None, width: int = 460):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setModal(True)
        self.setMinimumWidth(width)
        self.setStyleSheet(f"NeonDialog {{ background:{COLORS['bg']}; border: 2px solid {COLORS['green']}; }}")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(20, 16, 20, 16)
        self.lay.setSpacing(8)
        head = QLabel(f"// {title}")
        head.setObjectName("h1")
        self.lay.addWidget(head)
        self.lay.addWidget(hline())

    def keyPressEvent(self, ev) -> None:
        if ev.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(ev)


class NamePrompt(NeonDialog):
    def __init__(self, parent=None):
        super().__init__("NEW OPERATION", parent)
        self.lay.addWidget(QLabel("Choose your operator callsign:"))
        self.edit = QLineEdit(sanitize_name(getpass.getuser().upper()))
        self.edit.setMaxLength(20)
        self.edit.setToolTip("Letters, digits, dash and underscore")
        self.lay.addWidget(self.edit)
        row = QHBoxLayout()
        cancel = NeonButton("CANCEL", variant="danger")
        ok = NeonButton("BEGIN")
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self.accept)
        self.edit.returnPressed.connect(self.accept)
        row.addWidget(cancel)
        row.addStretch(1)
        row.addWidget(ok)
        self.lay.addLayout(row)

    def name(self) -> str:
        return sanitize_name(self.edit.text())


class ConfirmDialog(NeonDialog):
    def __init__(self, title: str, text: str, parent=None, yes: str = "YES", no: str = "NO"):
        super().__init__(title, parent)
        label = QLabel(text)
        label.setWordWrap(True)
        self.lay.addWidget(label)
        row = QHBoxLayout()
        b_no, b_yes = NeonButton(no), NeonButton(yes, variant="danger")
        b_no.clicked.connect(self.reject)
        b_yes.clicked.connect(self.accept)
        row.addWidget(b_no)
        row.addStretch(1)
        row.addWidget(b_yes)
        self.lay.addLayout(row)


class LoadDialog(NeonDialog):
    """Pick an autosave profile or a manual slot."""

    def __init__(self, saves: SaveSystem, parent=None, active=None):
        super().__init__("LOAD OPERATION", parent, 640)
        self.saves = saves
        self.active = active
        self.selected: SaveInfo | None = None
        self.list = QListWidget()
        self.list.setMinimumHeight(260)
        self.lay.addWidget(self.list)
        self.hint = QLabel("")
        self.hint.setObjectName("dim")
        self.lay.addWidget(self.hint)
        row = QHBoxLayout()
        self.cancel = NeonButton("CANCEL", variant="danger")
        self.delete = NeonButton("DELETE PROFILE", "Permanently delete the selected profile", "danger")
        self.load = NeonButton("LOAD")
        self.cancel.clicked.connect(self.reject)
        self.delete.clicked.connect(self._delete)
        self.load.clicked.connect(self._accept)
        row.addWidget(self.cancel)
        row.addWidget(self.delete)
        row.addStretch(1)
        row.addWidget(self.load)
        self.lay.addLayout(row)
        self.list.itemDoubleClicked.connect(lambda _: self._accept())
        self.list.currentRowChanged.connect(self._changed)
        self._fill()

    def _fill(self) -> None:
        self.list.clear()
        self.infos: list[SaveInfo | None] = []
        s = self.saves
        def header(text: str):
            item = QListWidgetItem(text)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setForeground(Qt.GlobalColor.cyan)
            self.list.addItem(item)
            self.infos.append(None)
        header("— AUTOSAVE PROFILES —")
        for info in s.list_profiles():
            self._add(info, f"{info.username:<14} LV{info.level:<3} {info.rank:<14} {s.format_time(info.playtime)}   {s.format_date(info.updated_at)}")
        header("— MANUAL SAVE SLOTS —")
        for info in s.list_slots():
            self._add(info, f"[slot {info.slot}] {info.username:<10} LV{info.level:<3} {info.rank:<14} {s.format_time(info.playtime)}   {s.format_date(info.updated_at)}")
        for i, info in enumerate(self.infos):
            if info:
                self.list.setCurrentRow(i)
                break
        self._changed(self.list.currentRow())

    def _add(self, info: SaveInfo, text: str) -> None:
        item = QListWidgetItem(text)
        item.setForeground(Qt.GlobalColor.green if info.kind == "profile" else Qt.GlobalColor.white)
        self.list.addItem(item)
        self.infos.append(info)

    def _changed(self, row: int) -> None:
        info = self.infos[row] if 0 <= row < len(self.infos) else None
        self.load.setEnabled(info is not None)
        self.delete.setEnabled(info is not None and info.kind == "profile" and info.path != self.active)
        self.hint.setText("Loading a manual slot restores it over its profile's autosave." if info and info.kind == "slot" else "")

    def _accept(self) -> None:
        row = self.list.currentRow()
        if 0 <= row < len(self.infos) and self.infos[row]:
            self.selected = self.infos[row]
            self.accept()

    def _delete(self) -> None:
        row = self.list.currentRow()
        info = self.infos[row] if 0 <= row < len(self.infos) else None
        if info and info.kind == "profile":
            if ConfirmDialog("DELETE PROFILE", f"Delete operator {info.username} and all their slots? This cannot be undone.", self).exec():
                self.saves.delete_profile(info.path)
                self._fill()


class SlotDialog(NeonDialog):
    """Choose a manual save slot ([ SAVE GAME ])."""

    def __init__(self, saves: SaveSystem, profile_path, parent=None):
        super().__init__("SAVE GAME", parent)
        self.slot = 0
        existing = {i.slot: i for i in saves.list_slots() if saves.slot_path(profile_path, i.slot) == i.path}
        for n in range(1, SLOT_COUNT + 1):
            info = existing.get(n)
            text = f"SLOT {n}  —  " + (f"LV{info.level} {info.rank}  {saves.format_date(info.updated_at)}" if info else "empty")
            btn = NeonButton(text)
            btn.clicked.connect(lambda _=False, s=n: self._pick(s))
            self.lay.addWidget(btn)
        cancel = NeonButton("CANCEL", variant="danger")
        cancel.clicked.connect(self.reject)
        self.lay.addWidget(cancel)

    def _pick(self, slot: int) -> None:
        self.slot = slot
        self.accept()


class PauseMenu(NeonDialog):
    """ESC menu. ``choice`` holds the selected action."""

    def __init__(self, parent=None):
        super().__init__("PAUSED", parent, 340)
        self.choice = "resume"
        for key, text, tip, variant in [
            ("resume", "RESUME", "Back to the operation (ESC)", ""),
            ("save", "SAVE GAME", "Save into a manual slot", ""),
            ("load", "LOAD GAME", "Load another save", ""),
            ("settings", "SETTINGS", "Audio, text speed, display", ""),
            ("archives", "ARCHIVES", "Achievements, stats, endings, lore", ""),
            ("menu", "MAIN MENU", "Autosaves and returns to the title screen", "cyan"),
            ("quit", "QUIT GAME", "Autosaves and exits", "danger"),
        ]:
            btn = NeonButton(text, tip, variant)
            btn.clicked.connect(lambda _=False, k=key: self._pick(k))
            self.lay.addWidget(btn)

    def _pick(self, key: str) -> None:
        self.choice = key
        self.accept()
