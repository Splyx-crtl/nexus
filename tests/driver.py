"""Headless helpers: drive the command generators the way the terminal UI does."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("NEXUS_NO_AUDIO", "1")
os.environ.setdefault("NEXUS_LICENSE_PUBKEY", "")             # headless tests need no game key
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nexus.database import Database
from nexus.game_engine import GameEngine
from nexus.outputs import Banner, Fx, Minigame, Out, Progress, Prompt, Type


def text_of(item: Out) -> str:
    return "".join(t for t, _ in item.spans) if item.spans else item.text


def solve(item: Minigame) -> dict:
    """Cheat solver: knows each puzzle's answer."""
    kind, p = item.kind, item.payload
    if kind == "firewall":
        p.guess(list(p.secret))
        return {"success": True, "failed_guesses": 0}
    if kind == "encryption":
        return {"success": p.check(p.key)}
    if kind == "routing":
        return {"success": p.validate(p.optimal_path)[0]}
    if kind == "access":
        return {"success": p.check(p.code)[0]}
    return {"success": True}   # trace


def new_engine(name="TESTER", seed=1):
    import random
    tmp = tempfile.mkdtemp(prefix="nexus_test_")
    db = Database(Path(tmp) / "t.db")
    db.create_profile(name)
    engine = GameEngine(db, None, rng=random.Random(seed))
    engine.async_log = []
    engine.async_line.connect(lambda t, s: engine.async_log.append(t))
    engine.banners = []
    engine.banner.connect(lambda k, l, o: engine.banners.append((k, l)))
    return engine


def run(engine, line, answers=None, fail_minigames=False):
    out, answers = [], list(answers or [])
    gen = engine.commands.execute(line)
    value = None
    try:
        item = next(gen)
        while True:
            value = None
            if isinstance(item, Out):
                out.append(text_of(item))
            elif isinstance(item, Type):
                out.append(item.text)
            elif isinstance(item, Prompt):
                value = answers.pop(0) if answers else ""
            elif isinstance(item, Minigame):
                value = {"success": False} if fail_minigames else solve(item)
            elif isinstance(item, Banner):
                out.append("<BANNER " + " | ".join(item.lines) + ">")
            item = gen.send(value)
    except StopIteration:
        pass
    return out
