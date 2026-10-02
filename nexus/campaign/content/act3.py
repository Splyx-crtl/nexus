"""Act III — The Network (levels 46-70, docs/story/02-acts-and-levels.md). Network reconnaissance commands (B4) were
deliberately left untouched through Acts I-II for this act: ping, dig/nslookup/host, whois, curl/wget, netstat/ss,
traceroute, ip/ifconfig/arp, and ssh/scp/sshpass as the climax. The target throughout is the Nexus Company edge server
at 203.0.113.9 — the "patient address" that has recurred since Act I Level 20. Chapter 1 (46-53) confirms the address is
real, resolves and looks up its domain, checks the player's own exposure, and introduces Oduya. Chapter 2 (54-61) digs
deeper into the same server: alternate DNS tools, a robots.txt-hinted hidden path leading to an exposed deployment
config with live credentials in it (an very ordinary, very real way servers get compromised — found, not cracked, same
principle as every credential in this campaign so far), a caution beat from Oduya, and a mystery subdomain that
resolves but can't be reached yet. Chapter 3 (62-70) is the ssh/scp climax: the deploy credentials found in Chapter 2
finally get used for a real login, the player explores someone else's machine with the same fs commands from Act I,
finds a log line that plants the ARCHITECT/NEXUS twist (paid off in full only in Act VII) without explaining it, and the
act closes with a milestone promoting to CRYPTOSMITH.
"""
from __future__ import annotations

from ..mission import Mission, Objective

