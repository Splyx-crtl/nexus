"""Act II — Traces (levels 21-45, docs/story/02-acts-and-levels.md), now complete. No new commands unlock in this act
(every bash command up to engine level 13 already exists from B3) — "new" here means technique: permissions actually
mattering, pipes/redirection used for a reason, and reading a system's history instead of just its files. Chapter 1
(21-30) introduces Reyes and closes on the Level-20 "patient address" resurfacing on the player's own machine. Chapter 2
(31-40) is redirection/tee/xargs plus Reyes' first real offer (Level 35, the story bible's first player decision — no
branching engine exists yet, so it's a free-form reply, same mechanism as Mira's first contact). Chapter 3 (41-45) closes
the act: Reyes delivers on that offer, Mira checks in personally, and the Level-45 milestone promotes to NETRUNNER.
"""
from __future__ import annotations

from ..mission import Mission, Objective

ACT2_CHAPTER1 = [
    Mission(
        id="act2_m21", number=21, act=2, size="mini", title="Lock It Down", scenario="traces_permissions",
        requires=["act1_m20"],
        briefing=["MIRA: That key's world-readable right now. Anyone on this box could read it. Lock it to yourself "
                  "only — permissions 600, owner read-write, nobody else anything."],
        debrief=["MIRA: Good. From here on, that's the default — nothing stays world-readable that doesn't need to be."],
        objectives=[Objective(event="chmod", match={"path__glob": "*vault.key", "mode": 0o600}, text="Set vault.key to permissions 600",
                              hints=["chmod 600 file makes it readable and writable by the owner only.", "Try: chmod 600 vault.key", "chmod 600 vault.key"])],
        solution=["chmod 600 vault.key"], reward_xp=45, tags=["bash", "act2", "chmod"],
    ),
    Mission(
        id="act2_m22", number=22, act=2, size="mini", title="Whose File Is This", scenario="traces_ownership",
        requires=["act2_m21"],
        briefing=["MIRA: There's a leftover config under /opt, still owned by root. I need it under your name so you "
                  "can actually work with it. chown needs sudo — chmod didn't, this does."],
        debrief=["MIRA: That's the difference: chmod changes what a file allows, chown changes who it belongs to. "
                 "The second one only root gets to decide."],
        objectives=[
            Objective(event="command", match={"name": "chown", "status": 0}, text="Make orphan.cfg yours (chown, via sudo)",
                     hints=["Only root can change a file's owner — you'll need sudo for this one.",
                           "Try: sudo chown operator /opt/orphan.cfg", "sudo chown operator /opt/orphan.cfg"]),
            Objective(event="sudo_used", match={"command": "chown"}, text="Use sudo to do it",
                     hints=["sudo runs one command as root.", "Try: sudo chown operator /opt/orphan.cfg", "sudo chown operator /opt/orphan.cfg"]),
        ],
        solution=["sudo chown operator /opt/orphan.cfg"], reward_xp=50, tags=["bash", "act2", "chown", "sudo"],
    ),
    Mission(
        id="act2_m23", number=23, act=2, size="mini", title="What Only Root Can See", scenario="traces_protected",
        requires=["act2_m22"],
        briefing=["MIRA: Everything I know about our other contacts is in /etc/nexus_contacts.conf. You don't have "
                  "permission to just read it — you'll need to borrow root's."],
        debrief=["MIRA: sudo isn't just for chown and chmod. It's 'run this one thing as root' — works for anything, "
                 "cat included."],
        objectives=[
            Objective(event="file_read", match={"path__glob": "*nexus_contacts.conf"}, text="Read the contacts file (sudo cat)",
                     hints=["Regular cat will say Permission denied — try it with sudo.", "Try: sudo cat /etc/nexus_contacts.conf",
                           "sudo cat /etc/nexus_contacts.conf"]),
            Objective(event="sudo_used", match={"command": "cat"}, text="Use sudo to do it",
                     hints=["sudo runs one command as root, whatever that command is.", "Try: sudo cat /etc/nexus_contacts.conf",
                           "sudo cat /etc/nexus_contacts.conf"]),
        ],
        solution=["sudo cat /etc/nexus_contacts.conf"], reward_xp=50, tags=["bash", "act2", "sudo"],
    ),
    Mission(
        id="act2_m24", number=24, act=2, size="standard", title="Kill It", scenario="traces_process",
        requires=["act2_m23"],
        briefing=["NEXUS: Your fans have been spinning for an hour and you're not doing anything. Something's running "
                  "that shouldn't be. Find it, then stop it."],
        debrief=["NEXUS: 'xmr-helper.' Someone's been mining on your hardware, on your electricity bill, without asking.",
                 "MIRA: Small-time. Annoying, not dangerous. But it means something got onto this box once. Worth remembering."],
        objectives=[
            Objective(event="command", match={"name": "ps", "status": 0}, text="Check what's actually running (ps aux)",
                     hints=["ps aux lists every running process with its owner and PID.", "Try: ps aux", "ps aux"]),
            Objective(event="process_killed", match={"pid": 4821}, text="Stop it (kill 4821)",
                     hints=["kill PID stops a process once you know its number.", "Try: kill 4821", "kill 4821"]),
        ],
        solution=["ps aux", "kill 4821"], reward_xp=70, tags=["bash", "act2", "ps", "kill"],
    ),
    Mission(
        id="act2_m25", number=25, act=2, size="mini", title="Who Else Is Here", scenario="traces_whosthere",
        requires=["act2_m24"],
        briefing=["MIRA: Habit worth building: check who's logged in right now, and who's logged in recently. Even "
                  "your own box. Especially your own box."],
        debrief=["MIRA: Nothing unusual there. Keep checking anyway — the one time you skip it is the time it matters."],
        objectives=[
            Objective(event="command", match={"name": "who", "status": 0}, text="Check who's logged in right now (who)",
                     hints=["who shows every session active right now.", "Try: who", "who"]),
            Objective(event="command", match={"name": "last", "status": 0}, text="Check recent login history (last)",
                     hints=["last shows a history of logins, not just the current one.", "Try: last", "last"]),
        ],
        solution=["who", "last"], reward_xp=45, tags=["bash", "act2", "who", "last"],
    ),
    Mission(
        id="act2_m26", number=26, act=2, size="story", title="Someone Else's Game", scenario="traces_rival",
        requires=["act2_m25"],
        briefing=["NEXUS: Someone got to job_007 before you. There's a note waiting."],
        debrief=["NEXUS: 'Insufferably pleased' seems accurate from one note.",
                 "MIRA: Reyes isn't the job. Don't get distracted proving a point — but don't let them walk over you either."],
        objectives=[
            Objective(event="file_read", match={"path__glob": "*claimed.txt"}, text="Read the calling card left in job_007",
                     hints=["There's a file inside the job_007 folder.", "Try: cat jobs/job_007/claimed.txt", "cat jobs/job_007/claimed.txt"]),
            Objective(event="file_read", match={"path__glob": "*about_reyes.txt"}, text="Read Mira's note about who that was",
                     hints=["Check your inbox.", "Try: cat inbox/about_reyes.txt", "cat inbox/about_reyes.txt"]),
        ],
        solution=["cat jobs/job_007/claimed.txt", "cat inbox/about_reyes.txt"], reward_xp=80, tags=["bash", "act2", "story", "reyes"],
    ),
    Mission(
        id="act2_m27", number=27, act=2, size="mini", title="Running on Empty", scenario="traces_disk",
        requires=["act2_m26"],
        briefing=["NEXUS: Disk's filling up and I don't know why. Check how much space is left, then find what's "
                  "actually eating it."],
        debrief=["NEXUS: A cache folder nobody's cleaned in a while. Not sinister. Just neglect. Clear it when you get a chance."],
        objectives=[
            Objective(event="command", match={"name": "df", "status": 0}, text="Check how much space is left (df)",
                     hints=["df -h shows disk usage per filesystem, human-readable.", "Try: df -h", "df -h"]),
            Objective(event="command", match={"name": "du", "status": 0}, text="Find what's taking the space (du)",
                     hints=["du -sh * sizes up everything in the current folder.", "Try: du -sh .cache", "du -sh .cache"]),
        ],
        solution=["df -h", "du -sh .cache"], reward_xp=45, tags=["bash", "act2", "df", "du"],
    ),
    Mission(
        id="act2_m28", number=28, act=2, size="standard", title="Not What It Looks Like", scenario="traces_symlink",
        requires=["act2_m27"],
        briefing=["MIRA: That backup file in your workspace isn't a real file. Find out what it actually is, and "
                  "where it actually points."],
        debrief=["MIRA: A symlink to /opt. Somebody wanted it to look like it lived in your workspace without "
                 "actually being there. Good catch."],
        objectives=[
            Objective(event="file_identified", match={"path__glob": "*backup_link"}, text="Find out what backup_link really is (file)",
                     hints=["file tells you a file's real type, not just its name.", "Try: file backup_link", "file backup_link"]),
            Objective(event="command", match={"name": "readlink", "status": 0}, text="Reveal exactly where it points (readlink)",
                     hints=["readlink prints a symlink's real target.", "Try: readlink backup_link", "readlink backup_link"]),
        ],
        solution=["file backup_link", "readlink backup_link"], reward_xp=70, tags=["bash", "act2", "file", "readlink"],
    ),
    Mission(
        id="act2_m29", number=29, act=2, size="mini", title="Housekeeping", scenario="traces_housekeeping",
        requires=["act2_m28"],
        briefing=["NEXUS: Idle curiosity: how long has this machine been up? And where does the system actually keep "
                  "the 'grep' binary? I like knowing where things live."],
        debrief=["NEXUS: Three days, four hours. And /usr/bin, same as everything else. Satisfied. Moving on."],
        objectives=[
            Objective(event="command", match={"name": "uptime", "status": 0}, text="Check how long the machine's been up (uptime)",
                     hints=["uptime shows how long since the last boot.", "Try: uptime", "uptime"]),
            Objective(event="command", match={"name": "whereis", "status": 0}, text="Find where grep actually lives (whereis)",
                     hints=["whereis shows a command's binary and manual page locations.", "Try: whereis grep", "whereis grep"]),
        ],
        solution=["uptime", "whereis grep"], reward_xp=35, tags=["bash", "act2", "uptime", "whereis"],
    ),
    Mission(
        id="act2_m30", number=30, act=2, size="milestone", title="Déjà Vu", scenario="traces_incident",
        requires=["act2_m29"],
        briefing=["NEXUS: Something's running that neither of us started. Full check — what's running, who's been "
                  "logging in, and lock down anything loose when you're done."],
        debrief=["NEXUS: 203.0.113.9. Same address from that server's logs. It's not watching the dead drop anymore. "
                 "It's watching you.",
                 "MIRA: That's not Reyes' style, and it's not random. Someone patient enough to wait weeks doesn't do "
                 "that for a hobby.",
                 "NEXUS: Chapter closed. Whatever this is, it just got personal. We should find out who's actually "
                 "running it — carefully."],
        objectives=[
            Objective(event="command", match={"name": "ps", "status": 0}, text="Check what's running (ps aux)",
                     hints=["ps aux lists every process with owner and PID.", "Try: ps aux", "ps aux"]),
            Objective(event="process_killed", match={"pid": 6650}, text="Stop the relay process (kill 6650)",
                     hints=["kill PID stops a process once you know its number.", "Try: kill 6650", "kill 6650"]),
            Objective(event="command", match={"name": "last", "status": 0}, text="Check the login history (last)",
                     hints=["last shows a history of who's logged in, and from where.", "Try: last", "last"]),
            Objective(event="chmod", match={"path__glob": "*access.token", "mode": 0o600}, text="Lock down access.token (chmod 600)",
                     hints=["chmod 600 restricts a file to its owner only.", "Try: chmod 600 access.token", "chmod 600 access.token"]),
        ],
        solution=["ps aux", "kill 6650", "last", "chmod 600 access.token"],
        reward_xp=180, tags=["bash", "act2", "milestone", "ps", "kill", "last", "chmod"],
    ),
]

