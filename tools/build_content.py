"""Generates the side/secret missions (017+), the extra servers and the matching test scripts.

Run:  python tools/build_content.py
Output: data/servers_extra.json, missions/mission_017.json ..., tests/side_scripts.json
The main story missions (001-016) are hand-written; this script only patches their metadata.
"""
from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from content_data import M, SERVERS  # noqa: E402

DIFF_XP = [500, 1100, 2400, 4800, 9000]
DIFF_CR = [600, 1300, 2800, 5500, 11000]
DIFF_NAME = {1: "EASY", 2: "NORMAL", 3: "HARD", 4: "EXPERT", 5: "NEXUS"}
CIPHER_LEVEL = {1: 1, 2: 1, 3: 2, 4: 3, 5: 3}


def b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def fname_of(m: dict, default: str) -> str:
    found = re.search(r"([a-z0-9_]+\.(?:dat|enc|txt))", m["brief"][0])
    return found.group(1) if found else default


CHOICES = [
    ("What do you do with what you found?", [
        ("nexus", "Report it to NEXUS security through the proper channel.", {"archer": 4}, 3),
        ("ghost", "Sell the intel to GHOST. Information wants to be traded.", {"ghost": 4}, -1),
        ("quiet", "Keep it to yourself. Knowledge is leverage.", {"zero": 3}, 1)]),
    ("How do you close the operation?", [
        ("clean", "Wipe your traces carefully and leave no footprint.", {"mira": 3}, 2),
        ("loud", "Leave a calling card. Let them know someone was here.", {"zero": 3}, -2),
        ("share", "Share the file with every contact you trust.", {"ghost": 2, "vector": 2}, 1)]),
    ("Someone asks who authorised this job...", [
        ("mira", "'MIRA did.' Hand the responsibility to your handler.", {"mira": -2}, 0),
        ("self", "'I did.' Take the credit and the risk.", {"archer": 2}, 2),
        ("zero", "'A friend.' Say nothing more.", {"zero": 4}, 0)]),
]


def build_server(sid: str, spec: dict, fs_jobs: dict) -> dict:
    fw = spec["fw"]
    srv = {
        "id": sid, "name": spec["name"], "ip": spec["ip"], "region": spec["region"], "pos": spec["pos"],
        "description": spec["desc"], "services": ["SSH", "HTTP"],
        "ports": [{"port": 22, "service": "SSH"}, {"port": 443, "service": "HTTPS"}],
        "security": spec["security"],
        "firewall": ({"enabled": True, "symbols": fw["symbols"], "length": fw["length"], "attempts": fw["attempts"],
                      "level": fw["level"], "label": fw["label"]} if fw else {"enabled": False}),
        "links": spec["links"], "motd": spec["motd"],
        "auth": {"mode": "password", "users": [{"name": spec["user"], "password": spec["pw"], "role": "user"}],
                 "welcome": [f"Session opened on {spec['name']}."]},
        "fs": {"public": {"_access": "public", "notice.txt": [f"{spec['name']} // {spec['region']}", "Authorised staff only. Everything is logged."]},
               "jobs": fs_jobs},
    }
    if spec.get("routing"):
        srv["routing"] = {"difficulty": spec["routing"]}
    if spec.get("requires_item"):
        srv["requires_item"] = spec["requires_item"]
    if spec.get("hidden"):
        srv["hidden"] = True
    if spec.get("trace"):
        t = dict(spec["trace"])
        t["min_role"] = "user"
        t["output"] = [f"TRACE COMPLETE on {spec['name']}.", "Origin resolved: see the origin report in the job folder."]
        srv["trace"] = t
    return srv


