"""The in-game terminal: renders command output, runs animations and prompts."""
from __future__ import annotations

import html
import os

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QTextEdit, QVBoxLayout, QWidget

from nexus.config import COLORS, STYLE_COLORS
from nexus.outputs import Banner, Fx, Minigame, Out, Progress, Prompt, Type, Wait

from .widgets import mono_font, play

LOGO = [
    "███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗",
    "████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝",
    "██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗",
    "██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║",
    "██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║",
    "╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝",
]
SPEED_MULT = [1.8, 1.3, 1.0, 0.55, 0.12]       # animation duration per text-speed setting 1..5
TYPE_CPS = [1, 2, 4, 8, 60]                    # characters per 16ms tick while typing


class TerminalInput(QLineEdit):
    """Line edit with history, TAB completion and skip hooks."""

    history_nav = Signal(int)
    tab_pressed = Signal()
    skip_pressed = Signal()
    clear_pressed = Signal()

    def keyPressEvent(self, ev: QKeyEvent) -> None:
        key = ev.key()
        if key == Qt.Key.Key_Up:
            self.history_nav.emit(-1)
        elif key == Qt.Key.Key_Down:
            self.history_nav.emit(1)
        elif key == Qt.Key.Key_Tab:
            self.tab_pressed.emit()
        elif key == Qt.Key.Key_L and ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.clear_pressed.emit()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space, Qt.Key.Key_Escape) and self.isReadOnly():
            self.skip_pressed.emit()
            if key == Qt.Key.Key_Escape:
                ev.ignore()
        else:
            super().keyPressEvent(ev)

    def focusNextPrevChild(self, _next: bool) -> bool:   # keep TAB for completion
        return False


