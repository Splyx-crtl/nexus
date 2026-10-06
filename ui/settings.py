"""Settings: audio, text speed, animations, CRT/glitch effects, display, theme and language."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QSlider, QSpinBox, QTabWidget,
                               QVBoxLayout, QWidget)

from nexus.config import DEFAULT_SETTINGS, RESOLUTIONS
from nexus.i18n import tr

from .widgets import NeonButton, labeled_row


class SettingsWidget(QWidget):
    """Embeddable settings panel. ``apply_cb`` runs on every change; ``reload_cb`` when theme/language change."""

    def __init__(self, settings, engine=None, apply_cb=lambda: None, reload_cb=lambda: None, parent=None):
        super().__init__(parent)
        self.settings, self.engine, self.apply_cb, self.reload_cb = settings, engine, apply_cb, reload_cb
        self._controls: dict[str, QWidget] = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        title = QLabel(f"// {tr('settings')}")
        title.setObjectName("h1")
        lay.addWidget(title)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)

        audio = QWidget()
        al = QVBoxLayout(audio)
        al.addWidget(self._slider("volume_master", "MASTER VOLUME", 0, 100, "Overall loudness"))
        al.addWidget(self._slider("volume_music", "MUSIC VOLUME", 0, 100, "Background music"))
        al.addWidget(self._slider("volume_sfx", "SFX VOLUME", 0, 100, "Terminal, alerts and UI sounds"))
        al.addWidget(self._check("typing_sound", "Typing sound", "Play a click for every few typed characters"))
        al.addStretch(1)
        self.tabs.addTab(audio, "AUDIO")

        game = QWidget()
        gl = QVBoxLayout(game)
        gl.addWidget(self._slider("text_speed", "TEXT SPEED", 1, 5, "1 = slow cinematic · 5 = near instant"))
        gl.addWidget(self._check("animations", "Animations", "Fades, sliding notifications and the animated menu background"))
        self.diff = QComboBox()
        for name in ("easy", "normal", "hard"):
            self.diff.addItem(name.upper(), name)
        if engine:
            self.diff.setCurrentIndex(max(0, self.diff.findData(engine.difficulty)))
            self.diff.currentIndexChanged.connect(lambda _: self.engine.set_difficulty(self.diff.currentData()))
        else:
            self.diff.setEnabled(False)
        gl.addWidget(labeled_row("DIFFICULTY", self.diff, "Easy: gentler trace alert, rewards x0.85 · Hard: sharper alert, rewards x1.2"))
        gl.addWidget(self._spin("font_size", "TEXT SIZE (ACCESSIBILITY)", 10, 24))
        gl.addWidget(self._spin("autosave_seconds", "AUTOSAVE EVERY (s)", 20, 600))
        gl.addWidget(self._check("random_events", "Random events", "Occasional alerts, messages and finds while you play"))
        gl.addWidget(self._check("call_scenes", "Call-style story scenes (3.0 campaign)",
                                  "Key story moments play as an incoming call (subtitles, accept/decline) instead of plain terminal text"))
        self.lang = QComboBox()
        self.lang.addItem("English", "en")
        self.lang.addItem("Deutsch", "de")
        self.lang.setCurrentIndex(max(0, self.lang.findData(settings.get("language"))))
        self.lang.currentIndexChanged.connect(lambda _: self._set("language", self.lang.currentData(), reload=True))
        gl.addWidget(labeled_row(tr("language"), self.lang, "Interface language (menus and headings)"))
        gl.addStretch(1)
        self.tabs.addTab(game, "GAMEPLAY")

        display = QWidget()
        dl = QVBoxLayout(display)
        self.mode = QComboBox()
        self.mode.addItems(["Windowed", "Fullscreen"])
        self.mode.setCurrentIndex(1 if settings.get("fullscreen") else 0)
        self.mode.currentIndexChanged.connect(lambda i: self._set("fullscreen", bool(i)))
        dl.addWidget(labeled_row("DISPLAY MODE", self.mode, "F11 toggles fullscreen anywhere"))
        self.res = QComboBox()
        self.res.addItems(RESOLUTIONS)
        if settings.get("resolution") in RESOLUTIONS:
            self.res.setCurrentText(settings.get("resolution"))
        self.res.currentTextChanged.connect(lambda t: self._set("resolution", t))
        dl.addWidget(labeled_row("RESOLUTION", self.res, "Applies in windowed mode"))
        self.theme = QComboBox()
        self._fill_themes()
        self.theme.currentIndexChanged.connect(lambda _: self._set("theme", self.theme.currentData(), reload=True))
        dl.addWidget(labeled_row(tr("theme"), self.theme, "Unlock more themes in the market or with achievements"))
        dl.addWidget(self._check("scanlines", "CRT effects", "Scanlines, vignette and the moving refresh band"))
        dl.addWidget(self._check("glitch_effects", "Glitch effects", "Title glitch, banner jitter and screen glitches"))
        dl.addStretch(1)
        self.tabs.addTab(display, "DISPLAY")

        self.tabs.addTab(self._accessibility_tab(), "ACCESSIBILITY")
        self.tabs.addTab(self._about_tab(), "ABOUT")

        row = QHBoxLayout()
        reset = NeonButton("RESET DEFAULTS", "Restore all settings", "danger")
        reset.clicked.connect(self._reset)
        row.addWidget(reset)
        row.addStretch(1)
        lay.addLayout(row)

    def _accessibility_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(self._check("reduced_motion", "Reduced motion",
                                   "Turns off the moving scanline band, the pulsing alert glow, glitch bursts and "
                                   "the menu background animation. The red alert tint and page transitions still "
                                   "show, just without the motion."))
        lay.addWidget(self._check_reload("showcase_mode", "Showcase / recording mode",
                                          "Replaces your callsign with \"OPERATOR\" everywhere it's shown on screen "
                                          "- safe for streaming or screen recording."))
        note = QLabel("Colorblind-friendly palette: pick \"COLORBLIND SAFE\" under Display -> Theme. It replaces "
                       "the usual red/green contrast with blue/orange/magenta so status colors stay distinguishable.")
        note.setObjectName("dim")
        note.setWordWrap(True)
        lay.addWidget(note)
        keys = QLabel("Keyboard: Tab / Shift+Tab moves focus, Enter confirms, Esc closes dialogs or opens the pause "
                       "menu, F11 toggles fullscreen, F12 saves a screenshot, F1 opens help, Ctrl+1..9 jumps between "
                       "sections.")
        keys.setObjectName("dim")
        keys.setWordWrap(True)
        lay.addWidget(keys)
        lay.addStretch(1)
        return w

    def _check_reload(self, key: str, label: str, hint: str) -> QCheckBox:
        c = QCheckBox(label)
        c.setToolTip(hint)
        c.setChecked(bool(self.settings.get(key)))
        c.toggled.connect(lambda v: self._set(key, v, reload=True))
        self._controls[key] = c
        return c

    def _about_tab(self) -> QWidget:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from nexus.config import ERROR_LOG, SAVES_DIR
        from nexus.version import AUTHOR, DISCORD_URL, RELEASES_URL, VERSION
        w = QWidget()
        lay = QVBoxLayout(w)
        title = QLabel(f"NEXUS // TERMINAL  v{VERSION}")
        title.setObjectName("h2")
        by = QLabel(f"Created by {AUTHOR}")
        by.setStyleSheet("font-size: 15px; font-weight: bold;")
        note = QLabel("Everything in NEXUS is a simulation. The game never touches real networks.\nShortcuts: F12 saves a screenshot to saves/screenshots.")
        note.setObjectName("dim")
        for x in (title, by, note):
            lay.addWidget(x)
        lay.addSpacing(10)

        def link_button(text, tip, fn, variant=""):
            b = NeonButton(text, tip, variant)
            b.clicked.connect(fn)
            lay.addWidget(b)

        if DISCORD_URL:
            link_button("JOIN THE DISCORD", DISCORD_URL, lambda: QDesktopServices.openUrl(QUrl(DISCORD_URL)), "cyan")
        if RELEASES_URL:
            link_button("CHECK FOR UPDATES", "Opens the releases page in your browser", lambda: QDesktopServices.openUrl(QUrl(RELEASES_URL)))
        link_button("OPEN SAVE FOLDER", "Show your saves, settings and screenshots", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(SAVES_DIR))))
        link_button("OPEN ERROR LOG", "If something went wrong, send this file to the developer",
                    lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(ERROR_LOG if ERROR_LOG.exists() else SAVES_DIR))))
        lay.addStretch(1)
        return w

    def _fill_themes(self) -> None:
        self.theme.blockSignals(True)
        self.theme.clear()
        from nexus.data import get_data
        unlocked = set(self.engine.db.unlocks("theme:")) if self.engine else set()
        for t in get_data().themes:
            if t.get("free") or f"theme:{t['id']}" in unlocked or not self.engine:
                self.theme.addItem(t["name"], t["id"])
        idx = self.theme.findData(self.settings.get("theme"))
        self.theme.setCurrentIndex(max(0, idx))
        self.theme.blockSignals(False)

    # ------------------------------------------------------------ factories
    def _set(self, key: str, value, reload: bool = False) -> None:
        self.settings.set(key, value)
        self.apply_cb()
        if reload:
            self.reload_cb()

    def _slider(self, key: str, label: str, lo: int, hi: int, hint: str) -> QWidget:
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(lo, hi)
        s.setValue(int(self.settings.get(key)))
        value = QLabel(str(s.value()))
        value.setMinimumWidth(32)
        s.valueChanged.connect(lambda v: (value.setText(str(v)), self._set(key, v)))
        wrap = QWidget()
        h = QHBoxLayout(wrap)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(s, 1)
        h.addWidget(value)
        self._controls[key] = s
        return labeled_row(label, wrap, hint)

    def _check(self, key: str, label: str, hint: str) -> QCheckBox:
        c = QCheckBox(label)
        c.setToolTip(hint)
        c.setChecked(bool(self.settings.get(key)))
        c.toggled.connect(lambda v: self._set(key, v))
        self._controls[key] = c
        return c

    def _spin(self, key: str, label: str, lo: int, hi: int) -> QWidget:
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setValue(int(self.settings.get(key)))
        s.valueChanged.connect(lambda v: self._set(key, v))
        self._controls[key] = s
        return labeled_row(label, s)

    def _reset(self) -> None:
        keep = {k: self.settings.get(k) for k in ("last_profile", "tutorial_seen")}
        for key, value in DEFAULT_SETTINGS.items():
            self.settings.values[key] = keep.get(key, value)
        self.settings.save()
        for key, widget in self._controls.items():
            value = self.settings.get(key)
            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            else:
                widget.setValue(int(value))
        self.mode.setCurrentIndex(1 if self.settings.get("fullscreen") else 0)
        self.res.setCurrentText(self.settings.get("resolution"))
        self.lang.setCurrentIndex(self.lang.findData(self.settings.get("language")))
        self._fill_themes()
        self.apply_cb()
        self.reload_cb()


class SettingsDialog(QDialog):
    """Modal wrapper (kept for the pause menu / tests)."""

    def __init__(self, settings, apply_cb, parent=None, engine=None, reload_cb=lambda: None):
        super().__init__(parent)
        self.setWindowTitle("SETTINGS")
        self.setModal(True)
        self.setMinimumSize(620, 480)
        lay = QVBoxLayout(self)
        self.widget = SettingsWidget(settings, engine, apply_cb, reload_cb)
        lay.addWidget(self.widget)
        close = NeonButton("APPLY & CLOSE")
        close.clicked.connect(self.accept)
        lay.addWidget(close)