def build() -> None:
    server_jobs: dict[str, dict] = {sid: {} for sid in SERVERS}
    scripts: dict[str, dict] = {}
    missions_out: list[dict] = []
    for m in M:
        sid, key = m["server"], m["key"]
        sp = SERVERS[sid]
        P = f"/jobs/{key}"
        t, diff = m["type"], m["diff"]
        keyword = m.get("keyword", "")
        enc = b64(keyword) if keyword else ""

        def txt(lines):
            return [ln.replace("{b64}", enc) for ln in lines]

        files: dict = {"brief.txt": txt(["## " + m["title"], *m["brief"]])}
        objectives, cmds = [], []
        tgt = fname_of(m, "target.dat")

        if sp.get("routing"):
            objectives.append({"id": "route", "text": f"Build a relay route to {sp['name']}", "event": "route", "server": sid})
        objectives.append({"id": "connect", "text": f"Connect to {sp['name']}", "event": "connect", "server": sid, "hint": f"connect {sid}"})
        cmds.append(f"connect {sid}")
        if t == "INFILTRATION" and diff <= 2:
            objectives.append({"id": "scan", "text": f"Scan {sp['name']}", "event": "scan", "server": sid})
            cmds.append("scan")
        if sp["fw"]:
            objectives.append({"id": "fw", "text": f"Breach the {sp['fw']['label']} firewall", "event": "firewall", "server": sid, "hint": "firewall"})
            cmds.append("firewall")
        if t == "INTELLIGENCE":
            cid, topic = m["topic"]
            objectives.insert(0, {"id": "topic", "text": f"Ask {cid.upper()} about it ('msg {cid} {topic}')", "event": "topic", "contact": cid, "topic": topic,
                                  "hint": f"msg {cid} {topic}"})
            cmds.insert(0, f"msg {cid} {topic}")
        objectives.append({"id": "login", "text": f"Log in as {sp['user']}", "event": "login", "server": sid, "user": sp["user"],
                           "hint": f"login {sp['user']} {sp['pw']}  (see ~/{sid}_access.txt)"})
        cmds.append(f"login {sp['user']} {sp['pw']}")
        on_start_files = {f"{sid}_access.txt": [f"{sp['name']}", f"user: {sp['user']}", f"pass: {sp['pw']}", f"task: {m['title']}"]}
        hidden_name = f".stash_{key}"
        files[hidden_name] = {"content": m["hidden"], "secret": True}
        hidden_obj = {"id": "stash", "text": "Find the hidden stash file", "event": "read", "server": sid, "path": f"{P}/{hidden_name}", "optional": True,
                      "bonus": {"xp": int(DIFF_XP[diff - 1] * 0.08), "credits": int(DIFF_CR[diff - 1] * 0.08)}, "hint": f"ls -a {P}"}
        cmd_hidden = f"cat {P}/{hidden_name}"
        bonus_items = list(m.get("bonus_items", []))

        def add_read(fid, text, path):
            objectives.append({"id": fid, "text": text, "event": "read", "server": sid, "path": path})
            cmds.append(f"cat {path}")

        def add_dl(fid, text, fname):
            objectives.append({"id": fid, "text": text, "event": "download", "server": sid, "file": fname})
            cmds.append(f"download {P}/{fname}")

        time_limit = m.get("time_limit")
        if t == "INFILTRATION":
            files[tgt] = txt(m["target"])
            add_read("read", f"Read {tgt}", f"{P}/{tgt}")
            add_dl("dl", f"Download {tgt}", tgt)
        elif t == "DECRYPTION":
            ctype, ckey = m["cipher"]
            files[tgt] = {"content": "[ENCRYPTED]", "encrypted": {"type": ctype, "key": ckey, "level": CIPHER_LEVEL[diff], "plain": m["plain"], "hints": m["hints"]}}
            objectives.append({"id": "decrypt", "text": f"Decrypt {tgt}", "event": "decrypt", "server": sid, "path": f"{P}/{tgt}", "hint": f"decrypt {P}/{tgt}"})
            cmds.append(f"decrypt {P}/{tgt}")
            add_read("read", f"Read the decrypted {tgt}", f"{P}/{tgt}")
        elif t == "INVESTIGATION":
            files["log_a.txt"], files["log_b.txt"], files["report.txt"] = txt(m["log_a"]), txt(m["log_b"]), txt(m["report"])
            add_read("log_a", "Read log_a.txt", f"{P}/log_a.txt")
            objectives.append({"id": "decode", "text": "Decode the handler id", "event": "decode", "contains_result": keyword, "hint": f"decode {enc}"})
            cmds.append(f"decode {enc}")
            add_read("log_b", "Read log_b.txt", f"{P}/log_b.txt")
            add_read("report", "Read the incident report", f"{P}/report.txt")
        elif t == "TRACE":
            files["alert.log"], files["origin.txt"] = txt(m["log_a"]), txt(m["report"])
            add_read("alert", "Read alert.log", f"{P}/alert.log")
            objectives.append({"id": "trace", "text": f"Trace the signal on {sp['name']}", "event": "trace", "server": sid, "hint": "trace"})
            cmds.append("trace")
            add_read("origin", "Read the origin report", f"{P}/origin.txt")
        elif t == "FIREWALL":
            on_start_files["payload.sig"] = ["SIGNATURE: PAYLOAD", "AUTHOR: VECTOR", "[SIMULATED] 0x42 0x00 0xFF"]
            objectives.append({"id": "upload", "text": "Upload payload.sig", "event": "upload", "server": sid, "file": "payload.sig", "hint": "upload payload.sig"})
            cmds.append("upload payload.sig")
            objectives.append({"id": "leave", "text": "Disconnect cleanly", "event": "disconnect"})
            cmds.append("disconnect")
        elif t == "RECOVERY":
            files["part_a.dat"] = txt(m["target"])
            files["part_b.dat"] = {"content": ["## PART B", "second half of the record", "checksum matches part A"], "grants_item": bonus_items[0] if bonus_items else None}
            if not bonus_items:
                files["part_b.dat"].pop("grants_item")
            files["manifest.txt"] = ["MANIFEST", "part_a.dat + part_b.dat = complete record"] + txt(m.get("log_a", []))
            add_read("manifest", "Read manifest.txt", f"{P}/manifest.txt")
            add_dl("dl_a", "Download part_a.dat", "part_a.dat")
            add_dl("dl_b", "Download part_b.dat", "part_b.dat")
        elif t in ("DEFENSE", "ESCAPE"):
            files[tgt] = txt(m["target"])
            add_dl("dl", f"Download {tgt}", tgt)
            if t == "DEFENSE":
                objectives.append({"id": "cool", "text": f"Cool the trace alert below {m['cool']}%", "event": "heat_below", "max": m["cool"],
                                   "hint": "disconnect, wait, or use a Heat Sink / Anonymous Credential"})
            else:
                objectives.append({"id": "leave", "text": "Disconnect before NEXUS catches you", "event": "disconnect"})
                cmds.append("disconnect")
        elif t == "INTELLIGENCE":
            files["notes.txt"] = txt(m["log_a"])
            add_read("notes", "Read notes.txt", f"{P}/notes.txt")
            objectives.append({"id": "decode", "text": "Decode the hidden line", "event": "decode", "contains_result": keyword, "hint": f"decode {enc}"})
            cmds.append(f"decode {enc}")
        elif t == "STORY":
            files[tgt if tgt != "target.dat" else "note.txt"] = txt(m["target"])
            files["ward_log.txt"] = txt(m.get("log_a", ["(empty)"]))
            add_read("note", f"Read {tgt if tgt != 'target.dat' else 'note.txt'}", f"{P}/{tgt if tgt != 'target.dat' else 'note.txt'}")
            add_read("log", "Read ward_log.txt", f"{P}/ward_log.txt")
        objectives.append(hidden_obj)
        cmds.append(cmd_hidden)
        cmds_tail = []
        if t in ("DEFENSE",):
            cmds_tail = ["disconnect"]

        # choices ------------------------------------------------------
        choice = None
        if t in ("INVESTIGATION", "STORY", "INTELLIGENCE") or m["n"] % 3 == 0:
            prompt, opts = CHOICES[m["n"] % len(CHOICES)]
            choice = {"key": key, "prompt": prompt, "options": [
                {"id": oid, "text": text, "trust": trust, "reward": {"reputation": rep}, "result": ""} for oid, text, trust, rep in opts]}

        reward_xp = int(DIFF_XP[diff - 1] * m.get("xp_mult", 1.0))
        reward_cr = int(DIFF_CR[diff - 1] * m.get("xp_mult", 1.0))
        quick = 40 * len(objectives) + 90
        bonus_goals = [
            {"id": "clean", "text": "Finish without a single mistake", "cond": "no_losses", "reward": {"xp": int(reward_xp * 0.12), "credits": int(reward_cr * 0.12)}},
            {"id": "quick", "text": f"Finish in under {quick} seconds", "cond": "time_under", "value": quick, "reward": {"xp": int(reward_xp * 0.1), "credits": int(reward_cr * 0.1)}},
        ]
        mission = {
            "id": f"mission_{m['n']:03d}", "number": m["n"], "title": m["title"], "type": t, "difficulty": diff, "chapter": m["ch"], "main": False,
            "required_level": m["lvl"], "min_reputation": m.get("rep", 0 if diff < 3 else 15 if diff == 3 else 30),
            "requires": m["req"], "description": m["desc"], "goal": m["brief"][0].replace("TASK: ", ""),
            "reward": {"xp": reward_xp, "credits": reward_cr, "reputation": 1 + diff, "items": []},
            "hint": f"Credentials are in ~/{sid}_access.txt. Check 'mission' for objectives.",
            "on_start": {"discover": [sid], "files": on_start_files},
            "story_start": m["start"], "story_end": [m["end"]],
            "objectives": objectives, "bonus_goals": bonus_goals,
            "on_complete": {"messages": [{"from": m["contact"], "text": m["msg"]}], "flags": m.get("flags", {})},
        }
        if m.get("requires_items"):
            mission["requires_items"] = m["requires_items"]
            mission["secret"] = any(i in ("ghost_token", "black_key", "nexus_core") for i in m["requires_items"])
        if bonus_items and t != "RECOVERY":
            mission["reward"]["items"] = bonus_items
        if time_limit:
            mission["time_limit"] = time_limit
        if m.get("heat_rate"):
            mission["heat_rate"] = m["heat_rate"]
        if choice:
            mission["choice"] = choice
        missions_out.append(mission)
        server_jobs[sid][key] = files
        scripts[mission["id"]] = {"commands": cmds + cmds_tail, "choice": 1 if choice else 0, "type": t,
                                  "items": list(m.get("requires_items", []))}

    # ---- write servers
    servers = []
    for sid, spec in SERVERS.items():
        servers.append(build_server(sid, spec, server_jobs[sid]))
    (ROOT / "data" / "servers_extra.json").write_text(json.dumps({"servers": servers}, indent=1, ensure_ascii=False), encoding="utf-8")
    for mission in missions_out:
        (ROOT / "missions" / f"{mission['id']}.json").write_text(json.dumps(mission, indent=1, ensure_ascii=False), encoding="utf-8")
    (ROOT / "tests" / "side_scripts.json").write_text(json.dumps(scripts, indent=1), encoding="utf-8")
    print(f"servers: {len(servers)}  side missions: {len(missions_out)}")


