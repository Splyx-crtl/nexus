"""First launch: boot sequence, system check, welcome and operator profile creation."""
from __future__ import annotations

import getpass

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from nexus.config import COLORS, VERSION
from nexus.i18n import tr
from nexus.security import sanitize_name

from .widgets import NeonBar, NeonButton, mono_font, play

CHECKS = [
    "KERNEL .......................... OK",
    "VIRTUAL NETWORK 10.42.0.0/16 .... OK",
    "SANDBOX: NO EXTERNAL ROUTES ..... OK",
    "SAVE DATABASE ................... OK",
    "AUDIO / DISPLAY ................. OK",
    "OPERATOR REGISTRY ............... EMPTY",
]


class FirstLaunchScreen(QWidget):
    created = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo = QLabel("NEXUS")
        self.logo.setStyleSheet(f"color:{COLORS['green']}; font-size: 54px; font-weight:bold; letter-spacing: 14px;")
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ver = QLabel(f"v{VERSION}  ·  TACTICAL CYBER OPERATIONS")
        self.ver.setObjectName("dim")
        self.ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status = QLabel("INITIALIZING...")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet(f"color:{COLORS['cyan']}; font-size: 16px; letter-spacing: 4px;")
        self.log = QLabel("")
        self.log.setFont(mono_font(12))
        self.log.setStyleSheet(f"color:{COLORS['green']};")
        self.log.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.log.setMinimumWidth(420)
        self.bar = NeonBar(COLORS["green"], 30, 16)
        self.bar.setFixedWidth(460)
        self.welcome = QLabel("")
        self.welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.welcome.setStyleSheet(f"color:{COLORS['white']}; font-size: 24px; font-weight:bold; letter-spacing: 5px;")
        self.form_title = QLabel(tr("create_profile"))
        self.form_title.setObjectName("h2")
        self.form_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.edit = QLineEdit(sanitize_name(getpass.getuser().upper()))
        self.edit.setMaxLength(20)
        self.edit.setFixedWidth(360)
        self.edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.edit.setPlaceholderText("Username")
        self.edit.setToolTip("Letters, digits, dash and underscore")
        self.btn = NeonButton(f"[ {tr('initialize')} ]", "Create your operator profile")
        self.btn.setFixedWidth(360)
        self.btn.clicked.connect(self._submit)
        self.edit.returnPressed.connect(self._submit)
        for w in (self.logo, self.ver, self.status):
            lay.addWidget(w, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(10)
        lay.addWidget(self.log, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.bar, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(10)
        lay.addWidget(self.welcome, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(14)
        for w in (self.form_title, self.edit, self.btn):
            lay.addWidget(w, 0, Qt.AlignmentFlag.AlignHCenter)
        self.step = 0
        self.timer = QTimer(self, interval=230)
        self.timer.timeout.connect(self._tick)

    def start(self) -> None:
        self.step = 0
        self.log.setText("")
        self.bar.set_value(0, len(CHECKS))
        self.welcome.setText("")
        self.status.setText("INITIALIZING...")
        for w in (self.form_title, self.edit, self.btn):
            w.hide()
        self.timer.start()
        play("boot")
        self.setFocus()

    def _tick(self) -> None:
        self.step += 1
        if self.step <= len(CHECKS):
            self.log.setText("\n".join(CHECKS[: self.step]))
            self.status.setText("SYSTEM CHECK")
            self.bar.set_value(self.step, len(CHECKS), f"{int(100 * self.step / len(CHECKS))}%")
            play("type")
        else:
            self.timer.stop()
            self._finish_boot()

    def _finish_boot(self) -> None:
        self.status.setText("SYSTEM CHECK COMPLETE")
        self.bar.set_value(len(CHECKS), len(CHECKS), "100%")
        self.welcome.setText(tr("welcome"))
        play("notify")
        for w in (self.form_title, self.edit, self.btn):
            w.show()
        self.edit.setFocus()
        self.edit.selectAll()

    def keyPressEvent(self, ev) -> None:
        if ev.key() in (Qt.Key.Key_Space, Qt.Key.Key_Escape) and self.timer.isActive():
            self.step = len(CHECKS)
            self.timer.stop()
            self.log.setText("\n".join(CHECKS))
            self._finish_boot()

    def _submit(self) -> None:
        name = sanitize_name(self.edit.text())
        self.created.emit(name)
