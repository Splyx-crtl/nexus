"""Game key activation screen: shown before anything else until the game has a valid licence (see nexus/license.py)."""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWidget

from nexus import license, online
from nexus.config import COLORS, VERSION
from nexus.version import DISCORD_URL

from .online_page import Job
from .widgets import NeonButton


class LicenseScreen(QWidget):
    activated = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.client = online.OnlineClient(settings)
        self._job: Job | None = None
        self._base = ""
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo = QLabel("NEXUS")
        logo.setStyleSheet(f"color:{COLORS['green']}; font-size: 54px; font-weight:bold; letter-spacing: 14px;")
        ver = QLabel(f"v{VERSION}  ·  GAME ACTIVATION")
        ver.setObjectName("dim")
        title = QLabel("ENTER YOUR GAME KEY")
        title.setStyleSheet(f"color:{COLORS['white']}; font-size: 22px; font-weight:bold; letter-spacing: 5px;")
        info = QLabel("NEXUS needs a game key. You get yours from the staff on our Discord server.\n"
                      "You need an internet connection once to activate; after that you can play offline.")
        info.setObjectName("dim")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setWordWrap(True)
        info.setFixedWidth(520)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("NX-XXXXX-XXXXX-XXXXX")
        self.edit.setMaxLength(40)
        self.edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.edit.setFixedWidth(420)
        self.edit.returnPressed.connect(self._activate)
        self.button = NeonButton("[ ACTIVATE ]", "Check the key on the NEXUS server and activate the game", "cyan")
        self.button.setFixedWidth(420)
        self.button.clicked.connect(self._activate)
        self.notice = QLabel("")
        self.notice.setWordWrap(True)
        self.notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.notice.setFixedWidth(520)
        for w in (logo, ver):
            w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(w, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(18)
        lay.addWidget(title, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(info, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(10)
        lay.addWidget(self.edit, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.button, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.notice, 0, Qt.AlignmentFlag.AlignHCenter)
        if DISCORD_URL:
            join = NeonButton("GET A KEY ON DISCORD", "Opens our Discord invite in your browser")
            join.setFixedWidth(420)
            join.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(DISCORD_URL)))
            lay.addSpacing(10)
            lay.addWidget(join, 0, Qt.AlignmentFlag.AlignHCenter)

    # --------------------------------------------------------------- flow --
    def start(self, message: str = "", auto: bool = False) -> None:
        """Show the screen. ``auto`` = try to renew with the stored key right away (an expired licence that only needs a connection)."""
        self.edit.setText(self.settings.get("license_key") or "")
        self._base = message if auto else ""            # an automatic renewal that fails keeps the reason it was needed
        self._say(message, "dim")
        self.edit.setFocus()
        if auto and self.edit.text().strip():
            self._activate()

    def _say(self, text: str, kind: str) -> None:
        color = {"ok": COLORS["green"], "error": COLORS["red"], "dim": COLORS["dim"]}[kind]
        self.notice.setStyleSheet(f"color:{color}; background:transparent;")
        self.notice.setText(text)

    def _busy(self, busy: bool) -> None:
        self.button.setEnabled(not busy)
        self.edit.setEnabled(not busy)

    def _activate(self) -> None:
        key = self.edit.text().strip()
        if not key:
            self._say("Enter your game key first.", "error")
            return
        if self._job is not None:
            return
        self._busy(True)
        self._say("Checking the key with the NEXUS server...", "dim")
        job = Job(lambda: self.client.activate_license(key), self)
        job.done.connect(lambda token: self._done(token, key))
        job.failed.connect(self._failed)
        job.refused.connect(self._failed)
        job.finished.connect(self._finished)
        self._job = job
        job.start()

    def _finished(self) -> None:
        self._job = None
        self._busy(False)

    def _done(self, token: str, key: str) -> None:
        status = license.store(self.settings, token, key)
        if not status.ok:
            self._say(status.message or "The server's answer could not be verified.", "error")
            return
        self._say("Key accepted. NEXUS is activated.", "ok")
        self.activated.emit()

    def _failed(self, message: str) -> None:
        self._say(f"{self._base}\n{message}" if self._base else message, "error")
        self._base = ""
