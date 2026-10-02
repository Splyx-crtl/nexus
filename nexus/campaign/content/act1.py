"""Act I — Awakening (levels 1-20, docs/story/02-acts-and-levels.md). Levels 1-14 are written: ten hand-written missions
closing "Chapter 1" (first contact with NEXUS, then Mira, then a first real result) plus four generated Minis for extra
practice/replay value. Levels 15-20 (the rest of Act I, up to the TRACER rank) are not written yet.

Every mission's 'number' must be >= the engine level of every command its solution uses (checked by
validator.check_command_levels and by solver.solve(), which solves at the mission's own level by default) — a mission a
player could not actually have the tools for yet is a bug, not a difficulty choice. See docs/3.0-PROGRESS.md's C2/C4 entries
for the real instance of this bug this file originally had (grep used three levels before it unlocks) and how it was caught.
"""
from __future__ import annotations

from ..generators import generate_batch
from ..mission import Mission, Objective

ACT1_HAND_WRITTEN = [
    Mission(
        id="act1_m01", number=1, act=1, size="mini", title="First Light", scenario="awakening_boot",
        briefing=["NEXUS: Good, you're online. Try 'ls' — show me what's actually in this folder."],
        debrief=["NEXUS: One file. Let's start there."],
        objectives=[Objective(event="command", match={"name": "ls", "status": 0}, text="List the folder with ls",
                              hints=["ls lists what's inside the current folder.", "Just type: ls", "ls"])],
        solution=["ls"], reward_xp=20, tags=["bash", "act1"],
    ),
    Mission(
        id="act1_m02", number=2, act=1, size="mini", title="Reading the Room", scenario="awakening_boot",
        requires=["act1_m01"],
        briefing=["NEXUS: Read it. 'cat welcome.txt'."],
        debrief=["NEXUS: There. Now you've heard me say hello twice. Let's not make a habit of it."],
        objectives=[Objective(event="file_read", match={"path__glob": "*welcome.txt"}, text="Read welcome.txt",
                              hints=["cat prints a file's contents.", "Try: cat welcome.txt", "cat welcome.txt"])],
        solution=["cat welcome.txt"], reward_xp=20, tags=["bash", "act1"],
    ),
    Mission(
        id="act1_m03", number=3, act=1, size="standard", title="The Hand-Off", scenario="awakening_deaddrop",
        requires=["act1_m02"],
        briefing=["NEXUS: Someone left you something. It won't be sitting out in the open — check for hidden files.",
                  "NEXUS: 'ls -a' shows everything 'ls' hides by default."],
        debrief=["NEXUS: A decommissioned server. Allegedly. I don't love how many times that word shows up in this business."],
        objectives=[
            Objective(event="command", match={"name": "ls", "args__contains": "-a", "status": 0}, text="List hidden files (ls -a)",
                     hints=["Hidden files start with a dot and don't show up in a plain ls.", "Try: ls -a", "ls -a"]),
            Objective(event="file_read", match={"path__glob": "*.dropbox/readme"}, text="Read the dropbox readme",
                     hints=["Something's inside the .dropbox folder.", "Try: cat .dropbox/readme", "cat .dropbox/readme"]),
            Objective(event="file_read", match={"path__glob": "*package.manifest"}, text="Read the job manifest",
                     hints=["There's a second file next to the readme.", "Try: cat .dropbox/package.manifest", "cat .dropbox/package.manifest"]),
        ],
        solution=["ls -a", "cat .dropbox/readme", "cat .dropbox/package.manifest"], reward_xp=60, tags=["bash", "act1", "hidden-files"],
    ),
    Mission(
        id="act1_m04", number=4, act=1, size="mini", title="Setting Up Shop", scenario="awakening_workspace",
        requires=["act1_m03"],
        briefing=["NEXUS: Before we go further, set up a proper workspace. Make a folder called 'jobs' and an empty file "
                  "in it called 'log.txt' — we'll use it."],
        debrief=["NEXUS: Tidy. I like tidy. It won't last."],
        objectives=[
            Objective(event="command", match={"name": "mkdir", "args__contains": "jobs", "status": 0}, text="Create a 'jobs' folder",
                     hints=["mkdir makes a new folder.", "Try: mkdir jobs", "mkdir jobs"]),
            Objective(event="command", match={"name": "touch", "args__contains": "jobs/log.txt", "status": 0}, text="Create jobs/log.txt",
                     hints=["touch creates an empty file.", "Try: touch jobs/log.txt", "touch jobs/log.txt"]),
        ],
        solution=["mkdir jobs", "touch jobs/log.txt"], reward_xp=25, tags=["bash", "act1"],
    ),
    Mission(
        id="act1_m05", number=5, act=1, size="mini", title="RTFM", scenario="awakening_manual",
        requires=["act1_m04"],
        briefing=["NEXUS: Every one of these tools has a manual built in. Get in the habit now: 'man ls'."],
        debrief=["NEXUS: When in doubt, that's where you look. Not at me."],
        objectives=[Objective(event="man_read", match={"name": "ls"}, text="Read the manual page for ls",
                              hints=["man opens a command's manual.", "Try: man ls", "man ls"])],
        solution=["man ls"], reward_xp=20, tags=["bash", "act1"],
    ),
    Mission(
        id="act1_m06", number=6, act=1, size="mini", title="Tidy Up", scenario="awakening_tidy",
        requires=["act1_m05"],
        briefing=["NEXUS: This folder's a mess. Get rid of the old draft, and rename the real one to something sane — 'protocol.txt' will do."],
        debrief=["NEXUS: Better. A messy folder is how you miss the one file that matters."],
        objectives=[
            Objective(event="command", match={"name": "rm", "args__contains": "draft_v2_FINAL_reall_OLD.txt", "status": 0},
                     text="Delete the old draft", hints=["rm deletes a file.", "Try: rm draft_v2_FINAL_reall_OLD.txt", "rm draft_v2_FINAL_reall_OLD.txt"]),
            Objective(event="command", match={"name": "mv", "status": 0}, text="Rename the real draft to protocol.txt",
                     hints=["mv renames (or moves) a file.", "Try: mv draft_v2_FINAL_reall.txt protocol.txt", "mv draft_v2_FINAL_reall.txt protocol.txt"]),
        ],
        solution=["rm draft_v2_FINAL_reall_OLD.txt", "mv draft_v2_FINAL_reall.txt protocol.txt"], reward_xp=30, tags=["bash", "act1"],
    ),
    Mission(
        id="act1_m07", number=7, act=1, size="standard", title="Needle and Haystack", scenario="awakening_search",
        requires=["act1_m06"],
        briefing=["NEXUS: Somewhere under this folder is a file named 'protocol.key'. I don't remember exactly where. "
                  "This is what 'find' is for."],
        debrief=["NEXUS: Buried two years deep. Someone wanted that forgotten, not just tidy."],
        objectives=[Objective(event="found", match={"path__glob": "*protocol.key"}, text="Find protocol.key",
                              hints=["find searches an entire folder tree by name.", "Try: find . -name protocol.key", "find . -name protocol.key"])],
        solution=["find . -name protocol.key"], reward_xp=45, tags=["bash", "act1", "find"],
    ),
    Mission(
        id="act1_m08", number=8, act=1, size="mini", title="A Familiar Name", scenario="awakening_firstgrep",
        requires=["act1_m07"],
        briefing=["NEXUS: There's a roster file. My name's apparently on it. Find the line — 'grep' searches a file's "
                  "contents for a word, instead of you reading the whole thing."],
        debrief=["NEXUS: 'classified.' Of course it is."],
        objectives=[Objective(event="grep_match", match={"pattern__contains": "NEXUS"}, text="Find the line mentioning NEXUS in roster.txt",
                              hints=["grep searches inside a file for a word or pattern.", "Try: grep NEXUS roster.txt", "grep NEXUS roster.txt"])],
        solution=["grep NEXUS roster.txt"], reward_xp=40, tags=["bash", "act1", "grep"],
    ),
    Mission(
        id="act1_m09", number=9, act=1, size="story", title="First Contact", scenario="awakening_contact",
        requires=["act1_m08"],
        briefing=["NEXUS: Someone's been watching our traffic. There's a message in your inbox."],
        debrief=["NEXUS: You just agreed to work for someone whose face you've never seen, based on one paragraph.",
                 "NEXUS: ...I approve, for what it's worth. Welcome to the deep end.",
                 "MIRA: Good. First job's already in the folder you just made. Don't make me regret this."],
        objectives=[
            Objective(event="file_read", match={"path__glob": "*unread_001.txt"}, text="Read Mira's message",
                     hints=["Someone left a message in your inbox folder.", "Try: cat inbox/unread_001.txt", "cat inbox/unread_001.txt"]),
            Objective(event="command", match={"name": "echo", "status": 0}, text="Reply below the line and save it to the same file",
                     hints=["She asked you to write your reply into the file and save it.",
                           "You can append text to a file with >>: echo \"I'm in.\" >> inbox/unread_001.txt",
                           "echo \"I'm in.\" >> inbox/unread_001.txt"]),
        ],
        solution=["cat inbox/unread_001.txt", 'echo "I\'m in." >> inbox/unread_001.txt'], reward_xp=70, tags=["bash", "act1", "story", "mira"],
    ),
    Mission(
        id="act1_m10", number=10, act=1, size="milestone", title="Allegedly Decommissioned", scenario="awakening_logs",
        requires=["act1_m09"],
        briefing=["MIRA: Remember that 'decommissioned' server from the dead drop? It's not as dead as advertised.",
                  "MIRA: There's a system log. Somewhere in today's noise is a line that actually matters — an account "
                  "that's about to expire and nobody's rotated. Find it."],
        debrief=["MIRA: Good work for a first job. Don't get used to me being this nice about it.",
                 "NEXUS: Chapter closed. There's more where that came from."],
        objectives=[Objective(event="grep_match", match={"pattern__contains": "contractor_temp"}, text="Find the contractor_temp line in the log",
                              hints=["grep searches a file for a word or pattern.", "Try: grep contractor_temp /var/log/system.log",
                                    "grep contractor_temp /var/log/system.log"])],
        solution=["grep contractor_temp /var/log/system.log"], reward_xp=100, tags=["bash", "act1", "grep", "milestone"],
    ),
]

# Extra practice / replay-value Minis (docs/story/02-acts-and-levels.md §1: "new" from here on is often technique or
# variety, not a brand-new command) — placed after Level 10 since grep is now safely unlocked for them.
ACT1_GENERATED = [
    *generate_batch("grep_mini", count=2, start_id=11, act=1, base_level=11, seed=1),
    *generate_batch("hidden_file_mini", count=2, start_id=13, act=1, base_level=13, seed=2),
]

ACT1 = [*ACT1_HAND_WRITTEN, *ACT1_GENERATED]
