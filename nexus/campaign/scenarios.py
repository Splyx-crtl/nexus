"""World-building scenarios: named factories that build the ``World``/``Session`` a mission needs, registered in ``SCENARIOS``.
Missions reference a scenario by name instead of embedding world data inline, so the same small set of starting points can be
reused and so a scenario can be unit-tested once rather than once per mission. One scenario commonly serves several missions
of the same act (e.g. every early Act I mission starts from the same freshly-booted player machine).

This is deliberately plain Python, not a declarative format — see ``docs/3.0-PROGRESS.md`` §C2's note on that trade-off.
"""
from __future__ import annotations

from typing import Callable

from ..shell.fs import User, VFS
from ..shell.machine import Machine, Session, World

EPOCH = 2524608000.0          # 2050-01-01 00:00:00 UTC, see docs/story/00-bible.md

SCENARIOS: dict[str, Callable[[], tuple[World, Session]]] = {}


def scenario(name: str):
    def wrap(fn: Callable[[], tuple[World, Session]]):
        SCENARIOS[name] = fn
        return fn
    return wrap


def _player_machine(home_extra: dict | None = None, root_extra: dict | None = None) -> Machine:
    """The player's own terminal: a modest Linux box, callsign 'operator' until the character editor (A6) names it properly.
    ``home_extra`` is merged into /home/operator; ``root_extra`` is merged at the filesystem root (e.g. for /var/log)."""
    m = Machine("home", "home-rig", "10.44.0.7", "linux", VFS("posix", clock=lambda: EPOCH))
    tree = {
        "etc": {"hostname": "home-rig"},
        "home": {"operator": {"_owner": "operator", "_group": "operator", **(home_extra or {})}},
        **(root_extra or {}),
    }
    m.fs.load(tree)
    m.add_user(User("root", 0, 0, ("root",), "/root", admin=True, password="toor"))
    m.add_user(User("operator", 1000, 1000, ("operator",), "/home/operator", password="hunter2"))
    return m


# ---------------------------------------------------------------------------------------------------- Act I — Awakening
@scenario("awakening_boot")
def awakening_boot() -> tuple[World, Session]:
    """Mission 1: NEXUS has just booted. One welcome file, nothing else — the player's very first `ls`/`cat`."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"welcome.txt": ["Boot sequence complete.", "", "...hello?", "", "I don't recognise this terminal. I don't recognise myself, either —",
                                         "give me a moment.", "", "There. Better.", "", "Something's wired this machine to me. I have no idea why, or for how",
                                         "long, or what you expect from this. But you're here, and so am I, so: hello.", "", "- call me NEXUS.",
                                         "Try 'cat welcome.txt' again if you need to re-read this. Or 'ls' to see what else is here."]})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("awakening_deaddrop")
def awakening_deaddrop() -> tuple[World, Session]:
    """A later Act I mission: a hidden folder dropped by an unknown contact. Teaches `ls -a`/`find`/`cat` on hidden files."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({
        "notes.txt": "Nothing here yet. NEXUS says to check for anything... unusual.\n",
        ".dropbox": {"readme": ["If you can read this, the hand-off worked.", "", "There's a job in 'package.manifest'. Don't ask who sent it."],
                     "package.manifest": ["TARGET: a Nexus Company contractor's test server", "STATUS: decommissioned, allegedly",
                                          "NOTE: allegedly."]},
    })
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("awakening_logs")
def awakening_logs() -> tuple[World, Session]:
    """An Act I mission teaching grep against a log file with a handful of real-looking, noisy lines plus one that matters."""
    world = World(clock=lambda: EPOCH)
    log = [
        "10:02:01 svc[auth]: session renewed for operator", "10:02:44 svc[cron]: backup job completed (0 errors)",
        "10:03:12 svc[auth]: failed login for admin from 203.0.113.9", "10:04:50 svc[net]: link flap on eth0, recovered",
        "10:05:21 svc[auth]: failed login for admin from 203.0.113.9", "10:06:03 svc[cron]: backup job completed (0 errors)",
        "10:06:47 svc[auth]: NOTICE account 'contractor_temp' expires in 1 day — rotate before 2050-01-02",
        "10:07:15 svc[auth]: failed login for admin from 203.0.113.9",
    ]
    m = _player_machine({"notes.txt": "NEXUS thinks something in today's log is worth flagging.\n"},
                        root_extra={"var": {"log": {"system.log": log}}})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")
