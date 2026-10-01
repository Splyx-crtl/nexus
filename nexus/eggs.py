"""Easter eggs hidden in the terminal."""
from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from .outputs import Banner, Fx, Out, Progress, Wait, dim, err, info, ok, warn

if TYPE_CHECKING:
    from .commands import CommandProcessor

HACK_ART = [
    r"  _   _    _    ____ _  __  _____ _   _ _____",
    r" | | | |  / \  / ___| |/ / |_   _| | | | ____|",
    r" | |_| | / _ \| |   | ' /    | | | |_| |  _|",
    r" |  _  |/ ___ \ |___| . \    | | |  _  | |___",
    r" |_| |_/_/   \_\____|_|\_\   |_| |_| |_|_____|",
    r"            P L A N E T",
]

_EGGS = {
    "sudo": ["operator is not in the sudoers file. This incident will be reported.",
             "(to nobody. nobody is listening.)"],
    "42": ["The answer to life, the universe and everything.", "NEXUS has been computing the question since 2031."],
    "xyzzy": ["Nothing happens."],
    "hello": ["Hello, operator. NEXUS sees you."],
    "nexus": ["NEXUS IS WATCHING.", "NEXUS IS HELPING.", "NEXUS IS ... ?"],
    "make coffee": ["ERROR 418: I'm a teapot. Also a cyber operations simulator."],
    "cat /dev/zero": ["0000000000000000000000000000000000000000", "Always zeros. Never ZERO."],
    "whoami zero": ["You are not ZERO.", "...are you?"],
    "zero": ["> a presence stirs behind the glass", "> ZERO is not a user. ZERO is a question."],
    "up up down down left right left right b a": ["KONAMI CODE ACCEPTED. +30 lives (cosmetic only)."],
    "ls /dev/null": ["It's empty. Like most promises."],
    "exit vim": ["Nobody ever exits vim. You are free to try."],
}


def easter_egg(proc: "CommandProcessor", line: str):
    """Returns a generator for a hidden command, or None if ``line`` is not an egg."""
    low = " ".join(line.lower().split())
    e = proc.e
    key = None
    if low.startswith("sudo"):
        key = "sudo"
    elif low in ("rm -rf /", "rm -rf *", "rm -rf /*"):
        key = "rmrf"
    elif low in ("hack the planet", "hack planet"):
        key = "planet"
    elif low in ("matrix", "wake up neo"):
        key = "matrix"
    elif low in _EGGS:
        key = low
    secret = next((c for c in e.data.secrets["commands"] if low in c["triggers"]), None) if key is None else None
    if key is None and secret is not None:
        return _run_secret(proc, secret)
    if key is None:
        return None

    def run() -> Iterator:
        if e.world.mark_once(f"egg:{key}"):
            e.bump("easter_eggs")
            e.bump("secret_commands")
            e.notify("ok", "SECRET DISCOVERED", f"Easter egg: {key}", sound="achievement")
        if key == "rmrf":
            yield warn("DELETING ROOT FILE SYSTEM...")
            yield Progress("RM -RF /", 1500, "err")
            yield Fx("glitch")
            yield err("!! KERNEL PANIC !!")
            yield Wait(500)
            yield ok("Just kidding. NEXUS restored your simulation from backup.")
            yield dim("(nothing real was ever at risk — this is a game)")
        elif key == "planet":
            for line in HACK_ART:
                yield Out(line, "ok")
            yield Fx("glitch")
        elif key == "matrix":
            import random
            rng = random.Random()
            for _ in range(8):
                yield Out("".join(rng.choice("01ｱｲｳｴｵｶｷｸ") for _ in range(60)), "ok")
            yield dim("Follow the white rabbit.")
        else:
            for text in _EGGS[key]:
                yield Out(text, "system")
    return run()


def apply_secret(proc: "CommandProcessor", sec: dict, once_key: str) -> Iterator:
    """Shared by secret commands and secret decode triggers."""
    e = proc.e
    style = sec.get("style", "system")
    for line in sec.get("lines", []):
        yield Out(line, style)
    fx = {k: v for k, v in sec.items() if k in ("flags", "message", "credits", "xp", "items", "discover")}
    new_hosts = [sid for sid in sec.get("discover", []) if not e.world.is_discovered(sid)]
    fx["once"] = False
    yield from proc._effects(fx, once_key)
    if new_hosts and sec.get("hidden_server"):
        e.bump("hidden_found", len(new_hosts))
    e.bump("secret_commands")
    e.notify("ok", "SECRET DISCOVERED", sec.get("id", "secret"), sound="achievement")
    e.server_changed.emit()


def _run_secret(proc: "CommandProcessor", sec: dict) -> Iterator:
    e = proc.e
    if sec.get("requires") and not e.check_requirement(sec["requires"]):
        for line in sec.get("fail_lines", ["> nothing happens."]):
            yield Out(line, "dim")
        return
    if not e.world.mark_once(f"secret:{sec['id']}"):
        for line in sec.get("lines", [])[:1]:
            yield Out(line, sec.get("style", "system"))
        yield dim("(you have already found this)")
        return
    yield from apply_secret(proc, sec, f"secretfx:{sec['id']}")
