"""Mini-game dialogs: firewall, encryption, routing, access code and trace.

Every dialog is modal, owns its own UI and returns ``result_data`` (a dict
with at least ``success``). The game logic lives in nexus/minigames.py.
"""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QSlider, QTextBrowser, QVBoxLayout, QWidget)

from nexus.config import COLORS
from nexus.minigames import SYMBOLS, AccessPuzzle, EncryptionPuzzle, FirewallPuzzle, RoutingPuzzle, TraceConfig

from .widgets import NeonBar, NeonButton, hline, mono_font, play

SYMBOL_COLORS = [COLORS["green"], COLORS["cyan"], COLORS["amber"], COLORS["red"], COLORS["purple"], "#e8fff4", "#ff8bd0", "#8aff6b"]


_tip_get = lambda: []          # noqa: E731  (replaced by the main window with the settings store)
_tip_set = lambda tips: None   # noqa: E731


def set_tip_store(getter, setter) -> None:
    global _tip_get, _tip_set
    _tip_get, _tip_set = getter, setter


TIPS = {
    "firewall": "HOW TO PLAY: pick symbols for every slot and press SUBMIT. ● means right symbol in the right slot, ○ means right symbol in the wrong slot. Use the feedback to deduce the code before you run out of attempts.",
    "encryption": "HOW TO PLAY: change the key (shift or keyword) until the PLAINTEXT PREVIEW turns into readable text, then press CONFIRM. Stuck? HINT reveals a clue.",
    "routing": "HOW TO PLAY: click neighbouring relays to build a chain from YOU to the target. Keep the total risk inside the budget and don't use too many hops. Click the last relay again to undo.",
    "access": "HOW TO PLAY: read all clues, combine them to deduce the code, enter it on the keypad. The scratch pad is for your notes. Wrong tries raise the alarm.",
    "trace": "HOW TO PLAY: packets race across the stream. Click only the glowing ▶ TARGET packet. Clicking a decoy or letting the target escape costs a life.",
}


