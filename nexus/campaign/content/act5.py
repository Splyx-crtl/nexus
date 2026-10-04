"""Act V — Windows (levels 96-120, docs/story/02-acts-and-levels.md), now complete. No new commands unlock here either
— PowerShell and cmd (B6) were built with low unlock levels of their own and have been available since early in the
game, just never put in front of the player because every target so far has been Linux. The "new" in this act is the
first Windows machine itself: PowerShell's own vocabulary and object pipeline for ideas the player already knows
(Get-ChildItem for ls, Get-Content for cat, Select-String for grep). Chapter 1 (96-103): the Act III Level-59
"unreachable" subdomain finally opens up as a Windows admin console, OPS-CONSOLE, and Kade Voss — Nexus Company's
security director — is introduced as the campaign's first named, active hunter. Chapter 2 (104-111): the object
pipeline (Where-Object/Sort-Object/Select-Object), a stranger's account nobody on the operation created, and a second,
never-upgraded cmd.exe machine. Chapter 3 (112-120): Test-Connection/Invoke-WebRequest/Measure-Object, the svc_update
mystery deliberately left open, Kade Voss tightening monitoring, the player's third major decision, and a milestone
promoting to ENGINEER. requires=["act4_m95"] on the first mission, now that Act IV exists to provide it.
"""
from __future__ import annotations

from ..mission import Mission, Objective

