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


@scenario("awakening_workspace")
def awakening_workspace() -> tuple[World, Session]:
    """Level 4: nothing to find yet, just an empty home — teaches mkdir/touch by asking the player to set up a workspace."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"notes.txt": "NEXUS: Let's set up a proper workspace before we go further.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("awakening_manual")
def awakening_manual() -> tuple[World, Session]:
    """Level 5: teaches 'man' — the most useful habit in the whole game — against a command already unlocked (ls)."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"notes.txt": "NEXUS: Every tool has a manual. Get in the habit of checking.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("awakening_tidy")
def awakening_tidy() -> tuple[World, Session]:
    """Level 6: a messy folder (badly named file, a stray copy) — teaches cp/mv/rm."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"draft_v2_FINAL_reall.txt": "Mira's contact protocol, typed in a hurry.\n",
                         "draft_v2_FINAL_reall_OLD.txt": "An older, wrong draft. Get rid of it.\n",
                         "notes.txt": "NEXUS: This folder's a mess. Clean it up: lose the old draft, rename the real one sensibly.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("awakening_search")
def awakening_search() -> tuple[World, Session]:
    """Level 7: a slightly bigger tree — the first real use of 'find', which unlocks at exactly this level."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({
        "notes.txt": "NEXUS: Somewhere under this folder is a file named 'protocol.key'. I don't remember where. Use find.\n",
        "archive": {"2049": {"q1": {"misc.txt": "nothing here"}, "q2": {"protocol.key": "CONTACT-PROTOCOL-7\n"}}, "2050": {"empty": {}}},
    })
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("awakening_firstgrep")
def awakening_firstgrep() -> tuple[World, Session]:
    """Level 8: the first use of grep, which unlocks at exactly this level — short and simple before the noisier Level 10 log."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"roster.txt": ["alice - analyst", "bshah - contractor", "cwu - analyst", "NEXUS - classified", "dpatel - analyst"],
                         "notes.txt": "NEXUS: My own name is buried in that roster file. Find the line with 'NEXUS' in it.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("awakening_contact")
def awakening_contact() -> tuple[World, Session]:
    """Level 9 (story): Mira reaches out for the first time, having noticed the player's activity since the dead drop."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"inbox": {"unread_001.txt": [
        "FROM: M.", "",
        "I've been watching your traffic for a week. You're sloppy in exactly the ways that don't get you caught, which is rarer than it sounds.",
        "", "I run a small, deniable network of independent operators. I'd like you to be one of them.",
        "", "Reply in this file if you're in. Nothing fancy — just write it below the line and save.", "---",
    ]}, "notes.txt": "NEXUS: Someone noticed us. Read inbox/unread_001.txt.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("awakening_logs")
def awakening_logs() -> tuple[World, Session]:
    """Level 10 (milestone): the "decommissioned" contractor test server from the Level 3 dead drop — a log with real-looking
    noise plus one line that matters. Closes Chapter 1 of Act I (first contact with NEXUS, Mira, and a first real result)."""
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