class MinigameDialog(QDialog):
    """Frameless neon dialog shell shared by all mini-games."""

    def __init__(self, parent: QWidget, title: str, subtitle: str = "", accent: str = COLORS["green"]):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setModal(True)
        self.accent = accent
        self.result_data: dict = {"success": False}
        self._done = False
        self.setStyleSheet(f"MinigameDialog {{ background:{COLORS['bg']}; border: 2px solid {accent}; }}")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(8)
        head = QHBoxLayout()
        self.title = QLabel(title)
        self.title.setObjectName("h1")
        self.title.setStyleSheet(f"color:{accent}; font-size: 20px; font-weight: bold; letter-spacing: 3px;")
        head.addWidget(self.title, 1)
        self.abort_btn = NeonButton("ABORT [ESC]", "Abandon the attempt", "danger")
        self.abort_btn.clicked.connect(self.abort)
        head.addWidget(self.abort_btn)
        outer.addLayout(head)
        self.subtitle = QLabel(subtitle)
        self.subtitle.setObjectName("dim")
        self.subtitle.setWordWrap(True)
        outer.addWidget(self.subtitle)
        outer.addWidget(hline())
        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        outer.addLayout(self.body, 1)
        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet("font-size: 15px; font-weight: bold;")
        outer.addWidget(self.status)
        self.tip_key = type(self).__name__.replace("Dialog", "").lower()
        self._maybe_tip(outer)
        parent_w = parent.window() if parent else None
        if parent_w:
            self.resize(min(parent_w.width() - 80, 860), min(parent_w.height() - 60, 660))

    def _maybe_tip(self, outer) -> None:
        """First time a mini-game opens, show a short how-to with a GOT IT button."""
        seen = _tip_get()
        if self.tip_key not in TIPS or self.tip_key in seen:
            return
        bar = QFrame()
        bar.setStyleSheet(f"QFrame {{ background:{COLORS['panel_hi']}; border:1px solid {COLORS['amber']}; }}")
        row = QHBoxLayout(bar)
        text = QLabel(TIPS[self.tip_key])
        text.setWordWrap(True)
        text.setStyleSheet(f"color:{COLORS['amber']}; border: none;")
        ok = NeonButton("GOT IT", "Hide this tip")
        row.addWidget(text, 1)
        row.addWidget(ok)

        def dismiss():
            bar.hide()
            _tip_set(_tip_get() + [self.tip_key])

        ok.clicked.connect(dismiss)
        outer.insertWidget(3, bar)

    def showEvent(self, ev) -> None:
        super().showEvent(ev)
        parent = self.parentWidget().window() if self.parentWidget() else None
        if parent:
            geo = parent.geometry()
            self.move(geo.x() + (geo.width() - self.width()) // 2, geo.y() + (geo.height() - self.height()) // 2)

    def message(self, text: str, color: str = COLORS["amber"]) -> None:
        self.status.setText(text)
        self.status.setStyleSheet(f"font-size: 15px; font-weight: bold; color:{color};")

    def finish(self, success: bool, text: str = "", **extra) -> None:
        if self._done:
            return
        self._done = True
        self.result_data = {"success": success, **extra}
        self.message(text or ("SUCCESS" if success else "FAILED"), COLORS["green"] if success else COLORS["red"])
        play("complete" if success else "error")
        for child in self.findChildren(NeonButton):
            if child is not self.abort_btn:
                child.setEnabled(False)
        QTimer.singleShot(1300, self.accept)

    def abort(self) -> None:
        if not self._done:
            self._done = True
            self.result_data = {"success": False, "aborted": True, **{k: v for k, v in self.result_data.items() if k != "success"}}
        self.reject()

    def keyPressEvent(self, ev) -> None:
        if ev.key() == Qt.Key.Key_Escape:
            self.abort()
        else:
            super().keyPressEvent(ev)


# =====================================================================
# A) Firewall
# =====================================================================
class FirewallDialog(MinigameDialog):
    def __init__(self, parent, puzzle: FirewallPuzzle):
        super().__init__(parent, f"FIREWALL // {puzzle.name}", "Deduce the symbol combination.  ● right symbol, right slot   ○ right symbol, wrong slot", COLORS["green"])
        self.p = puzzle
        self.cursor = 0
        self.current: list[int | None] = [None] * puzzle.length
        self.locked = dict(puzzle.revealed)
        for idx, sym in self.locked.items():
            self.current[idx] = sym
        self.failed_guesses = 0
        self.result_data = {"success": False, "failed_guesses": 0}

        self.attempts = NeonBar(COLORS["amber"], puzzle.max_attempts, 12)
        self.body.addWidget(QLabel("ATTEMPTS REMAINING"))
        self.body.addWidget(self.attempts)

        self.slots: list[NeonButton] = []
        row = QHBoxLayout()
        row.addStretch(1)
        for i in range(puzzle.length):
            b = NeonButton("", "Click to select this slot")
            b.setFixedSize(64, 64)
            b.clicked.connect(lambda _=False, n=i: self._select(n))
            self.slots.append(b)
            row.addWidget(b)
        row.addStretch(1)
        self.body.addLayout(row)

        pal = QHBoxLayout()
        pal.addStretch(1)
        for s in range(puzzle.symbols):
            b = NeonButton(SYMBOLS[s], f"Place symbol (key {s + 1})")
            b.setFixedSize(52, 52)
            b.setStyleSheet(f"font-size: 24px; color:{SYMBOL_COLORS[s]};")
            b.clicked.connect(lambda _=False, sym=s: self._place(sym))
            pal.addWidget(b)
        pal.addStretch(1)
        self.body.addLayout(pal)

        ctl = QHBoxLayout()
        ctl.addStretch(1)
        self.back_btn = NeonButton("⌫ BACK", "Remove the last symbol (Backspace)", "cyan")
        self.clear_btn = NeonButton("CLEAR", "Clear all slots", "cyan")
        self.submit_btn = NeonButton("▶ SUBMIT [ENTER]", "Test this combination")
        self.back_btn.clicked.connect(self._back)
        self.clear_btn.clicked.connect(self._clear)
        self.submit_btn.clicked.connect(self._submit)
        for b in (self.back_btn, self.clear_btn, self.submit_btn):
            ctl.addWidget(b)
        ctl.addStretch(1)
        self.body.addLayout(ctl)

        self.history = QTextBrowser()
        self.history.setStyleSheet(f"background:{COLORS['bg_alt']}; border: 1px solid {COLORS['border']}; font-size: 16px;")
        self.body.addWidget(self.history, 1)
        if self.locked:
            self.message("A symbol was revealed by FIREWALL ANALYSIS.", COLORS["cyan"])
        self._refresh()

    def _refresh(self) -> None:
        self.attempts.set_value(self.p.attempts_left, self.p.max_attempts, f"{self.p.attempts_left} / {self.p.max_attempts}")
        for i, b in enumerate(self.slots):
            sym = self.current[i]
            border = COLORS["amber"] if i == self.cursor else (COLORS["cyan"] if i in self.locked else COLORS["green_dim"])
            color = SYMBOL_COLORS[sym] if sym is not None else COLORS["dim"]
            b.setText(SYMBOLS[sym] if sym is not None else "·")
            b.setStyleSheet(f"font-size: 30px; color:{color}; border: 2px solid {border};")

    def _select(self, i: int) -> None:
        if i not in self.locked:
            self.cursor = i
            self._refresh()

    def _next_free(self, start: int) -> int:
        for k in range(self.p.length):
            idx = (start + k) % self.p.length
            if idx not in self.locked and self.current[idx] is None:
                return idx
        return start % self.p.length

    def _place(self, sym: int) -> None:
        if self._done:
            return
        if self.cursor in self.locked:
            self.cursor = self._next_free(self.cursor)
        self.current[self.cursor] = sym
        play("click")
        self.cursor = self._next_free(self.cursor + 1)
        self._refresh()

    def _back(self) -> None:
        for i in range(self.p.length - 1, -1, -1):
            if i not in self.locked and self.current[i] is not None:
                self.current[i] = None
                self.cursor = i
                break
        self._refresh()

    def _clear(self) -> None:
        self.current = [self.locked.get(i) for i in range(self.p.length)]
        self.cursor = self._next_free(0)
        self._refresh()

    def _submit(self) -> None:
        if self._done:
            return
        if any(s is None for s in self.current):
            self.message("Fill every slot first.", COLORS["amber"])
            play("error")
            return
        guess = [int(s) for s in self.current]
        exact, misplaced = self.p.guess(guess)
        pegs = f'<span style="color:{COLORS["green"]}">' + "● " * exact + "</span>" + f'<span style="color:{COLORS["amber"]}">' + "○ " * misplaced + "</span>"
        syms = " ".join(f'<span style="color:{SYMBOL_COLORS[s]}">{SYMBOLS[s]}</span>' for s in guess)
        self.history.append(f'<p>#{len(self.p.history)} &nbsp; {syms} &nbsp;&nbsp; {pegs or "<span style=color:#4b7a6c>— no match —</span>"}</p>')
        if self.p.solved:
            self._refresh()
            self.finish(True, "FIREWALL BREACHED", failed_guesses=self.failed_guesses)
            return
        self.failed_guesses += 1
        self.result_data["failed_guesses"] = self.failed_guesses
        play("error")
        if self.p.failed:
            secret = " ".join(SYMBOLS[s] for s in self.p.secret)
            self._refresh()
            self.finish(False, f"FIREWALL HELD — the code was {secret}", failed_guesses=self.failed_guesses)
            return
        self._clear()

    def keyPressEvent(self, ev) -> None:
        key = ev.key()
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_8 and key - Qt.Key.Key_1 < self.p.symbols:
            self._place(key - Qt.Key.Key_1)
        elif key == Qt.Key.Key_Backspace:
            self._back()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._submit()
        elif key == Qt.Key.Key_Left:
            self._select((self.cursor - 1) % self.p.length)
        elif key == Qt.Key.Key_Right:
            self._select((self.cursor + 1) % self.p.length)
        else:
            super().keyPressEvent(ev)


# =====================================================================
# B) Encryption
# =====================================================================
class EncryptionDialog(MinigameDialog):
    MAX_TRIES = 5

    def __init__(self, parent, puzzle: EncryptionPuzzle):
        names = {"caesar": "CAESAR SHIFT", "atbash": "ATBASH MIRROR", "vigenere": "VIGENÈRE KEYWORD"}
        super().__init__(parent, f"DECRYPT // {puzzle.title}", f"Cipher detected: {names[puzzle.type]}. Find the key so the plaintext becomes readable, then confirm.", COLORS["cyan"])
        self.p = puzzle
        self.tries = 0
        self.free_left = puzzle.free_hints
        self.extra_hints = 0
        self.result_data = {"success": False, "extra_hints": 0}

        self.body.addWidget(QLabel("CIPHERTEXT"))
        self.cipher = QPlainTextEdit(puzzle.ciphertext)
        self.cipher.setReadOnly(True)
        self.cipher.setFont(mono_font(14, True))
        self.cipher.setStyleSheet(f"color:{COLORS['red']}; background:{COLORS['bg_alt']}; border:1px solid {COLORS['border']}; padding:8px;")
        self.cipher.setMaximumHeight(130)
        self.body.addWidget(self.cipher)

        self.key_row = QHBoxLayout()
        self.body.addLayout(self.key_row)
        self.key_input = None
        if puzzle.type == "caesar":
            self.key_row.addWidget(QLabel("SHIFT"))
            self.slider = QSlider(Qt.Orientation.Horizontal)
            self.slider.setRange(0, 25)
            self.slider.valueChanged.connect(self._update)
            self.value_label = QLabel("0")
            self.value_label.setMinimumWidth(30)
            self.key_row.addWidget(self.slider, 1)
            self.key_row.addWidget(self.value_label)
        elif puzzle.type == "vigenere":
            self.key_row.addWidget(QLabel("KEYWORD"))
            self.key_input = QLineEdit()
            self.key_input.setPlaceholderText("type the key word...")
            self.key_input.setMaxLength(16)
            self.key_input.textChanged.connect(self._update)
            self.key_row.addWidget(self.key_input, 1)
        else:
            self.key_row.addWidget(QLabel("Atbash maps A↔Z, B↔Y ... The mirror is applied automatically."))

        self.body.addWidget(QLabel("PLAINTEXT PREVIEW"))
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(mono_font(14, True))
        self.preview.setStyleSheet(f"color:{COLORS['green']}; background:{COLORS['bg_alt']}; border:1px solid {COLORS['border']}; padding:8px;")
        self.body.addWidget(self.preview, 1)

        self.hint_label = QLabel("")
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet(f"color:{COLORS['amber']};")
        self.body.addWidget(self.hint_label)

        row = QHBoxLayout()
        self.hint_btn = NeonButton("", "Reveal the next hint", "cyan")
        self.confirm_btn = NeonButton("✔ CONFIRM DECRYPTION", "Check if the preview is the real plaintext")
        self.hint_btn.clicked.connect(self._hint)
        self.confirm_btn.clicked.connect(self._confirm)
        row.addWidget(self.hint_btn)
        row.addStretch(1)
        self.tries_label = QLabel("")
        row.addWidget(self.tries_label)
        row.addWidget(self.confirm_btn)
        self.body.addLayout(row)
        self._hint_btn_text()
        self._update()
        if puzzle.free_hints:
            self._hint(free=True)    # ENCRYPTION KEY / DECRYPTION upgrade: first hint is on the house

    def _hint_btn_text(self) -> None:
        left = self.p.hints[self.p.hints_used:]
        if not left:
            self.hint_btn.setText("NO MORE HINTS")
            self.hint_btn.setEnabled(False)
        elif self.free_left > 0:
            self.hint_btn.setText(f"HINT ({self.free_left} free)")
        else:
            self.hint_btn.setText("HINT (+4% alert)")

    def _hint(self, free: bool = False) -> None:
        text = self.p.next_hint()
        if text is None:
            return
        if self.free_left > 0:
            self.free_left -= 1
        elif not free:
            self.extra_hints += 1
            self.result_data["extra_hints"] = self.extra_hints
        old = self.hint_label.text()
        self.hint_label.setText((old + "\n" if old else "") + f"HINT: {text}")
        self._hint_btn_text()

    def _key(self):
        if self.p.type == "caesar":
            return self.slider.value()
        if self.p.type == "vigenere":
            return self.key_input.text()
        return None

    def _update(self) -> None:
        if self.p.type == "caesar":
            self.value_label.setText(str(self.slider.value()))
        self.preview.setPlainText(self.p.decode_with(self._key()))

    def _confirm(self) -> None:
        if self._done:
            return
        self.tries += 1
        if self.p.check(self._key()):
            self.finish(True, "DECRYPTION SUCCESSFUL", extra_hints=self.extra_hints)
            return
        play("error")
        self.tries_label.setText(f"WRONG — {self.MAX_TRIES - self.tries} tries left")
        if self.tries >= self.MAX_TRIES:
            self.finish(False, "CIPHER LOCKED OUT", extra_hints=self.extra_hints)


# =====================================================================
# C) Routing
# =====================================================================
class RoutingCanvas(QWidget):
    path_changed = Signal()

    def __init__(self, puzzle: RoutingPuzzle):
        super().__init__()
        self.p = puzzle
        self.path = [puzzle.start]
        self.hover: int | None = None
        self.phase = 0.0
        self.setMouseTracking(True)
        self.setMinimumHeight(280)
        self.locked = False
        timer = QTimer(self, interval=50)
        timer.timeout.connect(self._tick)
        timer.start()

    def _tick(self) -> None:
        self.phase = (self.phase + 0.12) % (2 * math.pi)
        self.update()

    def _pt(self, node_id: int) -> QPointF:
        n = self.p.nodes[node_id]
        return QPointF(34 + n.x * (self.width() - 68), 28 + n.y * (self.height() - 56))

    def _hit(self, point: QPointF) -> int | None:
        for n in self.p.nodes:
            if (self._pt(n.id) - point).manhattanLength() < 24:
                return n.id
        return None

    def reset(self) -> None:
        self.path = [self.p.start]
        self.path_changed.emit()
        self.update()

    def mouseMoveEvent(self, ev) -> None:
        self.hover = self._hit(ev.position())
        self.setCursor(Qt.CursorShape.PointingHandCursor if self.hover is not None else Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, ev) -> None:
        if self.locked:
            return
        node = self._hit(ev.position())
        if node is None:
            return
        head = self.path[-1]
        if node == head and len(self.path) > 1:
            self.path.pop()
            play("click")
        elif node in self.path:
            return
        elif frozenset((head, node)) in self.p.edges:
            self.path.append(node)
            play("click")
        else:
            play("error")
            return
        self.path_changed.emit()
        self.update()

    def _risk_color(self, risk: int) -> QColor:
        return QColor([COLORS["green"], COLORS["cyan"], COLORS["amber"], COLORS["red"]][min(risk, 3)])

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(COLORS["bg_alt"]))
        head = self.path[-1]
        on_path = set(zip(self.path, self.path[1:]))
        for edge in self.p.edges:
            a, b = tuple(edge)
            used = (a, b) in on_path or (b, a) in on_path
            p.setPen(QPen(QColor(COLORS["green"] if used else COLORS["border"]), 3 if used else 1))
            p.drawLine(self._pt(a), self._pt(b))
        neighbors = set(self.p.neighbors(head))
        for n in self.p.nodes:
            pt = self._pt(n.id)
            visible = self.p.reveal or n.id in neighbors or n.id in self.path or n.id in (self.p.start, self.p.goal)
            color = self._risk_color(n.risk) if visible else QColor(COLORS["dim"])
            if n.id == self.p.goal:
                color = QColor(COLORS["purple"])
            if n.id == self.p.start:
                color = QColor(COLORS["cyan"])
            r = 15
            if n.id in self.path:
                p.setBrush(QColor(0, 255, 156, 55))
            else:
                p.setBrush(QColor(COLORS["bg"]))
            p.setPen(QPen(color, 2))
            p.drawEllipse(pt, r, r)
            if n.id == head:
                p.setPen(QPen(QColor(COLORS["amber"]), 1))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(pt, r + 5 + 2 * math.sin(self.phase), r + 5 + 2 * math.sin(self.phase))
            elif n.id in neighbors and n.id not in self.path:
                p.setPen(QPen(QColor(255, 255, 255, 60), 1, Qt.PenStyle.DashLine))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(pt, r + 5, r + 5)
            p.setPen(color)
            p.setFont(mono_font(10, True))
            symbol = "" if n.id in (self.p.start, self.p.goal) else (str(n.risk) if visible else "?")
            p.drawText(QRectF(pt.x() - r, pt.y() - r, 2 * r, 2 * r), Qt.AlignmentFlag.AlignCenter, symbol)
            p.setFont(mono_font(8))
            p.setPen(QColor(COLORS["text"]))
            p.drawText(QRectF(pt.x() - 40, pt.y() + r + 2, 80, 12), Qt.AlignmentFlag.AlignCenter, n.label if n.id not in (self.p.start, self.p.goal) else n.label)


