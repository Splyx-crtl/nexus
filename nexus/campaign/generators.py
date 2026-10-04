"""Procedural generators for Mini missions (docs/story/02-acts-and-levels.md §4: "5x Mini" per 10 levels, varied so repeat
play doesn't feel stale). Each generator is deterministic given a seed — same seed, same mission — so generated missions are
reproducible for the solver bot and for tests, and so a player who replays a Mini after level 200 (docs/3.0-PROGRESS.md §C7)
sees a different, but still fair and solvable, instance.

A generator builds its own tiny scenario (closed over the random choice it made) and registers it under a unique name in
``scenarios.SCENARIOS`` — the same registry hand-authored missions use, so the rest of the campaign machinery (runner, solver)
does not need to know a mission was generated.
"""
from __future__ import annotations

import random

from ..shell.fs import User, VFS
from ..shell.machine import Machine, Session, World
from .mission import Mission, Objective
from .scenarios import EPOCH, SCENARIOS, scenario

KEYWORDS = ["breach", "override", "contractor_temp", "rotate", "quarantine", "ARCHITECT", "decommissioned", "anomaly"]
NOISE_LINES = ["session renewed for operator", "backup job completed (0 errors)", "link flap on eth0, recovered",
              "routine integrity check passed", "scheduled maintenance window opened", "cache cleared"]
HIDDEN_NAMES = [".keycard", ".access_token", ".old_notes", ".backup_key", ".staging"]
SECRETS = ["VAULT-7-ALPHA", "NX-COLD-STORAGE", "ECHO-NINE", "DEAD-DROP-3", "MERIDIAN-GATE"]


def _rig(home: dict) -> Machine:
    m = Machine("home", "home-rig", "10.44.0.7", "linux", VFS("posix", clock=lambda: EPOCH))
    m.fs.load({"home": {"operator": {"_owner": "operator", "_group": "operator", **home}}})
    m.add_user(User("root", 0, 0, ("root",), "/root", admin=True))
    m.add_user(User("operator", 1000, 1000, ("operator",), "/home/operator", password="hunter2"))
    return m


def generate_grep_mini(mission_id: str, number: int, act: int, seed: int) -> Mission:
    """Find one meaningful line in a noisy log by keyword — a fresh keyword and noise mix each time."""
    rng = random.Random(seed)
    keyword = rng.choice(KEYWORDS)
    lines = rng.sample(NOISE_LINES, 4)
    needle_pos = rng.randrange(len(lines) + 1)
    lines.insert(needle_pos, f"ALERT flagged entry mentioning '{keyword}' — needs review")
    scenario_name = f"gen_grep_{mission_id}"

    @scenario(scenario_name)
    def build(lines=lines) -> tuple[World, Session]:
        world = World(clock=lambda: EPOCH)
        m = _rig({"activity.log": lines, "notes.txt": f"NEXUS: something in activity.log mentions '{keyword}'. Find it.\n"})
        world.add(m)
        return world, Session(m, m.users["operator"], "bash")

    return Mission(
        id=mission_id, number=number, act=act, size="mini", title=f"Needle: {keyword}", scenario=scenario_name,
        briefing=[f"NEXUS: There's a line in activity.log mentioning '{keyword}'. grep for it."],
        objectives=[Objective(event="command", match={"name": "grep", "args__contains": keyword, "status": 0},
                              text=f"Find the log line mentioning '{keyword}'",
                              hints=["grep searches text for a pattern.", f"Try: grep {keyword} activity.log",
                                    f"grep {keyword} activity.log"])],
        solution=[f"grep {keyword} activity.log"], reward_xp=40, tags=["bash", "generated", "grep"],
    )


def generate_hidden_file_mini(mission_id: str, number: int, act: int, seed: int) -> Mission:
    """Find and read a hidden file containing a short code — a fresh filename and secret each time."""
    rng = random.Random(seed)
    name = rng.choice(HIDDEN_NAMES)
    secret = rng.choice(SECRETS)
    scenario_name = f"gen_hidden_{mission_id}"

    @scenario(scenario_name)
    def build(name=name, secret=secret) -> tuple[World, Session]:
        world = World(clock=lambda: EPOCH)
        m = _rig({name: f"{secret}\n", "notes.txt": "NEXUS: Something's hidden in this folder. Hidden files start with a dot.\n"})
        world.add(m)
        return world, Session(m, m.users["operator"], "bash")

    return Mission(
        id=mission_id, number=number, act=act, size="mini", title="Hidden in Plain Sight", scenario=scenario_name,
        briefing=["NEXUS: Hidden files don't show up with a plain 'ls'. You'll need the right flag."],
        objectives=[Objective(event="file_read", match={"path__glob": f"*{name}"}, text=f"Read the hidden file {name}",
                              hints=["'ls -a' shows files that start with a dot, which 'ls' hides by default.",
                                    f"Try: ls -a, then cat {name}", f"ls -a\ncat {name}"])],
        solution=["ls -a", f"cat {name}"], reward_xp=35, tags=["bash", "generated", "hidden-files"],
    )


GENERATORS = {"grep_mini": generate_grep_mini, "hidden_file_mini": generate_hidden_file_mini}


def generate_batch(kind: str, count: int, start_id: int, act: int, base_level: int, seed: int) -> list[Mission]:
    """``count`` generated missions of ``kind`` (a key of GENERATORS), ids/numbers/levels assigned sequentially from
    ``start_id``/``base_level``. Used to fill out an act's Mini-mission quota (docs/story/02-acts-and-levels.md §4)."""
    fn = GENERATORS[kind]
    return [fn(f"gen_{kind}_{start_id + i}", base_level + i, act, seed * 1000 + i) for i in range(count)]
