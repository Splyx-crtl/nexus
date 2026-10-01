"""Interactive tutorial: a coach panel that walks the player through every major system."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from nexus.config import COLORS
from nexus.i18n import tr

from .widgets import NeonBar, NeonButton

# page, title, text, wait-condition ("command:<prefix>" | "page:<key>" | None)
STEPS = [
    ("terminal", "THE TERMINAL", "This is your terminal. Everything you do in a mission happens here. Type  help  and press ENTER.", "command:help"),
    ("terminal", "MISSIONS", "Mission 001 is already running. Type  mission  to see your objectives. TAB completes commands, UP/DOWN browse history.", "command:mission"),
    ("operations", "OPERATIONS", "OPERATIONS lists every mission by chapter, with difficulty, type, level requirement and bonus goals. DAILY and WEEKLY hold challenges that pay credits, XP and rare items.", None),
    ("network", "NETWORK", "The NETWORK map shows every host you have discovered. Unexplored hosts appear as '?'. Select a node to CONNECT or SCAN it.", None),
    ("inventory", "INVENTORY", "Your items, upgrades and downloaded files. Filter by category; consumables can be used right here.", None),
    ("market", "NEXUS MARKET", "Spend credits on tools, upgrades, themes, access and intel. A better REPUTATION makes everything cheaper. Check the daily deal!", "page:market"),
    ("loadout", "LOADOUT", "Equip gear into five slots (TRACE, DECRYPT, FIREWALL, NETWORK, UTILITY). Equipped items boost your stats in every mini-game. Some slots unlock with the story.", None),
    ("inventory", "UPGRADES", "Open the UPGRADES tab: permanent boosts like TERMINAL SPEED, FIREWALL ANALYSIS or STORAGE. Each has five levels.", None),
    ("profile", "SAVING", "NEXUS autosaves continuously. PROFILE lets you save into manual slots, load other saves or start a new operator. Good luck, operator.", None),
]


class TutorialOverlay(QFrame):
    finished = Signal()

    def __init__(self, parent: QWidget, shell):
        super().__init__(parent)
        self.shell = shell
        self.index = 0
        self.done_wait = False
        self.setObjectName("panel")
        self.setStyleSheet(f"QFrame#panel {{ background:{COLORS['panel_hi']}; border: 2px solid {COLORS['amber']}; }}")
        self.setFixedWidth(420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        self.step_lbl = QLabel("")
        self.step_lbl.setStyleSheet(f"color:{COLORS['amber']}; letter-spacing: 2px; font-weight:bold;")
        self.title = QLabel("")
        self.title.setObjectName("h2")
        self.text = QLabel("")
        self.text.setWordWrap(True)
        self.hint = QLabel("")
        self.hint.setStyleSheet(f"color:{COLORS['green']};")
        self.bar = NeonBar(COLORS["amber"], len(STEPS), 6)
        row = QHBoxLayout()
        self.skip = NeonButton(tr("skip"), "Close the tutorial (type 'tutorial' to see the manual later)", "danger")
        self.next = NeonButton(tr("next"))
        self.skip.clicked.connect(self.close_tutorial)
        self.next.clicked.connect(self._next)
        row.addWidget(self.skip)
        row.addStretch(1)
        row.addWidget(self.next)
        for w in (self.step_lbl, self.title, self.text, self.hint, self.bar):
            lay.addWidget(w)
        lay.addLayout(row)
        parent.installEventFilter(self)
        shell.page_changed.connect(self._on_page)
        shell.command_ran.connect(self._on_command)
        self.hide()

    def eventFilter(self, obj, ev):
        if obj is self.parent() and ev.type() == ev.Type.Resize and self.isVisible():
            self._place()
        return False

    def _place(self) -> None:
        self.adjustSize()
        p = self.parent()
        self.move(p.width() - self.width() - 20, p.height() - self.height() - 24)
        self.raise_()

    def start(self) -> None:
        self.index = 0
        self.show()
        self._show_step()

    def _show_step(self) -> None:
        page, title, text, wait = STEPS[self.index]
        self.done_wait = wait is None
        self.shell.show_page(page)
        self.step_lbl.setText(f"{tr('chapter')} · STEP {self.index + 1} / {len(STEPS)}")
        self.title.setText(title)
        self.text.setText(text)
        self.bar.set_value(self.index + 1, len(STEPS))
        self.hint.setText("" if self.done_wait else "▶ Try it now — this step continues when you do.")
        self.next.setText(tr("next") if self.index < len(STEPS) - 1 else "FINISH")
        self.next.setEnabled(self.done_wait)
        self._place()

    def _complete_wait(self) -> None:
        self.done_wait = True
        self.hint.setText("✔ Nice! Press NEXT.")
        self.next.setEnabled(True)

    def _on_page(self, key: str) -> None:
        if not self.isVisible() or self.done_wait:
            return
        wait = STEPS[self.index][3]
        if wait == f"page:{key}":
            self._complete_wait()

    def _on_command(self, cmd: str) -> None:
        if not self.isVisible() or self.done_wait:
            return
        wait = STEPS[self.index][3]
        if wait and wait.startswith("command:") and cmd.strip().lower().startswith(wait.split(":", 1)[1]):
            self._complete_wait()

    def _next(self) -> None:
        if self.index >= len(STEPS) - 1:
            self.close_tutorial()
            return
        self.index += 1
        self._show_step()

    def close_tutorial(self) -> None:
        self.hide()
        self.shell.show_page("terminal")
        self.finished.emit()
