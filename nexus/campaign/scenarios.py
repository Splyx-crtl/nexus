"""World-building scenarios: named factories that build the ``World``/``Session`` a mission needs, registered in ``SCENARIOS``.
Missions reference a scenario by name instead of embedding world data inline, so the same small set of starting points can be
reused and so a scenario can be unit-tested once rather than once per mission. One scenario commonly serves several missions
of the same act (e.g. every early Act I mission starts from the same freshly-booted player machine).

This is deliberately plain Python, not a declarative format — see ``docs/3.0-PROGRESS.md`` §C2's note on that trade-off.
"""
from __future__ import annotations

from typing import Callable

from ..shell.fs import User, VFS
from ..shell.machine import Machine, Process, Service, Session, World

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


# ---------------------------------------------------------------------------------------------- Act II — Traces, Chapter 1
@scenario("traces_permissions")
def traces_permissions() -> tuple[World, Session]:
    """Level 21: a leaked key with loose permissions — teaches chmod. The file is owned by operator, so no sudo is needed
    yet; that comes next."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"vault.key": "-----BEGIN KEY-----\nNX7-CONTACT-PRIVATE\n-----END KEY-----\n",
                         "notes.txt": "MIRA: That key's world-readable right now. Anyone on this box could read it. Lock it to yourself only — 600.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("traces_ownership")
def traces_ownership() -> tuple[World, Session]:
    """Level 22: a root-owned stray file — teaches chown, and that it (unlike chmod) always needs sudo."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"notes.txt": "MIRA: There's a leftover config under /opt, still owned by root. I need it under your "
                         "name so you can actually work with it. chown needs sudo — chmod doesn't, this does.\n"},
                        root_extra={"opt": {"orphan.cfg": "last_touched_by: unknown\nstatus: orphaned\n"}})
    m.data["sudoers"] = {"operator": {"commands": "ALL", "nopasswd": True}}
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("traces_protected")
def traces_protected() -> tuple[World, Session]:
    """Level 23: a root-only config file — teaches sudo's general purpose (running ANY command as root), not just chown."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"notes.txt": "MIRA: Everything I know about our other contacts is in /etc/nexus_contacts.conf. "
                         "You don't have permission to just read it — you'll need to borrow root's.\n"},
                        root_extra={"etc": {"nexus_contacts.conf": {"content": ["wraith: courier, low-risk jobs only",
                                            "cipher: broker, verify everything twice", "echo-two: benched, don't contact"], "mode": 0o600}}})
    m.data["sudoers"] = {"operator": {"commands": "ALL", "nopasswd": True}}
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("traces_process")
def traces_process() -> tuple[World, Session]:
    """Level 24 (standard): an unwanted process eating resources — teaches ps (find it) and kill (stop it)."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"notes.txt": "NEXUS: Your fans have been spinning for an hour and you're not doing anything. "
                         "Something's running that shouldn't be. Find it, then stop it.\n"})
    m.processes.append(Process(pid=4821, user="operator", name="xmr-helper", cmd="/tmp/.sys/xmr-helper --silent --pool pool.example:3333", cpu=97.8, mem=4.2))
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("traces_whosthere")
def traces_whosthere() -> tuple[World, Session]:
    """Level 25: who/last — the home-rig has a login history worth reading, not just the active session."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"notes.txt": "MIRA: Habit worth building: check who's logged in, and who's logged in recently, "
                         "every time you sit down at a box. Even your own.\n"})
    m.data["last"] = ["operator pts/0    10.44.0.7        Thu Jan  8 09:12 - 09:50  (00:38)",
                      "operator pts/0    10.44.0.7        Wed Jan  7 18:03 - 18:40  (00:37)",
                      "operator pts/0    10.44.0.7        Wed Jan  7 08:55 - 09:15  (00:20)"]
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("traces_rival")
def traces_rival() -> tuple[World, Session]:
    """Level 26 (story): Reyes, introduced — a rival independent operator who beat the player to a contract and left a
    calling card about it. Mira fills in who they are."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"jobs": {"job_007": {"claimed.txt": ["Cute try. Already cleared this one an hour ago.",
                                                              "You'll want to be faster than that if you're going to make a name for yourself.",
                                                              "- R."]}},
                         "inbox": {"about_reyes.txt": ["MIRA: That's Reyes. Another independent, works the same kind of contracts we do.",
                                                       "Not an enemy. A competitor. Sharp, fast, and insufferably pleased about it.",
                                                       "You'll cross paths again. Get used to it."]},
                         "notes.txt": "NEXUS: Someone got to job_007 before you. There's a note.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("traces_disk")