class TerminalWidget(QWidget):
    fx_requested = Signal(str, object)
    command_finished = Signal()

    def __init__(self, engine, settings, parent=None):
        super().__init__(parent)
        self.engine, self.settings = engine, settings
        self.busy = False
        self.minigame_runner = lambda kind, payload: {"success": False}
        self.banner_cb = lambda kind, lines: None
        self._gen = None
        self._skip = False
        self._pending: list[tuple[str, str]] = []
        self._queue: list[str] = []
        self._prompt_mode = False
        self._hist_index = 0
        self._live_block = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.out = QTextEdit()
        self.out.setReadOnly(True)
        self.out.setFont(mono_font(self._font_size()))
        self.out.document().setMaximumBlockCount(3000)
        self.out.setFrameShape(QTextEdit.Shape.NoFrame)
        self.out.setCursorWidth(0)
        self.out.setStyleSheet(f"QTextEdit {{ background:{COLORS['bg']}; padding: 10px; }}")
        lay.addWidget(self.out, 1)

        row = QWidget()
        row.setStyleSheet(f"background:{COLORS['bg_alt']}; border-top: 1px solid {COLORS['border']};")
        rlay = QHBoxLayout(row)
        rlay.setContentsMargins(10, 4, 10, 4)
        self.prompt_label = QLabel()
        self.prompt_label.setFont(mono_font(self._font_size(), True))
        self.prompt_label.setStyleSheet(f"color:{COLORS['green']}; background:transparent;")
        self.input = TerminalInput()
        self.input.setFont(mono_font(self._font_size()))
        self.input.setStyleSheet("QLineEdit { border: none; background: transparent; color: %s; }" % COLORS["white"])
        self.input.setPlaceholderText("type 'help' ...")
        self.input.setToolTip("TAB: complete  ·  UP/DOWN: history  ·  ENTER/SPACE: skip animation  ·  Ctrl+L: clear")
        rlay.addWidget(self.prompt_label)
        rlay.addWidget(self.input, 1)
        lay.addWidget(row)

        self.input.returnPressed.connect(self._submit)
        self.input.history_nav.connect(self._navigate_history)
        self.input.tab_pressed.connect(self._complete)
        self.input.skip_pressed.connect(self._request_skip)
        self.input.clear_pressed.connect(self.clear)
        self.engine.async_line.connect(self._on_async)
        self.refresh_prompt()

    # ------------------------------------------------------------------ config
    def _font_size(self) -> int:
        return int(self.settings.get("font_size")) if self.settings else 12

    def apply_font_size(self) -> None:
        size = self._font_size()
        for w in (self.out, self.input):
            w.setFont(mono_font(size))
        self.prompt_label.setFont(mono_font(size, True))

    def _speed(self) -> int:
        return int(self.settings.get("text_speed")) if self.settings else 3

    def _duration(self, ms: int) -> int:
        """Scale an animation duration by text speed and the TERMINAL SPEED upgrade."""
        scaled = ms * SPEED_MULT[self._speed() - 1] * self.engine.player.anim_factor
        return max(1, int(scaled))

    def refresh_prompt(self) -> None:
        if not self._prompt_mode:
            self.prompt_label.setText(self.engine.prompt)

    def focus_input(self) -> None:
        self.input.setFocus()

    # ----------------------------------------------------------------- output
    def _span_html(self, text: str, style: str) -> str:
        color = STYLE_COLORS.get(style, STYLE_COLORS["normal"])
        weight = "font-weight:bold;" if style in ("title",) else ""
        return f'<span style="color:{color};{weight}">{html.escape(text)}</span>'

    def _line_html(self, text: str, style: str, spans=None) -> str:
        inner = "".join(self._span_html(t, s) for t, s in spans) if spans else self._span_html(text, style)
        return f'<div style="white-space:pre-wrap;">{inner or "&nbsp;"}</div>'

    def print_line(self, text: str = "", style: str = "normal", spans=None) -> None:
        self.out.append(self._line_html(text, style, spans))
        self._scroll_end()

    def _scroll_end(self) -> None:
        sb = self.out.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear(self) -> None:
        self.out.clear()

    def print_welcome(self) -> None:
        for line in LOGO:
            self.print_line(line, "accent")
        from nexus.version import AUTHOR, VERSION
        self.print_line(f"TACTICAL CYBER OPERATIONS  ·  v{VERSION}  ·  created by {AUTHOR}", "info")
        self.print_line("All systems are fictional. Nothing real is ever touched.", "dim")
        self.print_line("")
        self.print_line("Type 'help' for commands, 'tutorial' for the field manual, 'mission' for your orders.", "dim")
        self.print_line("")

    # ---- live (replaceable) last line
    def _live_set(self, html_text: str, new: bool = False) -> None:
        cursor = self.out.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if new or not self._live_block:
            self.out.append(html_text)
            self._live_block = True
        else:
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            cursor.insertHtml(html_text)
        self._scroll_end()

    # -------------------------------------------------------- async messages
    def _on_async(self, text: str, style: str) -> None:
        if self.busy:
            self._pending.append((text, style))
        else:
            self.print_line(text, style)

    def _flush_pending(self) -> None:
        pending, self._pending = self._pending, []
        for text, style in pending:
            self.print_line(text, style)

    # ------------------------------------------------------------- input
    def _submit(self) -> None:
        text = self.input.text()
        self.input.clear()
        if self._prompt_mode:
            self._answer_prompt(text)
            return
        if self.busy:
            return
        if text.strip():
            self.run_command(text)

    def run_command(self, line: str, echo: bool = True) -> None:
        if self.busy:
            self._queue.append(line)
            return
        if echo:
            self.print_line(spans=[(self.engine.prompt, "dim"), (line, "title")])
        self.busy = True
        self._skip = False
        self.input.setReadOnly(True)
        self._hist_index = len(self.engine.history) + 1
        self._gen = self.engine.commands.execute(line)
        self._step(None, first=True)

    def _finish(self) -> None:
        self._gen = None
        self.busy = False
        self._live_block = False
        self.input.setReadOnly(False)
        self.input.setEchoMode(QLineEdit.EchoMode.Normal)
        self._flush_pending()
        self.refresh_prompt()
        self.input.setFocus()
        self._hist_index = len(self.engine.history)
        self.command_finished.emit()
        if self._queue:
            QTimer.singleShot(50, lambda: self.run_command(self._queue.pop(0)))

    # ----------------------------------------------------- generator driver
    def _step(self, value=None, first: bool = False) -> None:
        while self._gen is not None:
            try:
                item = next(self._gen) if first else self._gen.send(value)
            except StopIteration:
                self._finish()
                return
            except Exception as exc:                       # defensive: keep the UI alive
                self.print_line(f"SYSTEM FAULT: {exc}", "err")
                self._finish()
                return
            first, value = False, None
            if isinstance(item, Out):
                self.print_line(item.text, item.style, item.spans)
                if item.style == "err":
                    play("error")
            elif isinstance(item, Wait):
                QTimer.singleShot(0 if self._skip else self._duration(item.ms), self._step)
                return
            elif isinstance(item, Progress):
                self._start_progress(item)
                return
            elif isinstance(item, Type):
                self._start_typing(item)
                return
            elif isinstance(item, Prompt):
                self._start_prompt(item)
                return
            elif isinstance(item, Minigame):
                value = self._run_minigame(item)
            elif isinstance(item, Banner):
                self.banner_cb(item.kind, item.lines)
            elif isinstance(item, Fx):
                self._handle_fx(item)

    def _run_minigame(self, item: Minigame) -> dict:
        self.engine.busy = True
        try:
            return self.minigame_runner(item.kind, item.payload) or {"success": False}
        finally:
            self.engine.busy = False

    def _handle_fx(self, fx: Fx) -> None:
        if fx.name == "clear":
            self.clear()
        elif fx.name == "glitch":
            play("glitch")
            self.fx_requested.emit("glitch", None)
        else:
            self.fx_requested.emit(fx.name, fx.arg)

    # ------------------------------------------------------------ progress
    def _start_progress(self, item: Progress) -> None:
        steps, state = 10, {"n": 0}
        total = self._duration(item.ms)
        interval = max(1, total // steps)

        def render(n: int) -> str:
            bar = "█" * n + "░" * (steps - n)
            return self._line_html(f"{item.label:<14} [{bar}] {n * 10:>3}%", item.style)

        def tick():
            if self._skip:
                state["n"] = steps
            else:
                state["n"] += 1
            self._live_set(render(state["n"]))
            if state["n"] >= steps:
                timer.stop()
                self._live_block = False
                if item.done:
                    self.print_line(item.done, "ok")
                QTimer.singleShot(0, self._step)

        timer = QTimer(self, interval=interval)
        timer.timeout.connect(tick)
        self._live_set(render(0), new=True)
        timer.start()

    # -------------------------------------------------------------- typing
    def _start_typing(self, item: Type) -> None:
        text, state = item.text, {"i": 0}
        per_tick = TYPE_CPS[self._speed() - 1]
        color = STYLE_COLORS.get(item.style, STYLE_COLORS["story"])
        self.out.append(self._line_html("", item.style))
        cursor = self.out.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        def tick():
            if self._skip:
                state["i"] = len(text)
            else:
                state["i"] = min(len(text), state["i"] + per_tick)
            cursor = self.out.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            cursor.insertHtml(self._line_html(text[:state["i"]], item.style))
            self._scroll_end()
            if state["i"] % 4 < per_tick and not self._skip:
                play("type")
            if state["i"] >= len(text):
                timer.stop()
                QTimer.singleShot(0, self._step)

        timer = QTimer(self, interval=16)
        timer.timeout.connect(tick)
        timer.start()

    # -------------------------------------------------------------- prompt
    def _start_prompt(self, item: Prompt) -> None:
        self._prompt_mode = True
        self.prompt_label.setText(item.text)
        self.input.setReadOnly(False)
        self.input.setEchoMode(QLineEdit.EchoMode.Password if item.secret else QLineEdit.EchoMode.Normal)
        self._prompt_secret = item.secret
        self.input.setFocus()

    def _answer_prompt(self, text: str) -> None:
        self._prompt_mode = False
        shown = "*" * len(text) if self._prompt_secret else text
        self.print_line(spans=[(self.prompt_label.text(), "dim"), (shown, "normal")])
        self.input.setReadOnly(True)
        self.input.setEchoMode(QLineEdit.EchoMode.Normal)
        self.refresh_prompt()
        self._step(text)

    def _request_skip(self) -> None:
        self._skip = True

    # --------------------------------------------------------- history / tab
    def _navigate_history(self, direction: int) -> None:
        hist = self.engine.history
        if not hist or self._prompt_mode:
            return
        self._hist_index = max(0, min(len(hist), self._hist_index + direction))
        self.input.setText(hist[self._hist_index] if self._hist_index < len(hist) else "")

    def _complete(self) -> None:
        if self._prompt_mode or self.busy:
            return
        text = self.input.text()
        options = self.engine.commands.complete(text)
        if not options:
            return
        head = text[: len(text) - len(text.split(" ")[-1])]
        if len(options) == 1:
            self.input.setText(head + options[0] + ("" if options[0].endswith("/") else " "))
            return
        common = os.path.commonprefix(options)
        if len(common) > len(text.split(" ")[-1]):
            self.input.setText(head + common)
        else:
            self.print_line("  ".join(options[:24]) + (" ..." if len(options) > 24 else ""), "dim")
