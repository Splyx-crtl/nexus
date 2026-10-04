"""Act VIII — Automation (levels 166-185, docs/story/02-acts-and-levels.md). Needs F2's "Endless Ops" piece, built
this session in nexus/campaign/endless.py (see its module docstring for the F2 scope decision — base/economy/teams
stay out of scope, only the procedural-mission generator Act VIII actually calls for was built). Framed in-fiction
as Mira plugging the player into a continuous contract queue instead of hand-picking jobs one at a time, which is
also the literal mechanism: ``generate_endless_chain`` produces the queue's actual missions.

Story spine (docs/story/00-bible.md §4 and docs/story/03-endings.md's consequence map): Clue 8 — Mira's file on a
former Project ARCHITECT test operator, found by the player in a place she didn't expect them to look (her own
locked "personal" folder on the shared contract-archive box), not volunteered. The reveal (Level 176) confirms she
is NEXUS's "familiarity" source: her younger sister Dana, recruited into the same test-operator program years ago,
who disappeared from Nexus Company's records — why Mira really left the company, and why she really recruited this
particular player. Level 177 is decision:7 per the consequence map (push Mira to tell NEXUS immediately, or let her
choose the moment) — narrative-only, same mechanism as decisions 1-6. Level 185 (milestone) closes the act and
promotes to ARCHITECT.

**Flagged inconsistency, found while planning this act (not fixed, left for the user to weigh in on):** the
consequence map in docs/story/03-endings.md §2 specifies exact content for decisions 1-6 that does not match what
was actually written into Acts II-VII during earlier sessions (e.g. its decision 2 requires Priya Shah to already
exist in Act III, but she is not introduced until Act IV; its decision 6 describes an unavoidable breach/sacrifice
mechanic Act VII never built). Decision *numbering* and *count* (1-8, matching the secret-ending gate on clues 2/5/8)
were kept consistent regardless, since the numbered tags are what C5 will actually key off of — only the specific
flavor text of decisions 2-4 and 6 diverges from the original design doc. Flagged in docs/3.0-PROGRESS.md for the
user to review; not worth unwinding five already-shipped acts over without their input.
"""
from __future__ import annotations

from ..endless import generate_endless_chain
from ..mission import Mission, Objective

_queue1 = generate_endless_chain("act8_q1", 167, 8, seed=801, length=3, requires_first=["act8_m166"],
                                 template_keys=["recon_sweep", "incident_response", "file_forensics"])
_queue2 = generate_endless_chain("act8_q2", 171, 8, seed=802, length=3, requires_first=["act8_m170"],
                                 template_keys=["windows_audit", "defense_watch", "recon_sweep"])
_queue3 = generate_endless_chain("act8_q3", 178, 8, seed=803, length=3, requires_first=["act8_m177"],
                                 template_keys=["incident_response", "file_forensics", "windows_audit"])
_queue4 = generate_endless_chain("act8_q4", 182, 8, seed=804, length=2, requires_first=["act8_m181"],
                                 template_keys=["defense_watch", "recon_sweep"])