def traces_disk() -> tuple[World, Session]:
    """Level 27: disk filling up for no obvious reason — teaches df (how full) and du (what's actually taking the space)."""
    world = World(clock=lambda: EPOCH)
    filler = "X" * 200
    m = _player_machine({".cache": {"spool": {f"part_{i:03d}.tmp": filler for i in range(6)}},
                         "notes.txt": "NEXUS: Disk's filling up and I don't know why. Check how much space is left, then "
                                     "find what's actually eating it.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("traces_symlink")
def traces_symlink() -> tuple[World, Session]:
    """Level 28 (standard): a file that isn't what it claims to be — teaches file (identify it) and readlink (see where
    it really points)."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"backup_link": {"link": "/opt/real_backup.tar"},
                         "notes.txt": "MIRA: That backup file in your workspace isn't a real file. Find out what it "
                                     "actually is, and where it actually points.\n"},
                        root_extra={"opt": {"real_backup.tar": "(binary archive, not for reading)\n"}})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("traces_housekeeping")
def traces_housekeeping() -> tuple[World, Session]:
    """Level 29: a light, mostly comic NEXUS-driven beat — uptime and whereis, the two commands too small for their own
    standard mission."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"notes.txt": "NEXUS: Idle curiosity: how long has this machine been up? And where does the "
                         "system actually keep the 'grep' binary? I like knowing where things live.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("traces_incident")
def traces_incident() -> tuple[World, Session]:
    """Level 30 (milestone): a full, small incident response on the player's own machine, chaining Chapter 1's tools —
    ps/kill, last, chmod. The login history quietly reuses 203.0.113.9, the patient address from Act I's Level 20, now
    probing the player directly instead of the old dead-drop server. Closes Act II, Chapter 1."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"access.token": "OP-TOKEN-7734-ACTIVE\n",
                         "notes.txt": "NEXUS: Something's running that neither of us started. Full check — what's "
                                     "running, who's been logging in, and lock down anything loose when you're done.\n"})
    m.processes.append(Process(pid=6650, user="operator", name="relay", cmd="/tmp/.sys/relay --beacon 203.0.113.9:4444", cpu=12.0, mem=1.5))
    m.data["last"] = ["operator pts/1    203.0.113.9      Fri Jan  9 02:14   still logged in",
                      "operator pts/0    10.44.0.7        Fri Jan  9 09:00 - 09:41  (00:41)",
                      "operator pts/0    10.44.0.7        Thu Jan  8 09:12 - 09:50  (00:38)"]
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


# ---------------------------------------------------------------------------------------------- Act II — Traces, Chapter 2
@scenario("traces_copy")
def traces_copy() -> tuple[World, Session]:
    """Level 31: tee — seeing output and saving it are not the same thing, and sometimes you need both at once."""
    world = World(clock=lambda: EPOCH)
    log = ["198.51.100.4 - auth attempt", "203.0.113.20 - auth attempt", "198.51.100.4 - auth attempt",
           "198.51.100.4 - auth attempt", "192.0.2.44 - auth attempt", "198.51.100.4 - auth attempt"]
    m = _player_machine({"auth_events.log": log,
                         "notes.txt": "MIRA: Same drill as before, but I need a copy of the result this time, not just a look at it. "
                                     "tee lets you see it and save it in the same breath.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("traces_report")
def traces_report() -> tuple[World, Session]:
    """Level 32: plain output redirection (>) — a written baseline survives, a glance at the terminal doesn't."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"notes.txt": "NEXUS: Before anything else gets weird on this box, I want a written baseline of "
                         "what SHOULD be running. Save it — don't just glance at it and move on.\n"})
    m.processes.append(Process(pid=1102, user="operator", name="sshd", cmd="/usr/sbin/sshd -D", cpu=0.1, mem=0.3))
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("traces_quiet")
def traces_quiet() -> tuple[World, Session]:
    """Level 33 (standard): stderr redirection (2>) — keep the real output clean by routing errors somewhere else."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"siteA.cfg": "region=eu\ntier=standard\n", "siteB.cfg": "region=us\ntier=priority\n",
                         "notes.txt": "MIRA: Read siteA, siteB and siteC's configs together. There's no siteC yet, so route whatever "
                                     "errors that throws into its own file instead of letting it clutter the real output.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("traces_feed")
def traces_feed() -> tuple[World, Session]:
    """Level 34: input redirection (<) — the natural way to hand a file to a command that only reads stdin."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"message.txt": "they are closer than you think\n",
                         "notes.txt": "NEXUS: Mira wants that message shouted, not whispered — all caps, saved to a new file.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("traces_offer")