ACT3_CHAPTER1 = [
    Mission(
        id="act3_m46", number=46, act=3, size="mini", title="Still There", scenario="network_ping",
        requires=["act2_m45"],
        briefing=["NEXUS: Everything so far has been secondhand — logs, login histories, somebody else's dossier. "
                  "Time to check for ourselves. Is it even still there?"],
        debrief=["NEXUS: Alive, answering, not even trying to hide. Confident, or careless. We'll find out which."],
        objectives=[Objective(event="ping", match={"machine": "cloud-edge"}, text="Ping 203.0.113.9 directly",
                              hints=["ping confirms a machine is actually reachable.", "Try: ping 203.0.113.9", "ping 203.0.113.9"])],
        solution=["ping 203.0.113.9"], reward_xp=50, tags=["bash", "act3", "net", "ping"],
    ),
    Mission(
        id="act3_m47", number=47, act=3, size="mini", title="Putting a Name to It", scenario="network_resolve",
        requires=["act3_m46"],
        briefing=["MIRA: If that address belongs to anyone, it'll have a name attached somewhere. Look it up."],
        debrief=["MIRA: nexus-company.com. Same company, same address, no coincidence left to argue about."],
        objectives=[Objective(event="command", match={"name": "dig", "status": 0}, text="Resolve nexus-company.com (dig)",
                              hints=["dig translates a domain name into an address.", "Try: dig nexus-company.com", "dig nexus-company.com"])],
        solution=["dig nexus-company.com"], reward_xp=45, tags=["bash", "act3", "net", "dig"],
    ),
    Mission(
        id="act3_m48", number=48, act=3, size="mini", title="Paper Trail", scenario="network_whois",
        requires=["act3_m47"],
        briefing=["NEXUS: Before you go further — who actually owns that domain, and since when?"],
        debrief=["NEXUS: 2031. Nineteen years before any of this. Whatever this is, it's not a recent decision."],
        objectives=[Objective(event="command", match={"name": "whois", "status": 0}, text="Check the domain's registration (whois)",
                              hints=["whois shows who registered a domain and when.", "Try: whois nexus-company.com", "whois nexus-company.com"])],
        solution=["whois nexus-company.com"], reward_xp=45, tags=["bash", "act3", "net", "whois"],
    ),
    Mission(
        id="act3_m49", number=49, act=3, size="standard", title="Know Your Own Position", scenario="network_selfcheck",
        requires=["act3_m48"],
        briefing=["MIRA: Before you poke at anyone else's network, know your own. What's your address, and what else "
                  "is on this segment with you?"],
        debrief=["MIRA: Good. Always know what you look like from the outside before you go looking at someone else."],
        objectives=[
            Objective(event="command", match={"name": "ip", "status": 0}, text="Check your own network address (ip addr)",
                     hints=["ip addr shows this machine's own interfaces and addresses.", "Try: ip addr", "ip addr"]),
            Objective(event="command", match={"name": "arp", "args__contains": "-a", "status": 0}, text="See who else is on your local network (arp -a)",
                     hints=["arp -a lists machines you've recently talked to on this network.", "Try: arp -a", "arp -a"]),
        ],
        solution=["ip addr", "arp -a"], reward_xp=65, tags=["bash", "act3", "net", "ip", "arp"],
    ),
    Mission(
        id="act3_m50", number=50, act=3, size="story", title="The Veteran", scenario="network_oduya",
        requires=["act3_m49"],
        briefing=["NEXUS: Mira asked someone else to weigh in before you go further. Read it."],
        debrief=["NEXUS: 'Boring footprint.' I can work with that framing.",
                 "MIRA: Oduya's been doing this longer than both of us combined. Listen when they bother to say something."],
        objectives=[Objective(event="file_read", match={"path__glob": "*oduya_intro.txt"}, text="Read Oduya's message",
                              hints=["Check your inbox.", "Try: cat inbox/oduya_intro.txt", "cat inbox/oduya_intro.txt"])],
        solution=["cat inbox/oduya_intro.txt"], reward_xp=70, tags=["bash", "act3", "story", "oduya"],
    ),
    Mission(
        id="act3_m51", number=51, act=3, size="mini", title="What's Showing", scenario="network_fetch",
        requires=["act3_m50"],
        briefing=["NEXUS: Let's see what it's willing to show a stranger. Pull the front page."],
        debrief=["NEXUS: 'Internal use only' — on a page anyone on the internet can load. That's not internal."],
        objectives=[Objective(event="command", match={"name": "curl", "status": 0}, text="Fetch the server's front page (curl)",
                              hints=["curl downloads whatever a web address serves, straight to the terminal.",
                                    "Try: curl http://nexus-company.com/", "curl http://nexus-company.com/"])],
        solution=["curl http://nexus-company.com/"], reward_xp=50, tags=["bash", "act3", "net", "curl"],
    ),
    Mission(
        id="act3_m52", number=52, act=3, size="standard", title="Left Out in the Open", scenario="network_download",
        requires=["act3_m51"],
        briefing=["MIRA: Try the obvious stuff first. changelog.txt, robots.txt, that kind of thing — people forget "
                  "those are public too."],
        debrief=["MIRA: 'Re-enabled relay for diagnostics — temporary.' On the same day that address started showing "
                 "up in our logs. That's not a coincidence either."],
        objectives=[
            Objective(event="command", match={"name": "wget", "status": 0}, text="Download the changelog (wget)",
                     hints=["wget saves a file instead of just printing it.", "Try: wget http://nexus-company.com/changelog.txt",
                           "wget http://nexus-company.com/changelog.txt"]),
            Objective(event="file_read", match={"path__glob": "*changelog.txt"}, text="Read what you downloaded",
                     hints=["It saved under its own name in the current folder.", "Try: cat changelog.txt", "cat changelog.txt"]),
        ],
        solution=["wget http://nexus-company.com/changelog.txt", "cat changelog.txt"], reward_xp=75, tags=["bash", "act3", "net", "wget"],
    ),
    Mission(
        id="act3_m53", number=53, act=3, size="milestone", title="The Full Shape of It", scenario="network_services",
        requires=["act3_m52"],
        briefing=["NEXUS: Last thing before Oduya's rules kick in for real: what's actually listening, on your box "
                  "and on the path between you and them?"],
        debrief=["NEXUS: Your own ssh is open to anyone who finds you first — worth remembering, not today's problem. "
                 "And the route to that server is short. Too short for something that's supposed to be 'internal.'",
                 "MIRA: Chapter closed. We know it's real, we know who it belongs to, and we know roughly what it's "
                 "running. Next chapter, we stop looking from the outside."],
        objectives=[
            Objective(event="command", match={"name": "netstat", "status": 0}, text="Check what's listening on your own machine (netstat)",
                     hints=["netstat lists network connections and listening ports on this machine.", "Try: netstat -tulpn", "netstat -tulpn"]),
            Objective(event="command", match={"name": "ss", "status": 0}, text="Double-check with the modern tool (ss)",
                     hints=["ss is the modern replacement for netstat.", "Try: ss -tulpn", "ss -tulpn"]),
            Objective(event="command", match={"name": "traceroute", "status": 0}, text="Map the path to the target (traceroute)",
                     hints=["traceroute shows every hop between you and a destination.", "Try: traceroute 203.0.113.9", "traceroute 203.0.113.9"]),
        ],
        solution=["netstat -tulpn", "ss -tulpn", "traceroute 203.0.113.9"],
        reward_xp=190, tags=["bash", "act3", "milestone", "netstat", "ss", "traceroute"],
    ),
]

