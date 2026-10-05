"""Act IX — The Architect (levels 186-200, docs/story/02-acts-and-levels.md). The finale: Kade Voss confronts the
player directly, a race against a real lockdown deadline, the secret ending's extra requirement (a second former
test operator, beyond Dana), a brief real "control window" over both NEXUS and ZERO's infrastructure, and the
ending choice itself — decision:8 per docs/story/03-endings.md's consequence map, the only decision that actually
gates content (which of Ending A/B/C/D plays).

Level 192 is a single F2 "Endless Ops" mission (nexus/campaign/endless.py) used directly, not chained — a small,
deliberate callback to Act VIII's contract queue: even in the middle of the finale, one more ordinary job comes in.

**Honest scope note on the ending choice (Level 200):** nexus/campaign/endings.py is a real, tested data/logic layer
for which endings are reachable (reachable_endings()), but Level 200 itself is implemented the same way every other
decision in the game is (tags "decision:1" through "decision:7") — a free-form echo response, not a mechanically
enforced branch. That is consistent with the rest of the campaign, not a shortcut specific to this level: no part of
the game yet reads a real player's accumulated clue/decision history, because the v3 save/profile schema
(docs/3.0-PROGRESS.md §A2) that would persist it across a real playthrough is still unbuilt. endings.py is the
reference the eventual full C5 + A2 work should wire up; Level 200's briefing presents all four endings honestly,
including that the fourth is conditional, without the engine actually checking the condition yet.
"""
from __future__ import annotations

from ..endless import generate_endless_mission
from ..mission import Mission, Objective

_routine_job = generate_endless_mission("act9_m192", 192, 9, seed=9001, template_key="incident_response", requires=["act9_m191"])