def traces_offer() -> tuple[World, Session]:
    """Level 35 (story, first real decision): Reyes offers a trade — information about 203.0.113.9 in exchange for
    what the player knows about contractor_temp. No mechanical branching exists yet (C5 is unbuilt) — the "choice" is the
    player's own free-form reply, same mechanism as act1_m09's first contact with Mira."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"inbox": {"reyes_offer.txt": [
        "- R.", "", "Heard you had a visitor. The patient kind, not the loud kind.",
        "", "I know something about that address. I'll trade — tell me what you know about 'contractor_temp' and the "
        "decommissioned box it came from, and I'll tell you who I think 203.0.113.9 actually is.",
        "", "Or don't. Your call. I'll find out either way, I'm just offering you a shortcut.", "---",
    ]}, "notes.txt": "NEXUS: Reyes again. This one actually wants something. Read it.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("traces_tally")
def traces_tally() -> tuple[World, Session]:
    """Level 36: nl and seq — numbering an existing list, and generating a fresh one."""
    world = World(clock=lambda: EPOCH)
    roster = ["wraith", "cipher", "echo-two", "vantage"]
    m = _player_machine({"contacts.roster": roster,
                         "notes.txt": "MIRA: Number that roster for me, readably, for printing. And I need ten fresh case IDs "
                                     "— 101 through 110 is fine.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("traces_mirror")
def traces_mirror() -> tuple[World, Session]:
    """Level 37: rev — a low-effort obfuscation trick (reversed text), the kind a cocky rival leaves on purpose."""
    world = World(clock=lambda: EPOCH)
    message = "they are closer than you think - R"
    m = _player_machine({"scrambled.txt": message[::-1] + "\n",
                         "notes.txt": "NEXUS: That file reads as nonsense forwards. Reyes has done this before — try it backwards.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("traces_format")
def traces_format() -> tuple[World, Session]:
    """Level 38 (standard): paste + column — merging two exports into one readable table, the finishing move on the
    report habit this chapter's been building (cut/tr at Level 16, tee at Level 31)."""
    world = World(clock=lambda: EPOCH)
    names = ["wraith", "cipher", "echo-two", "vantage"]
    statuses = ["active", "active", "benched", "active"]
    m = _player_machine({"names.txt": names, "statuses.txt": statuses,
                         "notes.txt": "MIRA: Merge these side by side into one table, lined up properly. I'm not reading two "
                                     "separate lists and matching them up myself.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("traces_sweep")
def traces_sweep() -> tuple[World, Session]:
    """Level 39: xargs — batch-deleting a folder of scratch files at once, the payoff for find (Act I) and xargs together."""
    world = World(clock=lambda: EPOCH)
    spool = {f"junk_{i}.tmp": "scratch\n" for i in range(4)}
    m = _player_machine({".cache": {"spool": spool},
                         "notes.txt": "NEXUS: That spool folder from before is still full of scratch files nobody needs. "
                                     "Find them all and clear them out in one go — don't delete them one at a time.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("traces_audit")
def traces_audit() -> tuple[World, Session]:
    """Level 40 (milestone): closes Act II, Chapter 2 by chaining this chapter's whole toolkit — grep -h (Act I), stderr
    redirection, tee, and an xargs cleanup — into one real audit pass."""
    world = World(clock=lambda: EPOCH)
    w1 = ["09:00 INFO service started", "09:14 ERROR disk allocation failed", "09:20 INFO heartbeat ok"]
    w2 = ["10:01 INFO service started", "10:40 ERROR auth backend unreachable"]
    m = _player_machine({"logs": {"w1.log": w1, "w2.log": w2}, "scratch1.tmp": "temp\n", "scratch2.tmp": "temp\n",
                         "notes.txt": "MIRA: Full pass before we call this chapter done: pull every ERROR line out of this week's "
                                     "logs (there's a third file listed that doesn't exist — don't let that break the real output), "
                                     "save a copy of what you find, review whatever errors it throws separately, then clear out "
                                     "the scratch files when you're done.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


# ---------------------------------------------------------------------------------------------- Act II — Traces, Chapter 3
@scenario("traces_dossier")
def traces_dossier() -> tuple[World, Session]:
    """Level 41 (standard): Reyes delivers on their Level-35 offer — a dossier folder worth searching all at once.
    Teaches grep -r, the first recursive search of the campaign."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"dossier": {
        "jan03.log": ["09:14 svc[auth]: probe from 203.0.113.9", "09:15 svc[auth]: probe rejected"],
        "jan04.log": ["02:14 svc[auth]: session opened from 203.0.113.9", "02:55 svc[auth]: session closed"],
        "misc": {"contractor_notes.txt": ["Follow-up needed: 203.0.113.9 flagged twice this month.",
                                          "Internal routing suggests it's not external. Can't confirm yet."]},
    }, "inbox": {"reyes_followup.txt": ["- R.", "", "Told you I'd find out. Everything I've got on that address is in the folder "
                                        "I dropped in your jobs directory. It's not much, but it's not nothing either.", "---"]},
                         "notes.txt": "NEXUS: Reyes actually came through. There's a dossier folder — search all of it at once, "
                                     "not file by file.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("traces_timeline")
def traces_timeline() -> tuple[World, Session]:
    """Level 42: a quick follow-up — how many times total, across everything, not just where."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"dossier": {
        "jan03.log": ["09:14 svc[auth]: probe from 203.0.113.9", "09:15 svc[auth]: probe rejected"],
        "jan04.log": ["02:14 svc[auth]: session opened from 203.0.113.9", "02:55 svc[auth]: session closed"],
        "misc": {"contractor_notes.txt": ["Follow-up needed: 203.0.113.9 flagged twice this month.",
                                          "Internal routing suggests it's not external. Can't confirm yet."]},
    }, "notes.txt": "MIRA: Don't just tell me where it shows up. Tell me how many times, total, across everything.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("traces_personal")
def traces_personal() -> tuple[World, Session]:
    """Level 43 (story): Mira checks in directly — this stopped being a routine client job a while ago."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"inbox": {"mira_checkin.txt": [
        "MIRA:", "", "This isn't just a client job anymore. Somebody's been patient enough to wait weeks, careful enough to "
        "only show up when nobody's watching, and interested enough to follow you home, metaphorically speaking.",
        "", "I want to know who's doing this. I think you do too. But I'm not deciding that for you — tell me if you're in, "
        "all the way, or if you want to hand this off to someone else before it gets complicated.", "---",
    ]}, "notes.txt": "NEXUS: Mira wants a straight answer. Read it, then give her one.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("traces_harden")
def traces_harden() -> tuple[World, Session]:
    """Level 44: before going further, lock the dossier down — chmod -R, the recursive flag on an already-known command."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"dossier": {
        "jan03.log": ["09:14 svc[auth]: probe from 203.0.113.9", "09:15 svc[auth]: probe rejected"],
        "jan04.log": ["02:14 svc[auth]: session opened from 203.0.113.9", "02:55 svc[auth]: session closed"],
        "misc": {"contractor_notes.txt": ["Follow-up needed: 203.0.113.9 flagged twice this month."]},
    }, "notes.txt": "NEXUS: If we're taking this further, that whole dossier folder needs to be locked down first. All of "
                   "it, not file by file.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("traces_handoff")
def traces_handoff() -> tuple[World, Session]:
    """Level 45 (milestone): closes Act II — assemble the case file, save it, and archive it somewhere only root can
    touch. Promotion to NETRUNNER, and the handoff into Act III's direct look at Nexus Company's own infrastructure."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"dossier": {
        "jan03.log": ["09:14 svc[auth]: probe from 203.0.113.9", "09:15 svc[auth]: probe rejected"],
        "jan04.log": ["02:14 svc[auth]: session opened from 203.0.113.9", "02:55 svc[auth]: session closed"],
        "misc": {"contractor_notes.txt": ["Follow-up needed: 203.0.113.9 flagged twice this month.",
                                          "Internal routing suggests it's not external. Can't confirm yet."]},
    }, "notes.txt": "MIRA: Pull everything on 203.0.113.9 into one file, keep a copy where only root can touch it, and "
                   "we're done with this chapter.\n"},
                        root_extra={"archive": {"_mode": 0o700}})
    m.data["sudoers"] = {"operator": {"commands": "ALL", "nopasswd": True}}
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


# ============================================================================================ Act III — The Network
NX_IP = "203.0.113.9"              # the "patient address" from Act I/II, confirmed in Act III as Nexus Company's own edge server
NX_DOMAIN = "nexus-company.com"
NX_HOST = "cloud-edge"


def _recon_world(services: list[Service] | None = None, extra_target_fs: dict | None = None, discovered: bool = False) -> tuple[World, Machine, Machine]:
    """Player's home-rig plus the Nexus Company edge server at NX_IP, linked as neighbours — the shared setup for every
    Act III, Chapter 1 recon mission. ``discovered`` pre-populates world.discovered, for missions that assume an earlier
    ping/lookup already happened."""
    world = World(clock=lambda: EPOCH)
    player = _player_machine({"notes.txt": "NEXUS: Time to stop reading about that address secondhand.\n"})
    target = Machine(NX_HOST, NX_HOST, NX_IP, "linux", VFS("posix", clock=lambda: EPOCH))
    target.domain = NX_DOMAIN
    target.add_user(User("root", 0, 0, ("root",), "/root", admin=True, password="toor"))
    target.add_user(User("deploy", 1000, 1000, ("deploy",), "/home/deploy", password="n3xus-deploy!"))
    target.fs.load(extra_target_fs or {"home": {"deploy": {"_owner": "deploy", "_group": "deploy"}}})
    target.services = services if services is not None else [Service(80, "http", "nginx/1.24.0", "open",
                      data={"pages": {"/": {"body": "<html><body><h1>Nexus Company</h1><p>Edge relay — internal use only.</p></body></html>", "status": 200}}})]
    world.add(player)
    world.add(target)
    player.neighbors.append(target.id)
    world.dns[NX_HOST] = NX_IP
    world.dns[NX_DOMAIN] = NX_IP
    world.whois[NX_DOMAIN] = ("Domain Name: NEXUS-COMPANY.COM\nRegistrar: MERIDIAN DOMAIN REGISTRY\n"
                              "Updated Date: 2049-11-03T00:00:00Z\nCreation Date: 2031-06-04T00:00:00Z\nRegistry Expiry Date: 2052-06-04T00:00:00Z")
    if discovered:
        world.discovered.add(target.id)
    return world, player, target


@scenario("network_ping")
def network_ping() -> tuple[World, Session]:
    """Level 46: confirm the address is actually alive before anything else — the first ping against a real destination."""
    world, player, _target = _recon_world()
    return world, Session(player, player.users["operator"], "bash")


@scenario("network_resolve")
def network_resolve() -> tuple[World, Session]:
    """Level 47: dig/nslookup/host — resolve nexus-company.com and confirm it lands on the same address that's been
    showing up in logs since Act I."""
    world, player, _target = _recon_world(discovered=True)
    return world, Session(player, player.users["operator"], "bash")


@scenario("network_whois")
def network_whois() -> tuple[World, Session]:
    """Level 48: whois — the domain's own paperwork. Registered 2031, years before any of this started."""
    world, player, _target = _recon_world(discovered=True)
    return world, Session(player, player.users["operator"], "bash")


@scenario("network_selfcheck")
def network_selfcheck() -> tuple[World, Session]:
    """Level 49 (standard): ip/ifconfig/arp — a look at the player's own network position before going further out."""
    world, player, _target = _recon_world(discovered=True)
    return world, Session(player, player.users["operator"], "bash")


@scenario("network_oduya")
def network_oduya() -> tuple[World, Session]:
    """Level 50 (story): Oduya, Mira's more experienced asset, is introduced — a warning before the player goes any
    further at a company target directly."""
    world, player, _target = _recon_world(discovered=True)
    player.fs.load({"home": {"operator": {"_owner": "operator", "_group": "operator", "inbox": {"oduya_intro.txt": [
        "FROM: Oduya", "", "Mira asked me to say something before you go further. I've worked Nexus Company targets "
        "longer than you've been doing this at all.", "",
        "They notice. Not always fast, but they notice. Confirm what you're looking at before you touch it, keep your "
        "footprint boring, and if something looks too easy, it probably is.",
        "", "Welcome to the part of the job that can actually go wrong.", "- O.",
    ]}}}})
    return world, Session(player, player.users["operator"], "bash")


@scenario("network_fetch")
def network_fetch() -> tuple[World, Session]:
    """Level 51: curl against the exposed edge page — the first look at what the server is actually showing the public."""
    world, player, _target = _recon_world(discovered=True)
    return world, Session(player, player.users["operator"], "bash")


@scenario("network_download")
def network_download() -> tuple[World, Session]:
    """Level 52 (standard): wget — a changelog file left reachable on the same web root, saved and read locally."""
    services = [Service(80, "http", "nginx/1.24.0", "open", data={"pages": {
        "/": {"body": "<html><body><h1>Nexus Company</h1><p>Edge relay — internal use only.</p></body></html>", "status": 200},
        "/changelog.txt": {"body": "2049-12-20 - rotated edge credentials\n2049-12-28 - disabled legacy telemetry relay\n"
                                   "2050-01-02 - re-enabled relay 'for diagnostics' (temporary)\n", "status": 200, "headers": {"Content-Type": "text/plain"}},
    }})]
    world, player, _target = _recon_world(services=services, discovered=True)
    return world, Session(player, player.users["operator"], "bash")


@scenario("network_services")
def network_services() -> tuple[World, Session]:
    """Level 53 (milestone): netstat/ss on the player's own machine, plus what's actually open on the target — a full
    picture of the edge server before Chapter 2 goes after what's actually running on it. Closes Chapter 1."""
    services = [Service(80, "http", "nginx/1.24.0", "open", data={"pages": {
        "/": {"body": "<html><body><h1>Nexus Company</h1><p>Edge relay — internal use only.</p></body></html>", "status": 200}}}),
        Service(22, "ssh", "OpenSSH 9.6", "closed"), Service(443, "https", "nginx/1.24.0", "open")]
    world, player, target = _recon_world(services=services, discovered=True)
    player.services = [Service(22, "ssh", "OpenSSH 9.6", "open")]
    return world, Session(player, player.users["operator"], "bash")


# ----------------------------------------------------------------------------------------- Act III — The Network, Chapter 2
OPS_PAGES = {
    "/": {"body": "<html><body><h1>Nexus Company</h1><p>Edge relay — internal use only.</p></body></html>", "status": 200},
    "/robots.txt": {"body": "User-agent: *\nDisallow: /ops-console/\n", "status": 200, "headers": {"Content-Type": "text/plain"}},
    "/ops-console/": {"body": "<html><body><h1>Index of /ops-console/</h1><ul><li><a href='backup.cfg'>backup.cfg</a></li></ul></body></html>", "status": 200},
    "/ops-console/backup.cfg": {"body": "# deploy automation config - DO NOT COMMIT\nDEPLOY_HOST=203.0.113.9\nDEPLOY_USER=deploy\n"
                                        "DEPLOY_PASS=n3xus-deploy!\n# see ops.nexus-company.com for the console itself\n# rotate before Q1 audit\n",
                                 "status": 200, "headers": {"Content-Type": "text/plain"}},
}


@scenario("network_altdns")
def network_altdns() -> tuple[World, Session]:
    """Level 54 (standard): nslookup and host — two more ways to resolve the same name, the habit of not trusting a
    single tool's answer."""
    world, player, _target = _recon_world(discovered=True)
    return world, Session(player, player.users["operator"], "bash")


@scenario("network_ifconfig")
def network_ifconfig() -> tuple[World, Session]:
    """Level 55: ifconfig — the older interface tool, same information ip addr already gave at Level 49."""
    world, player, _target = _recon_world(discovered=True)
    return world, Session(player, player.users["operator"], "bash")


@scenario("network_robots")
def network_robots() -> tuple[World, Session]:
    """Level 56: robots.txt — a polite request to crawlers, not a lock. It names the one path worth checking first."""
    services = [Service(80, "http", "nginx/1.24.0", "open", data={"pages": OPS_PAGES})]
    world, player, _target = _recon_world(services=services, discovered=True)
    return world, Session(player, player.users["operator"], "bash")


@scenario("network_backdoor_config")
def network_backdoor_config() -> tuple[World, Session]:
    """Level 57 (standard): the path robots.txt tried to hide leads straight to a deployment config with live
    credentials in it — a very ordinary, very real way servers get compromised."""
    services = [Service(80, "http", "nginx/1.24.0", "open", data={"pages": OPS_PAGES})]
    world, player, _target = _recon_world(services=services, discovered=True)
    return world, Session(player, player.users["operator"], "bash")


@scenario("network_caution")
def network_caution() -> tuple[World, Session]:
    """Level 58 (story): Oduya's warning from Level 50 becomes concrete — live credentials, found, not earned. What
    now is a real question, not a rhetorical one."""
    world, player, _target = _recon_world(discovered=True)
    player.fs.load({"home": {"operator": {"_owner": "operator", "_group": "operator", "inbox": {"oduya_caution.txt": [
        "FROM: Oduya", "", "Found credentials on a server you don't own. That's the easy part. The question is what "
        "you do with them.", "",
        "Mira will tell you this is fine because the client approved going after this target. I'll tell you that "
        "'approved' and 'careful' aren't the same thing. Tell me you're going to be careful.", "---",
    ]}}}})
    return world, Session(player, player.users["operator"], "bash")


@scenario("network_subdomain")
def network_subdomain() -> tuple[World, Session]:
    """Level 59: the backup config mentioned a console at ops.nexus-company.com — it resolves, but to a private
    address nothing here can actually reach. A real distinction: knowing a name's address isn't the same as reaching it."""
    world, player, _target = _recon_world(discovered=True)
    world.dns["ops.nexus-company.com"] = "10.20.30.5"
    world.whois["ops.nexus-company.com"] = ("Domain Name: OPS.NEXUS-COMPANY.COM\nRegistrar: MERIDIAN DOMAIN REGISTRY\n"
                                            "Updated Date: 2049-08-14T00:00:00Z\nCreation Date: 2047-02-01T00:00:00Z")
    return world, Session(player, player.users["operator"], "bash")


@scenario("network_banner")
def network_banner() -> tuple[World, Session]:
    """Level 60: curl -I — headers only, no body. Banner-grabbing: what the server volunteers about itself before
    you've asked it to do anything."""
    services = [Service(80, "http", "nginx/1.24.0", "open", data={"pages": OPS_PAGES})]
    world, player, _target = _recon_world(services=services, discovered=True)
    return world, Session(player, player.users["operator"], "bash")


@scenario("network_dossier2")
def network_dossier2() -> tuple[World, Session]:
    """Level 61 (milestone): compile Chapter 2's findings the same way Act II did — search, save, archive. Closes
    Chapter 2 and hands off directly into Chapter 3's login attempt."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"recon": {
        "robots.txt": "User-agent: *\nDisallow: /ops-console/\n",
        "backup.cfg": "# deploy automation config - DO NOT COMMIT\nDEPLOY_HOST=203.0.113.9\nDEPLOY_USER=deploy\n"
                     "DEPLOY_PASS=n3xus-deploy!\n# see ops.nexus-company.com for the console itself\n# rotate before Q1 audit\n",
    }, "notes.txt": "MIRA: Pull every credential-looking string out of what you've found this chapter into one file, "
                   "and archive a copy before we go any further.\n"},
                        root_extra={"archive": {"_mode": 0o700}})
    m.data["sudoers"] = {"operator": {"commands": "ALL", "nopasswd": True}}
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


# ----------------------------------------------------------------------------------------- Act III — The Network, Chapter 3
DEPLOY_USER, DEPLOY_PASS = "deploy", "n3xus-deploy!"
RELAY_FS = {
    "home": {"deploy": {"_owner": "deploy", "_group": "deploy", "deploy.log": ["Routine deploy, no incidents.\n"]}},
    "srv": {"relay": {
        "README.txt": ["Relay node for edge telemetry.", "Do not modify manually — managed by the deploy pipeline."],
        "relay.log": ["2050-01-01 00:00:02 relay: boot sequence nominal", "2050-01-01 00:00:05 relay: establishing uplink to ARCHITECT-NEXUS sync endpoint",
                      "2050-01-01 00:00:09 relay: sync accepted, partition: COMPLIANT", "2050-01-02 03:14:00 relay: unscheduled external poll (trace matched: house query)"],
    }},
}
RELAY_SERVICES = [Service(80, "http", "nginx/1.24.0", "open", data={"pages": OPS_PAGES}), Service(22, "ssh", "OpenSSH 9.6", "open")]


@scenario("network_login")
def network_login() -> tuple[World, Session]:
    """Level 62: the first real login to another machine — the deploy credentials found in Chapter 2, finally used."""
    world, player, _target = _recon_world(services=RELAY_SERVICES, discovered=True)
    return world, Session(player, player.users["operator"], "bash")


@scenario("network_remote_explore")
def network_remote_explore() -> tuple[World, Session]:
    """Level 63 (standard): once logged in, the same find/cat skills from Act I work identically on someone else's
    machine — nothing about the commands changes, only whose files they touch."""
    world, player, _target = _recon_world(services=RELAY_SERVICES, extra_target_fs=RELAY_FS, discovered=True)
    return world, Session(player, player.users["operator"], "bash")


@scenario("network_remote_sudo")
def network_remote_sudo() -> tuple[World, Session]:
    """Level 64: not every account is equally privileged — deploy has no sudo rights on this box at all."""
    world, player, _target = _recon_world(services=RELAY_SERVICES, extra_target_fs=RELAY_FS, discovered=True)
    return world, Session(player, player.users["operator"], "bash")


@scenario("network_architect_hint")
def network_architect_hint() -> tuple[World, Session]:
    """Level 65 (story): the relay log mentions "ARCHITECT-NEXUS sync" and a "partition" — meaningless to the player
    right now, and NEXUS's reaction to the name is noticeably off. The twist itself is Act VII; this just plants it."""
    world, player, _target = _recon_world(services=RELAY_SERVICES, extra_target_fs=RELAY_FS, discovered=True)
    return world, Session(player, player.users["operator"], "bash")


@scenario("network_loot")
def network_loot() -> tuple[World, Session]:
    """Level 66: scp pulls a copy of relay.log back for the record — the first file taken off someone else's machine
    instead of just read in place."""
    world, player, _target = _recon_world(services=RELAY_SERVICES, extra_target_fs=RELAY_FS, discovered=True)
    return world, Session(player, player.users["operator"], "bash")


@scenario("network_remote_ps")
def network_remote_ps() -> tuple[World, Session]:
    """Level 67 (standard): what's actually running on the relay box, and who else is logged in — the same incident-
    response habits from Act II, now aimed outward instead of at the player's own machine."""
    world, player, target = _recon_world(services=RELAY_SERVICES, extra_target_fs=RELAY_FS, discovered=True)
    target.processes = [Process(pid=210, user="deploy", name="relay-agent", cmd="/srv/relay/bin/relay-agent --config /srv/relay/config.yml", cpu=2.1, mem=0.8),
                        Process(pid=411, user="root", name="telemetry-shim", cmd="/usr/local/bin/telemetry-shim --passthrough", cpu=0.3, mem=0.2)]
    return world, Session(player, player.users["operator"], "bash")


@scenario("network_exit")
def network_exit() -> tuple[World, Session]:
    """Level 68: exit returns to the previous machine in the session stack, exactly where you left it — a real
    distinction worth testing deliberately, not just assuming."""
    world, player, _target = _recon_world(services=RELAY_SERVICES, discovered=True)
    player.fs.load({"home": {"operator": {"_owner": "operator", "_group": "operator",
                                          "welcome_back.txt": "Back on home-rig. If you can read this, exit actually worked.\n"}}})
    return world, Session(player, player.users["operator"], "bash")


@scenario("network_debrief")
def network_debrief() -> tuple[World, Session]:
    """Level 69 (story): Mira and NEXUS react to the ARCHITECT-NEXUS discovery. Stakes rise heading into the next act."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"inbox": {"mira_architect.txt": [
        "MIRA:", "", "'ARCHITECT-NEXUS sync.' 'Partition: compliant.' I don't love any of those words in that order.",
        "", "I don't know what that machine's actually part of yet. I intend to find out. So do you, I'd guess.", "---",
    ]}, "notes.txt": "NEXUS: Mira wants to talk about what you found. Read it.\n"})
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")


@scenario("network_handoff")
def network_handoff() -> tuple[World, Session]:
    """Level 70 (milestone): one last login, one last file pulled out, archived properly — closing Act III the same
    disciplined way Act II closed. Promotion to CRYPTOSMITH."""
    world, player, _target = _recon_world(services=RELAY_SERVICES, extra_target_fs=RELAY_FS, discovered=True)
    player.fs.load({"archive": {"_owner": "root", "_group": "root", "_mode": 0o700}})
    player.data["sudoers"] = {"operator": {"commands": "ALL", "nopasswd": True}}
    return world, Session(player, player.users["operator"], "bash")


# ============================================================================================ Act V — Windows
OPS_IP = "10.20.30.5"              # the "unreachable" subdomain from Act III Level 59 — now finally reachable
OPS_HOST = "OPS-CONSOLE"
OPS_DOMAIN = "NEXUSCORP"
OPS_USER, OPS_PASS = "opsadmin", "Meridian-2050!"

WIN_TREE = {
    "Users": {"opsadmin": {"_owner": "opsadmin", "_group": "opsadmin",
        "Desktop": {"notes.txt": ["Reminder: rotate the console password after the Q1 audit.", "Ticket queue is a mess again — ask IT to look at the backlog service."]},
        "Documents": {"kade_voss_memo.txt": [
            "FROM: K. Voss, Security Operations", "TO: Ops Console Admins", "SUBJECT: Anomalous access pattern — edge relay",
            "", "We've identified irregular access against the edge relay infrastructure over the past several weeks.",
            "Pattern suggests a patient external actor, not an automated scan. I am opening a formal investigation.",
            "", "Until further notice: rotate credentials on anything externally reachable, and report anything that",
            "doesn't look like routine traffic directly to me, not to the ticket queue.", "", "- K. Voss",
        ]},
    }, "Public": {}},
    "Windows": {"System32": {}},
    "inetpub": {"wwwroot": {}},
}


def _win_target_world() -> tuple[World, Machine, Machine]:
    """Player's home-rig plus a Windows admin console at the Act III Level-59 "unreachable" subdomain — the first
    Windows target of the campaign, shared by every Act V, Chapter 1 mission."""
    world = World(clock=lambda: EPOCH)
    player = _player_machine({"notes.txt": "MIRA: New target. Windows this time — different commands, same discipline.\n"})
    target = Machine(OPS_HOST, OPS_HOST, OPS_IP, "windows", VFS("windows", clock=lambda: EPOCH))
    target.domain = OPS_DOMAIN
    target.add_user(User("Administrator", 500, 500, ("Administrators",), "C:\\Users\\Administrator", admin=True, password="R3curs1ve!Root"))
    target.add_user(User(OPS_USER, 1000, 1000, ("Administrators",), f"C:\\Users\\{OPS_USER}", password=OPS_PASS))
    target.fs.load(WIN_TREE, "C:\\")
    target.services = [Service(22, "ssh", "OpenSSH for Windows 9.6", "open")]
    target.processes = [Process(pid=4, user="SYSTEM", name="System", cmd="", cpu=0.0, mem=0.1),
                        Process(pid=812, user=OPS_USER, name="explorer.exe", cmd="C:\\Windows\\explorer.exe", cpu=0.3, mem=1.2),
                        Process(pid=2290, user=OPS_USER, name="ticket-sync.exe", cmd="C:\\Program Files\\OpsTools\\ticket-sync.exe --poll 30", cpu=41.0, mem=3.4)]
    target.data["winservices"] = [{"Status": "Running", "Name": "Spooler", "DisplayName": "Print Spooler"},
                                  {"Status": "Stopped", "Name": "wuauserv", "DisplayName": "Windows Update"},
                                  {"Status": "Running", "Name": "sshd", "DisplayName": "OpenSSH SSH Server"}]
    world.add(player)
    world.add(target)
    player.neighbors.append(target.id)
    world.dns[OPS_HOST] = OPS_IP
    world.dns["ops.nexus-company.com"] = OPS_IP
    world.discovered.add(target.id)
    return world, player, target


@scenario("win_login")
def win_login() -> tuple[World, Session]:
    """Level 96: the Act III Level-59 subdomain is finally reachable — the first Windows login of the campaign."""
    world, player, _target = _win_target_world()
    player.fs.load({"home": {"operator": {"_owner": "operator", "_group": "operator", "inbox": {"mira_opsconsole.txt": [
        "MIRA:", "", "We found a way to that subdomain from Level 59. It's a Windows admin console — different world, "
        f"same job. Credentials: {OPS_USER} / {OPS_PASS}.", "", "ssh works the same way into Windows. The prompt will "
        "look different once you're in — that's normal.", "---",
    ]}}}})
    return world, Session(player, player.users["operator"], "bash")


@scenario("win_explore")
def win_explore() -> tuple[World, Session]:
    """Level 97: Get-ChildItem / Set-Location — the same navigation idea, PowerShell's own vocabulary for it."""
    world, player, _target = _win_target_world()
    return world, Session(player, player.users["operator"], "bash")


@scenario("win_notes")
def win_notes() -> tuple[World, Session]:
    """Level 98: Get-Content — reading a file on a Windows machine works the same as cat, under a different name."""
    world, player, _target = _win_target_world()
    return world, Session(player, player.users["operator"], "bash")


@scenario("win_process")
def win_process() -> tuple[World, Session]:
    """Level 99 (standard): Get-Process / Stop-Process — a runaway ticket-sync tool eating CPU, same incident-response
    habit as Act II, PowerShell's own cmdlets this time."""
    world, player, _target = _win_target_world()
    return world, Session(player, player.users["operator"], "bash")


@scenario("win_kade")
def win_kade() -> tuple[World, Session]:
    """Level 100 (story): Kade Voss, Nexus Company's security director, is introduced — a memo on the console itself,
    already investigating the same "patient" pattern from Acts I-III. The first named, active hunter in the campaign."""
    world, player, _target = _win_target_world()
    return world, Session(player, player.users["operator"], "bash")


@scenario("win_services")
def win_services() -> tuple[World, Session]:
    """Level 101: Get-Service — Windows's own service list, including its own sshd entry, right there in plain sight."""
    world, player, _target = _win_target_world()
    return world, Session(player, player.users["operator"], "bash")


@scenario("win_search")
def win_search() -> tuple[World, Session]:
    """Level 102 (standard): Select-String — the Windows grep. A ticket log with one line that actually matters among
    routine noise, same shape as Act I's first real log."""
    world, player, target = _win_target_world()
    target.fs.load({"inetpub": {"wwwroot": {}}, "Users": {OPS_USER: {"_owner": OPS_USER, "_group": OPS_USER,
        "ticket-sync.log": ["09:00 poll ok, 0 new tickets", "09:30 poll ok, 2 new tickets", "10:00 poll ok, 0 new tickets",
                            "10:30 WARNING auth token near expiry for svc-relay-sync", "11:00 poll ok, 1 new ticket"]}}}, "C:\\")
    return world, Session(player, player.users["operator"], "bash")


@scenario("win_dossier")
def win_dossier() -> tuple[World, Session]:
    """Level 103 (milestone): closes Act V, Chapter 1 — compile what Kade Voss's memo and the ticket log revealed, the
    same disciplined habit as every chapter close so far."""
    world = World(clock=lambda: EPOCH)
    m = _player_machine({"winnotes": {
        "kade_voss_memo.txt": ["FROM: K. Voss, Security Operations", "SUBJECT: Anomalous access pattern — edge relay",
                               "Pattern suggests a patient external actor, not an automated scan."],
        "ticket-sync.log": ["10:30 WARNING auth token near expiry for svc-relay-sync"],
    }, "notes.txt": "MIRA: Pull the Kade Voss memo and that token warning into one file. We need to know everything "
                   "he already knows before he gets any further ahead of us.\n"},
                        root_extra={"archive": {"_mode": 0o700}})
    m.data["sudoers"] = {"operator": {"commands": "ALL", "nopasswd": True}}
    world.add(m)
    return world, Session(m, m.users["operator"], "bash")
