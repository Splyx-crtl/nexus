"""Act I — Awakening (levels 1-20, docs/story/02-acts-and-levels.md), now fully written. Chapter 1 (1-10) is first contact
with NEXUS, then Mira, then a first real result. Levels 11-14 are generated Minis for extra practice/replay value. Chapter 2
(15-20) is Mira's first real client work, teaching sort/uniq/cut/tr/diff/sed/awk, and closes on a milestone that chains all
of it together — the Act's promotion to TRACER and the hook into Act II.

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

# Chapter 2: Mira's first real client work. Each mission below introduces one text-processing tool as a technique that
# actually matters, not a flashcard — and the Level 20 milestone chains all of them together.
ACT1_CHAPTER2 = [
    Mission(
        id="act1_m15", number=15, act=1, size="mini", title="Counting the Noise", scenario="awakening_signal",
        requires=["act1_m10"],
        briefing=["MIRA: First real job. A client says their portal keeps getting hammered. I don't want a guess, I want "
                  "numbers — sort the log so repeats sit together, then count them."],
        debrief=["MIRA: Four hits from the same address in under a minute. That's not curiosity, that's a script.",
                 "NEXUS: Welcome to paid work. It's the same job, it just matters more if you get it wrong now."],
        objectives=[
            Objective(event="command", match={"name": "sort", "status": 0}, text="Sort access.log",
                     hints=["sort puts matching lines next to each other, which is what uniq needs.", "Try: sort access.log", "sort access.log"]),
            Objective(event="command", match={"name": "uniq", "args__contains": "-c", "status": 0}, text="Count the repeats (uniq -c)",
                     hints=["uniq -c counts how many times each line repeats, but only if they're already next to each other.",
                           "Try: sort access.log | uniq -c", "sort access.log | uniq -c"]),
        ],
        solution=["sort access.log | uniq -c"], reward_xp=50, tags=["bash", "act1", "sort", "uniq"],
    ),
    Mission(
        id="act1_m16", number=16, act=1, size="mini", title="Extract and Clean", scenario="awakening_ledger",
        requires=["act1_m15"],
        briefing=["MIRA: I need just the callsigns out of that roster, in caps, for my own ledger. Nothing else — not "
                  "the role, not the status."],
        debrief=["MIRA: Clean. You're learning to give people exactly what they asked for and nothing they didn't."],
        objectives=[
            Objective(event="command", match={"name": "cut", "args__contains": "-f1", "status": 0}, text="Pull out just the callsigns (cut -f1)",
                     hints=["cut -d: -f1 prints the first field of each colon-separated line.", "Try: cut -d: -f1 contacts.roster",
                           "cut -d: -f1 contacts.roster"]),
            Objective(event="command", match={"name": "tr", "args__contains": "A-Z", "status": 0}, text="Convert them to upper case (tr a-z A-Z)",
                     hints=["tr a-z A-Z upper-cases whatever text flows through it.", "Try: cut -d: -f1 contacts.roster | tr a-z A-Z",
                           "cut -d: -f1 contacts.roster | tr a-z A-Z"]),
        ],
        solution=["cut -d: -f1 contacts.roster | tr a-z A-Z"], reward_xp=45, tags=["bash", "act1", "cut", "tr"],
    ),
    Mission(
        id="act1_m17", number=17, act=1, size="standard", title="What Changed", scenario="awakening_manifest",
        requires=["act1_m16"],
        briefing=["MIRA: Remember that 'decommissioned' server's manifest from the dead drop? I got a second copy through "
                  "a different route. Compare them."],
        debrief=["MIRA: 'Active, restricted access.' Someone rewrote the official paperwork and left the old copy lying "
                 "around for us to find. That's not a mistake, that's sloppy — which is useful.",
                 "NEXUS: Noted. 'Decommissioned' was never true. Someone's been lying in writing."],
        objectives=[Objective(event="command", match={"name": "diff", "args__contains": "-u"}, text="Compare the two manifests (diff -u)",
                              hints=["diff -u shows exactly which lines differ between two files.",
                                    "Try: diff -u official_manifest.txt leaked_manifest.txt", "diff -u official_manifest.txt leaked_manifest.txt"])],
        solution=["diff -u official_manifest.txt leaked_manifest.txt"], reward_xp=65, tags=["bash", "act1", "diff", "story"],
    ),
    Mission(
        id="act1_m18", number=18, act=1, size="story", title="Rewriting the Record", scenario="awakening_coverup",
        requires=["act1_m17"],
        briefing=["MIRA: Before you touch that box again — you left your real address sitting in its session log last "
                  "time. Scrub the line. In place. Now."],
        debrief=["NEXUS: Congratulations, you're now someone who edits history on request. I have opinions about that. "
                 "I'm keeping them to myself. For now.",
                 "MIRA: Don't make a habit of needing this."],
        objectives=[Objective(event="command", match={"name": "sed", "args__contains": "-i", "status": 0}, text="Delete your trace from session.log in place (sed -i)",
                              hints=["sed -i '/pattern/d' file deletes every line matching pattern, directly in the file.",
                                    "Your real address is 10.44.0.7 — try: sed -i '/10.44.0.7/d' session.log",
                                    "sed -i '/10.44.0.7/d' session.log"])],
        solution=["sed -i '/10.44.0.7/d' session.log"], reward_xp=70, tags=["bash", "act1", "sed", "story"],
    ),
    Mission(
        id="act1_m19", number=19, act=1, size="standard", title="Patterns in the Chaos", scenario="awakening_pattern",
        requires=["act1_m18"],
        briefing=["MIRA: Pull every address that failed a login this week. Just the addresses — I don't need the "
                  "timestamps or the service name."],
        debrief=["MIRA: One of these isn't like the others. We'll get to that.",
                 "NEXUS: You just wrote your first real filter instead of reading one off a hint card. That's the job, "
                 "from here on."],
        objectives=[Objective(event="command", match={"name": "awk", "status": 0}, text="Print the address from every failed-login line",
                              hints=["awk reads the file by column: $3 is the third word on a line, $4 the fourth.",
                                    """Try: awk '$3=="FAIL" {print $4}' weekly.log""", """awk '$3=="FAIL" {print $4}' weekly.log"""])],
        solution=["""awk '$3=="FAIL" {print $4}' weekly.log"""], reward_xp=75, tags=["bash", "act1", "awk"],
    ),
    Mission(
        id="act1_m20", number=20, act=1, size="milestone", title="The Pattern Holds", scenario="awakening_convergence",
        requires=["act1_m19"],
        briefing=["NEXUS: Three days of logs off that same server. Somewhere in there is a pattern, not just noise. "
                  "Everything you've learned this week, use it."],
        debrief=["NEXUS: Same address, three separate days, never more than once a day. That's not a script hammering a "
                 "door — that's someone patient, checking back.",
                 "MIRA: Patient is worse than noisy. Noisy is a script. Patient is a person who knows exactly what "
                 "they're looking for and isn't in a hurry to find it.",
                 "NEXUS: Chapter closed. Rank up — you've earned TRACER. There's someone I think Mira should put you in "
                 "touch with. This gets bigger from here."],
        objectives=[
            Objective(event="command", match={"name": "grep", "args__contains": "-h", "status": 0}, text="Search every log at once (grep -h ... logs/*.log)",
                     hints=["-h stops grep printing which file a line came from, so three files read like one.",
                           """Try: grep -h "failed login" logs/*.log""", """grep -h "failed login" logs/*.log"""]),
            Objective(event="command", match={"name": "awk", "status": 0}, text="Pull out just the address (awk '{print $NF}')",
                     hints=["$NF always means 'the last field', however many fields a line has.", "Try: ... | awk '{print $NF}'", "awk '{print $NF}'"]),
            Objective(event="command", match={"name": "uniq", "args__contains": "-c", "status": 0}, text="Count how often each address shows up (uniq -c)",
                     hints=["Sort first, then uniq -c counts the repeats.", "Try: ... | sort | uniq -c", "sort | uniq -c"]),
            Objective(event="command", match={"name": "sort", "args__contains": "-nr", "status": 0}, text="Rank the counts, highest first (sort -nr)",
                     hints=["sort -nr sorts numbers in reverse — biggest first.", "Try: ... | sort -nr", "sort -nr"]),
        ],
        solution=["""grep -h "failed login" logs/*.log | awk '{print $NF}' | sort | uniq -c | sort -nr"""],
        reward_xp=150, tags=["bash", "act1", "milestone", "grep", "awk", "sort", "uniq"],
    ),
]

ACT1 = [*ACT1_HAND_WRITTEN, *ACT1_GENERATED, *ACT1_CHAPTER2]