MAIN_TYPES = {1: ("INVESTIGATION", 1), 2: ("RECOVERY", 1), 3: ("INFILTRATION", 2), 4: ("INTELLIGENCE", 2), 5: ("TRACE", 2), 6: ("FIREWALL", 3),
              7: ("ESCAPE", 3), 8: ("DECRYPTION", 3), 9: ("INFILTRATION", 3), 10: ("STORY", 4), 11: ("INVESTIGATION", 4), 12: ("TRACE", 4),
              13: ("RECOVERY", 5), 14: ("ESCAPE", 5), 15: ("STORY", 5), 16: ("STORY", 5)}
MAIN_CHAPTER = {1: 1, 2: 1, 3: 2, 4: 2, 5: 2, 6: 3, 7: 3, 8: 3, 9: 3, 10: 4, 11: 4, 12: 4, 13: 5, 14: 5, 15: 6, 16: 6}
MAIN_QUICK = {1: 240, 2: 240, 3: 300, 4: 360, 5: 300, 6: 420, 7: 300, 8: 480, 9: 480, 10: 480, 11: 540, 12: 420, 13: 420, 14: 420, 15: 600, 16: 360}
MAIN_LEVEL = {1: 1, 2: 1, 3: 2, 4: 4, 5: 5, 6: 6, 7: 8, 8: 10, 9: 12, 10: 14, 11: 16, 12: 18, 13: 20, 14: 22, 15: 24, 16: 26}