class RoutingDialog(MinigameDialog):
    MAX_TRIES = 4

    def __init__(self, parent, puzzle: RoutingPuzzle):
        super().__init__(parent, f"ROUTING // {puzzle.target_name}", "Click adjacent relays to build a chain from YOU to the target. Numbers show each relay's detection risk (0 safe — 3 monitored). Click the last relay again to undo.", COLORS["purple"])
        self.p = puzzle
        self.tries = 0
        self.result_data = {"success": False}
        info = QHBoxLayout()
        self.risk_bar = NeonBar(COLORS["amber"], 20, 14)
        self.hops_label = QLabel("")
        info.addWidget(QLabel("RISK"))
        info.addWidget(self.risk_bar, 1)
        info.addSpacing(20)
        info.addWidget(self.hops_label)
        self.body.addLayout(info)
        self.canvas = RoutingCanvas(puzzle)
        self.canvas.path_changed.connect(self._update)
        self.body.addWidget(self.canvas, 1)
        row = QHBoxLayout()
        self.reset_btn = NeonButton("RESET", "Start the chain over", "cyan")
        self.go_btn = NeonButton("▶ ESTABLISH ROUTE", "Test the chain (path must reach the target)")
        self.reset_btn.clicked.connect(self.canvas.reset)
        self.go_btn.clicked.connect(self._go)
        row.addWidget(self.reset_btn)
        row.addStretch(1)
        self.tries_label = QLabel("")
        row.addWidget(self.tries_label)
        row.addWidget(self.go_btn)
        self.body.addLayout(row)
        self._update()

    def _update(self) -> None:
        risk = self.p.path_risk(self.canvas.path)
        color = COLORS["green"] if risk <= self.p.budget * 0.6 else COLORS["amber"] if risk <= self.p.budget else COLORS["red"]
        self.risk_bar.set_color(color)
        self.risk_bar.set_value(min(risk, self.p.budget * 1.5), self.p.budget * 1.5, f"{risk} / {self.p.budget}")
        hops = len(self.canvas.path) - 1
        self.hops_label.setText(f"HOPS {hops}/{self.p.max_hops}")
        self.hops_label.setStyleSheet(f"color:{COLORS['red'] if hops > self.p.max_hops else COLORS['text']};")
        if self.canvas.path[-1] == self.p.goal:
            self.message("Target reached — establish the route!", COLORS["green"])
        else:
            self.message("")

    def _go(self) -> None:
        if self._done:
            return
        ok, reason = self.p.validate(self.canvas.path)
        if ok:
            self.canvas.locked = True
            self.finish(True, reason)
            return
        self.tries += 1
        play("error")
        self.message(reason, COLORS["red"])
        self.tries_label.setText(f"{self.MAX_TRIES - self.tries} tries left")
        if self.tries >= self.MAX_TRIES:
            self.canvas.locked = True
            self.finish(False, "ROUTE COLLAPSED — detected")