ACT3_CHAPTER2 = [
    Mission(
        id="act3_m54", number=54, act=3, size="standard", title="Two More Ways to Ask", scenario="network_altdns",
        requires=["act3_m53"],
        briefing=["MIRA: Don't trust one tool's answer when there are three that ask the same question differently. "
                  "Confirm it with nslookup and host too."],
        debrief=["MIRA: Same answer, three times. Good. Now you actually trust it instead of just believing it."],
        objectives=[
            Objective(event="command", match={"name": "nslookup", "status": 0}, text="Resolve nexus-company.com (nslookup)",
                     hints=["nslookup is an older, simpler DNS lookup tool.", "Try: nslookup nexus-company.com", "nslookup nexus-company.com"]),
            Objective(event="command", match={"name": "host", "status": 0}, text="Resolve it again (host)",
                     hints=["host gives the same answer in the simplest format of all three.", "Try: host nexus-company.com", "host nexus-company.com"]),
        ],
        solution=["nslookup nexus-company.com", "host nexus-company.com"], reward_xp=55, tags=["bash", "act3", "net", "dns"],
    ),
    Mission(
        id="act3_m55", number=55, act=3, size="mini", title="The Older Way", scenario="network_ifconfig",
        requires=["act3_m54"],
        briefing=["NEXUS: Some systems still only have the old tool installed. Check your own interfaces the "
                  "old-fashioned way."],
        debrief=["NEXUS: Same information ip addr gave you, different formatting. Know both — you won't always get "
                 "to choose."],
        objectives=[Objective(event="command", match={"name": "ifconfig", "status": 0}, text="Check your interfaces the old way (ifconfig)",
                              hints=["ifconfig predates ip and shows the same kind of information.", "Try: ifconfig", "ifconfig"])],
        solution=["ifconfig"], reward_xp=35, tags=["bash", "act3", "net", "ifconfig"],
    ),
    Mission(
        id="act3_m56", number=56, act=3, size="mini", title="Check the Robots", scenario="network_robots",
        requires=["act3_m55"],
        briefing=["NEXUS: Every site has a file telling search engines what not to crawl. It's a polite request, not "
                  "a lock — and it's usually the first place worth looking."],
        debrief=["NEXUS: 'Disallow: /ops-console/.' They just told us exactly where to look."],
        objectives=[Objective(event="command", match={"name": "curl", "args__contains": "http://nexus-company.com/robots.txt", "status": 0},
                              text="Check robots.txt", hints=["It's just another path on the same server.",
                                                              "Try: curl http://nexus-company.com/robots.txt", "curl http://nexus-company.com/robots.txt"])],
        solution=["curl http://nexus-company.com/robots.txt"], reward_xp=45, tags=["bash", "act3", "net", "curl"],
    ),
    Mission(
        id="act3_m57", number=57, act=3, size="standard", title="Through the Unlocked Door", scenario="network_backdoor_config",
        requires=["act3_m56"],
        briefing=["MIRA: You know where to look now. See what's actually there, and if something's downloadable, "
                  "download it and read it properly."],
        debrief=["MIRA: Live deploy credentials. Sitting in a config file. On a path they tried to hide with a "
                 "request-only text file.",
                 "NEXUS: This isn't a technique. This is just someone forgetting to lock a door."],
        objectives=[
            Objective(event="command", match={"name": "curl", "args__contains": "http://nexus-company.com/ops-console/", "status": 0},
                     text="See what's in the ops-console path", hints=["Same move as robots.txt, different path.",
                                                                       "Try: curl http://nexus-company.com/ops-console/", "curl http://nexus-company.com/ops-console/"]),
            Objective(event="command", match={"name": "wget", "status": 0}, text="Download backup.cfg",
                     hints=["wget saves it locally instead of just printing it.", "Try: wget http://nexus-company.com/ops-console/backup.cfg",
                           "wget http://nexus-company.com/ops-console/backup.cfg"]),
            Objective(event="file_read", match={"path__glob": "*backup.cfg"}, text="Read what you downloaded",
                     hints=["It saved under its own name.", "Try: cat backup.cfg", "cat backup.cfg"]),
        ],
        solution=["curl http://nexus-company.com/ops-console/", "wget http://nexus-company.com/ops-console/backup.cfg", "cat backup.cfg"],
        reward_xp=90, tags=["bash", "act3", "net", "curl", "wget"],
    ),
    Mission(
        id="act3_m58", number=58, act=3, size="story", title="Found, Not Earned", scenario="network_caution",
        requires=["act3_m57"],
        briefing=["NEXUS: Oduya again. This one's worth reading slowly."],
        debrief=["NEXUS: Whatever you told them, I noticed you actually thought about it this time instead of just "
                 "typing the first thing that came to mind.",
                 "MIRA: That's the job. Good instincts, kept in check. Keep both."],
        objectives=[
            Objective(event="file_read", match={"path__glob": "*oduya_caution.txt"}, text="Read Oduya's message",
                     hints=["Check your inbox.", "Try: cat inbox/oduya_caution.txt", "cat inbox/oduya_caution.txt"]),
            Objective(event="command", match={"name": "echo", "status": 0}, text="Answer honestly",
                     hints=["Same move as before — write it, append it to the file.",
                           'echo "your answer here" >> inbox/oduya_caution.txt', 'echo "I\'ll be careful." >> inbox/oduya_caution.txt']),
        ],
        solution=["cat inbox/oduya_caution.txt", 'echo "I\'ll be careful." >> inbox/oduya_caution.txt'],
        reward_xp=85, tags=["bash", "act3", "story", "oduya", "decision:2"],
    ),
    Mission(
        id="act3_m59", number=59, act=3, size="mini", title="A Name That Doesn't Answer", scenario="network_subdomain",
        requires=["act3_m58"],
        briefing=["NEXUS: That config mentioned a console at a subdomain. Look it up — both the address and who's "
                  "behind it."],
        debrief=["NEXUS: It resolves. We're nowhere near it, though — that address isn't on any path we can reach "
                 "from here. Knowing a name's address isn't the same as being able to get to it.",
                 "MIRA: File it. We'll come back to that one."],
        objectives=[
            Objective(event="command", match={"name": "dig", "args__contains": "ops.nexus-company.com", "status": 0}, text="Resolve ops.nexus-company.com",
                     hints=["Same tool, different name this time.", "Try: dig ops.nexus-company.com", "dig ops.nexus-company.com"]),
            Objective(event="command", match={"name": "whois", "args__contains": "ops.nexus-company.com", "status": 0}, text="Check who registered it",
                     hints=["whois works on subdomains too.", "Try: whois ops.nexus-company.com", "whois ops.nexus-company.com"]),
        ],
        solution=["dig ops.nexus-company.com", "whois ops.nexus-company.com"], reward_xp=55, tags=["bash", "act3", "net", "dig", "whois"],
    ),
    Mission(
        id="act3_m60", number=60, act=3, size="mini", title="What It Volunteers", scenario="network_banner",
        requires=["act3_m59"],
        briefing=["MIRA: Before we're done with this server for now — what does it say about itself without being "
                  "asked? Headers only, nothing else."],
        debrief=["MIRA: nginx, version and all. Filed for later — that matters once we're looking for weaknesses "
                 "instead of just doors."],
        objectives=[Objective(event="command", match={"name": "curl", "args__contains": "-I", "status": 0}, text="Grab the server's headers (curl -I)",
                              hints=["-I fetches only the headers, not the page itself.", "Try: curl -I http://nexus-company.com/", "curl -I http://nexus-company.com/"])],
        solution=["curl -I http://nexus-company.com/"], reward_xp=40, tags=["bash", "act3", "net", "curl"],
    ),
    Mission(
        id="act3_m61", number=61, act=3, size="milestone", title="Everything This Chapter Found", scenario="network_dossier2",
        requires=["act3_m60"],
        briefing=["MIRA: Pull every credential-looking string out of what you've found this chapter into one file, "
                  "and archive a copy before we go any further."],
        debrief=["MIRA: Filed and locked. Chapter closed.",
                 "NEXUS: Next time we touch that server, it won't be from the outside looking in."],
        objectives=[
            Objective(event="file_read", match={"path__glob": "*creds_summary.txt"}, text="Assemble and review the findings (grep -r ... | tee)",
                     hints=["Same trick as Act II's case file — search, and save a copy while you're looking.",
                           "Try: grep -r DEPLOY recon | tee creds_summary.txt", "grep -r DEPLOY recon | tee creds_summary.txt\ncat creds_summary.txt"]),
            Objective(event="sudo_used", match={"command": "cp"}, text="Archive a copy somewhere only root can reach (sudo cp)",
                     hints=["Same archive folder as before — root-only, and it lives at /archive, not inside your home folder.",
                           "Try: sudo cp creds_summary.txt /archive/creds_summary.txt", "sudo cp creds_summary.txt /archive/creds_summary.txt"]),
        ],
        solution=["grep -r DEPLOY recon | tee creds_summary.txt", "cat creds_summary.txt", "sudo cp creds_summary.txt /archive/creds_summary.txt"],
        reward_xp=195, tags=["bash", "act3", "milestone", "grep", "tee", "sudo"],
    ),
]

