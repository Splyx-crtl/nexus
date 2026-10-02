"""Act II — Traces (levels 21-45, docs/story/02-acts-and-levels.md). No new commands unlock in this act (every bash
command up to engine level 13 already exists from B3) — "new" here means technique: permissions actually mattering,
pipes/redirection used for a reason, and reading a system's history instead of just its files. Chapter 1 (21-30) is
written: Reyes is introduced, and the chapter closes on the Level-20 "patient address" resurfacing on the player's own
machine. Chapters 2-3 (31-45) are not written yet.
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

ACT2 = [*ACT2_CHAPTER1]