ACT2_CHAPTER2 = [
    Mission(
        id="act2_m31", number=31, act=2, size="mini", title="Keep a Copy", scenario="traces_copy",
        requires=["act2_m30"],
        briefing=["MIRA: Same drill as before, but I need a copy of the result this time, not just a look at it. "
                  "tee lets you see it and save it in the same breath."],
        debrief=["MIRA: That's the one you'll reach for constantly. Seeing something and keeping it are different problems."],
        objectives=[
            Objective(event="command", match={"name": "sort", "status": 0}, text="Sort auth_events.log",
                     hints=["Same pattern as before: sort first, then count.", "Try: sort auth_events.log", "sort auth_events.log"]),
            Objective(event="command", match={"name": "tee", "status": 0}, text="Count and save a copy in one line (uniq -c | tee)",
                     hints=["tee writes to a file AND still shows you the output.", "Try: sort auth_events.log | uniq -c | tee summary.txt",
                           "sort auth_events.log | uniq -c | tee summary.txt"]),
        ],
        solution=["sort auth_events.log | uniq -c | tee summary.txt"], reward_xp=55, tags=["bash", "act2", "tee"],
    ),
    Mission(
        id="act2_m32", number=32, act=2, size="mini", title="Save It This Time", scenario="traces_report",
        requires=["act2_m31"],
        briefing=["NEXUS: Before anything else gets weird on this box, I want a written baseline of what SHOULD be "
                  "running. Save it — don't just glance at it and move on."],
        debrief=["NEXUS: Filed. Next time something looks off, we have something honest to compare it to."],
        objectives=[Objective(event="file_read", match={"path__glob": "*process_report.txt"}, text="Write and re-read a process baseline",
                              hints=["> sends a command's output into a file instead of the screen.",
                                    "Try: ps aux > process_report.txt, then cat process_report.txt", "ps aux > process_report.txt\ncat process_report.txt"])],
        solution=["ps aux > process_report.txt", "cat process_report.txt"], reward_xp=45, tags=["bash", "act2", "redirection"],
    ),
    Mission(
        id="act2_m33", number=33, act=2, size="standard", title="Route the Noise", scenario="traces_quiet",
        requires=["act2_m32"],
        briefing=["MIRA: Read siteA, siteB and siteC's configs together. There's no siteC yet, so route whatever errors "
                  "that throws into its own file instead of letting it clutter the real output."],
        debrief=["MIRA: Clean output, errors filed separately. That's the difference between a report and a mess."],
        objectives=[Objective(event="file_read", match={"path__glob": "*errors.log"}, text="Route the missing-file error into errors.log and check it",
                              hints=["2> sends only error messages to a file, leaving normal output alone.",
                                    "Try: cat siteA.cfg siteB.cfg siteC.cfg 2> errors.log, then cat errors.log",
                                    "cat siteA.cfg siteB.cfg siteC.cfg 2> errors.log\ncat errors.log"])],
        solution=["cat siteA.cfg siteB.cfg siteC.cfg 2> errors.log", "cat errors.log"], reward_xp=70, tags=["bash", "act2", "redirection"],
    ),
    Mission(
        id="act2_m34", number=34, act=2, size="mini", title="Feed It In", scenario="traces_feed",
        requires=["act2_m33"],
        briefing=["NEXUS: Mira wants that message shouted, not whispered — all caps, saved to a new file."],
        debrief=["NEXUS: tr never takes a filename directly — < is the only clean way to hand it one."],
        objectives=[Objective(event="file_read", match={"path__glob": "*shout.txt"}, text="Upper-case message.txt into shout.txt and check it",
                              hints=["tr only reads from standard input, never a filename — < feeds it a file.",
                                    "Try: tr a-z A-Z < message.txt > shout.txt, then cat shout.txt",
                                    "tr a-z A-Z < message.txt > shout.txt\ncat shout.txt"])],
        solution=["tr a-z A-Z < message.txt > shout.txt", "cat shout.txt"], reward_xp=50, tags=["bash", "act2", "redirection", "tr"],
    ),
    Mission(
        id="act2_m35", number=35, act=2, size="story", title="Reyes' Offer", scenario="traces_offer",
        requires=["act2_m34"],
        briefing=["NEXUS: Reyes again. This one actually wants something. Read it."],
        debrief=["NEXUS: Whatever you told them, that's on the record now. I hope it was the right call.",
                 "MIRA: There isn't always a clean answer with Reyes. Welcome to working with other people."],
        objectives=[
            Objective(event="file_read", match={"path__glob": "*reyes_offer.txt"}, text="Read Reyes' offer",
                     hints=["Check your inbox.", "Try: cat inbox/reyes_offer.txt", "cat inbox/reyes_offer.txt"]),
            Objective(event="command", match={"name": "echo", "status": 0}, text="Reply — your call what you tell them",
                     hints=["Same as replying to Mira, early on: write it, append it to the file.",
                           'echo "your reply here" >> inbox/reyes_offer.txt', 'echo "Deal." >> inbox/reyes_offer.txt']),
        ],
        solution=["cat inbox/reyes_offer.txt", 'echo "Fine. Deal." >> inbox/reyes_offer.txt'],
        reward_xp=90, tags=["bash", "act2", "story", "reyes", "decision:1"],
    ),
    Mission(
        id="act2_m36", number=36, act=2, size="mini", title="Numbers, Old and New", scenario="traces_tally",
        requires=["act2_m35"],
        briefing=["MIRA: Number that roster for me, readably, for printing. And I need ten fresh case IDs — 101 "
                  "through 110 is fine."],
        debrief=["MIRA: Small stuff, but it's the small stuff that makes a report look like it came from someone "
                 "who knows what they're doing."],
        objectives=[
            Objective(event="command", match={"name": "nl", "status": 0}, text="Number the roster (nl)",
                     hints=["nl numbers every non-blank line of a file.", "Try: nl contacts.roster", "nl contacts.roster"]),
            Objective(event="command", match={"name": "seq", "status": 0}, text="Generate case IDs 101-110 (seq)",
                     hints=["seq FIRST LAST prints a run of numbers.", "Try: seq 101 110", "seq 101 110"]),
        ],
        solution=["nl contacts.roster", "seq 101 110"], reward_xp=35, tags=["bash", "act2", "nl", "seq"],
    ),
    Mission(
        id="act2_m37", number=37, act=2, size="mini", title="Read It Backwards", scenario="traces_mirror",
        requires=["act2_m36"],
        briefing=["NEXUS: That file reads as nonsense forwards. Reyes has done this before — try it backwards."],
        debrief=["NEXUS: 'They are closer than you think.' Reyes' idea of a joke, probably. Probably."],
        objectives=[Objective(event="command", match={"name": "rev", "status": 0}, text="Read scrambled.txt in reverse (rev)",
                              hints=["rev reverses every line, character by character.", "Try: rev scrambled.txt", "rev scrambled.txt"])],
        solution=["rev scrambled.txt"], reward_xp=35, tags=["bash", "act2", "rev"],
    ),
    Mission(
        id="act2_m38", number=38, act=2, size="standard", title="One Table, Not Two Lists", scenario="traces_format",
        requires=["act2_m37"],
        briefing=["MIRA: Merge these side by side into one table, lined up properly. I'm not reading two separate "
                  "lists and matching them up myself."],
        debrief=["MIRA: Now that's a report. Keep formatting things like you expect someone else to actually read them."],
        objectives=[
            Objective(event="command", match={"name": "paste", "status": 0}, text="Merge the two files side by side (paste)",
                     hints=["paste joins files line by line, side by side.", "Try: paste names.txt statuses.txt", "paste names.txt statuses.txt"]),
            Objective(event="command", match={"name": "column", "args__contains": "-t", "status": 0}, text="Line the columns up (column -t)",
                     hints=["column -t turns separator-joined text into a lined-up table.",
                           "Try: paste names.txt statuses.txt | column -t", "paste names.txt statuses.txt | column -t"]),
        ],
        solution=["paste names.txt statuses.txt | column -t"], reward_xp=70, tags=["bash", "act2", "paste", "column"],
    ),
    Mission(
        id="act2_m39", number=39, act=2, size="mini", title="Clean Sweep", scenario="traces_sweep",
        requires=["act2_m38"],
        briefing=["NEXUS: That spool folder from before is still full of scratch files nobody needs. Find them all "
                  "and clear them out in one go — don't delete them one at a time."],
        debrief=["NEXUS: Four files, one command. That's the entire point of xargs."],
        objectives=[
            Objective(event="command", match={"name": "xargs", "status": 0}, text="Delete every .tmp file in one go (find | xargs rm)",
                     hints=["find lists the files; xargs turns that list into arguments for another command.",
                           "Try: find .cache/spool -name '*.tmp' | xargs rm", "find .cache/spool -name '*.tmp' | xargs rm"]),
            Objective(event="delete", match={"path__glob": "*.tmp"}, count=4, text="All four scratch files actually gone",
                     hints=["If xargs built the command right, all four should disappear in one shot.",
                           "find .cache/spool -name '*.tmp' | xargs rm", "find .cache/spool -name '*.tmp' | xargs rm"]),
        ],
        solution=["find .cache/spool -name '*.tmp' | xargs rm"], reward_xp=55, tags=["bash", "act2", "xargs"],
    ),
    Mission(
        id="act2_m40", number=40, act=2, size="milestone", title="Full Pass", scenario="traces_audit",
        requires=["act2_m39"],
        briefing=["MIRA: Full pass before we call this chapter done: pull every ERROR line out of this week's logs "
                  "— there's a third file listed that doesn't exist, don't let that break the real output — save a "
                  "copy of what you find, review whatever errors it throws separately, then clear out the scratch "
                  "files when you're done."],
        debrief=["MIRA: Two real errors, one dead file reference, and a tidy workspace when you're finished. That's "
                 "the whole job, every time, just at different scales.",
                 "NEXUS: Chapter closed. Whatever's coming next, you've got the habits for it now."],
        objectives=[
            Objective(event="command", match={"name": "grep", "args__contains": "-h", "status": 0}, text="Pull ERROR lines from all the logs at once (grep -h)",
                     hints=["-h keeps multiple files from cluttering the output with filenames.",
                           "Try: grep -h ERROR logs/w1.log logs/w2.log logs/w3.log 2> scan_errors.log | tee scan_results.txt"]),
            Objective(event="file_read", match={"path__glob": "*scan_results.txt"}, text="Review the saved results (scan_results.txt)",
                     hints=["tee wrote a copy while you were looking at it — read it back.", "Try: cat scan_results.txt", "cat scan_results.txt"]),
            Objective(event="file_read", match={"path__glob": "*scan_errors.log"}, text="Review what went wrong separately (scan_errors.log)",
                     hints=["2> routed the missing-file error to its own file.", "Try: cat scan_errors.log", "cat scan_errors.log"]),
            Objective(event="delete", match={"path__glob": "*.tmp"}, count=2, text="Clear out the scratch files (find | xargs rm)",
                     hints=["Same move as the spool cleanup.", "Try: find . -name '*.tmp' | xargs rm", "find . -name '*.tmp' | xargs rm"]),
        ],
        solution=["grep -h ERROR logs/w1.log logs/w2.log logs/w3.log 2> scan_errors.log | tee scan_results.txt",
                 "cat scan_results.txt", "cat scan_errors.log", "find . -name '*.tmp' | xargs rm"],
        reward_xp=190, tags=["bash", "act2", "milestone", "grep", "redirection", "tee", "xargs"],
    ),
]

