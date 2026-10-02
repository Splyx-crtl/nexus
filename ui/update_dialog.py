"""Update notice: background check + mandatory/optional update dialog that downloads and starts the installer."""
from __future__ import annotations

import html
import os
import re
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QObject, QPointF, QPropertyAnimation, QRect, QRectF, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QTextBrowser, QVBoxLayout, QWidget

from nexus import updater
from nexus.config import COLORS, FROZEN
from nexus.version import GITHUB_REPO, UPDATE_REQUIRED, VERSION

from .widgets import NeonBar, NeonButton, mono_font


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


# ------------------------------------------------------------------ helpers
def notes_to_html(text: str) -> str:
    """Release notes (GitHub markdown subset: headings, bullets, **bold**, `code`) -> themed HTML. Input is escaped first."""
    green, cyan, dim, white = COLORS["green"], COLORS["cyan"], COLORS["dim"], COLORS["white"]

    def inline(s: str) -> str:
        s = html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", rf'<b style="color:{white}">\1</b>', s)
        return re.sub(r"`(.+?)`", rf'<span style="color:{cyan}">\1</span>', s)

    if not text.strip():
        return f'<div style="color:{dim}">No release notes.</div>'
    out: list[str] = []
    for raw in text.replace("\r", "").split("\n"):
        line = raw.rstrip()
        if not line.strip():
            out.append('<div style="font-size:5px">&nbsp;</div>')
        elif line.lstrip().startswith("#"):
            title = line.lstrip("# ").strip()
            out.append(f'<div style="color:{green}; font-weight:bold; letter-spacing:2px; margin-top:6px">{inline(title.upper())}</div>')
        elif re.match(r"\s*[-*•]\s+", line):
            body = re.sub(r"^\s*[-*•]\s+", "", line)
            out.append(f'<div style="margin-left:6px"><span style="color:{green}">&#9656;</span> {inline(body)}</div>')
        else:
            out.append(f'<div style="color:{dim}">{inline(line)}</div>')
    return "".join(out)


def format_bytes(n: float) -> str:
    return f"{n / 1_048_576:.1f} MB" if n >= 1_048_576 else f"{n / 1024:.0f} KB"