# =====================================================================
# D) Access code
# =====================================================================
class AccessDialog(MinigameDialog):
    def __init__(self, parent, puzzle: AccessPuzzle):
        super().__init__(parent, f"ACCESS // {puzzle.title}", "Combine the intercepted clues and deduce the code. Every wrong try raises the alarm.", COLORS["amber"])
        self.p = puzzle
        self.entry = ""
        self.result_data = {"success": False}
        top = QHBoxLayout()
        clues = QVBoxLayout()
        clues.addWidget(QLabel("INTERCEPTED CLUES"))
        for i, clue in enumerate(puzzle.clues, 1):
            lab = QLabel(f"[{i}] {clue}")
            lab.setWordWrap(True)
            lab.setStyleSheet(f"color:{COLORS['cyan']}; padding: 3px 0;")
            clues.addWidget(lab)
        clues.addStretch(1)
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("scratch pad — jot down your deductions...")
        self.notes.setMaximumHeight(110)
        clues.addWidget(self.notes)
        top.addLayout(clues, 3)

        right = QVBoxLayout()
        self.display = QLabel("")
        self.display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.display.setStyleSheet(f"font-size: 34px; letter-spacing: 12px; color:{COLORS['green']}; border:1px solid {COLORS['green_dim']}; padding: 10px; background:{COLORS['bg_alt']};")
        right.addWidget(self.display)
        grid = QGridLayout()
        for i, key in enumerate(["1", "2", "3", "4", "5", "6", "7", "8", "9", "⌫", "0", "↵"]):
            b = NeonButton(key, "Keypad (you can also type on the keyboard)")
            b.setFixedHeight(44)
            b.clicked.connect(lambda _=False, k=key: self._key(k))
            grid.addWidget(b, i // 3, i % 3)
        right.addLayout(grid)
        self.attempts = NeonBar(COLORS["amber"], puzzle.max_attempts, 12)
        right.addWidget(QLabel("ATTEMPTS"))
        right.addWidget(self.attempts)
        self.feedback = QTextBrowser()
        self.feedback.setMaximumHeight(110)
        right.addWidget(self.feedback)
        top.addLayout(right, 2)
        self.body.addLayout(top, 1)
        self._refresh()

    def _refresh(self) -> None:
        self.display.setText(self.entry.ljust(self.p.length, "•"))
        self.attempts.set_value(self.p.attempts_left, self.p.max_attempts, f"{self.p.attempts_left} / {self.p.max_attempts}")

    def _key(self, key: str) -> None:
        if self._done:
            return
        if key == "⌫":
            self.entry = self.entry[:-1]
        elif key == "↵":
            self._submit()
            return
        elif key.isdigit() and len(self.entry) < self.p.length:
            self.entry += key
            play("click")
        self._refresh()

    def _submit(self) -> None:
        if len(self.entry) != self.p.length:
            self.message(f"Enter {self.p.length} digits.", COLORS["amber"])
            return
        solved, correct = self.p.check(self.entry)
        if solved:
            self._refresh()
            self.finish(True, "ACCESS GRANTED")
            return
        play("error")
        self.feedback.append(f"{self.entry}  →  {correct} digit(s) in the right place")
        self.entry = ""
        self._refresh()
        if self.p.attempts_left <= 0:
            self.finish(False, f"LOCKED OUT — the code was {self.p.code}")

    def keyPressEvent(self, ev) -> None:
        if self.notes.hasFocus():
            super().keyPressEvent(ev)
            return
        key = ev.key()
        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            self._key(chr(key))
        elif key == Qt.Key.Key_Backspace:
            self._key("⌫")
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._key("↵")
        else:
            super().keyPressEvent(ev)


# =====================================================================
# E) Trace
# =====================================================================
class TraceCanvas(QWidget):
    hit = Signal()
    miss = Signal(str)

    LANES = 6
    PKT_W, PKT_H = 84, 28

    def __init__(self, cfg: TraceConfig):
        super().__init__()
        self.cfg = cfg
        self.rng = random.Random()
        self.packets: list[dict] = []
        self.bursts: list[list[float]] = []
        self.phase = 0.0
        self.running = True
        self.setMinimumHeight(300)
        self.setMouseTracking(True)
        self.timer = QTimer(self, interval=16)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        for _ in range(cfg.decoys):
            self._spawn(initial=True)
        self._spawn(target=True, initial=True)

    def _label(self) -> str:
        return ":".join(f"{self.rng.randrange(256):02X}" for _ in range(3))

    def _lane_y(self, lane: int) -> float:
        return 18 + (lane + 0.5) * (self.height() - 36) / self.LANES

    def _spawn(self, target: bool = False, initial: bool = False) -> None:
        w = max(self.width(), 640)
        x = self.rng.uniform(-self.PKT_W, w * 0.7) if initial else -self.PKT_W - self.rng.uniform(0, 80)
        speed = self.rng.uniform(110, 210) * self.cfg.speed
        self.packets.append({"x": x, "lane": self.rng.randrange(self.LANES), "speed": speed, "label": self._label(),
                             "target": target, "dead": 0.0})

    def _tick(self) -> None:
        if not self.running:
            return
        dt = 0.016
        self.phase = (self.phase + dt * 6) % (2 * math.pi)
        for pk in list(self.packets):
            pk["x"] += pk["speed"] * dt
            if pk["dead"] > 0:
                pk["dead"] -= dt
                if pk["dead"] <= 0:
                    self.packets.remove(pk)
                continue
            if pk["x"] > self.width() + 10:
                self.packets.remove(pk)
                if pk["target"]:
                    self.miss.emit("TARGET ESCAPED")
                    self._spawn(target=True)
                else:
                    self._spawn()
        for b in list(self.bursts):
            b[2] += dt
            if b[2] > 0.5:
                self.bursts.remove(b)
        self.update()

    def mousePressEvent(self, ev) -> None:
        if not self.running:
            return
        pt = ev.position()
        for pk in reversed(self.packets):
            if pk["dead"] > 0:
                continue
            rect = QRectF(pk["x"], self._lane_y(pk["lane"]) - self.PKT_H / 2, self.PKT_W, self.PKT_H)
            if rect.contains(pt):
                self.bursts.append([rect.center().x(), rect.center().y(), 0.0])
                if pk["target"]:
                    pk["dead"] = 0.25
                    pk["target"] = False
                    self.hit.emit()
                    self._spawn(target=True)
                else:
                    self.miss.emit("WRONG PACKET")
                return

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(COLORS["bg_alt"]))
        p.setFont(mono_font(8))
        for lane in range(self.LANES):
            y = self._lane_y(lane)
            p.setPen(QPen(QColor(COLORS["border"]), 1, Qt.PenStyle.DotLine))
            p.drawLine(0, int(y), self.width(), int(y))
        p.setPen(QColor(15, 59, 51))
        for i in range(14):                                             # faint scrolling hex background
            p.drawText(int((i * 97 + self.phase * 40) % (self.width() + 80)) - 40, 14 + (i * 41) % max(40, self.height() - 20), f"{(i * 2654435761) & 0xFFFF:04X}")
        p.setFont(mono_font(9, True))
        for pk in self.packets:
            rect = QRectF(pk["x"], self._lane_y(pk["lane"]) - self.PKT_H / 2, self.PKT_W, self.PKT_H)
            if pk["dead"] > 0:
                p.setBrush(QColor(0, 255, 156, 90))
                p.setPen(QPen(QColor(COLORS["green"]), 2))
            elif pk["target"]:
                pulse = 0.6 + 0.4 * math.sin(self.phase)
                p.setBrush(QColor(34, 211, 238, int(60 + 60 * pulse)))
                p.setPen(QPen(QColor(COLORS["cyan"]), 2))
            else:
                p.setBrush(QColor(0, 255, 156, 14))
                p.setPen(QPen(QColor(COLORS["green_dim"]), 1))
            p.drawRoundedRect(rect, 3, 3)
            p.setPen(QColor(COLORS["white"] if pk["target"] else COLORS["green_dim"]))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, ("▶ " if pk["target"] else "") + pk["label"])
        for x, y, age in self.bursts:
            p.setPen(QPen(QColor(0, 255, 156, int(255 * (1 - age / 0.5))), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(x, y), 10 + age * 80, 10 + age * 80)


class TraceDialog(MinigameDialog):
    def __init__(self, parent, cfg: TraceConfig):
        super().__init__(parent, f"TRACE // {cfg.title}", "Packets are racing across the stream. Click the glowing ▶ TARGET packet before it escapes. Clicking decoys or letting it escape costs a life.", COLORS["cyan"])
        self.cfg = cfg
        self.hits = 0
        self.misses = 0
        self.result_data = {"success": False}
        row = QHBoxLayout()
        self.progress = NeonBar(COLORS["cyan"], cfg.required_hits, 14)
        self.lives = QLabel("")
        self.lives.setStyleSheet(f"color:{COLORS['red']}; font-size: 18px;")
        row.addWidget(QLabel("TRACE"))
        row.addWidget(self.progress, 1)
        row.addSpacing(20)
        row.addWidget(self.lives)
        self.body.addLayout(row)
        self.canvas = TraceCanvas(cfg)
        self.canvas.hit.connect(self._hit)
        self.canvas.miss.connect(self._miss)
        self.body.addWidget(self.canvas, 1)
        self._refresh()

    def _refresh(self) -> None:
        self.progress.set_value(self.hits, self.cfg.required_hits, f"{self.hits} / {self.cfg.required_hits}")
        left = self.cfg.max_misses - self.misses
        self.lives.setText("♥ " * max(0, left) + "♡ " * min(self.misses, self.cfg.max_misses))

    def _hit(self) -> None:
        self.hits += 1
        play("notify")
        self._refresh()
        if self.hits >= self.cfg.required_hits:
            self.canvas.running = False
            self.finish(True, "SIGNAL LOCKED — TRACE COMPLETE")

    def _miss(self, reason: str) -> None:
        if self._done:
            return
        self.misses += 1
        play("error")
        self.message(reason, COLORS["red"])
        self._refresh()
        if self.misses > self.cfg.max_misses:
            self.canvas.running = False
            self.finish(False, "TRACE LOST")


# =====================================================================
def run_minigame(parent: QWidget, kind: str, payload) -> dict:
    """Open the right dialog modally and return its result dict."""
    dialogs = {"firewall": FirewallDialog, "encryption": EncryptionDialog, "routing": RoutingDialog,
               "access": AccessDialog, "trace": TraceDialog}
    dialog = dialogs[kind](parent, payload)
    dialog.exec()
    return dialog.result_data
