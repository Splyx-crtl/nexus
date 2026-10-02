"""Qt terminal widget for the 3.0 shell engine (``nexus.shell``): the UI side of B9.

Deliberately separate from ``ui/terminal.py`` (the shipped 2.x terminal, driven by ``nexus.commands.CommandProcessor`` and tied to
missions/banners/minigames): the new shell engine is not part of the released campaign yet (see docs/3.0-PROGRESS.md, category C).
This widget is the connective tissue that proves the engine works in a real window — prompt-per-shell (bash/PowerShell/cmd.exe),
coloured stdout/stderr, history and tab completion — and is what a future campaign-integration step (C2) will build on.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QTextEdit, QVBoxLayout, QWidget

from nexus.config import COLORS
from nexus.shell import commands  # noqa: F401  (registers every command on import)
from nexus.shell.fs import FsError
from nexus.shell.interp import Shell
from nexus.shell.machine import World

from .widgets import mono_font

STREAM_COLOR = {1: COLORS["text"], 2: COLORS["red"]}
PROMPT_COLOR = COLORS["cyan"]
ECHO_COLOR = COLORS["white"]


def _family_of(shell_name: str) -> str:
    return {"bash": "bash", "powershell": "ps", "cmd": "cmd"}.get(shell_name, "bash")


class HistoryInput(QLineEdit):
    """A QLineEdit with shell-style Up/Down history recall and Tab completion."""

    tab_pressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.history_source: list[str] = []
        self._browse_index: int | None = None
        self._draft = ""

    def keyPressEvent(self, ev: QKeyEvent) -> None:
        if ev.key() == Qt.Key.Key_Up:
            self._browse(-1)
            return
        if ev.key() == Qt.Key.Key_Down:
            self._browse(1)
            return
        if ev.key() == Qt.Key.Key_Tab:
            self.tab_pressed.emit()
            return
        self._browse_index = None
        super().keyPressEvent(ev)

    def _browse(self, step: int) -> None:
        hist = self.history_source
        if not hist:
            return
        if self._browse_index is None:
            self._draft = self.text()
            self._browse_index = len(hist)
        self._browse_index = max(0, min(len(hist), self._browse_index + step))
        self.setText(hist[self._browse_index] if self._browse_index < len(hist) else self._draft)
        self.end(False)

    def reset_browse(self) -> None:
        self._browse_index = None


class ShellTerminal(QWidget):
    """One Kali-style console bound to a ``nexus.shell.interp.Shell``. Reusable for any ``World``/``Session``."""

    command_run = Signal(str)          # emitted after each line, with the raw command text (for tests / telemetry)

    def __init__(self, shell: Shell, parent=None):
        super().__init__(parent)
        self.shell = shell
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(mono_font(12))
        self.output.setStyleSheet(f"QTextEdit {{ background:{COLORS['bg']}; color:{COLORS['text']}; border:1px solid {COLORS['border']}; padding:8px; }}")
        lay.addWidget(self.output, 1)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.prompt_label = QLabel("")
        self.prompt_label.setFont(mono_font(12, True))
        self.prompt_label.setStyleSheet(f"color:{PROMPT_COLOR}; background:transparent;")
        self.prompt_label.setWordWrap(False)
        row.addWidget(self.prompt_label)
        self.input = HistoryInput()
        self.input.setFont(mono_font(12))
        self.input.setStyleSheet(f"QLineEdit {{ background:{COLORS['bg_alt']}; color:{COLORS['white']}; border:1px solid {COLORS['border']}; padding:4px; }}")
        self.input.returnPressed.connect(self._submit)
        self.input.tab_pressed.connect(self._complete)
        row.addWidget(self.input, 1)
        lay.addLayout(row)
        self._refresh_prompt()
        self.input.setFocus()

    # ------------------------------------------------------------------ running
    def focus_input(self) -> None:
        self.input.setFocus()

    def _refresh_prompt(self) -> None:
        self.prompt_label.setText(self.shell.session.prompt())
        self.input.history_source = self.shell.session.history

    def _append(self, text: str, color: str) -> None:
        if not text:
            return
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.output.setTextCursor(cursor)
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        self.output.insertHtml(f'<span style="color:{color}">{safe}</span>')
        self.output.moveCursor(QTextCursor.MoveOperation.End)

    def run_command(self, line: str, echo: bool = True) -> None:
        """Run one line (used by Enter and by anything scripting the terminal, e.g. tests)."""
        if echo:
            self._append(self.shell.session.prompt() + line + "\n", PROMPT_COLOR)
        result = self.shell.run(line)
        if any(req.get("kind") == "clear" for req in result.interactive):
            self.output.clear()
        for fd, text in result.chunks:
            self._append(text, STREAM_COLOR.get(fd, COLORS["text"]))
        if result.chunks and not result.text.endswith("\n"):
            self._append("\n", COLORS["text"])
        self._refresh_prompt()
        self.command_run.emit(line)

    def _submit(self) -> None:
        line = self.input.text()
        self.input.clear()
        self.input.reset_browse()
        if line.strip():
            self.run_command(line)
        else:
            self._append(self.shell.session.prompt() + "\n", PROMPT_COLOR)

    # ------------------------------------------------------------------ tab completion
    def _complete(self) -> None:
        text = self.input.text()
        head, _, partial = text.rpartition(" ") if " " in text else ("", "", text)
        is_command = head == ""
        matches = self._command_matches(partial) if is_command else self._path_matches(partial)
        if not matches:
            return
        common = _longest_common_prefix(matches)
        if len(matches) == 1:
            completed = matches[0]
            trailer = "" if completed.endswith(("/", "\\")) else " "
            self.input.setText((head + " " if head else "") + completed + trailer)
        elif common and common != partial:
            self.input.setText((head + " " if head else "") + common)
        else:
            self._append("  ".join(sorted(matches)) + "\n", COLORS["dim"])
        self.input.end(False)

    def _command_matches(self, partial: str) -> list[str]:
        from nexus.shell.registry import specs
        family = _family_of(self.shell.session.shell)
        names = {s.name for s in specs(family) if s.level <= self.shell.level()}
        if family == "bash":
            from nexus.shell.interp import BUILTINS
            names |= set(BUILTINS)
        pref = partial if family == "bash" else partial.lower()
        return sorted(n for n in names if (n if family == "bash" else n.lower()).startswith(pref))

    def _path_matches(self, partial: str) -> list[str]:
        fs, session = self.shell.session.fs, self.shell.session
        directory, _, prefix = partial.rpartition(fs.sep)
        base = directory or "."
        try:
            kids = fs.listdir(session.user, base, session.cwd)
        except FsError:
            return []
        names = [k.name + (fs.sep if k.is_dir else "") for k in kids if k.name.lower().startswith(prefix.lower()) and (prefix or not k.name.startswith("."))]
        return [((directory + fs.sep) if directory else "") + n for n in names]


def _longest_common_prefix(items: list[str]) -> str:
    if not items:
        return ""
    short = min(items, key=len)
    for i, ch in enumerate(short):
        if any(it[i].lower() != ch.lower() for it in items):
            return short[:i]
    return short


def make_shell(world: World, session, level=lambda: 10**6) -> Shell:
    """Convenience constructor used by the UI harness and tests."""
    return Shell(world, session, level=level)