ACT8_CHAPTER1 = [
    Mission(
        id="act8_m166", number=166, act=8, size="story", title="The Queue", scenario="auto8_queue_intro",
        requires=["act7_m165"],
        briefing=["MIRA: Word's gotten around. Check your inbox before you pick up anything new."],
        debrief=["MIRA: It'll keep coming whether you're watching or not. Work it at your own pace.",
                 "NEXUS: Funny, watching contracts arrive without a person attached to each one anymore."],
        objectives=[Objective(event="file_read", match={"path__glob": "*mira_queue.txt"}, text="Read Mira's message about the queue",
                              hints=["Check your inbox.", "Try: cat inbox/mira_queue.txt", "cat inbox/mira_queue.txt"])],
        solution=["cat inbox/mira_queue.txt"], reward_xp=120, tags=["bash", "act8", "story", "f2"],
    ),
    *_queue1,
    Mission(
        id="act8_m170", number=170, act=8, size="standard", title="Two Names on One Box", scenario="auto8_archive_notice",
        requires=[_queue1[-1].id],
        briefing=["NEXUS: This queue job routes through Mira's own archive box, not a client's. Have a look while "
                  "you're in there."],
        debrief=["NEXUS: 'operator' and 'mira.' Two home directories on a box that's supposed to just hold "
                 "contract records."],
        objectives=[Objective(event="command", match={"name": "ls", "status": 0}, text="See who else has a home directory on this box (ls /home)",
                              hints=["Log in, then list /home directly.",
                                    "Try: sshpass -p hunter2 ssh operator@10.70.0.4, then ls /home",
                                    "sshpass -p hunter2 ssh operator@10.70.0.4\nls /home"])],
        solution=["sshpass -p hunter2 ssh operator@10.70.0.4", "ls /home"],
        reward_xp=140, tags=["bash", "act8", "standard"],
    ),
    *_queue2,
    Mission(
        id="act8_m174", number=174, act=8, size="story", title="Locked, Not Hidden", scenario="auto8_archive_locked",
        requires=[_queue2[-1].id],
        briefing=["NEXUS: 'personal', owned by mira, locked to her alone. We have sudo on this box. That doesn't "
                  "mean we should use it."],
        debrief=["NEXUS: Permission denied. For now, that's a real door, not just an inconvenience.",
                 "MIRA — not sent, just true: some locks are there because nobody's gotten around to removing them. "
                 "Some are there on purpose."],
        objectives=[Objective(event="command", match={"name": "ls", "status": 2}, text="Try to look inside mira's home directory (ls -la /home/mira)",
                              hints=["It's locked down tight — try it and see what the shell actually says.",
                                    "Try: ls -la /home/mira", "ls -la /home/mira"])],
        solution=["sshpass -p hunter2 ssh operator@10.70.0.4", "ls -la /home/mira"],
        reward_xp=150, tags=["bash", "act8", "story"],
    ),
    Mission(
        id="act8_m175", number=175, act=8, size="milestone", title="Found, Not Told", scenario="auto8_dana_found",
        requires=["act8_m174"],
        briefing=["MIRA hasn't said not to. She also hasn't said to. That's not the same as permission."],
        debrief=["NEXUS: 'Dana.' There's a name in a file that reads like it was never meant for anyone but Mira "
                 "herself.",
                 "MIRA — not sent, just true: that wasn't yours to read yet. I understand why you did. Give me a "
                 "minute before you say anything."],
        objectives=[Objective(event="file_read", match={"path__glob": "*dana_notes.txt"}, text="Read what's actually in the locked folder",
                              hints=["sudo gets past the permission, same as any other locked file on a box you "
                                    "administer.",
                                    "Try: sudo cat /home/mira/personal/dana_notes.txt",
                                    "sudo ls /home/mira/personal\nsudo cat /home/mira/personal/dana_notes.txt"])],
        solution=["sshpass -p hunter2 ssh operator@10.70.0.4", "sudo ls /home/mira/personal", "sudo cat /home/mira/personal/dana_notes.txt"],
        reward_xp=260, tags=["bash", "act8", "milestone", "story"],
    ),
]