ACT3_CHAPTER3 = [
    Mission(
        id="act3_m62", number=62, act=3, size="mini", title="First Login", scenario="network_login",
        requires=["act3_m61"],
        briefing=["MIRA: You have a working password now. Use it. sshpass hands it to ssh without a prompt — that's "
                  "how you script a login instead of typing it by hand every time."],
        debrief=["MIRA: You're in. Don't get comfortable — Oduya's rules apply from here on, for real."],
        objectives=[Objective(event="ssh_login", match={"user": "deploy"}, text="Log into the edge server as deploy",
                              hints=["sshpass -p PASSWORD ssh user@host logs in without an interactive prompt.",
                                    "Try: sshpass -p n3xus-deploy! ssh deploy@nexus-company.com", "sshpass -p n3xus-deploy! ssh deploy@nexus-company.com"])],
        solution=["sshpass -p n3xus-deploy! ssh deploy@nexus-company.com"], reward_xp=90, tags=["bash", "act3", "net", "ssh"],
    ),
    Mission(
        id="act3_m63", number=63, act=3, size="standard", title="New Ground", scenario="network_remote_explore",
        requires=["act3_m62"],
        briefing=["NEXUS: Same commands, different machine. Find out what's actually on here before anything else."],
        debrief=["NEXUS: A relay service, managed by a deploy pipeline, apparently. Nothing unusual yet."],
        objectives=[
            Objective(event="command", match={"name": "find", "status": 0}, text="Find what's under /srv (find /srv -type f)",
                     hints=["find works on a remote machine exactly like it does locally, once you're logged in.",
                           "Try: find /srv -type f", "find /srv -type f"]),
            Objective(event="file_read", match={"path__glob": "*README.txt"}, text="Read the relay's README",
                     hints=["It's inside /srv/relay.", "Try: cat /srv/relay/README.txt", "cat /srv/relay/README.txt"]),
        ],
        solution=["sshpass -p n3xus-deploy! ssh deploy@nexus-company.com", "find /srv -type f", "cat /srv/relay/README.txt"],
        reward_xp=95, tags=["bash", "act3", "net", "find"],
    ),
    Mission(
        id="act3_m64", number=64, act=3, size="mini", title="Not That Privileged", scenario="network_remote_sudo",
        requires=["act3_m63"],
        briefing=["MIRA: Before you assume you can do anything you want on there — check. What does deploy actually "
                  "have rights to?"],
        debrief=["MIRA: Nothing. A service account, exactly as privileged as it needs to be and not one bit more. "
                 "That's how it's supposed to work, for once."],
        objectives=[Objective(event="command", match={"name": "sudo", "args__contains": "-l", "status": 1}, text="Check what deploy can run as root (sudo -l)",
                              hints=["sudo -l lists what you're allowed to run — if anything.", "Try: sudo -l", "sudo -l"])],
        solution=["sshpass -p n3xus-deploy! ssh deploy@nexus-company.com", "sudo -l"], reward_xp=55, tags=["bash", "act3", "net", "sudo"],
    ),
    Mission(
        id="act3_m65", number=65, act=3, size="story", title="A Word NEXUS Doesn't Like", scenario="network_architect_hint",
        requires=["act3_m64"],
        briefing=["NEXUS: Check the relay's own log. Logs tell you what a thing actually does, not what its README "
                  "claims."],
        debrief=["NEXUS: 'ARCHITECT-NEXUS sync.' ...I don't have a clever line for that one. Give me a moment.",
                 "MIRA: NEXUS? You went quiet.", "NEXUS: I'm fine. Keep going. We'll come back to this."],
        objectives=[Objective(event="file_read", match={"path__glob": "*relay.log"}, text="Read the relay's own log",
                              hints=["Same folder as the README.", "Try: cat /srv/relay/relay.log", "cat /srv/relay/relay.log"])],
        solution=["sshpass -p n3xus-deploy! ssh deploy@nexus-company.com", "cat /srv/relay/relay.log"],
        reward_xp=100, tags=["bash", "act3", "story", "architect"],
    ),
    Mission(
        id="act3_m66", number=66, act=3, size="mini", title="Taking a Copy", scenario="network_loot",
        requires=["act3_m65"],
        briefing=["MIRA: Get a copy of that log off their machine and onto yours. I want it somewhere they can't "
                  "quietly edit it later."],
        debrief=["MIRA: Filed. If that line disappears from their server tomorrow, we'll still have it."],
        objectives=[
            Objective(event="scp", match={"direction": "down"}, text="Copy relay.log to your own machine (scp)",
                     hints=["scp works like cp, but one side can be a remote host.",
                           "Try: sshpass -p n3xus-deploy! scp deploy@nexus-company.com:/srv/relay/relay.log relay.log",
                           "sshpass -p n3xus-deploy! scp deploy@nexus-company.com:/srv/relay/relay.log relay.log"]),
            Objective(event="file_read", match={"path__glob": "*relay.log"}, text="Confirm it copied correctly",
                     hints=["Read it back locally.", "Try: cat relay.log", "cat relay.log"]),
        ],
        solution=["sshpass -p n3xus-deploy! scp deploy@nexus-company.com:/srv/relay/relay.log relay.log", "cat relay.log"],
        reward_xp=85, tags=["bash", "act3", "net", "scp"],
    ),
    Mission(
        id="act3_m67", number=67, act=3, size="standard", title="Who Else Is On This One", scenario="network_remote_ps",
        requires=["act3_m66"],
        briefing=["NEXUS: Same habit as always, just pointed somewhere else this time: what's running, and who's "
                  "logged in?"],
        debrief=["NEXUS: 'telemetry-shim, --passthrough,' running as root. Could be nothing. Could be exactly why "
                 "that address has been so patient. Not your box to clean up — yet. Just remember it."],
        objectives=[
            Objective(event="command", match={"name": "ps", "status": 0}, text="Check what's running on the relay box (ps aux)",
                     hints=["Same command, someone else's machine.", "Try: ps aux", "ps aux"]),
            Objective(event="command", match={"name": "who", "status": 0}, text="Check who else is logged in (who)",
                     hints=["who shows every active session on this machine.", "Try: who", "who"]),
        ],
        solution=["sshpass -p n3xus-deploy! ssh deploy@nexus-company.com", "ps aux", "who"],
        reward_xp=95, tags=["bash", "act3", "net", "ps", "who"],
    ),
    Mission(
        id="act3_m68", number=68, act=3, size="mini", title="Coming Back", scenario="network_exit",
        requires=["act3_m67"],
        briefing=["MIRA: Log in, confirm you can get back out cleanly, then prove it."],
        debrief=["MIRA: Good. Always know you can get back before you go anywhere worth going."],
        objectives=[
            Objective(event="command", match={"name": "exit", "status": 0}, text="Log out of the edge server (exit)",
                     hints=["exit returns you to whichever machine you connected from.", "Try: exit", "exit"]),
            Objective(event="file_read", match={"path__glob": "*welcome_back.txt"}, text="Confirm you're back on home-rig",
                     hints=["This file only exists locally.", "Try: cat welcome_back.txt", "cat welcome_back.txt"]),
        ],
        solution=["sshpass -p n3xus-deploy! ssh deploy@nexus-company.com", "exit", "cat welcome_back.txt"],
        reward_xp=50, tags=["bash", "act3", "net", "ssh"],
    ),
    Mission(
        id="act3_m69", number=69, act=3, size="story", title="I Don't Love Any of Those Words", scenario="network_debrief",
        requires=["act3_m68"],
        briefing=["NEXUS: Mira wants to talk about what you found. Read it."],
        debrief=["NEXUS: For what it's worth — neither do I.",
                 "MIRA: We're not done with that server. We're just done with it from the outside."],
        objectives=[Objective(event="file_read", match={"path__glob": "*mira_architect.txt"}, text="Read Mira's reaction",
                              hints=["Check your inbox.", "Try: cat inbox/mira_architect.txt", "cat inbox/mira_architect.txt"])],
        solution=["cat inbox/mira_architect.txt"], reward_xp=70, tags=["bash", "act3", "story"],
    ),
    Mission(
        id="act3_m70", number=70, act=3, size="milestone", title="Inside, Properly", scenario="network_handoff",
        requires=["act3_m69"],
        briefing=["MIRA: Last pass. Log in, pull the relay log one more time for a clean copy, archive it properly, "
                  "and log back out. By the book, start to finish."],
        debrief=["MIRA: Clean work. In, out, documented, nothing left behind.",
                 "NEXUS: Rank up — CRYPTOSMITH. Act closed. Next time, we stop reading their infrastructure from the "
                 "outside and start taking apart what they're actually protecting.",
                 "MIRA: That means keys, hashes, the things people think are unbreakable because they've never had "
                 "anyone patient enough try."],
        objectives=[
            Objective(event="scp", match={"direction": "down"}, text="Pull a clean copy of relay.log (scp)",
                     hints=["Same move as before.", "Try: sshpass -p n3xus-deploy! scp deploy@nexus-company.com:/srv/relay/relay.log relay.log",
                           "sshpass -p n3xus-deploy! scp deploy@nexus-company.com:/srv/relay/relay.log relay.log"]),
            Objective(event="sudo_used", match={"command": "cp"}, text="Archive it somewhere only root can reach (sudo cp)",
                     hints=["Same archive habit as Act II — it lives at /archive, not inside your home folder.", "Try: sudo cp relay.log /archive/relay.log", "sudo cp relay.log /archive/relay.log"]),
        ],
        solution=["sshpass -p n3xus-deploy! scp deploy@nexus-company.com:/srv/relay/relay.log relay.log", "sudo cp relay.log /archive/relay.log"],
        reward_xp=220, tags=["bash", "act3", "milestone", "scp", "sudo"],
    ),
]

ACT3 = [*ACT3_CHAPTER1, *ACT3_CHAPTER2, *ACT3_CHAPTER3]
