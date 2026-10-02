"""Main window: owns pages, overlays and the whole application flow."""
from __future__ import annotations
import sqlite3

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout, QWidget

from nexus import config, i18n
from nexus.config import APP_FULL_NAME, ASSETS_DIR, COLORS
from nexus.data import get_data
from nexus.game_engine import GameEngine
from nexus.save_system import SaveSystem, SettingsStore

from .app_shell import KEYS, AppShell
from .cinematic import CinematicScreen, LoadingScreen
from .dialogs import LoadDialog, NamePrompt, PauseMenu, SlotDialog
from .first_launch import FirstLaunchScreen
from .main_menu import MainMenu
from .tutorial import TutorialOverlay
from .widgets import BannerOverlay, FadeOverlay, ScanlineOverlay, ToastManager, build_stylesheet, play, set_sound

INTRO_LINES = [
    "2031. The networks never sleep.",
    "Between the banks, the satellites and the power grid, a system called NEXUS watches over everything.",
    "It finds threats before they find us. It never makes mistakes. It never forgets.",
    "You are its newest operator.",
    "Your handler's voice is calm. Your first mission is simple.",
    "Welcome to NEXUS, {player}.",
]


def make_icon() -> QIcon:
    png = ASSETS_DIR / "nexus.png"
    if png.exists():
        return QIcon(str(png))
    pix = QPixmap(64, 64)
    pix.fill(QColor(COLORS["bg"]))
    p = QPainter(pix)
    p.setPen(QColor(COLORS["green"]))
    p.drawRect(3, 3, 58, 58)
    font = p.font()
    font.setPixelSize(42)
    font.setBold(True)
    p.setFont(font)
    p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "N")
    p.end()
    return QIcon(pix)


