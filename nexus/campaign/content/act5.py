"""Act V — Windows (levels 96-120, docs/story/02-acts-and-levels.md). No new commands unlock here either — PowerShell
and cmd (B6) were built with low unlock levels of their own and have been available since early in the game, just never
put in front of the player because every target so far has been Linux. The "new" in this act is the first Windows
machine itself: PowerShell's own vocabulary and object pipeline for ideas the player already knows (Get-ChildItem for
ls, Get-Content for cat, Select-String for grep). Chapter 1 (96-103) is written: the Act III Level-59 "unreachable"
subdomain finally opens up as a Windows admin console, and Kade Voss — Nexus Company's security director — is
introduced as the campaign's first named, active hunter. Chapters 2-3 (104-120) are not written yet.
"""
from __future__ import annotations

from ..mission import Mission, Objective

ACT5_CHAPTER1 = [
    Mission(
        id="act5_m96", number=96, act=5, size="mini", title="A Door That Finally Opens", scenario="win_login",
        requires=["act3_m70"],
        briefing=["MIRA: We found a way to that subdomain from Level 59. It's a Windows admin console — different "
                  "world, same job. Credentials are in your inbox."],
        debrief=["MIRA: You're in. The prompt looks different — that's all that's different."],
        objectives=[Objective(event="ssh_login", match={"user": "opsadmin"}, text="Log into the Windows console as opsadmin",
                              hints=["Same sshpass + ssh pattern as Act III, a Windows machine on the other end this time.",
                                    "Try: sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5", "sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5"])],
        solution=["sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5"], reward_xp=95, tags=["bash", "act5", "ps", "ssh"],
    ),
    Mission(
        id="act5_m97", number=97, act=5, size="mini", title="New Vocabulary", scenario="win_explore",
        requires=["act5_m96"],
        briefing=["NEXUS: Same idea as ls and cd, different names. Get-ChildItem lists, Set-Location moves. Try both."],
        debrief=["NEXUS: PowerShell spells everything out in full. Verbose, but you always know what a command does "
                 "just from its name."],
        objectives=[
            Objective(event="command", match={"name": "Get-ChildItem", "status": 0}, text="List the current folder (Get-ChildItem)",
                     hints=["Get-ChildItem is PowerShell's ls.", "Try: Get-ChildItem", "Get-ChildItem"]),
            Objective(event="command", match={"name": "Set-Location", "status": 0}, text="Move into Desktop (Set-Location)",
                     hints=["Set-Location is PowerShell's cd.", "Try: Set-Location Desktop", "Set-Location Desktop"]),
        ],
        solution=["sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5", "Get-ChildItem", "Set-Location Desktop"],
        reward_xp=55, tags=["bash", "act5", "ps"],
    ),
    Mission(
        id="act5_m98", number=98, act=5, size="mini", title="Reading the Desk", scenario="win_notes",
        requires=["act5_m97"],
        briefing=["MIRA: Whoever sits at this console left themselves notes. Read them."],
        debrief=["MIRA: 'Rotate the console password after the audit.' Nobody ever actually does that."],
        objectives=[Objective(event="file_read", match={"path__glob": "*notes.txt"}, text="Read the desktop notes (Get-Content)",
                              hints=["Get-Content is PowerShell's cat.", "Try: Get-Content Desktop\\notes.txt", "Get-Content Desktop\\notes.txt"])],
        solution=["sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5", "Get-Content Desktop\\notes.txt"],
        reward_xp=45, tags=["bash", "act5", "ps"],
    ),
    Mission(
        id="act5_m99", number=99, act=5, size="standard", title="Something's Eating the CPU Again", scenario="win_process",
        requires=["act5_m98"],
        briefing=["NEXUS: Familiar problem, new operating system. Find what's running hot, then stop it."],
        debrief=["NEXUS: 'ticket-sync.exe,' polling every 30 seconds and burning CPU doing it. Not malicious. Just "
                 "badly written. Still worth knowing."],
        objectives=[
            Objective(event="command", match={"name": "Get-Process", "status": 0}, text="Check what's running (Get-Process)",
                     hints=["Get-Process is PowerShell's ps.", "Try: Get-Process", "Get-Process"]),
            Objective(event="process_killed", match={"pid": 2290}, text="Stop ticket-sync.exe (Stop-Process -Id 2290)",
                     hints=["Stop-Process -Id PID stops a process once you know its number.", "Try: Stop-Process -Id 2290", "Stop-Process -Id 2290"]),
        ],
        solution=["sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5", "Get-Process", "Stop-Process -Id 2290"],
        reward_xp=90, tags=["bash", "act5", "ps"],
    ),
    Mission(
        id="act5_m100", number=100, act=5, size="story", title="The Hunter Has a Name", scenario="win_kade",
        requires=["act5_m99"],
        briefing=["NEXUS: There's a memo in Documents. Read it — all of it."],
        debrief=["NEXUS: Kade Voss. Security director, already investigating the exact pattern we've been following "
                 "since that first server. Not hunting us specifically yet. Close enough that it won't stay that way.",
                 "MIRA: Now it has a name and a job title. That's worse, somehow, than not knowing."],
        objectives=[Objective(event="file_read", match={"path__glob": "*kade_voss_memo.txt"}, text="Read Kade Voss's memo",
                              hints=["It's in the Documents folder.", "Try: Get-Content Documents\\kade_voss_memo.txt", "Get-Content Documents\\kade_voss_memo.txt"])],
        solution=["sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5", "Get-Content Documents\\kade_voss_memo.txt"],
        reward_xp=110, tags=["bash", "act5", "story", "kade-voss"],
    ),
    Mission(
        id="act5_m101", number=101, act=5, size="mini", title="What's Actually Running", scenario="win_services",
        requires=["act5_m100"],
        briefing=["MIRA: Check what services this box is actually running. Including the one you logged in through."],
        debrief=["MIRA: Their own sshd, right there in the list. Nothing hidden about how you got in — which means "
                 "nothing hidden about how someone could notice, either."],
        objectives=[Objective(event="command", match={"name": "Get-Service", "status": 0}, text="List the running services (Get-Service)",
                              hints=["Get-Service lists Windows background services and whether they're running.", "Try: Get-Service", "Get-Service"])],
        solution=["sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5", "Get-Service"], reward_xp=45, tags=["bash", "act5", "ps"],
    ),
    Mission(
        id="act5_m102", number=102, act=5, size="standard", title="One Line Among the Routine", scenario="win_search",
        requires=["act5_m101"],
        briefing=["NEXUS: There's a sync tool logging its own activity. Most of it's noise. Find the line that isn't."],
        debrief=["NEXUS: An auth token near expiry, for an account called 'svc-relay-sync.' That name isn't a "
                 "coincidence either."],
        objectives=[Objective(event="command", match={"name": "Select-String", "args__contains": "WARNING", "status": 0}, text="Search the ticket-sync log (Select-String)",
                              hints=["Select-String is PowerShell's grep.", "Try: Select-String -Pattern WARNING ticket-sync.log",
                                    "Select-String -Pattern WARNING ticket-sync.log"])],
        solution=["sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5", "Select-String -Pattern WARNING ticket-sync.log"],
        reward_xp=85, tags=["bash", "act5", "ps"],
    ),
    Mission(
        id="act5_m103", number=103, act=5, size="milestone", title="Know What He Knows", scenario="win_dossier",
        requires=["act5_m102"],
        briefing=["MIRA: Pull the Kade Voss memo and that token warning into one file. We need to know everything he "
                  "already knows before he gets any further ahead of us."],
        debrief=["MIRA: Filed and locked. Chapter closed.",
                 "NEXUS: A named opponent who's already looking in the right direction. That changes the shape of "
                 "this. We go carefully from here."],
        objectives=[
            Objective(event="file_read", match={"path__glob": "*kade_dossier.txt"}, text="Assemble what you've found (grep -r ... | tee)",
                     hints=["Same habit as every chapter close so far.", "Try: grep -r Voss winnotes | tee kade_dossier.txt",
                           "grep -r Voss winnotes | tee kade_dossier.txt\ncat kade_dossier.txt"]),
            Objective(event="sudo_used", match={"command": "cp"}, text="Archive it somewhere only root can reach (sudo cp)",
                     hints=["It lives at /archive, at the filesystem root.", "Try: sudo cp kade_dossier.txt /archive/kade_dossier.txt",
                           "sudo cp kade_dossier.txt /archive/kade_dossier.txt"]),
        ],
        solution=["grep -r Voss winnotes | tee kade_dossier.txt", "cat kade_dossier.txt", "sudo cp kade_dossier.txt /archive/kade_dossier.txt"],
        reward_xp=200, tags=["bash", "act5", "milestone", "grep", "tee", "sudo"],
    ),
]

ACT5 = [*ACT5_CHAPTER1]