class VersionHero(QWidget):
    """Old version -> animated chevrons -> new version, big and glowing."""

    def __init__(self, old: str, new: str, parent=None):
        super().__init__(parent)
        self.old, self.new = old, new
        self.speed = 1.0
        self._phase = 0.0
        self.setFixedHeight(118)
        self._timer = QTimer(self, interval=60)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self) -> None:
        if self.isVisible():
            self._phase = (self._phase + 0.09 * self.speed) % 1.0
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        green, cyan = QColor(COLORS["green"]), QColor(COLORS["cyan"])
        p.save()                                                        # flattened radial glow that fades out inside the widget
        p.translate(w * 0.74, h * 0.5)
        p.scale(1.0, h * 0.5 / (w * 0.24))
        glow = QRadialGradient(QPointF(0, 0), w * 0.24)
        glow.setColorAt(0, QColor(green.red(), green.green(), green.blue(), 60))
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(QRectF(-w * 0.24, -w * 0.24, w * 0.48, w * 0.48), glow)
        p.restore()

        p.setFont(mono_font(11))
        p.setPen(QColor(COLORS["dim"]))
        p.drawText(QRectF(0, 6, w * 0.4, 18), Qt.AlignmentFlag.AlignCenter, "INSTALLED")
        p.setPen(QColor(COLORS["green_dim"]))
        p.drawText(QRectF(w * 0.5, 6, w * 0.5, 18), Qt.AlignmentFlag.AlignCenter, "NEW BUILD")

        f = mono_font(34, True)
        p.setFont(f)
        p.setPen(QColor(COLORS["dim"]))
        p.drawText(QRectF(0, 26, w * 0.4, 70), Qt.AlignmentFlag.AlignCenter, self.old)
        for spread, alpha in ((4, 28), (2, 50)):                       # cheap glow behind the new version
            p.setPen(QColor(green.red(), green.green(), green.blue(), alpha))
            for ox, oy in ((-spread, 0), (spread, 0), (0, -spread), (0, spread)):
                p.drawText(QRectF(w * 0.5 + ox, 26 + oy, w * 0.5, 70), Qt.AlignmentFlag.AlignCenter, self.new)
        p.setPen(green)
        p.drawText(QRectF(w * 0.5, 26, w * 0.5, 70), Qt.AlignmentFlag.AlignCenter, self.new)

        cx, cy = w * 0.455, 62.0                                        # three chevrons that light up in sequence
        for i in range(3):
            lit = (self._phase * 3 - i) % 3
            alpha = int(255 * max(0.18, 1 - lit / 1.6)) if lit < 1.6 else 46
            p.setPen(QPen(QColor(cyan.red(), cyan.green(), cyan.blue(), alpha), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            x = cx + (i - 1) * 16
            p.drawLine(QPointF(x - 5, cy - 11), QPointF(x + 3, cy))
            p.drawLine(QPointF(x + 3, cy), QPointF(x - 5, cy + 11))


class Badge(QLabel):
    def __init__(self, text: str, color: str, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(f"color:{color}; border:1px solid {color}; padding: 2px 10px; font-weight:bold; letter-spacing:3px;"
                           "background:transparent;")


class UpdateDialog(QDialog):
    """Frameless neon window: version hero, formatted notes, staged progress (download -> verify -> installer)."""

    def __init__(self, release: dict, parent=None, required: bool = UPDATE_REQUIRED):
        super().__init__(parent)
        self.release, self.required, self.worker = release, required, None
        self._t0 = 0.0
        self._grid: QPixmap | None = None
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setModal(True)
        self.setMinimumWidth(640)
        accent = COLORS["red"] if required else COLORS["cyan"]
        self.accent = accent

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 22)
        lay.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("// SYSTEM UPDATE")
        title.setStyleSheet(f"color:{COLORS['green']}; font-size:20px; font-weight:bold; letter-spacing:5px; background:transparent;")
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(Badge("REQUIRED" if required else "OPTIONAL", accent))
        lay.addLayout(head)

        self.hero = VersionHero(VERSION, release["version"])
        lay.addWidget(self.hero)

        log_title = QLabel("WHAT'S NEW")
        log_title.setStyleSheet(f"color:{COLORS['dim']}; letter-spacing:4px; font-size:10px; background:transparent;")
        lay.addWidget(log_title)
        notes = QTextBrowser()
        notes.setMinimumHeight(120)
        notes.setMaximumHeight(190)
        notes.setOpenLinks(False)
        notes.setStyleSheet(f"QTextBrowser {{ background:{COLORS['bg_alt']}; border:1px solid {COLORS['border']}; padding:8px 10px; }}")
        notes.setHtml(notes_to_html(release.get("notes") or ""))
        lay.addWidget(notes)
        self.notes = notes

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color:{COLORS['text']}; background:transparent;")
        lay.addWidget(self.status)
        self.stats = QLabel("")
        self.stats.setStyleSheet(f"color:{COLORS['dim']}; font-size:11px; background:transparent;")
        lay.addWidget(self.stats)
        self.bar = NeonBar(COLORS["green"], 40, 18)
        lay.addWidget(self.bar)
        self.stats.hide()
        self.bar.hide()
        self._idle_text()

        row = QHBoxLayout()
        self.later = NeonButton("QUIT GAME" if required else "LATER", variant="danger")
        self.go = NeonButton("▶  UPDATE NOW")
        self.go.setMinimumHeight(40)
        self.go.setMinimumWidth(190)
        self.go.setDefault(True)
        self.later.clicked.connect(self._later)
        self.go.clicked.connect(self._start)
        row.addWidget(self.later)
        row.addStretch(1)
        row.addWidget(self.go)
        lay.addLayout(row)

        self.setWindowOpacity(0.0)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(260)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)

    def showEvent(self, ev) -> None:
        super().showEvent(ev)
        self._fade.start()

    # ------------------------------------------------------------ painting
    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(COLORS["bg"]))
        if self._grid is None or self._grid.size() != self.size():            # faint grid, rendered once per size
            grid = QPixmap(self.size())
            grid.fill(Qt.GlobalColor.transparent)
            gp = QPainter(grid)
            gp.setPen(QColor(255, 255, 255, 7))
            for x in range(0, w, 28):
                gp.drawLine(x, 0, x, h)
            for y in range(0, h, 28):
                gp.drawLine(0, y, w, y)
            gp.end()
            self._grid = grid
        p.drawPixmap(0, 0, self._grid)
        top = QLinearGradient(0, 0, 0, 110)
        g = QColor(COLORS["green"])
        top.setColorAt(0, QColor(g.red(), g.green(), g.blue(), 36))
        top.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(QRect(0, 0, w, 110), top)
        p.setPen(QPen(QColor(COLORS["green"]), 2))
        p.drawRect(1, 1, w - 3, h - 3)
        acc = QColor(self.accent)
        p.setPen(QPen(acc, 3))
        s = 18
        for x, y, dx, dy in ((2, 2, 1, 1), (w - 3, 2, -1, 1), (2, h - 3, 1, -1), (w - 3, h - 3, -1, -1)):
            p.drawLine(x, y, x + dx * s, y)
            p.drawLine(x, y, x, y + dy * s)

    # --------------------------------------------------------------- logic
    def _idle_text(self) -> None:
        why = "This update is required to keep playing." if self.required else "You can update now or later."
        self.status.setStyleSheet(f"color:{COLORS['text']}; background:transparent;")
        self.status.setText(f"{why}\nYour saves are kept. The installer opens after the download.")

    def keyPressEvent(self, ev) -> None:           # ESC must not dismiss a required update
        if ev.key() == Qt.Key.Key_Escape:
            if not self.required and self.later.isEnabled():
                self.reject()
            return
        super().keyPressEvent(ev)

    def _later(self) -> None:
        if self.required:
            QApplication.quit()
        self.reject()

    def _start(self) -> None:
        self.go.setEnabled(False)
        self.later.setEnabled(False)
        self.hero.speed = 3.0
        self.bar.set_color(COLORS["green"])
        self.bar.set_value(0, 1, "0%")
        self.bar.show()
        self.stats.show()
        self.stats.setText("connecting...")
        self.status.setStyleSheet(f"color:{COLORS['green']}; font-weight:bold; letter-spacing:2px; background:transparent;")
        self.status.setText("[1/3]  DOWNLOADING INSTALLER")
        self._t0 = time.monotonic()
        self.worker = _DownloadWorker(self.release)
        self.worker.progress.connect(self._on_progress)
        self.worker.done.connect(self._launch)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def _on_progress(self, done: int, total: int) -> None:
        elapsed = max(0.001, time.monotonic() - self._t0)
        rate = done / elapsed
        if total > 0:
            pct = int(done * 100 / total)
            self.bar.set_value(done, total, f"{pct}%")
            eta = (total - done) / rate if rate else 0
            self.stats.setText(f"{format_bytes(done)} / {format_bytes(total)}   ·   {format_bytes(rate)}/s   ·   ETA {eta:0.0f}s")
            if done >= total:
                self.status.setText("[2/3]  VERIFYING CHECKSUM")
        else:
            self.bar.set_value(done % 1000, 1000, "")
            self.stats.setText(f"{format_bytes(done)}   ·   {format_bytes(rate)}/s")

    def _failed(self, msg: str) -> None:
        self.hero.speed = 1.0
        self.status.setStyleSheet(f"color:{COLORS['red']}; font-weight:bold; background:transparent;")
        self.status.setText(f"UPDATE FAILED\n{msg}\nCheck your connection and try again.")
        self.stats.hide()
        self.bar.hide()
        self.go.setText("↻  TRY AGAIN")
        self.go.setEnabled(True)
        self.later.setEnabled(True)

    def _launch(self, path: str) -> None:
        self.bar.set_value(1, 1, "100%")
        self.status.setText("[3/3]  STARTING INSTALLER ... NEXUS WILL CLOSE")
        self.stats.setText("your saves stay untouched")
        try:
            os.startfile(path)                          # runs the new NEXUS-Setup.exe (Windows)
        except (AttributeError, OSError):
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        QTimer.singleShot(900, QApplication.quit)       # let the player read the last stage


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
