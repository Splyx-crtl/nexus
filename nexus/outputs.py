"""Output protocol between command handlers (generators) and the terminal UI.

A command handler is a generator that *yields* these objects. The terminal
renders them (with animation) and can send a value back for ``Prompt`` and
``Minigame`` items. The same protocol is used by the headless test driver.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Out:
    text: str = ""
    style: str = "normal"
    spans: list[tuple[str, str]] | None = None   # [(text, style), ...] overrides text


@dataclass
class Wait:
    ms: int


@dataclass
class Progress:
    label: str
    ms: int = 1200
    style: str = "info"
    done: str = ""          # optional line printed when finished


@dataclass
class Type:
    text: str
    style: str = "story"


@dataclass
class Prompt:
    text: str
    secret: bool = False


@dataclass
class Minigame:
    kind: str               # firewall | encryption | routing | access | trace
    payload: Any = None


@dataclass
class Banner:
    kind: str               # zero | alert | failure | complete | achievement | blackout
    lines: list[str] = field(default_factory=list)
    block: bool = True


@dataclass
class Fx:
    name: str               # clear | glitch | shake | flash | sound | menu | pause | settings | exit_menu
    arg: Any = None


# --- tiny constructors used all over the command handlers -------------------
def out(text: str = "", style: str = "normal") -> Out:
    return Out(text, style)


def ok(text: str) -> Out:
    return Out(text, "ok")


def err(text: str) -> Out:
    return Out(text, "err")


def info(text: str) -> Out:
    return Out(text, "info")


def warn(text: str) -> Out:
    return Out(text, "warn")


def dim(text: str) -> Out:
    return Out(text, "dim")


def kv(label: str, value: str, width: int = 14, value_style: str = "ok") -> Out:
    """Label/value line with two colours."""
    return Out(spans=[(f"{label:<{width}}", "dim"), (value, value_style)])
