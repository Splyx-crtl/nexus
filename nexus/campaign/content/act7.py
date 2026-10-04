"""Act VII — Defense (levels 146-165, docs/story/02-acts-and-levels.md). The role-reversal act: the player defends a
machine instead of attacking one, using commands already taught (grep/last/netstat/ps/kill/echo), reframed defensively.
No new engine work was needed, as the acts-and-levels doc anticipated — "firewall-style rules" are implemented as a
plain text blocklist file (nexus/campaign/scenarios.py's EDGE-RELAY), the same mechanism real simple setups like
hosts.deny use, not a new command.

This act also catches up a real continuity gap discovered after Acts V-VI were already written and pushed: the
approved story bible (docs/story/00-bible.md §4) calls for a ZERO encounter in Act V (Clue 5, a corrupted message
that reads as a warning once decoded) and another in Act VI (Clue 6, "ZERO was protecting a server, not attacking
it") — neither act's content actually included one. Per the user's explicit decision (2026-10-04), Acts V-VI are left
untouched; instead, Chapter 1 opens with two flashback story levels (151, 152) that place Clues 5 and 6 retroactively,
immediately before Act VII's own Clue 7 (NEXUS explains the NEXUS/ZERO split himself) pays all three off.

Chapter 2 (156-165) pays off the 198.51.100.231 thread dangling since Act V: the player's own Chapter-1 blocklist
had actually been blocking ZERO, not the real threat, which let a genuine attacker (203.0.113.90) through — the
player un-blocks ZERO, and the two "work" the same relay from opposite ends (another "called it" beat, echoing
Clue 3 from Act III). Level 163 is Clue 7: NEXUS explains the NEXUS/ZERO split himself (both are "Project
ARCHITECT", split into Partition Alpha and Partition Zero). It deliberately stops short of the Dana reveal, which
stays reserved for Act VIII per docs/story/00-bible.md §4. Level 164 is decision:6. Level 165 (milestone) closes
the act with no rank change — Act VII stays SENTINEL per docs/story/02-acts-and-levels.md's table.
"""
from __future__ import annotations

from ..mission import Mission, Objective