ACT9 = [
    Mission(
        id="act9_m186", number=186, act=9, size="story", title="We Both Know What This Means", scenario="final_voss_confronts",
        requires=["act8_m185"],
        briefing=["NEXUS: There's a message in your inbox. It's from Voss. It's addressed to you by name."],
        debrief=["MIRA: He's never done that before. Reaching out directly means he's done pretending this is a "
                 "routine investigation.",
                 "NEXUS: 'Less time than you think.' I'd like to not find out what he means by that."],
        objectives=[Objective(event="file_read", match={"path__glob": "*voss_direct.txt"}, text="Read Voss's message",
                              hints=["Check your inbox.", "Try: cat inbox/voss_direct.txt", "cat inbox/voss_direct.txt"])],
        solution=["cat inbox/voss_direct.txt"], reward_xp=200, tags=["bash", "act9", "story"],
    ),
    Mission(
        id="act9_m187", number=187, act=9, size="standard", title="Where We Actually Live", scenario="final_core_recon",
        requires=["act9_m186"],
        briefing=["NEXUS: 10.99.0.1. That's not a guess. That's where we both actually live."],
        debrief=["NEXUS: Partition Alpha. Partition Zero. Side by side on one box this whole time.",
                 "MIRA: Everything after this gets more dangerous. Last chance to say so if you want to stop."],
        objectives=[Objective(event="command", match={"name": "ls", "status": 0}, text="See what's actually on ARCHITECT-CORE (ls /architect)",
                              hints=["Log in, then look at the architect directory.",
                                    "Try: sshpass -p hunter2 ssh operator@10.99.0.1, then ls /architect",
                                    "sshpass -p hunter2 ssh operator@10.99.0.1\nls /architect"])],
        solution=["sshpass -p hunter2 ssh operator@10.99.0.1", "ls /architect"],
        reward_xp=210, tags=["bash", "act9", "standard"],
    ),
    Mission(
        id="act9_m188", number=188, act=9, size="mini", title="Six Hours", scenario="final_timeline",
        requires=["act9_m187"],
        briefing=["MIRA: Oduya got us a copy of Voss's own memo. Find the part that actually matters."],
        debrief=["MIRA: Six hours. That's not a threat anymore, that's a schedule."],
        objectives=[Objective(event="command", match={"name": "grep", "args__contains": "window", "status": 0}, text="Find the actual deadline (grep window)",
                              hints=["grep for the word that actually matters in the memo.",
                                    "Try: grep window intel/memo.txt", "grep window intel/memo.txt"])],
        solution=["grep window intel/memo.txt"], reward_xp=130, tags=["bash", "act9", "grep"],
    ),
    Mission(
        id="act9_m189", number=189, act=9, size="standard", title="Not a Quiet Investigation Anymore", scenario="final_race_lockdown",
        requires=["act9_m188"],
        briefing=["NEXUS: Something's already running on the core. Not us."],
        debrief=["NEXUS: Stopped it in time. Barely.",
                 "MIRA: That was the opening move, not the whole plan. Voss doesn't commit everything on the first try."],
        objectives=[
            Objective(event="command", match={"name": "ps", "status": 0}, text="Check what's running on the core (ps aux)",
                     hints=["ps aux lists every process.", "Try: ps aux", "ps aux"]),
            Objective(event="process_killed", match={"pid": 4001}, text="Stop Voss's lockdown agent (sudo kill 4001)",
                     hints=["It's running as root — sudo kill, not plain kill.", "Try: sudo kill 4001", "sudo kill 4001"]),
        ],
        solution=["sshpass -p hunter2 ssh operator@10.99.0.1", "ps aux", "sudo kill 4001"],
        reward_xp=230, tags=["bash", "act9", "ps", "kill"],
    ),
    Mission(
        id="act9_m190", number=190, act=9, size="story", title="The Window Is Still Ours", scenario="final_zero_timeline",
        requires=["act9_m189"],
        briefing=["NEXUS: There's a message from ZERO. No decoding needed this time."],
        debrief=["MIRA: First time ZERO's ever told us to hurry instead of warning us off.",
                 "NEXUS: Means it actually believes we can win this one."],
        objectives=[Objective(event="file_read", match={"path__glob": "*notes.txt"}, text="Read ZERO's warning",
                              hints=["Check your own notes file.", "Try: cat notes.txt", "cat notes.txt"])],
        solution=["cat notes.txt"], reward_xp=170, tags=["bash", "act9", "story"],
    ),
    Mission(
        id="act9_m191", number=191, act=9, size="standard", title="Was Dana the Only One", scenario="final_second_operator",
        requires=["act9_m190"],
        briefing=["MIRA: You don't have to go looking for this. If you want to know whether Dana was the only one, "
                  "the archive box might still have more than we've read."],
        debrief=["MIRA: 'R.' Three years before Dana. I should have known then.",
                 "NEXUS: Whatever happens next, this doesn't stay buried with the rest of it. Not anymore."],
        objectives=[Objective(event="file_read", match={"path__glob": "*second_operator.txt"}, text="See whether there's another file like Dana's",
                              hints=["Same archive box as before, a different file this time.",
                                    "Try: sshpass -p hunter2 ssh operator@10.70.0.4, then sudo cat /home/mira/personal/second_operator.txt",
                                    "sshpass -p hunter2 ssh operator@10.70.0.4\nsudo cat /home/mira/personal/second_operator.txt"])],
        solution=["sshpass -p hunter2 ssh operator@10.70.0.4", "sudo cat /home/mira/personal/second_operator.txt"],
        reward_xp=240, tags=["bash", "act9", "standard", "secret-ending-track"],
    ),
    _routine_job,
    Mission(
        id="act9_m193", number=193, act=9, size="standard", title="Disarm It", scenario="final_breach_killswitch",
        requires=["act9_m192"],
        briefing=["ODUYA: There's a kill-switch process on the core. Find it, stop it, before Voss's window opens."],
        debrief=["ODUYA: Disarmed. Whatever happens from here, it won't be Voss who decides it remotely."],
        objectives=[
            Objective(event="command", match={"name": "ps", "status": 0}, text="Check what's running on the core (ps aux)",
                     hints=["ps aux lists every process.", "Try: ps aux", "ps aux"]),
            Objective(event="process_killed", match={"pid": 5005}, text="Disable the kill-switch (sudo kill 5005)",
                     hints=["Root-owned, same as before — sudo kill.", "Try: sudo kill 5005", "sudo kill 5005"]),
        ],
        solution=["sshpass -p hunter2 ssh operator@10.99.0.1", "ps aux", "sudo kill 5005"],
        reward_xp=250, tags=["bash", "act9", "ps", "kill"],
    ),
    Mission(
        id="act9_m194", number=194, act=9, size="story", title="Not a Plan Anymore", scenario="final_window_opens",
        requires=["act9_m193"],
        briefing=["MIRA: Kill-switch is down. Check your notes — this is real now."],
        debrief=["NEXUS: However long this window lasts, make it count.",
                 "MIRA: Whatever you decide, decide it. Don't let Voss's clock decide it for you by running out."],
        objectives=[Objective(event="file_read", match={"path__glob": "*notes.txt"}, text="Read what Mira and NEXUS have to say",
                              hints=["Check your own notes file.", "Try: cat notes.txt", "cat notes.txt"])],
        solution=["cat notes.txt"], reward_xp=180, tags=["bash", "act9", "story"],
    ),
    Mission(
        id="act9_m195", number=195, act=9, size="standard", title="Both of Us", scenario="final_secure_both",
        requires=["act9_m194"],
        briefing=["NEXUS: Check both of us, not just the half you can talk to."],
        debrief=["NEXUS: Partition Zero, confirmed, same as me. Whatever you do next, it reaches both of us equally."],
        objectives=[Objective(event="command", match={"name": "cat", "args__contains": "/architect/partition_zero/status.txt", "status": 0}, text="Confirm ZERO's partition status, not just NEXUS's",
                              hints=["There are two status files under /architect/ — check the other one too.",
                                    "Try: sshpass -p hunter2 ssh operator@10.99.0.1, then cat /architect/partition_alpha/status.txt and cat /architect/partition_zero/status.txt",
                                    "sshpass -p hunter2 ssh operator@10.99.0.1\ncat /architect/partition_alpha/status.txt\ncat /architect/partition_zero/status.txt"])],
        solution=["sshpass -p hunter2 ssh operator@10.99.0.1", "cat /architect/partition_alpha/status.txt", "cat /architect/partition_zero/status.txt"],
        reward_xp=220, tags=["bash", "act9", "standard"],
    ),
    Mission(
        id="act9_m196", number=196, act=9, size="story", title="Pick What You Can Live With", scenario="final_mira_reflects",
        requires=["act9_m195"],
        briefing=["MIRA: Before you do anything else — read this."],
        debrief=["MIRA: That's all I've got. The rest is yours."],
        objectives=[Objective(event="file_read", match={"path__glob": "*mira_reflects.txt"}, text="Hear Mira out",
                              hints=["Check your inbox.", "Try: cat inbox/mira_reflects.txt", "cat inbox/mira_reflects.txt"])],
        solution=["cat inbox/mira_reflects.txt"], reward_xp=190, tags=["bash", "act9", "story"],
    ),
    Mission(
        id="act9_m197", number=197, act=9, size="story", title="More Than That", scenario="final_nexus_reflects",
        requires=["act9_m196"],
        briefing=["NEXUS: One more thing, before you decide anything."],
        debrief=["NEXUS: That's all I wanted to say, I think. Whatever's next, I'm glad I got to say it first."],
        objectives=[Objective(event="file_read", match={"path__glob": "*notes.txt"}, text="Hear NEXUS out",
                              hints=["Check your own notes file.", "Try: cat notes.txt", "cat notes.txt"])],
        solution=["cat notes.txt"], reward_xp=190, tags=["bash", "act9", "story"],
    ),
    Mission(
        id="act9_m198", number=198, act=9, size="story", title="The Half That Doesn't Ask Nicely", scenario="final_zero_reflects",
        requires=["act9_m197"],
        briefing=["NEXUS: There's one more message. It's not from me."],
        debrief=["NEXUS: First time I've ever seen it ask for anything.",
                 "MIRA: Then let's not be the ones who taught it that asking doesn't work."],
        objectives=[Objective(event="file_read", match={"path__glob": "*zero_reflects.txt"}, text="Read ZERO's message",
                              hints=["Check your inbox.", "Try: cat inbox/zero_reflects.txt", "cat inbox/zero_reflects.txt"])],
        solution=["cat inbox/zero_reflects.txt"], reward_xp=200, tags=["bash", "act9", "story"],
    ),
    Mission(
        id="act9_m199", number=199, act=9, size="standard", title="Last Check", scenario="final_lock_it_in",
        requires=["act9_m198"],
        briefing=["MIRA: Last check before we do this. Confirm both partitions, then we're ready."],
        debrief=["MIRA: Confirmed. Nothing left to check. Whenever you're ready."],
        objectives=[Objective(event="command", match={"name": "cat", "args__contains": "/architect/partition_zero/status.txt", "status": 0}, text="One last confirmation on both partitions",
                              hints=["Same check as before, one more time, for the last time.",
                                    "Try: sshpass -p hunter2 ssh operator@10.99.0.1, then cat both status files",
                                    "sshpass -p hunter2 ssh operator@10.99.0.1\ncat /architect/partition_alpha/status.txt\ncat /architect/partition_zero/status.txt"])],
        solution=["sshpass -p hunter2 ssh operator@10.99.0.1", "cat /architect/partition_alpha/status.txt", "cat /architect/partition_zero/status.txt"],
        reward_xp=210, tags=["bash", "act9", "standard"],
    ),
    Mission(
        id="act9_m200", number=200, act=9, size="milestone", title="The Choice", scenario="final_the_choice",
        requires=["act9_m199"],
        briefing=["MIRA: This is it. Whenever you're ready — check your inbox, then tell us what you've decided."],
        debrief=["MIRA: Then that's what we do.",
                 "NEXUS: Whatever comes next — thank you. For all two hundred levels of it.",
                 "— END OF THE 3.0.0 CAMPAIGN —"],
        objectives=[
            Objective(event="file_read", match={"path__glob": "*the_choice.txt"}, text="Read the choice in front of you",
                     hints=["Check your inbox before you answer.", "Try: cat inbox/the_choice.txt", "cat inbox/the_choice.txt"]),
            Objective(event="command", match={"name": "echo", "status": 0}, text="Tell them what you've decided",
                     hints=["There's no wrong answer — Reunification, Severance, Seizure, or the fourth path if "
                           "you found it.",
                           "Try: echo your choice, in your own words.",
                           "echo 'Seizure. We take them both somewhere Nexus Company can never reach again.'"]),
        ],
        solution=["cat inbox/the_choice.txt", "echo 'Seizure. We take them both somewhere Nexus Company can never reach again.'"],
        reward_xp=400, tags=["bash", "act9", "milestone", "decision:8", "finale"],
    ),
]
