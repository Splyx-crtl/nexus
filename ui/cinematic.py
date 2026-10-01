"""Full-screen story screens: loading/boot sequence, intro and endings."""
from __future__ import annotations

import html

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from nexus.config import COLORS

from .widgets import NeonBar, mono_font, play


class CinematicScreen(QWidget):
    """Typed story text. SPACE/ENTER/click = next line, ESC = skip all."""

    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.lines: list[str] = []
        self.idx = 0
        self.chars = 0
        self.speed = 2
        self._all_shown = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(80, 60, 80, 40)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title = QLabel("")
        self.title.setObjectName("h1")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet(f"color:{COLORS['green']}; font-size: 34px; font-weight: bold; letter-spacing: 8px;")
        self.sub = QLabel("")
        self.sub.setObjectName("dim")
        self.sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body = QLabel("")
        self.body.setWordWrap(True)
        self.body.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.body.setFont(mono_font(17))
        self.body.setFixedWidth(820)
        self.body.setMinimumHeight(260)
        self.hint = QLabel("[SPACE] next   ·   [ESC] skip")
        self.hint.setObjectName("dim")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for w in (self.title, self.sub, self.body, self.hint):
            lay.addWidget(w, 0, Qt.AlignmentFlag.AlignHCenter)
        self.timer = QTimer(self, interval=28)
        self.timer.timeout.connect(self._tick)

    def play(self, title: str, subtitle: str, lines: list[str], speed: int = 2) -> None:
        self.title.setText(title)
        self.sub.setText(subtitle)
        self.lines, self.idx, self.chars, self.speed = lines, 0, 0, speed
        self._all_shown = False
        self.hint.setText("[SPACE] next   ·   [ESC] skip")
        self.body.setText("")
        self.timer.start()
        self.setFocus()

    def _render(self) -> None:
        shown = []
        for i, line in enumerate(self.lines[: self.idx + 1]):
            text = line if i < self.idx else line[: self.chars]
            color = COLORS["text"] if i < self.idx else COLORS["white"]
            shown.append(f'<p style="color:{color}; margin-bottom:8px">{html.escape(text)}</p>')
        self.body.setText("".join(shown[-6:]))

    def _tick(self) -> None:
        if self._all_shown or self.idx >= len(self.lines):
            return
        line = self.lines[self.idx]
        if self.chars < len(line):
            self.chars += self.speed
            if self.chars % 6 < self.speed:
                play("type")
        self._render()

    def _advance(self) -> None:
        if self._all_shown:
            self._end()
            return
        line = self.lines[self.idx]
        if self.chars < len(line):
            self.chars = len(line)
        elif self.idx + 1 >= len(self.lines):
            self._all_shown = True
            self.hint.setText("[SPACE] continue")
        else:
            self.idx += 1
            self.chars = 0
        self._render()

    def _end(self) -> None:
        self.timer.stop()
        self.finished.emit()

    def mousePressEvent(self, _) -> None:
        self._advance()

    def keyPressEvent(self, ev) -> None:
        if ev.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._advance()
        elif ev.key() == Qt.Key.Key_Escape:
            self._end()


class LoadingScreen(QWidget):
    """Fake kernel boot sequence shown while a profile loads."""

    finished = Signal()
    STEPS = [
        "INITIALISING NEXUS KERNEL ................ OK",
        "LOADING VIRTUAL WORLD DATA ............... OK",
        "MOUNTING SIMULATED NETWORK 10.42.0.0/16 .. OK",
        "SANDBOX CHECK: NO EXTERNAL ROUTES ........ OK",
        "RESTORING OPERATOR PROFILE ............... OK",
        "CALIBRATING TERMINAL ..................... OK",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title = QLabel("NEXUS // BOOT")
        self.title.setObjectName("h1")
        self.log = QLabel("")
        self.log.setFont(mono_font(13))
        self.log.setStyleSheet(f"color:{COLORS['green']};")
        self.bar = NeonBar(COLORS["green"], 30, 14)
        self.bar.setFixedWidth(520)
        for w in (self.title, self.log, self.bar):
            lay.addWidget(w, 0, Qt.AlignmentFlag.AlignHCenter)
        self.step = 0
        self.timer = QTimer(self, interval=170)
        self.timer.timeout.connect(self._tick)

    def start(self) -> None:
        self.step = 0
        self.log.setText("")
        self.bar.set_value(0, len(self.STEPS))
        play("boot")
        self.timer.start()

    def _tick(self) -> None:
        self.step += 1
        self.log.setText("\n".join(self.STEPS[: self.step]))
        self.bar.set_value(self.step, len(self.STEPS))
        play("type")
        if self.step >= len(self.STEPS):
            self.timer.stop()
            QTimer.singleShot(250, self.finished.emit)

    def keyPressEvent(self, ev) -> None:
        if ev.key() in (Qt.Key.Key_Space, Qt.Key.Key_Escape, Qt.Key.Key_Return):
            self.timer.stop()
            self.finished.emit()
