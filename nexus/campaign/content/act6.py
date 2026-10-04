"""Act VI — Rights & Automation (levels 121-145, docs/story/02-acts-and-levels.md). B8 (PowerShell .ps1 and cmd batch
scripting) now exists, so this act can use it; bash scripting itself needed no new engine work (B2), it had simply
never been the point of a mission yet — every script so far was typed inline, one line at a time. The "specialisation
choice" the acts table calls for is implemented as a narrative decision only (tags decision:5), the same mechanism as
the game's other major decisions — the full F2 specialisation/economy system is a much larger, still-undefined feature
and this act does not block on it (see docs/3.0-PROGRESS.md's note on this deliberate scope choice). Chapter 1
(121-129) is written: real bash script files replace the grep/tee/sudo-cp ritual the player has retyped by hand at
the end of every chapter since Act II. Chapters 2-3 (130-145, PowerShell and cmd.exe scripting, the specialisation
decision, and the act finale) are not written yet.
"""
from __future__ import annotations

from ..mission import Mission, Objective

ACT6_CHAPTER1 = [
    Mission(
        id="act6_m121", number=121, act=6, size="mini", title="Stop Doing This By Hand", scenario="auto_first_script",
        requires=["act4_m95"],
        briefing=["MIRA: You've retyped the same three commands every morning for weeks. Write them into a script, "
                  "once, and stop."],
        debrief=["MIRA: One command instead of three, every morning from now on. That's the whole idea."],
        objectives=[Objective(event="command", match={"name": "bash", "args__contains": "morning_check.sh", "status": 0}, text="Write and run a script (bash morning_check.sh)",
                              hints=["Build the file with echo first, then run it with bash.",
                                    "Try: echo \"whoami\" > morning_check.sh (then uptime, then date, each with >>), then: bash morning_check.sh",
                                    "echo \"whoami\" > morning_check.sh\necho \"uptime\" >> morning_check.sh\necho \"date\" >> morning_check.sh\nbash morning_check.sh"])],
        solution=["echo \"whoami\" > morning_check.sh", "echo \"uptime\" >> morning_check.sh", "echo \"date\" >> morning_check.sh", "bash morning_check.sh"],
        reward_xp=95, tags=["bash", "act6", "scripting"],
    ),
    Mission(
        id="act6_m122", number=122, act=6, size="standard", title="One Script, Many Files", scenario="auto_loop_script",
        requires=["act6_m121"],
        briefing=["NEXUS: Three files, three separate sha256sum calls, every time. Put the loop in the script "
                  "instead of your fingers."],
        debrief=["NEXUS: Same loop, any number of files. That's the entire point of automation — the effort doesn't "
                 "grow with the list."],
        objectives=[Objective(event="command", match={"name": "bash", "args__contains": "hash_all.sh", "status": 0}, text="Write and run a script that loops over every file (bash hash_all.sh)",
                              hints=["bash's for loop works inside a script exactly like it does on one line.",
                                    "Try: echo 'for f in file1.txt file2.txt file3.txt; do sha256sum \"reports/$f\"; done' > hash_all.sh, then: bash hash_all.sh",
                                    "echo 'for f in file1.txt file2.txt file3.txt; do sha256sum \"reports/$f\"; done' > hash_all.sh\nbash hash_all.sh"])],
        solution=["echo 'for f in file1.txt file2.txt file3.txt; do sha256sum \"reports/$f\"; done' > hash_all.sh", "bash hash_all.sh"],
        reward_xp=110, tags=["bash", "act6", "scripting", "for"],
    ),
    Mission(
        id="act6_m123", number=123, act=6, size="mini", title="Check Before You Act", scenario="auto_if_script",
        requires=["act6_m122"],
        briefing=["MIRA: Before anything automated runs twice by accident and breaks something, put a safety check "
                  "at the top."],
        debrief=["MIRA: A thirty-second check now saves you from explaining a mess later."],
        objectives=[Objective(event="command", match={"name": "bash", "args__contains": "safety_check.sh", "status": 0}, text="Write and run a script with a safety check (bash safety_check.sh)",
                              hints=["bash's if/else works inside a script exactly like it does on one line.",
                                    "Try: echo 'if [ -f lockfile ]; then echo \"already running, abort\"; else echo \"clear to proceed\"; fi' > safety_check.sh, then: bash safety_check.sh",
                                    "echo 'if [ -f lockfile ]; then echo \"already running, abort\"; else echo \"clear to proceed\"; fi' > safety_check.sh\nbash safety_check.sh"])],
        solution=["echo 'if [ -f lockfile ]; then echo \"already running, abort\"; else echo \"clear to proceed\"; fi' > safety_check.sh", "bash safety_check.sh"],
        reward_xp=70, tags=["bash", "act6", "scripting", "if"],
    ),
    Mission(
        id="act6_m124", number=124, act=6, size="story", title="The Same Ritual, Every Time", scenario="auto_reflection",
        requires=["act6_m123"],
        briefing=["NEXUS: Something's been bothering me. Check your own history."],
        debrief=["NEXUS: grep, tee, sudo cp. Over and over, chapter after chapter, since Act II. You've been doing "
                 "the same three steps by hand this entire time.",
                 "MIRA: He's not wrong. Fix that before this act is out."],
        objectives=[Objective(event="command", match={"name": "history", "status": 0}, text="Check your own command history",
                              hints=["There's a builtin for exactly this.", "Try: history", "history"])],
        solution=["history"], reward_xp=85, tags=["bash", "act6", "story"],
    ),
    Mission(
        id="act6_m125", number=125, act=6, size="standard", title="Write It Once", scenario="auto_function_script",
        requires=["act6_m124"],
        briefing=["MIRA: If you're going to log things consistently, write the logging once as its own piece, not "
                  "copy-pasted every time you need it."],
        debrief=["MIRA: Now every future script can just call log_event instead of re-writing the same echo line."],
        objectives=[Objective(event="command", match={"name": "bash", "args__contains": "utils.sh", "status": 0}, text="Write and run a script that defines and calls a function (bash utils.sh)",
                              hints=["A bash function is name() { ...; }, callable like any other command afterward.",
                                    "Try: echo 'log_event() { echo \"[LOG] $1\"; }' > utils.sh (then two more lines calling it with >>), then: bash utils.sh",
                                    "echo 'log_event() { echo \"[LOG] $1\"; }' > utils.sh\necho 'log_event \"deployment started\"' >> utils.sh\necho 'log_event \"deployment finished\"' >> utils.sh\nbash utils.sh"])],
        solution=["echo 'log_event() { echo \"[LOG] $1\"; }' > utils.sh", "echo 'log_event \"deployment started\"' >> utils.sh",
                 "echo 'log_event \"deployment finished\"' >> utils.sh", "bash utils.sh"],
        reward_xp=120, tags=["bash", "act6", "scripting", "function"],
    ),
    Mission(
        id="act6_m126", number=126, act=6, size="mini", title="Make It Executable", scenario="auto_executable",
        requires=["act6_m125"],
        briefing=["NEXUS: You don't have to type 'bash' in front of a script every time. Make it executable, and "
                  "run it like any other program."],
        debrief=["NEXUS: chmod +x, then ./ instead of bash. One less word to type, every single time from now on."],
        objectives=[
            Objective(event="command", match={"name": "chmod", "args__contains": "+x", "status": 0}, text="Make the script executable (chmod +x)",
                     hints=["chmod +x sets the execute bit.", "Try: chmod +x direct.sh", "chmod +x direct.sh"]),
            Objective(event="command", match={"name": "echo", "args__contains": "direct run works", "status": 0}, text="Run it directly (./direct.sh)",
                     hints=["With the execute bit set, run it by path, no 'bash' needed.", "Try: ./direct.sh", "./direct.sh"]),
        ],
        solution=["echo 'echo \"direct run works\"' > direct.sh", "chmod +x direct.sh", "./direct.sh"],
        reward_xp=75, tags=["bash", "act6", "scripting", "chmod"],
    ),
    Mission(
        id="act6_m127", number=127, act=6, size="standard", title="One Script, Any Chapter", scenario="auto_generic_script",
        requires=["act6_m126"],
        briefing=["MIRA: Stop retyping the same three commands at the end of every job. Write one script that takes "
                  "the pattern, the folder and the output name as arguments."],
        debrief=["MIRA: Now it's not 'the thing I do at the end of a chapter,' it's a tool with a name. Use it next "
                 "time instead of thinking about it."],
        objectives=[
            Objective(event="file_read", match={"path__glob": "*findings.txt"}, text="Build and run the generic script, then check its output",
                     hints=["$1, $2 and $3 inside the script become whatever you pass it, in order.",
                           "Try: echo 'grep -r \"$1\" \"$2\" | tee \"$3\"' > archive_chapter.sh (then the sudo cp line with >>), "
                           "chmod +x it, run it, then read findings.txt back",
                           "echo 'grep -r \"$1\" \"$2\" | tee \"$3\"' > archive_chapter.sh\necho 'sudo cp \"$3\" /archive/\"$3\"' >> archive_chapter.sh\n"
                           "chmod +x archive_chapter.sh\n./archive_chapter.sh anomaly reports findings.txt\ncat findings.txt"]),
            Objective(event="sudo_used", match={"command": "cp"}, text="Confirm it archived the result (sudo cp, inside the script)",
                     hints=["The script's second line does this for you.", "It runs automatically once the script does.", "./archive_chapter.sh anomaly reports findings.txt"]),
        ],
        solution=["echo 'grep -r \"$1\" \"$2\" | tee \"$3\"' > archive_chapter.sh", "echo 'sudo cp \"$3\" /archive/\"$3\"' >> archive_chapter.sh",
                 "chmod +x archive_chapter.sh", "./archive_chapter.sh anomaly reports findings.txt", "cat findings.txt"],
        reward_xp=160, tags=["bash", "act6", "scripting", "milestone-skill"],
    ),
    Mission(
        id="act6_m128", number=128, act=6, size="mini", title="Same Tool, Different Question", scenario="auto_reuse_script",
        requires=["act6_m127"],
        briefing=["MIRA: Same script. Different question. If you have to edit it to reuse it, it wasn't really a "
                  "tool."],
        debrief=["MIRA: No edits. Just different arguments. That's a real tool, not a one-off."],
        objectives=[
            Objective(event="file_read", match={"path__glob": "*all_status.txt"}, text="Run the same script with different arguments, then check its output",
                     hints=["It's already built and executable from last time.", "Try: ./archive_chapter.sh STATUS reports all_status.txt, then read the result back",
                           "./archive_chapter.sh STATUS reports all_status.txt\ncat all_status.txt"]),
            Objective(event="sudo_used", match={"command": "cp"}, text="Confirm it archived this result too",
                     hints=["Same script, same second line.", "./archive_chapter.sh STATUS reports all_status.txt", "./archive_chapter.sh STATUS reports all_status.txt"]),
        ],
        solution=["./archive_chapter.sh STATUS reports all_status.txt", "cat all_status.txt"], reward_xp=65, tags=["bash", "act6", "scripting"],
    ),
    Mission(
        id="act6_m129", number=129, act=6, size="milestone", title="Use The Tool", scenario="auto_chapter_close",
        requires=["act6_m128"],
        briefing=["MIRA: Use the script. Don't type it by hand one more time."],
        debrief=["MIRA: Filed, archived, and it took one line instead of three. Chapter closed.",
                 "NEXUS: Rank up — SENTINEL. Every chapter from here on, you have the option of doing it the old "
                 "way or the way you just built. I know which one I'd pick."],
        objectives=[
            Objective(event="file_read", match={"path__glob": "*chapter1_summary.txt"}, text="Close the chapter with your own tool, then check its output",
                     hints=["Same script as Levels 127-128, new arguments again.", "Try: ./archive_chapter.sh scripts autonotes chapter1_summary.txt, then read the result back",
                           "./archive_chapter.sh scripts autonotes chapter1_summary.txt\ncat chapter1_summary.txt"]),
            Objective(event="sudo_used", match={"command": "cp"}, text="Confirm it archived properly",
                     hints=["The script's own second line handles this.", "./archive_chapter.sh scripts autonotes chapter1_summary.txt",
                           "./archive_chapter.sh scripts autonotes chapter1_summary.txt"]),
        ],
        solution=["./archive_chapter.sh scripts autonotes chapter1_summary.txt", "cat chapter1_summary.txt"],
        reward_xp=210, tags=["bash", "act6", "milestone", "scripting"],
    ),
]