ACT8_CHAPTER2 = [
    Mission(
        id="act8_m176", number=176, act=8, size="story", title="Her Name Was Dana", scenario="auto8_mira_reaction",
        requires=["act8_m175"],
        briefing=["MIRA: I owe you the rest of it, properly, in my own words. Read it when you're ready."],
        debrief=["MIRA: Now you know. All of it, not just a file's worth.",
                 "NEXUS: I don't have anything useful to say yet. I think I need to."],
        objectives=[Objective(event="file_read", match={"path__glob": "*mira_dana.txt"}, text="Hear Mira out, in full",
                              hints=["Check your inbox.", "Try: cat inbox/mira_dana.txt", "cat inbox/mira_dana.txt"])],
        solution=["cat inbox/mira_dana.txt"], reward_xp=230, tags=["bash", "act8", "story"],
    ),
    Mission(
        id="act8_m177", number=177, act=8, size="story", title="When To Tell Him", scenario="auto8_decision7",
        requires=["act8_m176"],
        briefing=["MIRA: NEXUS doesn't know any of this yet. Tell me what you think — now, or when I'm ready to "
                  "say it right."],
        debrief=["MIRA: Noted. Either way, I'm doing it — I just wanted your read on the timing."],
        objectives=[Objective(event="command", match={"name": "echo", "status": 0}, text="Tell Mira what you think",
                              hints=["Read her question first, then answer honestly.",
                                    "Try: cat inbox/mira_asks.txt, then echo your answer.",
                                    "cat inbox/mira_asks.txt\necho 'Tell him now. He deserves to hear it from you, not stumble onto it like I did.'"])],
        solution=["cat inbox/mira_asks.txt", "echo 'Tell him now. He deserves to hear it from you, not stumble onto it like I did.'"],
        reward_xp=160, tags=["bash", "act8", "story", "decision:7"],
    ),
    *_queue3,
    Mission(
        id="act8_m181", number=181, act=8, size="story", title="A Name-Shaped Hole", scenario="auto8_nexus_learns",
        requires=[_queue3[-1].id],
        briefing=["NEXUS: Mira told me. I need a moment before I'm good for anything else today."],
        debrief=["NEXUS: I finish your sentences sometimes. I always told myself that was just good modeling.",
                 "MIRA: And now?",
                 "NEXUS: Now I think it was always going to be more than that, and nobody asked me first either."],
        objectives=[Objective(event="file_read", match={"path__glob": "*notes.txt"}, text="Hear NEXUS out",
                              hints=["Check your own notes file.", "Try: cat notes.txt", "cat notes.txt"])],
        solution=["cat notes.txt"], reward_xp=180, tags=["bash", "act8", "story"],
    ),
    *_queue4,
    Mission(
        id="act8_m184", number=184, act=8, size="story", title="The Three of Us", scenario="auto8_quiet_beat",
        requires=[_queue4[-1].id],
        briefing=["MIRA: Before we close this out — check your inbox. Nothing urgent, for once."],
        debrief=["MIRA: Nexus Company doesn't know we know. Kade Voss doesn't know. Small advantage, but it's ours.",
                 "NEXUS: Whatever's next, I'd rather face it like this than however I was facing things before."],
        objectives=[Objective(event="file_read", match={"path__glob": "*mira_quiet.txt"}, text="Read Mira's message",
                              hints=["Check your inbox.", "Try: cat inbox/mira_quiet.txt", "cat inbox/mira_quiet.txt"])],
        solution=["cat inbox/mira_quiet.txt"], reward_xp=140, tags=["bash", "act8", "story"],
    ),
    Mission(
        id="act8_m185", number=185, act=8, size="milestone", title="What We're Actually For", scenario="auto8_close",
        requires=["act8_m184"],
        briefing=["MIRA: That's the act. One more, and we find out what all of this was actually for."],
        debrief=["MIRA: Filed and locked.",
                 "NEXUS: Nine acts in, and I only just found out why I understand you so well. I'd call that an "
                 "overdue correction, not a closed book.",
                 "MIRA: Last stretch. Let's go find out what Nexus Company actually built, and why."],
        objectives=[
            Objective(event="file_read", match={"path__glob": "*act8_summary.txt"}, text="Assemble the act's findings (grep -r ... | tee)",
                     hints=["Same habit as every chapter close, one more time for the whole act.",
                           "Try: grep -r Act autonotes | tee act8_summary.txt",
                           "grep -r Act autonotes | tee act8_summary.txt\ncat act8_summary.txt"]),
            Objective(event="sudo_used", match={"command": "cp"}, text="Archive it (sudo cp)",
                     hints=["It lives at /archive, at the filesystem root.", "Try: sudo cp act8_summary.txt /archive/act8_summary.txt",
                           "sudo cp act8_summary.txt /archive/act8_summary.txt"]),
        ],
        solution=["grep -r Act autonotes | tee act8_summary.txt", "cat act8_summary.txt", "sudo cp act8_summary.txt /archive/act8_summary.txt"],
        reward_xp=280, tags=["bash", "act8", "milestone"],
    ),
]

ACT8 = [*ACT8_CHAPTER1, *ACT8_CHAPTER2]