def patch_main() -> None:
    """Add type / chapter / bonus goals to the hand-written story missions (idempotent)."""
    for n in range(1, 17):
        path = ROOT / "missions" / f"mission_{n:03d}.json"
        mission = json.loads(path.read_text(encoding="utf-8"))
        mtype, _ = MAIN_TYPES[n]
        mission["type"], mission["chapter"], mission["main"] = mtype, MAIN_CHAPTER[n], True
        xp, cr = mission["reward"].get("xp", 0), mission["reward"].get("credits", 0)
        mission["bonus_goals"] = [
            {"id": "clean", "text": "Finish without a single mistake", "cond": "no_losses", "reward": {"xp": int(xp * 0.1), "credits": int(cr * 0.1)}},
            {"id": "quick", "text": f"Finish in under {MAIN_QUICK[n]} seconds", "cond": "time_under", "value": MAIN_QUICK[n],
             "reward": {"xp": int(xp * 0.08), "credits": int(cr * 0.08)}},
        ]
        mission["required_level"] = 1                      # story missions chain via 'requires' only (keeps old saves compatible)
        path.write_text(json.dumps(mission, indent=1, ensure_ascii=False), encoding="utf-8")


def check_progression() -> None:
    """Sanity check: XP economy reaches level 100 and every mission is reachable."""
    def need(level):
        return sum(100 + 40 * l for l in range(1, level))
    items = []
    for n in range(1, 17):
        mission = json.loads((ROOT / "missions" / f"mission_{n:03d}.json").read_text(encoding="utf-8"))
        items.append((MAIN_LEVEL[n], mission["reward"]["xp"], n))
    for m in M:
        items.append((m["lvl"], int(DIFF_XP[m["diff"] - 1] * m.get("xp_mult", 1.0)), m["n"]))
    total = 0
    for lvl, xp, n in sorted(items):
        if need(lvl) > total + 1.0 * 0:
            gap = need(lvl) - total
            if gap > 0 and n > 16:
                print(f"  note: mission {n} needs level {lvl} but missions below it only give {total} XP (gap {gap}); dailies/weeklies/training fill it")
        total += xp
    lvl = 1
    while lvl < 100 and need(lvl + 1) <= total:
        lvl += 1
    print(f"total mission XP {total:,} -> level {lvl} (level 100 needs {need(100):,})")


if __name__ == "__main__":
    build()
    patch_main()
    check_progression()
