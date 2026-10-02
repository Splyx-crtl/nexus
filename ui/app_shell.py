"""The application shell: sidebar navigation, top bar with status cards and the page stack."""
from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QStackedWidget,
                               QVBoxLayout, QWidget)

from nexus import reputation
from nexus.config import COLORS, VERSION
from nexus.i18n import tr

from .achievements_page import AchievementsPage
from .archives import ArchivesWidget
from .contacts_panel import ContactsPanel
from .inventory import InventoryPanel
from .loadout_page import LoadoutPage
from .map_view import MapPanel
from .market_page import MarketPage
from .online_page import OnlinePage
from .operations_page import OperationsPage
from .profile_page import ProfilePage
from .settings import SettingsWidget
from .terminal_page import TerminalPage
from .widgets import NavButton, NeonBar, NeonButton, StatCard, hline, play

NAV = [("terminal", "▌", "terminal"), ("operations", "◆", "operations"), ("network", "◎", "network"), ("market", "$", "market"),
       ("loadout", "▣", "loadout"), ("inventory", "▤", "inventory"), ("comms", "✉", "comms"), ("profile", "☺", "profile"),
       ("achievements", "★", "achievements"), ("online", "◈", "online"), ("archives", "▥", "archives"), ("settings", "⚙", "settings")]
KEYS = ["terminal", "operations", "network", "market", "loadout", "inventory", "comms", "profile", "achievements", "online", "archives", "settings"]


class NotificationPopup(QDialog):
    """Drop-down list of recent notifications (the 'bell')."""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet(f"NotificationPopup {{ background:{COLORS['panel']}; border: 1px solid {COLORS['green_dim']}; }}")
        lay = QVBoxLayout(self)
        head = QLabel(f"// {tr('notifications')}")
        head.setObjectName("h2")
        lay.addWidget(head)
        lst = QListWidget()
        lst.setMinimumSize(380, 320)
        notes = engine.db.get_notifications(30)
        for n in notes:
            stamp = time.strftime("%H:%M", time.localtime(n["ts"]))
            item = QListWidgetItem(f"{stamp}  {n['title']}\n        {n['text'][:80]}")
            lst.addItem(item)
        if not notes:
            lst.addItem(tr("no_notifications"))
        lay.addWidget(lst)


