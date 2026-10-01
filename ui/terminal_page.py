"""TERMINAL page: the command terminal plus the HUD dashboard."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QSplitter, QVBoxLayout, QWidget

from nexus.config import COLORS

from .dashboard import DashboardPanel
from .minigames import run_minigame
from .terminal import TerminalWidget


class TerminalPage(QWidget):
    fx_requested = Signal(str, object)
    save_requested = Signal()
    load_requested = Signal()

    def __init__(self, engine, settings, parent=None):
        super().__init__(parent)
        self.engine = engine
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setHandleWidth(6)
        self.terminal = TerminalWidget(engine, settings)
        frame = QWidget()
        frame.setStyleSheet(f"border: 1px solid {COLORS['border']};")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.addWidget(self.terminal)
        split.addWidget(frame)
        self.dashboard = DashboardPanel(engine)
        self.dashboard.setMinimumWidth(300)
        split.addWidget(self.dashboard)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 1)
        split.setSizes([820, 340])
        lay.addWidget(split)
        self.terminal.minigame_runner = lambda kind, payload: run_minigame(self.window(), kind, payload)
        self.terminal.fx_requested.connect(self.fx_requested)
        self.dashboard.save_requested.connect(self.save_requested)
        self.dashboard.load_requested.connect(self.load_requested)

    def start_session(self, first_run: bool) -> None:
        self.terminal.print_welcome()
        e = self.engine
        if first_run:
            e.db.set_flag("intro_pending", False)
            self.terminal.run_command("mission start 1", echo=False)
        else:
            self.terminal.print_line(f"Welcome back, {e.player.username}.  Type 'mission' for your orders, 'daily' for today's operations.", "ok")
        self.terminal.focus_input()