class MainWindow(QMainWindow):
    PAGE_MENU, PAGE_FIRST, PAGE_LOADING, PAGE_SHELL, PAGE_STORY = range(5)

    def __init__(self, settings: SettingsStore, saves: SaveSystem, sound):
        super().__init__()
        self.settings, self.saves, self.sound = settings, saves, sound
        self.data = get_data()
        self.engine: GameEngine | None = None
        self.shell: AppShell | None = None
        self.tutorial: TutorialOverlay | None = None
        self.pending_ending: str | None = None
        self._after_story = None
        self._last_res: str | None = None
        self._first_run = False
        self._session_started = False
        self.setWindowTitle(APP_FULL_NAME)
        self.setWindowIcon(make_icon())
        self.setMinimumSize(1060, 680)
        set_sound(sound)
        from .update_dialog import UpdateManager
        self.updates = UpdateManager(self)
        from . import minigames as _mg
        _mg.set_tip_store(lambda: list(self.settings.get("seen_tips") or []), lambda tips: self.settings.set("seen_tips", tips))
        self._apply_language()
        self._apply_theme()

        central = QWidget()
        self.setCentralWidget(central)
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        self.stack.currentChanged.connect(lambda _i: self._update_music())
        lay.addWidget(self.stack)
        self.menu = MainMenu()
        self.first = FirstLaunchScreen()
        self.loading = LoadingScreen()
        self.shell_holder = QWidget()
        QVBoxLayout(self.shell_holder).setContentsMargins(0, 0, 0, 0)
        self.story = CinematicScreen()
        for page in (self.menu, self.first, self.loading, self.shell_holder, self.story):
            self.stack.addWidget(page)

        self.toasts = ToastManager(central, top_offset=72)
        self.banner = BannerOverlay(central)
        self.banner.sound_cb = play
        self.banner.finished.connect(self._banner_done)
        self.scan = ScanlineOverlay(central)
        self.fade = FadeOverlay(central)

        self._wire_menu()
        self.first.created.connect(self._on_profile_created)
        self.loading.finished.connect(self._loading_done)
        self.story.finished.connect(self._story_done)

        for seq, fn in (("Esc", self.on_escape), ("F5", self.quick_save), ("Ctrl+S", self.quick_save),
                        ("F9", self.load_in_game), ("F12", self.take_screenshot), ("F11", self.toggle_fullscreen), ("F1", lambda: self._run("help"))):
            QShortcut(QKeySequence(seq), self, activated=fn)
        for i in range(9):
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self, activated=lambda n=i: self._goto_index(n))
        self.apply_settings()

    # -------------------------------------------------------------- setup --
    def _wire_menu(self) -> None:
        self.menu.action.connect(self.on_menu_action)

    def _apply_language(self) -> None:
        i18n.set_language(self.settings.get("language"))

    def _apply_theme(self) -> None:
        """Select the saved theme (falls back to DEFAULT if it is not unlocked for this operator)."""
        wanted = self.settings.get("theme")
        themes = get_data().themes
        theme = next((t for t in themes if t["id"] == wanted), themes[0])
        if not theme.get("free") and self.engine is not None and not self.engine.db.is_unlocked(f"theme:{theme['id']}"):
            theme = themes[0]
        config.apply_theme(theme["palette"])
        QApplication.instance().setStyleSheet(build_stylesheet(int(self.settings.get("font_size"))))

    # -------------------------------------------------------------- start --
    def startup(self) -> None:
        """Called once after show(): first-launch flow or straight to the menu with the latest profile."""
        latest = self.saves.latest_profile()
        if latest is None:
            self.stack.setCurrentIndex(self.PAGE_FIRST)
            self.first.start()
            return
        db = self._open_with_retry(latest.path)
        if db is None:
            QApplication.instance().quit()
            return
        self._attach_engine(db)
        self.stack.setCurrentIndex(self.PAGE_MENU)
        self._update_music()
        self.updates.start()

    def _update_music(self) -> None:
        """Menu music in the menus, calm terminal music while playing, tension music when the heat is high."""
        in_shell = self.stack.currentIndex() == self.PAGE_SHELL
        mood = "menu"
        if in_shell:
            heat = self.engine.heat if self.engine else 0
            mood = "tension" if heat >= (50 if self.sound.mood == "tension" else 70) else "terminal"
        self.sound.set_music(mood)

    def _open_with_retry(self, path):
        """Open a save; if another program holds it (second NEXUS window, sync tool), explain and let the player retry."""
        while True:
            try:
                return self.saves.open_profile(path)
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower():
                    raise
                box = QMessageBox(self)
                box.setIcon(QMessageBox.Icon.Warning)
                box.setWindowTitle("NEXUS")
                box.setText("Your save file is in use by another program.")
                box.setInformativeText("Close every other NEXUS window (Task Manager → Details → NEXUS.exe) and pause "
                                       "cloud-sync tools such as OneDrive, then try again. Your progress is not damaged.")
                retry = box.addButton("Try again", QMessageBox.ButtonRole.AcceptRole)
                box.addButton("Quit", QMessageBox.ButtonRole.RejectRole)
                box.exec()
                if box.clickedButton() is not retry:
                    return None

    def _on_profile_created(self, name: str) -> None:
        db = self.saves.create_profile(name)
        self._attach_engine(db)
        self._first_run = True
        self._update_music()
        self.updates.start()
        self._transition(self._start_loading)

    def _attach_engine(self, db) -> None:
        """Make ``db`` the active operation: new engine, signals, shell and menu card."""
        self._teardown()
        self.settings.set("last_profile", db.path.name)
        self.engine = GameEngine(db, self.settings)
        e = self.engine
        self._first_run = bool(db.get_flag("intro_pending"))
        e.toast.connect(lambda k, t, x: self.toasts.show(k, t, x))
        e.banner.connect(lambda k, lines, opts: self.banner.push(k, lines))
        e.sound.connect(play)
        e.heat_changed.connect(lambda h: setattr(self.scan, "alert", h >= 70))
        e.heat_changed.connect(lambda _h: self._update_music())
        e.ending_reached.connect(self._on_ending)
        e.state_changed.connect(self._refresh_menu_card)
        self._apply_theme()
        self._session_started = False
        self._build_shell()
        self.menu.set_engine(e)
        self.apply_settings()

    def _build_shell(self) -> None:
        if self.shell is not None:
            self.shell.stop()
            self.shell_holder.layout().removeWidget(self.shell)
            self.shell.deleteLater()
        self.shell = AppShell(self.engine, self.settings)
        self.shell_holder.layout().addWidget(self.shell)
        s = self.shell
        s.menu_requested.connect(self.pause)
        s.save_requested.connect(self.save_game)
        s.load_requested.connect(self.load_in_game)
        s.new_operator_requested.connect(self.new_operation)
        s.settings_applied.connect(self.apply_settings)
        s.reload_requested.connect(self.reload_ui)
        s.fx_requested.connect(self._on_fx)
        s.terminal_page.terminal.banner_cb = self.banner.push
        if self.tutorial is not None:
            self.tutorial.deleteLater()
        self.tutorial = TutorialOverlay(self.centralWidget(), s)
        self.tutorial.finished.connect(lambda: self.settings.set("tutorial_seen", True))

    def _refresh_menu_card(self) -> None:
        if self.engine and self.stack.currentIndex() == self.PAGE_MENU:
            self.menu.card.update_from(self.engine)

    def _teardown(self) -> None:
        if self.engine:
            self.scan.alert = False
            if self.shell:
                self.shell.stop()
            self.engine.shutdown()
            self.engine = None
        self.banner.queue.clear()
        self.banner.hide()

    # ---------------------------------------------------------------- menu --
    def on_menu_action(self, key: str) -> None:
        if key == "exit":
            self.close()
        elif key == "continue":
            self.enter_game("terminal")
        else:
            self.enter_game(key)

    def enter_game(self, page: str) -> None:
        if not self.engine:
            return
        if self._first_run and not self._session_started:
            self._play_story("NEXUS", "PROLOGUE", [line.replace("{player}", self.engine.player.username) for line in INTRO_LINES],
                             lambda: self._show_shell(page), speed=2)
        else:
            self._transition(lambda: self._show_shell(page))

    def _show_shell(self, page: str) -> None:
        self.stack.setCurrentIndex(self.PAGE_SHELL)
        self.shell.set_active(True)
        self.shell.show_page(page)
        if not self._session_started:
            self._session_started = True
            first = self._first_run
            self.shell.terminal_page.start_session(first)
            self._first_run = False
            if first and not self.settings.get("tutorial_seen"):
                QTimer.singleShot(700, lambda: self.tutorial and self.tutorial.start())
        self.apply_settings()
        self.fade.raise_()

    def _start_loading(self) -> None:
        self.stack.setCurrentIndex(self.PAGE_LOADING)
        self.loading.setFocus()
        self.loading.start()

    def _loading_done(self) -> None:
        self.enter_game("terminal")

    def to_menu(self) -> None:
        def go():
            if self.shell:
                self.shell.set_active(False)
            if self.engine:
                self.engine.save()
                self.menu.set_engine(self.engine)
            self.stack.setCurrentIndex(self.PAGE_MENU)
        self._transition(go)

    # ------------------------------------------------------------ settings --
    def apply_settings(self) -> None:
        s = self.settings
        self._apply_language()
        self.scan.show_lines = bool(s.get("scanlines"))
        self.menu.title.enabled = bool(s.get("glitch_effects"))
        self.menu.bg.animated = bool(s.get("animations"))
        self.banner.glitch_enabled = bool(s.get("glitch_effects"))
        self.sound.apply_volumes()
        if self.shell:
            self.shell.terminal_page.terminal.apply_font_size()
        if s.get("fullscreen"):
            if not self.isFullScreen():
                self.showFullScreen()
        else:
            if self.isFullScreen():
                self.showNormal()
            res = str(s.get("resolution"))
            if res != self._last_res and not self.isMaximized():
                w, h = (int(v) for v in res.split("x"))
                self.resize(w, h)
            self._last_res = res
        self.scan.raise_()

    def reload_ui(self) -> None:
        """Theme or language changed: rebuild every themed widget while keeping the running game."""
        page = self.shell.current if self.shell else "settings"
        in_shell = self.stack.currentIndex() == self.PAGE_SHELL
        self._apply_language()
        self._apply_theme()
        old = self.menu
        self.menu = MainMenu()
        self.stack.insertWidget(self.PAGE_MENU, self.menu)
        self.stack.removeWidget(old)
        old.deleteLater()
        self._wire_menu()
        if self.engine:
            self.menu.set_engine(self.engine)
            self._build_shell()
            if in_shell:
                self.shell.set_active(True)
                self.stack.setCurrentIndex(self.PAGE_SHELL)
                self.shell.terminal_page.start_session(False)
                self.shell.show_page(page)
            else:
                self.stack.setCurrentIndex(self.PAGE_MENU)
        self.apply_settings()
        self.scan.raise_()

    def toggle_fullscreen(self) -> None:
        self.settings.set("fullscreen", not self.isFullScreen())
        self.apply_settings()

    def _transition(self, callback) -> None:
        if self.settings.get("animations"):
            self.fade.transition(callback)
        else:
            callback()

    # ------------------------------------------------------------- in game --
    def _goto_index(self, n: int) -> None:
        if self.shell and self.stack.currentIndex() == self.PAGE_SHELL:
            self.shell.show_page(KEYS[n])

    def _run(self, command: str) -> None:
        if self.shell and self.stack.currentIndex() == self.PAGE_SHELL:
            self.shell.run_command(command, True)

    def on_escape(self) -> None:
        if self.banner.active:
            self.banner._skip()
            return
        if self.stack.currentIndex() == self.PAGE_SHELL:
            self.pause()

    def pause(self) -> None:
        if not self.engine or self.stack.currentIndex() != self.PAGE_SHELL:
            return
        self.engine.busy = True
        dlg = PauseMenu(self)
        dlg.exec()
        self.engine.busy = False
        choice = dlg.choice
        actions = {"save": self.save_game, "load": self.load_in_game, "settings": lambda: self.shell.show_page("settings"),
                   "archives": lambda: self.shell.show_page("archives"), "menu": self.to_menu, "quit": self.close}
        actions.get(choice, lambda: None)()
        if self.shell and choice == "resume":
            self.shell.show_page(self.shell.current)

    def take_screenshot(self) -> None:
        """F12: save the window as a PNG (handy for sharing clips and bug reports)."""
        import time
        from nexus.config import SAVES_DIR
        folder = SAVES_DIR / "screenshots"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"nexus_{time.strftime('%Y%m%d_%H%M%S')}.png"
        if self.grab().save(str(path)):
            self.toasts.show("ok", "SCREENSHOT SAVED", path.name)

    def quick_save(self) -> None:
        if self.engine:
            self.engine.save()
            self.saves.save_slot(self.engine.db, 1)
            self.toasts.show("ok", "GAME SAVED", "Saved to slot 1.")

    def save_game(self) -> None:
        if not self.engine:
            return
        dlg = SlotDialog(self.saves, self.engine.db.path, self)
        if dlg.exec() and dlg.slot:
            self.engine.save()
            self.saves.save_slot(self.engine.db, dlg.slot)
            self.toasts.show("ok", "GAME SAVED", f"Saved to slot {dlg.slot}.")
            play("notify")

    def load_in_game(self) -> None:
        dlg = LoadDialog(self.saves, self, active=self.engine.db.path if self.engine else None)
        if dlg.exec() and dlg.selected:
            self.open_save(dlg.selected)

    def open_save(self, info) -> None:
        """Load a profile or manual slot. The running game is closed first: a slot overwrites the profile file."""
        if self.engine:
            self.engine.save()
        self._teardown()
        try:
            db = self.saves.load_slot(info.path) if info.kind == "slot" else self.saves.open_profile(info.path)
        except Exception as exc:                                    # corrupt/locked file: fall back to the latest profile
            self.toasts.show("err", "LOAD FAILED", str(exc)[:80])
            latest = self.saves.latest_profile()
            if latest is None:
                return
            db = self.saves.open_profile(latest.path)
        self._switch_to(db)

    def new_operation(self) -> None:
        dlg = NamePrompt(self)
        if dlg.exec():
            db = self.saves.create_profile(dlg.name())
            self._switch_to(db, first_run=True)

    def _switch_to(self, db, first_run: bool = False) -> None:
        def go():
            self._attach_engine(db)
            if first_run:
                self._first_run = True
            self.stack.setCurrentIndex(self.PAGE_LOADING)
            self.loading.setFocus()
            self.loading.start()
        self._transition(go)

    def _on_fx(self, name: str, arg) -> None:
        if name == "glitch":
            self.scan.glitch(8)
        elif name == "pause":
            self.pause()
        elif name == "settings":
            self.shell.show_page("settings")
        elif name == "load_menu":
            self.load_in_game()
        elif name == "exit_menu":
            self.to_menu()
        elif name == "theme":
            self.reload_ui()
        elif name == "tutorial":
            if self.tutorial:
                self.tutorial.start()

    # ------------------------------------------------------------- endings --
    def _on_ending(self, ending_id: str) -> None:
        self.pending_ending = ending_id
        if not self.banner.active:
            QTimer.singleShot(400, self._play_ending)

    def _banner_done(self) -> None:
        if self.shell and self.stack.currentIndex() == self.PAGE_SHELL and self.shell.current == "terminal":
            self.shell.terminal_page.terminal.focus_input()
        if self.pending_ending:
            QTimer.singleShot(400, self._play_ending)

    def _play_ending(self) -> None:
        if not self.pending_ending or self.banner.active:
            return
        ending = self.data.endings[self.pending_ending]
        self.pending_ending = None
        name = self.engine.player.username if self.engine else "OPERATOR"
        self._play_story(ending["title"], ending["subtitle"], [line.replace("{player}", name) for line in ending["lines"]],
                         lambda: self._transition(self._back_to_game), speed=2)

    def _back_to_game(self) -> None:
        self.stack.setCurrentIndex(self.PAGE_SHELL)
        if self.shell:
            term = self.shell.terminal_page.terminal
            term.print_line("")
            term.print_line("=== CAMPAIGN COMPLETE — free play continues: side missions, secrets, the market and the road to NEXUS PRIME. ===", "ok")
            self.shell.show_page("terminal")

    def _play_story(self, title: str, subtitle: str, lines: list[str], after, speed: int = 2) -> None:
        self._after_story = after

        def go():
            self.stack.setCurrentIndex(self.PAGE_STORY)
            self.story.play(title, subtitle, lines, speed)

        self._transition(go)

    def _story_done(self) -> None:
        after, self._after_story = self._after_story, None
        if after:
            after()

    # --------------------------------------------------------------- close --
    def closeEvent(self, ev) -> None:
        self._teardown()
        self.settings.save()
        super().closeEvent(ev)
