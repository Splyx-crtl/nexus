"""Command registry and the context object every command handler receives."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .fs import FsError, User
from .machine import Machine, Session, World


@dataclass
class CommandSpec:
    name: str
    fn: Callable
    family: str = "bash"            # bash | ps | cmd
    level: int = 1                  # player level that unlocks it
    summary: str = ""
    usage: str = ""
    man: str = ""                   # full manual text (man / Get-Help -Full)
    lesson: str = ""                # shown once when the command is unlocked ("what does this do?")
    aliases: tuple[str, ...] = ()
    category: str = "core"
    remote: bool = True             # exists on target machines too (False = only on the player's toolkit machine)


REGISTRY: dict[tuple[str, str], CommandSpec] = {}


def command(name: str, family: str = "bash", level: int = 1, summary: str = "", usage: str = "", man: str = "", lesson: str = "",
            aliases: tuple[str, ...] = (), category: str = "core", remote: bool = True):
    """Decorator: register ``fn(ctx, args) -> int`` as a command of a shell family."""
    def wrap(fn: Callable) -> Callable:
        spec = CommandSpec(name, fn, family, level, summary, usage, man, lesson, aliases, category, remote)
        REGISTRY[(family, name.lower() if family != "bash" else name)] = spec
        for alias in aliases:
            REGISTRY[(family, alias.lower() if family != "bash" else alias)] = spec
        return fn
    return wrap


def lookup(family: str, name: str) -> CommandSpec | None:
    return REGISTRY.get((family, name if family == "bash" else name.lower()))


def specs(family: str) -> list[CommandSpec]:
    seen, out = set(), []
    for (fam, _), spec in sorted(REGISTRY.items(), key=lambda kv: kv[0][1]):
        if fam == family and spec.name not in seen:
            seen.add(spec.name)
            out.append(spec)
    return out


class Ctx:
    """What a command may touch: its arguments' world (file system, user, cwd), stdin, and two output streams."""

    def __init__(self, shell, name: str, stdin: str | None):
        self.shell = shell
        self.name = name
        self.stdin = stdin
        self.chunks: list[tuple[int, str]] = []
        self.delay_ms = 0
        self.interactive: list[dict] = []              # requests for the UI: tool windows, prompts ...

    # -- convenience ---------------------------------------------------------------------------------
    @property
    def session(self) -> Session:
        return self.shell.session

    @property
    def machine(self) -> Machine:
        return self.shell.session.machine

    @property
    def world(self) -> World:
        return self.shell.world

    @property
    def fs(self):
        return self.shell.session.machine.fs

    @property
    def user(self) -> User:
        return self.shell.session.user

    @property
    def cwd(self) -> str:
        return self.shell.session.cwd

    @property
    def env(self) -> dict[str, str]:
        return self.shell.session.env

    def path(self, p: str) -> str:
        return self.fs.norm(p, self.cwd)

    # -- output --------------------------------------------------------------------------------------
    def out(self, text: str = "", end: str = "\n") -> None:
        self.chunks.append((1, text + end))

    def err(self, text: str, end: str = "\n") -> None:
        self.chunks.append((2, text + end))

    def fail(self, text: str) -> int:
        """`name: message` on stderr, exit status 1 (the pattern of nearly every real tool)."""
        self.err(f"{self.name}: {text}")
        return 1

    def fs_error(self, exc: FsError, path: str = "", verb: str = "") -> int:
        """Word a file-system error like the real tools: `cat: x: No such file or directory`, `rm: cannot remove 'x': Permission denied`."""
        shown = path or exc.path
        text = "Operation not permitted" if exc.code == "EACCES" and verb in ("changing permissions of", "changing ownership of") else exc.text
        self.err(f"{self.name}: {verb + ' ' + chr(39) + shown + chr(39) if verb else shown}: {text}")
        return 1

    @property
    def tty(self) -> bool:
        """True when stdout is the terminal (not a pipe or file): `ls` then prints columns."""
        return self.shell._cmd_tty

    width = 100

    def read_text(self, path: str) -> str:
        """Read a file as the current user (permissions apply) and report it to the mission system. Raises FsError."""
        data = self.fs.read(self.user, path, self.cwd)
        self.event("file_read", path=self.path(path), machine=self.machine.id)
        return data if isinstance(data, str) else data.decode("latin-1")

    def now(self) -> float:
        return self.world.clock()

    def event(self, event: str, /, **data) -> None:
        self.shell.emit(event, **data)

    def wait(self, ms: int) -> None:
        self.delay_ms += ms

    def request(self, kind: str, **data) -> None:
        """Ask the UI for something a text stream cannot show (a tool window, a password prompt ...)."""
        self.interactive.append({"kind": kind, **data})
