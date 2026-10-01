"""Update notice: background check + mandatory/optional update dialog that downloads and starts the installer."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QApplication, QLabel, QTextBrowser, QProgressBar

from nexus import updater
from nexus.config import COLORS, FROZEN
from nexus.version import GITHUB_REPO, UPDATE_REQUIRED, VERSION

from .dialogs import NeonDialog
from .widgets import NeonButton


class _CheckWorker(QThread):
    found = Signal(dict)

    def run(self) -> None:
        release = updater.check_for_update()
        if release:
            self.found.emit(release)


class _DownloadWorker(QThread):
    progress = Signal(int, int)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, release: dict):
        super().__init__()
        self.release = release

    def run(self) -> None:
        try:
            dest = Path(tempfile.gettempdir()) / "nexus_update" / self.release["name"]
            updater.download(self.release, dest, lambda d, t: self.progress.emit(d, t))
            self.done.emit(str(dest))
        except Exception as exc:                                   # network/checksum problems: show, keep playing
            self.failed.emit(str(exc))


class UpdateDialog(NeonDialog):
    def __init__(self, release: dict, parent=None, required: bool = UPDATE_REQUIRED):
        super().__init__("UPDATE AVAILABLE", parent, 560)
        self.release, self.required, self.worker = release, required, None
        head = QLabel(f"NEXUS {release['version']} is available  (you have {VERSION})")
        head.setObjectName("h2")
        self.lay.addWidget(head)
        notes = QTextBrowser()
        notes.setMaximumHeight(150)
        notes.setPlainText(release.get("notes") or "No release notes.")
        self.lay.addWidget(notes)
        text = "This update is required to keep playing." if required else "You can update now or later."
        self.info = QLabel(text + "\nYour saves are kept. The installer opens after the download.")
        self.info.setWordWrap(True)
        self.info.setObjectName("dim")
        self.lay.addWidget(self.info)
        self.bar = QProgressBar()
        self.bar.hide()
        self.lay.addWidget(self.bar)
        from PySide6.QtWidgets import QHBoxLayout
        row = QHBoxLayout()
        self.later = NeonButton("QUIT GAME" if required else "LATER", variant="danger")
        self.go = NeonButton("UPDATE NOW")
        self.later.clicked.connect(self._later)
        self.go.clicked.connect(self._start)
        row.addWidget(self.later)
        row.addStretch(1)
        row.addWidget(self.go)
        self.lay.addLayout(row)

    def keyPressEvent(self, ev) -> None:           # ESC must not dismiss a required update
        if not self.required:
            super().keyPressEvent(ev)

    def _later(self) -> None:
        if self.required:
            QApplication.quit()
        self.reject()

    def _start(self) -> None:
        self.go.setEnabled(False)
        self.later.setEnabled(False)
        self.bar.show()
        self.info.setText("Downloading...")
        self.worker = _DownloadWorker(self.release)
        self.worker.progress.connect(lambda d, t: (self.bar.setMaximum(max(t, 1)), self.bar.setValue(d)))
        self.worker.done.connect(self._launch)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def _failed(self, msg: str) -> None:
        self.info.setText(f"Download failed: {msg}\nCheck your connection and try again.")
        self.go.setEnabled(True)
        self.later.setEnabled(True)
        self.bar.hide()

    def _launch(self, path: str) -> None:
        self.info.setText("Starting the installer... NEXUS will close.")
        try:
            os.startfile(path)                          # runs the new NEXUS-Setup.exe (Windows)
        except (AttributeError, OSError):
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        QApplication.quit()


class UpdateManager(QObject):
    """Starts the background check once and shows the dialog if a newer release exists."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.worker: _CheckWorker | None = None

    def start(self) -> None:
        # Only installed builds check (development runs from source are never nagged); NEXUS_UPDATE_CHECK=1 forces it.
        if not GITHUB_REPO or not (FROZEN or os.environ.get("NEXUS_UPDATE_CHECK")):
            return
        self.worker = _CheckWorker()
        self.worker.found.connect(self._show)
        self.worker.start()

    def _show(self, release: dict) -> None:
        UpdateDialog(release, self.window).exec()