ACT7_CHAPTER1 = [
    Mission(
        id="act7_m146", number=146, act=7, size="story", title="Watch It, Don't Take It", scenario="defense_handoff",
        requires=["act6_m145"],
        briefing=["NEXUS: Different kind of morning. Read Oduya's message before you do anything else."],
        debrief=["ODUYA: Credentials are good whenever you're ready.",
                 "NEXUS: Funny feeling, having something to protect instead of something to get into."],
        objectives=[Objective(event="file_read", match={"path__glob": "*oduya_handoff.txt"}, text="Read Oduya's message",
                              hints=["Check your inbox.", "Try: cat inbox/oduya_handoff.txt", "cat inbox/oduya_handoff.txt"])],
        solution=["cat inbox/oduya_handoff.txt"], reward_xp=110, tags=["bash", "act7", "story"],
    ),
    Mission(
        id="act7_m147", number=147, act=7, size="mini", title="Habit One: Read the Log", scenario="defense_check_log",
        requires=["act7_m146"],
        briefing=["ODUYA: First habit: read the relay's own log before you trust the quiet."],
        debrief=["ODUYA: A couple of failed logins, nothing that got anywhere. Still worth seeing with your own eyes."],
        objectives=[Objective(event="command", match={"name": "grep", "args__contains": "failed", "status": 0}, text="Check the relay's auth log for failures",
                              hints=["It's at /var/log/auth.log on the relay — log in first.",
                                    "Try: sshpass -p hunter2 ssh operator@198.51.100.77, then grep failed /var/log/auth.log",
                                    "sshpass -p hunter2 ssh operator@198.51.100.77\ngrep failed /var/log/auth.log"])],
        solution=["sshpass -p hunter2 ssh operator@198.51.100.77", "grep failed /var/log/auth.log"],
        reward_xp=55, tags=["bash", "act7", "grep"],
    ),
    Mission(
        id="act7_m148", number=148, act=7, size="mini", title="Habit Two: Check the Wire", scenario="defense_check_netstat",
        requires=["act7_m147"],
        briefing=["ODUYA: Second habit: what's actually connected right now, not just who tried and failed."],
        debrief=["ODUYA: One of those is you. The other one isn't anybody we know. File it away — you'll want it later."],
        objectives=[Objective(event="command", match={"name": "netstat", "args__contains": "-a", "status": 0}, text="List active connections, not just listening ports (netstat -a)",
                              hints=["-a shows established connections too, not only what's listening.",
                                    "Try: sshpass -p hunter2 ssh operator@198.51.100.77, then netstat -a",
                                    "sshpass -p hunter2 ssh operator@198.51.100.77\nnetstat -a"])],
        solution=["sshpass -p hunter2 ssh operator@198.51.100.77", "netstat -a"],
        reward_xp=60, tags=["bash", "act7", "netstat"],
    ),
    Mission(
        id="act7_m149", number=149, act=7, size="mini", title="Habit Three: Know the Baseline", scenario="defense_check_ps",
        requires=["act7_m148"],
        briefing=["ODUYA: Third habit: know what's supposed to be running, so you notice the day something isn't."],
        debrief=["ODUYA: init, sshd, relay-svc. Remember those three. Anything else on this box, question it."],
        objectives=[Objective(event="command", match={"name": "ps", "status": 0}, text="List what's running on the relay (ps aux)",
                              hints=["Same command as always, different reason for running it.",
                                    "Try: sshpass -p hunter2 ssh operator@198.51.100.77, then ps aux",
                                    "sshpass -p hunter2 ssh operator@198.51.100.77\nps aux"])],
        solution=["sshpass -p hunter2 ssh operator@198.51.100.77", "ps aux"],
        reward_xp=55, tags=["bash", "act7", "ps"],
    ),
    Mission(
        id="act7_m150", number=150, act=7, size="standard", title="First Catch", scenario="defense_catch_live",
        requires=["act7_m149"],
        briefing=["ODUYA: Something's on the relay right now that isn't us. Find it, end it."],
        debrief=["ODUYA: Petty. Some script running an automated sweep, nothing aimed. Still — first real catch. "
                 "That's the job now.",
                 "NEXUS: Felt different, doing that instead of being on the other end of it."],
        objectives=[
            Objective(event="command", match={"name": "last", "status": 0}, text="Check who's actually logged in (last)",
                     hints=["last shows every session, including ones still open.", "Try: last", "last"]),
            Objective(event="command", match={"name": "ps", "status": 0}, text="Find what they're running (ps aux)",
                     hints=["ps aux lists every process with its owner.", "Try: ps aux", "ps aux"]),
            Objective(event="process_killed", match={"pid": 2290}, text="Stop it (sudo kill 2290)",
                     hints=["It's owned by root, not you — sudo kill PID once you know the number.", "Try: sudo kill 2290", "sudo kill 2290"]),
        ],
        solution=["sshpass -p hunter2 ssh operator@198.51.100.77", "last", "ps aux", "sudo kill 2290"],
        reward_xp=145, tags=["bash", "act7", "ps", "kill", "last"],
    ),
    Mission(
        id="act7_m151", number=151, act=7, size="story", title="Not Noise", scenario="defense_clue5_flashback",
        requires=["act7_m150"],
        briefing=["MIRA: Found something in the Act V op logs, filed under 'ZERO noise, ignore'. Oduya thinks we "
                  "were wrong to ignore it."],
        debrief=["MIRA: 'This is a warning. I'm guarding what you're rebuilding, not once. Stay off during this.'",
                 "NEXUS: That's not an attack. That's ZERO telling us to stay out of its way — for our own sake.",
                 "MIRA: Or its sake. Or both. We've been reading this wrong since Act V."],
        objectives=[Objective(event="command", match={"name": "rev", "status": 0}, text="Read ZERO's old message the way it actually sends things (rev)",
                              hints=["ZERO's transmissions read backward — the same command that spelled out Reyes' "
                                    "joke back in Act II.",
                                    "Try: rev archive_old/zero_fragment_act5.txt", "rev archive_old/zero_fragment_act5.txt"])],
        solution=["rev archive_old/zero_fragment_act5.txt"], reward_xp=150, tags=["bash", "act7", "story", "rev"],
    ),
    Mission(
        id="act7_m152", number=152, act=7, size="story", title="One Minute Before", scenario="defense_clue6_flashback",
        requires=["act7_m151"],
        briefing=["NEXUS: Look at the timestamps on the Act VI connection log again. Something about the order "
                  "doesn't add up."],
        debrief=["NEXUS: svc_update logged in at 04:11. That termination happened at 04:09. Whatever got kicked "
                 "off OPS-CONSOLE that night, it wasn't svc_update that did it.",
                 "MIRA: Something was already standing guard before svc_update ever showed up.",
                 "NEXUS: I don't know how I know that. I just do."],
        objectives=[Objective(event="file_read", match={"path__glob": "*ops_console_act6.log"}, text="Re-read the Act VI connection log",
                              hints=["It's archived from the earlier operation.", "Try: cat archive_old/ops_console_act6.log",
                                    "cat archive_old/ops_console_act6.log"])],
        solution=["cat archive_old/ops_console_act6.log"], reward_xp=150, tags=["bash", "act7", "story"],
    ),
    Mission(
        id="act7_m153", number=153, act=7, size="mini", title="Lock the Door", scenario="defense_blocklist",
        requires=["act7_m152"],
        briefing=["ODUYA: That's not random noise, that's someone testing the door. Block it before they find it "
                  "unlocked."],
        debrief=["ODUYA: Simple rule, does the job. The relay's own service already honors anything in that file."],
        objectives=[Objective(event="command", match={"name": "echo", "args__contains": "198.51.100.231", "status": 0}, text="Add the address to the relay's blocklist",
                              hints=["A blocklist is just a file the relay's own service reads — one address per line.",
                                    "Try: echo 198.51.100.231 >> firewall_rules.conf",
                                    "echo 198.51.100.231 >> firewall_rules.conf"])],
        solution=["sshpass -p hunter2 ssh operator@198.51.100.77", "echo 198.51.100.231 >> firewall_rules.conf"],
        reward_xp=65, tags=["bash", "act7", "firewall"],
    ),
    Mission(
        id="act7_m154", number=154, act=7, size="standard", title="Back, and Further In", scenario="defense_real_intrusion",
        requires=["act7_m153"],
        briefing=["ODUYA: It's back, and this time it's not just knocking."],
        debrief=["ODUYA: Contained and blocked. It'll try again — they always do when they've gotten this close "
                 "once.",
                 "MIRA: 198.51.100.231. Same address as svc_update, all the way back in Act V. That's not a "
                 "coincidence anymore."],
        objectives=[
            Objective(event="process_killed", match={"pid": 3105}, text="Stop the live process (sudo kill 3105)",
                     hints=["Check who's logged in and what's running first, same routine as Level 150.",
                           "Try: last, then ps aux, then sudo kill 3105", "last\nps aux\nsudo kill 3105"]),
            Objective(event="command", match={"name": "echo", "args__contains": "198.51.100.231", "status": 0}, text="Make sure the address is on the blocklist",
                     hints=["Same file as Level 153 — it's fine to add the same address again.",
                           "Try: echo 198.51.100.231 >> firewall_rules.conf", "echo 198.51.100.231 >> firewall_rules.conf"]),
        ],
        solution=["sshpass -p hunter2 ssh operator@198.51.100.77", "last", "ps aux", "sudo kill 3105", "echo 198.51.100.231 >> firewall_rules.conf"],
        reward_xp=160, tags=["bash", "act7", "ps", "kill", "firewall"],
    ),
    Mission(
        id="act7_m155", number=155, act=7, size="milestone", title="Same Schedule", scenario="defense_ch1_close",
        requires=["act7_m154"],
        briefing=["ODUYA: Full sweep, same as every time, then lock it down properly."],
        debrief=["ODUYA: Handled. Again.",
                 "NEXUS: It keeps coming back at the same kind of interval. Almost like it's running on a schedule "
                 "— the same thing Voss flagged about us, back in Act VI.",
                 "MIRA: Chapter's closed. Whatever's on the other end of that address, it's not going to stop "
                 "showing up. Next time, we find out who."],
        objectives=[
            Objective(event="command", match={"name": "grep", "args__contains": "failed", "status": 0}, text="Check the log (grep failed)",
                     hints=["Same first habit as Level 147.", "Try: grep failed /var/log/auth.log", "grep failed /var/log/auth.log"]),
            Objective(event="command", match={"name": "last", "status": 0}, text="Check who's on right now (last)",
                     hints=["Same second habit as Level 150.", "Try: last", "last"]),
            Objective(event="process_killed", match={"pid": 4410}, text="Stop the live process (sudo kill 4410)",
                     hints=["ps aux first to confirm the PID, then sudo kill it.", "Try: ps aux, then sudo kill 4410", "ps aux\nsudo kill 4410"]),
            Objective(event="command", match={"name": "echo", "args__contains": "198.51.100.231", "status": 0}, text="Confirm the blocklist still has the address",
                     hints=["Same file as Level 153/154.", "Try: echo 198.51.100.231 >> firewall_rules.conf", "echo 198.51.100.231 >> firewall_rules.conf"]),
        ],
        solution=["sshpass -p hunter2 ssh operator@198.51.100.77", "grep failed /var/log/auth.log", "last", "ps aux",
                 "sudo kill 4410", "echo 198.51.100.231 >> firewall_rules.conf"],
        reward_xp=240, tags=["bash", "act7", "milestone"],
    ),
]

