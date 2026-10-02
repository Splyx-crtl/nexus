"""Act I — Awakening (levels 1-20, docs/story/02-acts-and-levels.md). Only the first few levels are written, as a proof of
the v3 pipeline end to end; the rest of the act follows in later passes, plus a sample of generated Minis (C2's generator)."""
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
        id="act1_m04", number=4, act=1, size="standard", title="One Line That Matters", scenario="awakening_logs",
        requires=["act1_m03"],
        briefing=["NEXUS: Somewhere in today's log is a line that actually matters. The rest is noise — grep for the signal.",
                  "NEXUS: We're looking for anything about a contractor account."],
        debrief=["NEXUS: An account about to expire, and nobody's rotated it. Somebody's going to have a bad week. Not our problem. Yet."],
        objectives=[Objective(event="grep_match", match={"pattern__contains": "contractor_temp"}, text="Find the contractor_temp line in the log",
                              hints=["grep searches a file for a word or pattern.", "Try: grep contractor_temp /var/log/system.log",
                                    "grep contractor_temp /var/log/system.log"])],
        solution=["grep contractor_temp /var/log/system.log"], reward_xp=60, tags=["bash", "act1", "grep"],
    ),
]

ACT1_GENERATED = [
    *generate_batch("grep_mini", count=2, start_id=5, act=1, base_level=5, seed=1),
    *generate_batch("hidden_file_mini", count=2, start_id=7, act=1, base_level=7, seed=2),
]

ACT1 = [*ACT1_HAND_WRITTEN, *ACT1_GENERATED]