# ----------------------------------------------------------------------------------------- Act I, Chapter 2 (levels 15-20)
@scenario("awakening_signal")
def awakening_signal() -> tuple[World, Session]:
    """Level 15: Mira's first real client job. Teaches sort+uniq -c as a pair (sort's own lesson recommends exactly this
    combination) to turn a flat log into a count."""
    world = World(clock=lambda: EPOCH)
    log = ["203.0.113.9 - login attempt", "198.51.100.4 - login attempt", "203.0.113.9 - login attempt",
           "203.0.113.9 - login attempt", "198.51.100.4 - login attempt", "203.0.113.9 - login attempt",
           "192.0.2.15 - login attempt", "203.0.113.9 - login attempt"]
    m = _player_machine({"access.log": log,
                         "notes.txt": "MIRA: A client says their portal keeps getting hammered. I want numbers, not guesses.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("awakening_ledger")
def awakening_ledger() -> tuple[World, Session]:
    """Level 16: prepping a report for Mira's own ledger — teaches cut (pick a field) and tr (reformat it)."""
    world = World(clock=lambda: EPOCH)
    roster = ["wraith:fixer:active", "cipher:broker:active", "echo-two:lookout:benched", "vantage:courier:active"]
    m = _player_machine({"contacts.roster": roster,
                         "notes.txt": "MIRA: I need just the callsigns out of that roster, in caps, for my ledger. Nothing else.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("awakening_manifest")
def awakening_manifest() -> tuple[World, Session]:
    """Level 17 (standard): the Level-3 dead-drop manifest, and a second copy Mira got her hands on independently. diff
    proves the official paperwork was quietly rewritten — the Act's first hard evidence that "decommissioned" was a lie."""
    world = World(clock=lambda: EPOCH)
    official = ["TARGET: a Nexus Company contractor's test server", "STATUS: decommissioned, allegedly", "NOTE: allegedly."]
    leaked = ["TARGET: a Nexus Company contractor's test server", "STATUS: active, restricted access",
             "NOTE: do not log this anywhere."]
    m = _player_machine({"official_manifest.txt": official, "leaked_manifest.txt": leaked,
                         "notes.txt": "MIRA: Same server, two manifests. One's ours from the dead drop. One isn't. Compare them.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("awakening_coverup")
def awakening_coverup() -> tuple[World, Session]:
    """Level 18 (story): the first morally uncomfortable ask — scrub the player's own access trace with sed before someone
    on the other end notices. NEXUS has opinions about this that it mostly keeps to itself."""
    world = World(clock=lambda: EPOCH)
    log = ["09:58:01 svc[auth]: session renewed for operator",
           "09:59:40 svc[auth]: login success for operator from 10.44.0.7",
           "10:00:02 svc[cron]: backup job completed (0 errors)"]
    m = _player_machine({"session.log": log,
                         "notes.txt": "MIRA: You forgot to scrub your access line last time. There's a trace with your real address on it. Fix that.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("awakening_pattern")
def awakening_pattern() -> tuple[World, Session]:
    """Level 19 (standard): a week's combined auth log — teaches awk (pull a column out by a condition) to separate one
    real pattern from routine noise."""
    world = World(clock=lambda: EPOCH)
    log = ["2050-01-03 auth FAIL 203.0.113.9", "2050-01-03 auth OK 198.51.100.4",
           "2050-01-04 auth FAIL 203.0.113.9", "2050-01-04 auth FAIL 203.0.113.9",
           "2050-01-05 auth OK 192.0.2.15"]
    m = _player_machine({"weekly.log": log,
                         "notes.txt": "MIRA: Pull every address that failed a login this week. Just the addresses — I don't need the rest of the line.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("awakening_convergence")
def awakening_convergence() -> tuple[World, Session]:
    """Level 20 (milestone): three days of logs across the same "decommissioned" server. Chains grep/awk/sort/uniq — every
    technique Chapter 2 taught — to prove one address has been patient and consistent where everything else was noise.
    Closes Act I, Chapter 2: promotion to TRACER, and the hook into Act II."""
    world = World(clock=lambda: EPOCH)
    day1 = ["09:58:01 svc[auth]: failed login for admin from 203.0.113.9",
            "10:02:04 svc[auth]: session renewed for operator",
            "10:15:30 svc[auth]: failed login for admin from 198.51.100.4"]
    day2 = ["08:40:12 svc[auth]: failed login for admin from 203.0.113.9",
            "09:00:00 svc[cron]: backup job completed (0 errors)"]
    day3 = ["23:58:59 svc[auth]: failed login for admin from 203.0.113.9",
            "00:02:10 svc[auth]: failed login for admin from 192.0.2.15"]
    m = _player_machine({"logs": {"day1.log": day1, "day2.log": day2, "day3.log": day3},
                         "notes.txt": "NEXUS: Three days of logs off that server. Somewhere in there is a pattern, not just noise. Find it.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")