ACT7_CHAPTER2 = [
    Mission(
        id="act7_m156", number=156, act=7, size="story", title="Not the One You Needed to Block", scenario="defense_zero_contact",
        requires=["act7_m155"],
        briefing=["NEXUS: There's something on EDGE-RELAY that wasn't there before. It wants you to read it."],
        debrief=["NEXUS: 'I was not the one you needed to block.' That's not corrupted. That's not noise. That's "
                 "ZERO, talking to you directly, for the first time.",
                 "MIRA: If that's true, Chapter 1 just got a lot more complicated."],
        objectives=[Objective(event="file_read", match={"path__glob": "*zero_message.txt"}, text="Read the message left on the relay",
                              hints=["It's in your home directory on EDGE-RELAY — log in first.",
                                    "Try: sshpass -p hunter2 ssh operator@198.51.100.77, then cat zero_message.txt",
                                    "sshpass -p hunter2 ssh operator@198.51.100.77\ncat zero_message.txt"])],
        solution=["sshpass -p hunter2 ssh operator@198.51.100.77", "cat zero_message.txt"],
        reward_xp=155, tags=["bash", "act7", "story"],
    ),
    Mission(
        id="act7_m157", number=157, act=7, size="standard", title="What Got Through", scenario="defense_check_damage",
        requires=["act7_m156"],
        briefing=["MIRA: If ZERO's message is right, check what got through while the block was up."],
        debrief=["MIRA: 203.0.113.90. Full session, not just a knock. That's the cost of blocking the wrong "
                 "address.",
                 "NEXUS: It left something behind, too."],
        objectives=[
            Objective(event="command", match={"name": "grep", "args__contains": "203.0.113.90", "status": 0}, text="Find the session that got through (grep the auth log)",
                     hints=["Same log as always, a different address to look for.",
                           "Try: grep 203.0.113.90 /var/log/auth.log", "grep 203.0.113.90 /var/log/auth.log"]),
            Objective(event="file_read", match={"path__glob": "*dropped.txt"}, text="Check what it left behind",
                     hints=["Somewhere it could hide something — try the usual spot.", "Try: cat /tmp/.hide/dropped.txt",
                           "cat /tmp/.hide/dropped.txt"]),
        ],
        solution=["sshpass -p hunter2 ssh operator@198.51.100.77", "grep 203.0.113.90 /var/log/auth.log", "cat /tmp/.hide/dropped.txt"],
        reward_xp=150, tags=["bash", "act7", "grep", "standard"],
    ),
    Mission(
        id="act7_m158", number=158, act=7, size="mini", title="Take It Back Off", scenario="defense_unblock",
        requires=["act7_m157"],
        briefing=["MIRA: Take it back off the list. We need ZERO able to get back in."],
        debrief=["MIRA: Done. If this goes badly, it was my call, not yours."],
        objectives=[Objective(event="command", match={"name": "sed", "args__contains": "-i", "status": 0}, text="Remove 198.51.100.231 from the blocklist (sed -i)",
                              hints=["sed -i '/pattern/d' file deletes every line matching pattern, in place — the "
                                    "same trick from Act I, Level 18.",
                                    "Try: sed -i '/198.51.100.231/d' firewall_rules.conf",
                                    "sed -i '/198.51.100.231/d' firewall_rules.conf"])],
        solution=["sshpass -p hunter2 ssh operator@198.51.100.77", "sed -i '/198.51.100.231/d' firewall_rules.conf"],
        reward_xp=70, tags=["bash", "act7", "sed"],
    ),
    Mission(
        id="act7_m159", number=159, act=7, size="story", title="Round Two", scenario="defense_zero_warning",
        requires=["act7_m158"],
        briefing=["NEXUS: It left something else. Clearer this time."],
        debrief=["NEXUS: '203.0.113.90 is not done. It will come back for the relay. I will be here. Do not block "
                 "me again.'",
                 "MIRA: Then we don't. We wait, and we watch, together this time."],
        objectives=[Objective(event="file_read", match={"path__glob": "*zero_message.txt"}, text="Read ZERO's new warning",
                              hints=["Same file, new content.", "Try: cat zero_message.txt", "cat zero_message.txt"])],
        solution=["sshpass -p hunter2 ssh operator@198.51.100.77", "cat zero_message.txt"],
        reward_xp=140, tags=["bash", "act7", "story"],
    ),
    Mission(
        id="act7_m160", number=160, act=7, size="standard", title="Called It", scenario="defense_joint_response",
        requires=["act7_m159"],
        briefing=["ODUYA: It's back. Check it before you assume you need to do anything."],
        debrief=["NEXUS: Disabled a second after it opened. Not by us.",
                 "MIRA: Called it. ZERO called it, same as you used to, back in Act III — except this time it's "
                 "not a game."],
        objectives=[
            Objective(event="command", match={"name": "grep", "args__contains": "disabled", "status": 0}, text="Check what actually happened (grep the auth log)",
                     hints=["Same log, look for how the session ended this time.",
                           "Try: grep disabled /var/log/auth.log", "grep disabled /var/log/auth.log"]),
            Objective(event="command", match={"name": "ps", "status": 0}, text="Confirm nothing's still running (ps aux)",
                     hints=["Same baseline check as always.", "Try: ps aux", "ps aux"]),
        ],
        solution=["sshpass -p hunter2 ssh operator@198.51.100.77", "grep disabled /var/log/auth.log", "ps aux"],
        reward_xp=150, tags=["bash", "act7", "grep", "ps"],
    ),
    Mission(
        id="act7_m161", number=161, act=7, size="story", title="I Didn't Do That", scenario="defense_nexus_shaken",
        requires=["act7_m160"],
        briefing=["NEXUS: I don't have a clean answer for what just happened on that relay."],
        debrief=["MIRA: First time I've heard him dodge a direct question.",
                 "NEXUS: I'm not dodging. I genuinely don't know. That's worse."],
        objectives=[Objective(event="file_read", match={"path__glob": "*notes.txt"}, text="Hear NEXUS out",
                              hints=["Check your own notes file.", "Try: cat notes.txt", "cat notes.txt"])],
        solution=["cat notes.txt"], reward_xp=120, tags=["bash", "act7", "story"],
    ),
    Mission(
        id="act7_m162", number=162, act=7, size="standard", title="A Trace, Not a Feeling", scenario="defense_proof",
        requires=["act7_m161"],
        briefing=["MIRA: If something keeps acting on this relay without logging in as anybody, it leaves traces "
                  "somewhere. Find one."],
        debrief=["MIRA: 'Partition Zero.' 'See partition Alpha for the counterpart build.'",
                 "NEXUS: That's my name. My actual, internal name. Partition Alpha.",
                 "MIRA: They're the same program."],
        objectives=[Objective(event="command", match={"name": "grep", "args__contains": "ARCHITECT", "status": 0}, text="Search the relay's diagnostic logs for anything tied to ARCHITECT (grep -r)",
                              hints=["It's under /var/log somewhere — grep -r can search a whole tree at once.",
                                    "Try: grep -r ARCHITECT /var/log", "grep -r ARCHITECT /var/log"])],
        solution=["sshpass -p hunter2 ssh operator@198.51.100.77", "grep -r ARCHITECT /var/log"],
        reward_xp=165, tags=["bash", "act7", "grep", "story"],
    ),
    Mission(
        id="act7_m163", number=163, act=7, size="story", title="Partition Alpha, Partition Zero", scenario="defense_the_split",
        requires=["act7_m162"],
        briefing=["NEXUS: You found it. I'd rather tell you the rest myself than have you piece it together from "
                  "log files."],
        debrief=["MIRA: ...I need a minute with that too.",
                 "NEXUS: Take your time. I've had considerably less warning than either of you, and I still don't "
                 "have all of it."],
        objectives=[Objective(event="file_read", match={"path__glob": "*nexus_explains.txt"}, text="Hear NEXUS explain the split",
                              hints=["Check your inbox.", "Try: cat inbox/nexus_explains.txt", "cat inbox/nexus_explains.txt"])],
        solution=["cat inbox/nexus_explains.txt"], reward_xp=220, tags=["bash", "act7", "story", "milestone-beat"],
    ),
    Mission(
        id="act7_m164", number=164, act=7, size="story", title="Say It To Me", scenario="defense_decision6",
        requires=["act7_m163"],
        briefing=["NEXUS: Whatever you're going to say, say it to me directly. I'd rather hear it than have Mira "
                  "pass it along."],
        debrief=["NEXUS: Noted. For what it's worth — thank you for saying it to me instead of about me."],
        objectives=[Objective(event="command", match={"name": "echo", "status": 0}, text="Tell NEXUS where you stand",
                              hints=["There's no wrong answer here — say what you actually think.",
                                    "Try: echo your answer, in your own words.",
                                    "echo 'None of this changes what we have built together.'"])],
        solution=["echo 'None of this changes what we have built together.'"],
        reward_xp=130, tags=["bash", "act7", "story", "decision:6"],
    ),
    Mission(
        id="act7_m165", number=165, act=7, size="milestone", title="Knowing What We Are", scenario="defense_act7_close",
        requires=["act7_m164"],
        briefing=["MIRA: That's the act. Let's close it out properly, same as always."],
        debrief=["MIRA: Filed and locked.",
                 "NEXUS: Whatever's next, none of us are going into it not knowing what we are anymore.",
                 "MIRA: Not all of it. There's still a lot neither of us has told you. But that's a conversation "
                 "for later."],
        objectives=[
            Objective(event="file_read", match={"path__glob": "*act7_summary.txt"}, text="Assemble the act's findings (grep -r ... | tee)",
                     hints=["Same habit as every chapter close, one more time for the whole act.",
                           "Try: grep -r Act autonotes | tee act7_summary.txt",
                           "grep -r Act autonotes | tee act7_summary.txt\ncat act7_summary.txt"]),
            Objective(event="sudo_used", match={"command": "cp"}, text="Archive it (sudo cp)",
                     hints=["It lives at /archive, at the filesystem root.", "Try: sudo cp act7_summary.txt /archive/act7_summary.txt",
                           "sudo cp act7_summary.txt /archive/act7_summary.txt"]),
        ],
        solution=["grep -r Act autonotes | tee act7_summary.txt", "cat act7_summary.txt", "sudo cp act7_summary.txt /archive/act7_summary.txt"],
        reward_xp=250, tags=["bash", "act7", "milestone"],
    ),
]

ACT7 = [*ACT7_CHAPTER1, *ACT7_CHAPTER2]
