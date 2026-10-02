"""Act III — The Network (levels 46-70, docs/story/02-acts-and-levels.md). Network reconnaissance commands (B4) were
deliberately left untouched through Acts I-II for this act: ping, dig/nslookup/host, whois, curl/wget, netstat/ss,
traceroute, ip/ifconfig/arp, and ssh/scp/sshpass as the climax. The target throughout is the Nexus Company edge server
at 203.0.113.9 — the "patient address" that has recurred since Act I Level 20. Chapter 1 (46-53) is written: confirm the
address is real, resolve and look up its domain, check the player's own exposure, Oduya is introduced, and the chapter
closes having mapped the target's public footprint without touching it directly yet. Chapters 2-3 (54-70) are not
written yet.
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

ACT3 = [*ACT3_CHAPTER1]