class AppShell(QWidget):
    menu_requested = Signal()
    save_requested = Signal()
    load_requested = Signal()
    new_operator_requested = Signal()
    reload_requested = Signal()
    settings_applied = Signal()
    fx_requested = Signal(str, object)
    page_changed = Signal(str)
    command_ran = Signal(str)

    def __init__(self, engine, settings, parent=None):
        super().__init__(parent)
        self.engine, self.settings = engine, settings
        self.current = "terminal"
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ------------------------------------------------------ sidebar
        side = QFrame()
        side.setFixedWidth(206)
        side.setStyleSheet(f"QFrame {{ background:{COLORS['bg_alt']}; border-right: 1px solid {COLORS['border']}; }}")
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 12, 0, 12)
        sl.setSpacing(0)
        logo = QLabel("NEXUS")
        logo.setStyleSheet(f"color:{COLORS['green']}; font-size: 26px; font-weight:bold; letter-spacing: 6px; padding-left: 16px;")
        ver = QLabel(f"v{VERSION}  ·  OPERATIONS")
        ver.setStyleSheet(f"color:{COLORS['dim']}; font-size: 10px; padding-left: 18px; letter-spacing: 2px;")
        sl.addWidget(logo)
        sl.addWidget(ver)
        sl.addSpacing(12)
        self.nav: dict[str, NavButton] = {}
        for key, glyph, label in NAV:
            btn = NavButton(f"{glyph}  {tr(label)}", f"{tr(label)}  (Ctrl+{KEYS.index(key) + 1 if KEYS.index(key) < 9 else '-'})")
            btn._label = label
            btn._glyph = glyph
            btn.clicked.connect(lambda _=False, k=key: self.show_page(k))
            sl.addWidget(btn)
            self.nav[key] = btn
        sl.addStretch(1)
        self.mini = QLabel("")
        self.mini.setWordWrap(True)
        self.mini.setStyleSheet(f"color:{COLORS['text']}; padding: 8px 16px; border-top: 1px solid {COLORS['border']};")
        sl.addWidget(self.mini)
        self.menu_btn = NeonButton(f"{tr('menu')} [ESC]", "Pause menu: save, load, settings, main menu")
        self.menu_btn.clicked.connect(self.menu_requested)
        wrap = QHBoxLayout()
        wrap.setContentsMargins(12, 0, 12, 0)
        wrap.addWidget(self.menu_btn)
        sl.addLayout(wrap)
        root.addWidget(side)

        # ---------------------------------------------------- main column
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        top = QFrame()
        top.setFixedHeight(66)
        top.setStyleSheet(f"QFrame#topbar {{ background:{COLORS['panel']}; border-bottom: 1px solid {COLORS['border']}; }}")
        top.setObjectName("topbar")
        tl = QHBoxLayout(top)
        tl.setContentsMargins(14, 4, 14, 4)
        tl.setSpacing(8)
        self.title = QLabel("")
        self.title.setObjectName("h2")
        tl.addWidget(self.title)
        tl.addStretch(1)
        self.c_level = StatCard(tr("level"), COLORS["green"])
        self.c_credits = StatCard(tr("credits"))
        self.c_rep = StatCard(tr("reputation"), COLORS["cyan"])
        self.c_heat = StatCard(tr("trace_alert"), COLORS["green"])
        for c in (self.c_level, self.c_credits, self.c_rep, self.c_heat):
            c.setFixedWidth(184)
            tl.addWidget(c)
        self.bell = NeonButton("◉ 0", "Notifications", "cyan")
        self.bell.clicked.connect(self._show_notifications)
        tl.addWidget(self.bell)
        self.saved = QLabel("")
        self.saved.setObjectName("dim")
        tl.addWidget(self.saved)
        col.addWidget(top)
        self.stack = QStackedWidget()
        col.addWidget(self.stack, 1)
        root.addLayout(col, 1)

        # ----------------------------------------------------------- pages
        self.pages: dict[str, QWidget] = {}
        self.terminal_page = TerminalPage(engine, settings)
        run = self.run_command
        self.pages["terminal"] = self.terminal_page
        self.pages["operations"] = OperationsPage(engine, run)
        self.pages["network"] = MapPanel(engine, run)
        self.pages["market"] = MarketPage(engine, run)
        self.pages["loadout"] = LoadoutPage(engine)
        self.pages["inventory"] = InventoryPanel(engine, run)
        self.pages["comms"] = ContactsPanel(engine, run)
        self.pages["profile"] = ProfilePage(engine)
        self.pages["achievements"] = AchievementsPage(engine)
        self.pages["online"] = OnlinePage(engine, settings)
        self.pages["archives"] = ArchivesWidget(engine)
        self.pages["settings"] = SettingsWidget(settings, engine, self.settings_applied.emit, self.reload_requested.emit)
        for key in KEYS:
            self.stack.addWidget(self.pages[key])

        self.terminal_page.fx_requested.connect(self.fx_requested)
        self.terminal_page.save_requested.connect(self.save_requested)
        self.terminal_page.load_requested.connect(self.load_requested)
        profile = self.pages["profile"]
        profile.save_requested.connect(self.save_requested)
        profile.load_requested.connect(self.load_requested)
        profile.new_operator_requested.connect(self.new_operator_requested)
        profile.command_requested.connect(lambda c: self.run_command(c, True))
        self.terminal_page.terminal.command_finished.connect(self._on_command)

        engine.state_changed.connect(self.refresh_status)
        engine.heat_changed.connect(lambda _h: self.refresh_status())
        engine.saved.connect(self._on_saved)
        engine.comms_changed.connect(self._refresh_badges)
        engine.mission_changed.connect(self._refresh_badges)
        self.timer = QTimer(self, interval=1000)
        self.timer.timeout.connect(self._tick)
        self._last_cmd = ""
        self.refresh_status()
        self.show_page("terminal")

    # ---------------------------------------------------------------- nav --
    def retranslate(self) -> None:
        for key, btn in self.nav.items():
            btn.set_label(f"{btn._glyph}  {tr(btn._label)}")

    def show_page(self, key: str) -> None:
        if key not in self.pages:
            return
        self.current = key
        page = self.pages[key]
        if hasattr(page, "refresh"):
            page.refresh()
        self.stack.setCurrentWidget(page)
        for k, btn in self.nav.items():
            btn.setChecked(k == key)
        self.title.setText(f"// {tr(dict((k, l) for k, _g, l in NAV)[key])}")
        self._refresh_badges()
        if key == "terminal":
            self.terminal_page.terminal.focus_input()
        self.page_changed.emit(key)

    def run_command(self, command: str, goto_terminal: bool | None = None) -> None:
        """Run a command in the terminal (used by buttons on other pages)."""
        if goto_terminal is None:
            goto_terminal = command.split()[0] in ("mission", "connect", "scan", "msg") if command.split() else False
        if goto_terminal:
            self.show_page("terminal")
        self.terminal_page.terminal.run_command(command)

    def _on_command(self) -> None:
        hist = self.engine.history
        self._last_cmd = hist[-1] if hist else ""
        self.command_ran.emit(self._last_cmd)
        for key in ("inventory", "market", "loadout", "operations", "profile"):
            page = self.pages[key]
            if key == self.current and hasattr(page, "refresh"):
                page.refresh()

    # ------------------------------------------------------------- status --
    def set_active(self, active: bool) -> None:
        if active:
            self.timer.start()
            self.refresh_status()
        else:
            self.timer.stop()

    def _tick(self) -> None:
        self.engine.tick(1.0)

    def refresh_status(self) -> None:
        e, p = self.engine, self.engine.player
        self.c_level.set(f"LV {p.level} · {p.rank}", (p.xp, p.xp_needed))
        self.c_credits.set(f"${p.credits:,}", color=COLORS["amber"])
        self.c_rep.set(f"{p.reputation} · {reputation.status(p.reputation).split()[0]}", (p.reputation, 100))
        heat = e.heat
        color = COLORS["green"] if heat < 40 else COLORS["amber"] if heat < 70 else COLORS["red"]
        self.c_heat.set(f"{heat:.0f}%", (heat, 100), color)
        if self.c_heat.bar:
            self.c_heat.bar.set_color(color)
        self.mini.setText(f"{p.username.upper()}\n{p.rank}  ·  LV {p.level}")
        self.bell.setText(f"◉ {self._unread()}")

    def _unread(self) -> int:
        return self.engine.db.count_notifications_after(self.engine.db.get_world("notif_seen", 0))

    def _refresh_badges(self) -> None:
        e = self.engine
        self.nav["comms"].set_badge(e.db.unread_count())
        self.nav["operations"].set_badge(e.progress.claimable_count())

    def _show_notifications(self) -> None:
        pop = NotificationPopup(self.engine, self)
        notes = self.engine.db.get_notifications(1)
        if notes:
            self.engine.db.set_world("notif_seen", notes[0]["id"])
        self.bell.setText("◉ 0")
        pos = self.bell.mapToGlobal(self.bell.rect().bottomRight())
        pop.adjustSize()
        pop.move(pos.x() - pop.width(), pos.y() + 4)
        pop.exec()

    def _on_saved(self) -> None:
        self.saved.setText(f"● AUTOSAVED {time.strftime('%H:%M:%S')}")
        self.saved.setStyleSheet(f"color:{COLORS['green_dim']};")

    def stop(self) -> None:
        self.timer.stop()
        self.pages["online"].stop()