ACT2_CHAPTER3 = [
    Mission(
        id="act2_m41", number=41, act=2, size="standard", title="What Reyes Found", scenario="traces_dossier",
        requires=["act2_m40"],
        briefing=["NEXUS: Reyes actually came through. There's a dossier folder — search all of it at once, not file "
                  "by file."],
        debrief=["NEXUS: Not external, not random, and flagged more than once. Reyes wasn't exaggerating.",
                 "MIRA: That's more than I expected them to actually hand over."],
        objectives=[
            Objective(event="file_read", match={"path__glob": "*reyes_followup.txt"}, text="Read Reyes' follow-up",
                     hints=["Check your inbox first.", "Try: cat inbox/reyes_followup.txt", "cat inbox/reyes_followup.txt"]),
            Objective(event="command", match={"name": "grep", "args__contains": "-r", "status": 0}, text="Search the whole dossier at once for 203.0.113.9 (grep -r)",
                     hints=["-r makes grep search every file under a folder, not just one.",
                           "Try: grep -r 203.0.113.9 dossier", "grep -r 203.0.113.9 dossier"]),
        ],
        solution=["cat inbox/reyes_followup.txt", "grep -r 203.0.113.9 dossier"], reward_xp=75, tags=["bash", "act2", "grep", "reyes"],
    ),
    Mission(
        id="act2_m42", number=42, act=2, size="mini", title="How Many Times", scenario="traces_timeline",
        requires=["act2_m41"],
        briefing=["MIRA: Don't just tell me where it shows up. Tell me how many times, total, across everything."],
        debrief=["MIRA: Four. Spread out, patient, never in a hurry. That matches everything else we've seen."],
        objectives=[Objective(event="command", match={"name": "wc", "args__contains": "-l", "status": 0}, text="Count every mention across the whole dossier",
                              hints=["Pipe the recursive grep into wc -l to total the matches.",
                                    "Try: grep -r 203.0.113.9 dossier | wc -l", "grep -r 203.0.113.9 dossier | wc -l"])],
        solution=["grep -r 203.0.113.9 dossier | wc -l"], reward_xp=40, tags=["bash", "act2", "grep", "wc"],
    ),
    Mission(
        id="act2_m43", number=43, act=2, size="story", title="A Straight Answer", scenario="traces_personal",
        requires=["act2_m42"],
        briefing=["NEXUS: Mira wants a straight answer. Read it, then give her one."],
        debrief=["MIRA: Noted. Whatever happens next, that's the line you drew, not me.",
                 "NEXUS: For what it's worth — I'd have answered the same way. Don't quote me on having 'worth.'"],
        objectives=[
            Objective(event="file_read", match={"path__glob": "*mira_checkin.txt"}, text="Read Mira's check-in",
                     hints=["Check your inbox.", "Try: cat inbox/mira_checkin.txt", "cat inbox/mira_checkin.txt"]),
            Objective(event="command", match={"name": "echo", "status": 0}, text="Give her a straight answer",
                     hints=["Same move as before — write it, append it to the file.",
                           'echo "your answer here" >> inbox/mira_checkin.txt', 'echo "I\'m in. All the way." >> inbox/mira_checkin.txt']),
        ],
        solution=["cat inbox/mira_checkin.txt", 'echo "I\'m in. All the way." >> inbox/mira_checkin.txt'],
        reward_xp=85, tags=["bash", "act2", "story", "decision:1"],
    ),
    Mission(
        id="act2_m44", number=44, act=2, size="mini", title="Lock the Whole Folder", scenario="traces_harden",
        requires=["act2_m43"],
        briefing=["NEXUS: If we're taking this further, that whole dossier folder needs to be locked down first. All "
                  "of it, not file by file. Use 700, not 600 — a folder needs its own execute bit just to be entered, "
                  "even by its owner. Strip that and you'd lock yourself out along with everyone else."],
        debrief=["NEXUS: Good. Whatever happens next, that folder isn't the weak point."],
        objectives=[Objective(event="command", match={"name": "chmod", "args__contains": "-R", "status": 0}, text="Lock the whole dossier folder down (chmod -R 700)",
                              hints=["-R applies chmod to a folder and everything inside it. Use 700, not 600 — directories need "
                                    "their own execute bit to be entered, even by the owner.",
                                    "Try: chmod -R 700 dossier", "chmod -R 700 dossier"])],
        solution=["chmod -R 700 dossier"], reward_xp=40, tags=["bash", "act2", "chmod"],
    ),
    Mission(
        id="act2_m45", number=45, act=2, size="milestone", title="Case Closed, For Now", scenario="traces_handoff",
        requires=["act2_m44"],
        briefing=["MIRA: Pull everything on 203.0.113.9 into one file, keep a copy where only root can touch it, and "
                  "we're done with this chapter."],
        debrief=["MIRA: Filed, locked, and backed up. That's everything we can learn from the outside.",
                 "NEXUS: Whoever's behind that address isn't going to volunteer more than this. Which means the next "
                 "move is going straight at the source — their own infrastructure, not just its shadow in a log file.",
                 "MIRA: Rank up. NETRUNNER. You've earned it, and you're going to need it — this is where it stops "
                 "being footprints and starts being the actual building."],
        objectives=[
            Objective(event="file_read", match={"path__glob": "*case_summary.txt"}, text="Assemble the case file and review it (grep -r ... | tee)",
                     hints=["Same trick from before — search, and save a copy while you're looking at it.",
                           "Try: grep -r 203.0.113.9 dossier | tee case_summary.txt", "grep -r 203.0.113.9 dossier | tee case_summary.txt\ncat case_summary.txt"]),
            Objective(event="sudo_used", match={"command": "cp"}, text="Archive a copy somewhere only root can reach (sudo cp)",
                     hints=["The archive folder is root-only — you'll need sudo to put anything in it.",
                           "Try: sudo cp case_summary.txt archive/case_summary.txt", "sudo cp case_summary.txt archive/case_summary.txt"]),
        ],
        solution=["grep -r 203.0.113.9 dossier | tee case_summary.txt", "cat case_summary.txt", "sudo cp case_summary.txt archive/case_summary.txt"],
        reward_xp=200, tags=["bash", "act2", "milestone", "grep", "tee", "sudo"],
    ),
]

ACT2 = [*ACT2_CHAPTER1, *ACT2_CHAPTER2, *ACT2_CHAPTER3]