ACT5_CHAPTER1 = [
    Mission(
        id="act5_m96", number=96, act=5, size="mini", title="A Door That Finally Opens", scenario="win_login",
        requires=["act4_m95"],
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

ACT5_CHAPTER2 = [
    Mission(
        id="act5_m104", number=104, act=5, size="mini", title="Who Has a Key", scenario="win_users",
        requires=["act5_m103"],
        briefing=["MIRA: Same habit as always, PowerShell's version. Who actually has an account on this box?"],
        debrief=["MIRA: opsadmin, Administrator. Nothing unexpected yet. Keep checking — that's exactly the kind of "
                 "thing that changes without anyone announcing it."],
        objectives=[Objective(event="command", match={"name": "Get-LocalUser", "status": 0}, text="List local accounts (Get-LocalUser)",
                              hints=["Get-LocalUser lists every account on the machine.", "Try: Get-LocalUser", "Get-LocalUser"])],
        solution=["sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5", "Get-LocalUser"], reward_xp=45, tags=["bash", "act5", "ps"],
    ),
    Mission(
        id="act5_m105", number=105, act=5, size="standard", title="Filter, Don't Scroll", scenario="win_filter",
        requires=["act5_m104"],
        briefing=["NEXUS: Don't read the whole process list hunting for the busy one. Ask for exactly what you want."],
        debrief=["NEXUS: One line, exactly the process that matters. That's the whole point of a pipeline — you "
                 "describe what you want, not how to find it."],
        objectives=[Objective(event="command", match={"name": "Where-Object", "status": 0}, text="Filter processes by CPU (Where-Object)",
                              hints=["Where-Object {$_.CPU -gt 10} keeps only processes over that threshold.",
                                    "Try: Get-Process | Where-Object {$_.CPU -gt 10}", "Get-Process | Where-Object {$_.CPU -gt 10}"])],
        solution=["sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5", "Get-Process | Where-Object {$_.CPU -gt 10}"],
        reward_xp=90, tags=["bash", "act5", "ps"],
    ),
    Mission(
        id="act5_m106", number=106, act=5, size="mini", title="Rank Them", scenario="win_rank",
        requires=["act5_m105"],
        briefing=["MIRA: Instead of filtering, just put them in order. Busiest first."],
        debrief=["MIRA: Same information, different question. Filtering asks 'which ones qualify.' Sorting asks "
                 "'which one's worst.'"],
        objectives=[Objective(event="command", match={"name": "Sort-Object", "args__contains": "-Descending", "status": 0}, text="Sort processes by CPU, highest first",
                              hints=["Sort-Object CPU -Descending ranks the list by that property.",
                                    "Try: Get-Process | Sort-Object CPU -Descending", "Get-Process | Sort-Object CPU -Descending"])],
        solution=["sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5", "Get-Process | Sort-Object CPU -Descending"],
        reward_xp=50, tags=["bash", "act5", "ps"],
    ),
    Mission(
        id="act5_m107", number=107, act=5, size="standard", title="Just the Worst One", scenario="win_worst",
        requires=["act5_m106"],
        briefing=["NEXUS: Don't make me read a sorted list either. Give me exactly one answer: what's the single "
                  "worst offender?"],
        debrief=["NEXUS: Chain them together and the pipeline does the thinking for you. Sort, then take the top of "
                 "the list. That's the whole technique."],
        objectives=[
            Objective(event="command", match={"name": "Sort-Object", "status": 0}, text="Sort by CPU (Sort-Object)",
                     hints=["Same as before.", "Try: Get-Process | Sort-Object CPU -Descending | Select-Object -First 1",
                           "Get-Process | Sort-Object CPU -Descending | Select-Object -First 1"]),
            Objective(event="command", match={"name": "Select-Object", "args__contains": "-First", "status": 0}, text="Take just the top result (Select-Object -First 1)",
                     hints=["Select-Object -First 1 keeps only the first item.", "Try: ... | Select-Object -First 1", "Select-Object -First 1"]),
        ],
        solution=["sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5", "Get-Process | Sort-Object CPU -Descending | Select-Object -First 1"],
        reward_xp=85, tags=["bash", "act5", "ps"],
    ),
    Mission(
        id="act5_m108", number=108, act=5, size="story", title="One Account Too Many", scenario="win_extra_account",
        requires=["act5_m107"],
        briefing=["MIRA: Check the account list again. Compare it to what you saw at Level 104."],
        debrief=["NEXUS: 'svc_update.' Created two days ago. Added to Administrators the same day. Nobody on this "
                 "operation did that.",
                 "MIRA: Kade Voss is investigating from outside. We're in. That's someone else, already inside, "
                 "before either of us got here."],
        objectives=[
            Objective(event="command", match={"name": "Get-LocalUser", "status": 0}, text="Check the account list again",
                     hints=["Same command as Level 104 — compare what comes back.", "Try: Get-LocalUser", "Get-LocalUser"]),
            Objective(event="file_read", match={"path__glob": "*account_changes.log"}, text="Check when that account was created",
                     hints=["There's a log for exactly this, at the system root, not in your own folder.",
                           "Try: Get-Content C:\\Windows\\Logs\\account_changes.log", "Get-Content C:\\Windows\\Logs\\account_changes.log"]),
        ],
        solution=["sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5", "Get-LocalUser", "Get-Content C:\\Windows\\Logs\\account_changes.log"],
        reward_xp=120, tags=["bash", "act5", "story"],
    ),
    Mission(
        id="act5_m109", number=109, act=5, size="mini", title="One by One", scenario="win_foreach",
        requires=["act5_m108"],
        briefing=["NEXUS: Run the same small step over every item in a list instead of repeating yourself. Just the "
                  "names from Documents, nothing else."],
        debrief=["NEXUS: That's a loop, PowerShell's way. Same idea as everything else, new spelling."],
        objectives=[Objective(event="command", match={"name": "ForEach-Object", "status": 0}, text="Print just the names (ForEach-Object)",
                              hints=["ForEach-Object {$_.Name} runs once per item and prints just that piece.",
                                    "Try: Get-ChildItem Documents | ForEach-Object {$_.Name}", "Get-ChildItem Documents | ForEach-Object {$_.Name}"])],
        solution=["sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5", "Get-ChildItem Documents | ForEach-Object {$_.Name}"],
        reward_xp=50, tags=["bash", "act5", "ps"],
    ),
    Mission(
        id="act5_m110", number=110, act=5, size="standard", title="The Machine Nobody Upgraded", scenario="win_legacy",
        requires=["act5_m109"],
        briefing=["MIRA: Not every machine in this network got the PowerShell upgrade. Here's one that didn't — "
                  "same job, older tools."],
        debrief=["MIRA: 'legacy-index.exe,' 63% CPU, nobody's touched this box in years by the look of it. Old "
                 "tools, same incident-response habit."],
        objectives=[
            Objective(event="command", match={"name": "tasklist", "status": 0}, text="Check what's running (tasklist)",
                     hints=["tasklist is cmd.exe's process list.", "Try: tasklist", "tasklist"]),
            Objective(event="process_killed", match={"pid": 1188}, text="Stop legacy-index.exe (taskkill /PID 1188)",
                     hints=["taskkill /PID number stops a process the old way.", "Try: taskkill /PID 1188", "taskkill /PID 1188"]),
        ],
        solution=["sshpass -p Legacy-Svc-99 ssh svcacct@10.20.30.9", "tasklist", "taskkill /PID 1188"],
        reward_xp=90, tags=["bash", "act5", "cmd"],
    ),
    Mission(
        id="act5_m111", number=111, act=5, size="milestone", title="Nobody Else Noticed Yet", scenario="win_dossier2",
        requires=["act5_m110"],
        briefing=["MIRA: Everything from this chapter, one file. The extra account especially — Kade Voss needs to "
                  "not be the only one who eventually notices that."],
        debrief=["MIRA: Filed and locked. Chapter closed.",
                 "NEXUS: Two things true at once: Kade Voss is closing in on us, and someone else already got there "
                 "first. I don't love either half of that sentence."],
        objectives=[
            Objective(event="file_read", match={"path__glob": "*win5_dossier.txt"}, text="Assemble the findings (grep -r ... | tee)",
                     hints=["Same habit as every chapter close so far.", "Try: grep -r svc_update winnotes | tee win5_dossier.txt",
                           "grep -r svc_update winnotes | tee win5_dossier.txt\ncat win5_dossier.txt"]),
            Objective(event="sudo_used", match={"command": "cp"}, text="Archive it (sudo cp)",
                     hints=["It lives at /archive, at the filesystem root.", "Try: sudo cp win5_dossier.txt /archive/win5_dossier.txt",
                           "sudo cp win5_dossier.txt /archive/win5_dossier.txt"]),
        ],
        solution=["grep -r svc_update winnotes | tee win5_dossier.txt", "cat win5_dossier.txt", "sudo cp win5_dossier.txt /archive/win5_dossier.txt"],
        reward_xp=210, tags=["bash", "act5", "milestone", "grep", "tee", "sudo"],
    ),
]

ACT5_CHAPTER3 = [
    Mission(
        id="act5_m112", number=112, act=5, size="mini", title="Still Connected", scenario="win_ping",
        requires=["act5_m111"],
        briefing=["MIRA: Check on the legacy box from inside the network this time, not from outside looking in."],
        debrief=["MIRA: Still up, still answering. Still years behind on patches, too."],
        objectives=[Objective(event="command", match={"name": "Test-Connection", "status": 0}, text="Ping LEGACY-SRV (Test-Connection)",
                              hints=["Test-Connection is PowerShell's ping.", "Try: Test-Connection 10.20.30.9", "Test-Connection 10.20.30.9"])],
        solution=["sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5", "Test-Connection 10.20.30.9"],
        reward_xp=50, tags=["bash", "act5", "ps"],
    ),
    Mission(
        id="act5_m113", number=113, act=5, size="standard", title="What Nobody Mentioned", scenario="win_webapp",
        requires=["act5_m112"],
        briefing=["NEXUS: This console runs a web service too, not just file shares. Nobody put that in any memo. "
                  "See what it's serving."],
        debrief=["NEXUS: 'Ticket queue, relay health, account audit' — an actual internal dashboard. That's worth a "
                 "much closer look, later, when it's not the only thing on the agenda."],
        objectives=[Objective(event="command", match={"name": "Invoke-WebRequest", "status": 0}, text="Fetch the dashboard (Invoke-WebRequest)",
                              hints=["Invoke-WebRequest is PowerShell's curl.", "Try: Invoke-WebRequest -Uri http://10.20.30.5/", "Invoke-WebRequest -Uri http://10.20.30.5/"])],
        solution=["sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5", "Invoke-WebRequest -Uri http://10.20.30.5/"],
        reward_xp=85, tags=["bash", "act5", "ps"],
    ),
    Mission(
        id="act5_m114", number=114, act=5, size="mini", title="Add It Up", scenario="win_measure",
        requires=["act5_m113"],
        briefing=["MIRA: Don't eyeball the process list and guess. Get an actual total."],
        debrief=["MIRA: A number, not an impression. That's the difference between a report and a hunch."],
        objectives=[Objective(event="command", match={"name": "Measure-Object", "status": 0}, text="Total the CPU usage across processes (Measure-Object)",
                              hints=["Measure-Object -Sum adds up a numeric property across every object.",
                                    "Try: Get-Process | Measure-Object CPU -Sum", "Get-Process | Measure-Object CPU -Sum"])],
        solution=["sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5", "Get-Process | Measure-Object CPU -Sum"],
        reward_xp=45, tags=["bash", "act5", "ps"],
    ),
    Mission(
        id="act5_m115", number=115, act=5, size="story", title="Someone Else's Login", scenario="win_origin",
        requires=["act5_m114"],
        briefing=["NEXUS: If svc_update logged in, it came from somewhere. Find out where."],
        debrief=["NEXUS: 198.51.100.231. Not Kade Voss's documented range. Not us.",
                 "MIRA: So there's a third party, already inside, and we don't know who. Noted. Filed. Not solved "
                 "today — we don't have enough to chase it yet."],
        objectives=[Objective(event="file_read", match={"path__glob": "*auth_history.txt"}, text="Find where svc_update logged in from",
                              hints=["There's an auth history log at the system root.", "Try: Get-Content C:\\Windows\\Logs\\auth_history.txt",
                                    "Get-Content C:\\Windows\\Logs\\auth_history.txt"])],
        solution=["sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5", "Get-Content C:\\Windows\\Logs\\auth_history.txt"],
        reward_xp=115, tags=["bash", "act5", "story"],
    ),
    Mission(
        id="act5_m116", number=116, act=5, size="standard", title="Not Right Now, Anyway", scenario="win_quiet",
        requires=["act5_m115"],
        briefing=["MIRA: Check that account again. I want to know if it's still a live concern or just a loose end "
                  "for now."],
        debrief=["MIRA: Still there, still enabled. Not actively doing anything we can see right now. That's not "
                 "the same as gone."],
        objectives=[
            Objective(event="command", match={"name": "Get-LocalUser", "status": 0}, text="Check the account list (Get-LocalUser)",
                     hints=["Same command as before.", "Try: Get-LocalUser", "Get-LocalUser"]),
            Objective(event="command", match={"name": "Where-Object", "status": 0}, text="Filter to just that account (Where-Object)",
                     hints=["Where-Object Name -eq svc_update filters by a property directly, no scriptblock needed.",
                           "Try: Get-LocalUser | Where-Object Name -eq svc_update", "Get-LocalUser | Where-Object Name -eq svc_update"]),
        ],
        solution=["sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5", "Get-LocalUser | Where-Object Name -eq svc_update"],
        reward_xp=80, tags=["bash", "act5", "ps"],
    ),
    Mission(
        id="act5_m117", number=117, act=5, size="story", title="The Net Closing", scenario="win_tightening",
        requires=["act5_m116"],
        briefing=["NEXUS: Broadcast memo, all console admins. Read it — it affects you too, now."],
        debrief=["NEXUS: 'Closer than people think.' He's not wrong. Every session logged from here on, reviewed "
                 "daily. We don't get to be sloppy anymore, if we ever did."],
        objectives=[Objective(event="file_read", match={"path__glob": "*voss_broadcast.txt"}, text="Read Kade Voss's broadcast memo",
                              hints=["Check your inbox.", "Try: cat inbox/voss_broadcast.txt", "cat inbox/voss_broadcast.txt"])],
        solution=["cat inbox/voss_broadcast.txt"], reward_xp=100, tags=["bash", "act5", "story", "kade-voss"],
    ),
    Mission(
        id="act5_m118", number=118, act=5, size="mini", title="What's Not Running", scenario="win_banner",
        requires=["act5_m117"],
        briefing=["MIRA: One more pass — which services are supposed to be running and aren't? A stopped service is "
                  "sometimes a weakness, sometimes just neglect. Worth knowing either way."],
        debrief=["MIRA: Filed. Doesn't matter today. Might matter later."],
        objectives=[Objective(event="command", match={"name": "Where-Object", "status": 0}, text="Filter services to the stopped ones",
                              hints=["Where-Object Status -eq Stopped filters the service list by that property.",
                                    "Try: Get-Service | Where-Object Status -eq Stopped", "Get-Service | Where-Object Status -eq Stopped"])],
        solution=["sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5", "Get-Service | Where-Object Status -eq Stopped"],
        reward_xp=50, tags=["bash", "act5", "ps"],
    ),
    Mission(
        id="act5_m119", number=119, act=5, size="story", title="Push or Pull Back", scenario="win_pullback",
        requires=["act5_m118"],
        briefing=["NEXUS: Mira wants a real decision this time, not just an opinion. Read it."],
        debrief=["NEXUS: On the record, then. Whatever happens from here, that's the call you made, with everything "
                 "you actually knew at the time.",
                 "MIRA: That's all any of us get."],
        objectives=[
            Objective(event="file_read", match={"path__glob": "*mira_pullback.txt"}, text="Read Mira's question",
                     hints=["Check your inbox.", "Try: cat inbox/mira_pullback.txt", "cat inbox/mira_pullback.txt"]),
            Objective(event="command", match={"name": "echo", "status": 0}, text="Give her a real answer",
                     hints=["Same move as always — write it, append it to the file.",
                           'echo "your answer here" >> inbox/mira_pullback.txt', 'echo "We keep pushing." >> inbox/mira_pullback.txt']),
        ],
        solution=["cat inbox/mira_pullback.txt", 'echo "We keep pushing." >> inbox/mira_pullback.txt'],
        reward_xp=130, tags=["bash", "act5", "story", "decision:3"],
    ),
    Mission(
        id="act5_m120", number=120, act=5, size="milestone", title="Everything This Act Found", scenario="win_handoff2",
        requires=["act5_m119"],
        briefing=["MIRA: Full record before we close this out: Voss, the dashboard, svc_update, all of it, one file, "
                  "archived properly."],
        debrief=["MIRA: Filed and locked. Act closed.",
                 "NEXUS: Rank up — ENGINEER. A named hunter closing in, an unidentified third party already inside, "
                 "and a dashboard we haven't even really looked at yet. None of that went away. It just got written "
                 "down properly, which is the only way to carry this much forward.",
                 "MIRA: Next time we touch that edge server infrastructure for real, we go in knowing what we're "
                 "dealing with. That's worth more than it sounds like."],
        objectives=[
            Objective(event="file_read", match={"path__glob": "*act5_summary.txt"}, text="Assemble everything (grep -r ... | tee)",
                     hints=["Same habit as every chapter close so far.", "Try: grep -r . winfinal | tee act5_summary.txt",
                           "grep -r . winfinal | tee act5_summary.txt\ncat act5_summary.txt"]),
            Objective(event="sudo_used", match={"command": "cp"}, text="Archive it (sudo cp)",
                     hints=["It lives at /archive, at the filesystem root.", "Try: sudo cp act5_summary.txt /archive/act5_summary.txt",
                           "sudo cp act5_summary.txt /archive/act5_summary.txt"]),
        ],
        solution=["grep -r . winfinal | tee act5_summary.txt", "cat act5_summary.txt", "sudo cp act5_summary.txt /archive/act5_summary.txt"],
        reward_xp=230, tags=["bash", "act5", "milestone", "grep", "tee", "sudo"],
    ),
]

ACT5 = [*ACT5_CHAPTER1, *ACT5_CHAPTER2, *ACT5_CHAPTER3]