ACT6_CHAPTER2 = [
    Mission(
        id="act6_m130", number=130, act=6, size="mini", title="Build It In PowerShell", scenario="auto_ps_build",
        requires=["act6_m129"],
        briefing=["MIRA: Same idea as the bash scripts, PowerShell's own way of writing them. Set-Content writes, "
                  "Add-Content appends."],
        debrief=["MIRA: One script, both checks, one call from now on."],
        objectives=[Objective(event="command", match={"name": "whoami", "status": 0}, text="Write and run a status script (.\\status.ps1)",
                              hints=["Set-Content first, then Add-Content for each extra line, then run it.",
                                    "Try: Set-Content -Path status.ps1 -Value 'Get-Date' (then Add-Content for whoami), then: .\\status.ps1",
                                    "Set-Content -Path status.ps1 -Value 'Get-Date'\nAdd-Content -Path status.ps1 -Value 'whoami'\n.\\status.ps1"])],
        solution=["sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5", "Set-Content -Path status.ps1 -Value 'Get-Date'",
                 "Add-Content -Path status.ps1 -Value 'whoami'", ".\\status.ps1"],
        reward_xp=90, tags=["bash", "act6", "ps", "scripting"],
    ),
    Mission(
        id="act6_m131", number=131, act=6, size="standard", title="Filter, In a File This Time", scenario="auto_ps_filter_script",
        requires=["act6_m130"],
        briefing=["NEXUS: That stopped-services filter from before — save it. You're going to want it again."],
        debrief=["NEXUS: Now it's stopped_services.ps1, not something you have to remember how to spell correctly "
                 "under pressure."],
        objectives=[Objective(event="command", match={"name": "Where-Object", "status": 0}, text="Write and run the filter as a script",
                              hints=["The whole pipeline goes in as one line of script content.",
                                    "Try: Set-Content -Path stopped_services.ps1 -Value 'Get-Service | Where-Object Status -eq Stopped', then: .\\stopped_services.ps1",
                                    "Set-Content -Path stopped_services.ps1 -Value 'Get-Service | Where-Object Status -eq Stopped'\n.\\stopped_services.ps1"])],
        solution=["sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5", "Set-Content -Path stopped_services.ps1 -Value 'Get-Service | Where-Object Status -eq Stopped'",
                 ".\\stopped_services.ps1"],
        reward_xp=115, tags=["bash", "act6", "ps", "scripting"],
    ),
    Mission(
        id="act6_m132", number=132, act=6, size="mini", title="If, In a Script", scenario="auto_ps_if_script",
        requires=["act6_m131"],
        briefing=["MIRA: Track whether Voss's monitoring order is still in effect, and have the script say so "
                  "either way."],
        debrief=["MIRA: Flip one value at the top of the script later, and the whole report changes with it."],
        objectives=[Objective(event="command", match={"name": "Write-Output", "args__contains": "Voss monitoring: active", "status": 0}, text="Write and run an if/else script",
                              hints=["Set a variable, then branch on it with if/else — same shape as the bash version from Level 123.",
                                    "Try: Set-Content -Path watch_status.ps1 -Value '$monitoring = 1' (then Add-Content for the if/else), then: .\\watch_status.ps1",
                                    "Set-Content -Path watch_status.ps1 -Value '$monitoring = 1'\nAdd-Content -Path watch_status.ps1 -Value 'if ($monitoring -eq 1) { Write-Output \"Voss monitoring: active\" } else { Write-Output \"monitoring lifted\" }'\n.\\watch_status.ps1"])],
        solution=["sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5", "Set-Content -Path watch_status.ps1 -Value '$monitoring = 1'",
                 "Add-Content -Path watch_status.ps1 -Value 'if ($monitoring -eq 1) { Write-Output \"Voss monitoring: active\" } else { Write-Output \"monitoring lifted\" }'",
                 ".\\watch_status.ps1"],
        reward_xp=100, tags=["bash", "act6", "ps", "scripting", "if"],
    ),
    Mission(
        id="act6_m133", number=133, act=6, size="story", title="Not Just Faster", scenario="auto_opsec",
        requires=["act6_m132"],
        briefing=["NEXUS: Mira wants a word about something other than saving time."],
        debrief=["NEXUS: Every chapter's worth of typing, logged somewhere Voss can read it, start to finish. A "
                 "script that runs in two seconds barely gives him anything.",
                 "MIRA: Automation isn't just convenience from here on. It's cover."],
        objectives=[Objective(event="file_read", match={"path__glob": "*mira_opsec.txt"}, text="Read Mira's message",
                              hints=["Check your inbox.", "Try: cat inbox/mira_opsec.txt", "cat inbox/mira_opsec.txt"])],
        solution=["cat inbox/mira_opsec.txt"], reward_xp=95, tags=["bash", "act6", "story"],
    ),
    Mission(
        id="act6_m134", number=134, act=6, size="standard", title="The Other Machine", scenario="auto_batch_for",
        requires=["act6_m133"],
        briefing=["MIRA: Same idea, the old machine's own language. It never got PowerShell, but batch files work "
                  "fine."],
        debrief=["MIRA: Three files, one command, same as everything else you've automated this chapter."],
        objectives=[Objective(event="command", match={"name": "echo", "args__contains": "d1.log", "status": 0}, text="Write and run a batch for-loop (check_logs.bat)",
                              hints=["Batch for-loops only work inside a saved .bat file, not typed live at the prompt — build the file first.",
                                    "Try: echo for %%f in (d1.log d2.log d3.log) do echo checking %%f > check_logs.bat, then: check_logs.bat",
                                    "echo for %%f in (d1.log d2.log d3.log) do echo checking %%f > check_logs.bat\ncheck_logs.bat"])],
        solution=["sshpass -p Legacy-Svc-99 ssh svcacct@10.20.30.9", "echo for %%f in (d1.log d2.log d3.log) do echo checking %%f > check_logs.bat", "check_logs.bat"],
        reward_xp=120, tags=["bash", "act6", "cmd", "scripting", "for"],
    ),
    Mission(
        id="act6_m135", number=135, act=6, size="mini", title="Did It Land", scenario="auto_batch_exist",
        requires=["act6_m134"],
        briefing=["MIRA: Check whether last night's export actually landed before anything downstream assumes it "
                  "did."],
        debrief=["MIRA: One check before trusting the rest of the pipeline. Cheap insurance."],
        objectives=[Objective(event="command", match={"name": "echo", "args__contains": "confirmed", "status": 0}, text="Write and run an exist-check batch file",
                              hints=["cmd's if exist genuinely checks the filesystem, same as the bash version.",
                                    "Try: echo if exist export_2050_01_09.csv (> verify_export.bat (then two more lines with >>), then: verify_export.bat",
                                    "echo if exist export_2050_01_09.csv (> verify_export.bat\necho echo export confirmed>> verify_export.bat\necho )>> verify_export.bat\nverify_export.bat"])],
        solution=["sshpass -p Legacy-Svc-99 ssh svcacct@10.20.30.9", "echo if exist export_2050_01_09.csv (> verify_export.bat",
                 "echo echo export confirmed>> verify_export.bat", "echo )>> verify_export.bat", "verify_export.bat"],
        reward_xp=85, tags=["bash", "act6", "cmd", "scripting", "if"],
    ),
    Mission(
        id="act6_m136", number=136, act=6, size="standard", title="One Command, Not Four", scenario="auto_ps_recheck",
        requires=["act6_m135"],
        briefing=["MIRA: Check on svc_update again. Same question as Act V — is it still there, still enabled."],
        debrief=["MIRA: Still there. Still unexplained. At least now checking takes one command instead of "
                 "remembering the exact cmdlet chain every time."],
        objectives=[Objective(event="command", match={"name": "Where-Object", "status": 0}, text="Write and run the svc_update re-check script",
                              hints=["Same filter idea as Level 131, a different question.",
                                    "Try: Set-Content -Path check_svc_update.ps1 -Value 'Get-LocalUser | Where-Object Name -eq svc_update', then: .\\check_svc_update.ps1",
                                    "Set-Content -Path check_svc_update.ps1 -Value 'Get-LocalUser | Where-Object Name -eq svc_update'\n.\\check_svc_update.ps1"])],
        solution=["sshpass -p Meridian-2050! ssh opsadmin@10.20.30.5", "Set-Content -Path check_svc_update.ps1 -Value 'Get-LocalUser | Where-Object Name -eq svc_update'",
                 ".\\check_svc_update.ps1"],
        reward_xp=130, tags=["bash", "act6", "ps", "scripting"],
    ),
    Mission(
        id="act6_m137", number=137, act=6, size="milestone", title="Both Platforms, Automated", scenario="auto_chapter2_close",
        requires=["act6_m136"],
        briefing=["MIRA: One more file, one more archive, chapter closed."],
        debrief=["MIRA: Filed and locked. Chapter closed.",
                 "NEXUS: Linux, Windows, old machine and new — all of it automated now, not just the easy half."],
        objectives=[
            Objective(event="file_read", match={"path__glob": "*ch2_summary.txt"}, text="Assemble the chapter's findings (grep -r ... | tee)",
                     hints=["Same habit as every chapter close so far.", "Try: grep -r automation autonotes | tee ch2_summary.txt",
                           "grep -r automation autonotes | tee ch2_summary.txt\ncat ch2_summary.txt"]),
            Objective(event="sudo_used", match={"command": "cp"}, text="Archive it (sudo cp)",
                     hints=["It lives at /archive, at the filesystem root.", "Try: sudo cp ch2_summary.txt /archive/ch2_summary.txt",
                           "sudo cp ch2_summary.txt /archive/ch2_summary.txt"]),
        ],
        solution=["grep -r automation autonotes | tee ch2_summary.txt", "cat ch2_summary.txt", "sudo cp ch2_summary.txt /archive/ch2_summary.txt"],
        reward_xp=215, tags=["bash", "act6", "milestone"],
    ),
]

ACT6 = [*ACT6_CHAPTER1, *ACT6_CHAPTER2]
