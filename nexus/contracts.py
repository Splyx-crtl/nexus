"""Endless procedural contracts: a fresh job on one of the side-grid servers whenever you want one."""
from __future__ import annotations

import base64
import random
from typing import TYPE_CHECKING

from .simulation import _build_node

if TYPE_CHECKING:
    from .game_engine import GameEngine

CONTRACT_NUMBER = 900
TIER_XP = [350, 800, 1700, 3200, 5600]
TIER_CREDITS = [450, 1000, 2100, 4000, 7000]
TYPES = ["INFILTRATION", "RECOVERY", "DECRYPTION", "TRACE", "ESCAPE"]
SUBJECTS = ["client roster", "night shipment log", "maintenance schedule", "audit trail", "badge access list",
            "sensor calibration", "payment queue", "firmware changelog", "visitor records", "backup index"]
FACTS = ["entry 14 was edited after hours", "three records share one signature", "a checksum does not match", "the file was opened from an unlisted terminal",
         "someone renamed the owner field to '0'", "the last backup is 14 minutes older than the log says", "a hidden note is tagged NEXUS-LEGAL",
         "two timestamps are exactly 0.8 seconds apart", "the same name appears in every failed login"]
KEYWORDS = ["LANTERN", "HARBOR", "COPPER", "SILENT", "ORBIT", "FERRO", "MIRAGE", "TUNDRA", "VELVET", "QUARTZ"]
CLIENTS = ["a shipping broker", "an anonymous fixer", "a retired operator", "a nervous archivist", "a rival crew", "a utility contractor"]


def tier_for_level(level: int) -> int:
    return 1 if level < 10 else 2 if level < 25 else 3 if level < 45 else 4 if level < 70 else 5


class ContractManager:
    def __init__(self, engine: "GameEngine"):
        self.e = engine
        self.refresh()

    # ----------------------------------------------------------- state --
    def available(self) -> bool:
        return self.e.missions.is_complete("mission_003")

    def spec(self) -> dict | None:
        return self.e.db.get_world("contract")

    def mission_id(self) -> str | None:
        spec = self.spec()
        return f"contract_{spec['n']:05d}" if spec else None

    def status(self) -> str:
        mid = self.mission_id()
        return self.e.missions.status(mid) if mid else "none"

    SECURITY_BY_TIER = {1: ("MEDIUM",), 2: ("MEDIUM", "HIGH"), 3: ("HIGH", "MEDIUM"), 4: ("HIGH", "CRITICAL"), 5: ("CRITICAL", "HIGH")}

    def _candidates(self, kind: str, tier: int = 3) -> list[str]:
        out = []
        allowed = self.SECURITY_BY_TIER[tier]
        for sid, raw in self.e.data.servers.items():
            if raw.get("hidden") or "jobs" not in raw.get("fs", {}) or not raw.get("auth", {}).get("users"):
                continue
            if kind == "TRACE" and not raw.get("trace"):
                continue
            if raw.get("security") in allowed:
                out.append(sid)
        return sorted(out) or sorted(sid for sid, raw in self.e.data.servers.items()
                                     if not raw.get("hidden") and "jobs" in raw.get("fs", {}) and raw.get("auth", {}).get("users")
                                     and (kind != "TRACE" or raw.get("trace")))

    # -------------------------------------------------------- generation --
    def generate(self, rng: random.Random | None = None) -> tuple[bool, str]:
        e = self.e
        if not self.available():
            return False, "Contracts unlock after mission 003."
        if self.status() == "active":
            return False, "Finish or abort your active contract first."
        rng = rng or random.Random()
        tier = tier_for_level(e.player.level)
        kind = rng.choice(TYPES)
        sid = rng.choice(self._candidates(kind, tier))
        n = int(e.db.get_stat("contracts_generated")) + 1
        words = rng.sample(FACTS, 2)
        keyword = rng.choice(KEYWORDS)
        cipher = ("caesar", rng.randint(3, 20)) if tier <= 2 else ("atbash", None) if tier == 3 else ("vigenere", keyword)
        spec = {"n": n, "server": sid, "type": kind, "tier": tier, "subject": rng.choice(SUBJECTS), "facts": words, "keyword": keyword,
                "cipher": list(cipher), "client": rng.choice(CLIENTS), "seed": rng.randrange(1 << 30)}
        e.db.set_world("contract", spec)
        e.bump("contracts_generated")
        self.refresh()
        return True, f"CONTRACT #{n} accepted: {kind} on {e.data.servers[sid]['name']}  (tier {tier})"

    def refresh(self) -> None:
        """Re-create the dynamic mission + its files from the stored spec (also after loading a save)."""
        e = self.e
        e.missions.unregister_prefix("contract_")
        spec = self.spec()
        if not spec or spec["server"] not in e.world.servers:
            return
        mission, files = self._build(spec)
        e.missions.register_dynamic(mission)
        srv = e.world.servers[spec["server"]]
        jobs = srv.root.children.get("jobs")
        if jobs is not None:
            jobs.children["contract"] = _build_node("contract", "/jobs/contract", files, "user")

    # ------------------------------------------------------------- build --
    def _build(self, spec: dict) -> tuple[dict, dict]:
        e = self.e
        raw = e.data.servers[spec["server"]]
        user = raw["auth"]["users"][0]
        sid, kind, tier = spec["server"], spec["type"], spec["tier"]
        rng = random.Random(spec["seed"])
        P = "/jobs/contract"
        name = raw["name"]
        enc = base64.b64encode(spec["keyword"].encode()).decode()
        body = [f"## {spec['subject'].upper()}", f"client: {spec['client']}", f"observation: {spec['facts'][0]}", f"observation: {spec['facts'][1]}"]
        files: dict = {"brief.txt": [f"## CONTRACT #{spec['n']}", f"type: {kind}   tier: {tier}", f"client: {spec['client']}",
                                     f"subject: {spec['subject']}"]}
        objectives: list[dict] = []
        if raw.get("routing"):
            objectives.append({"id": "route", "text": f"Build a relay route to {name}", "event": "route", "server": sid})
        objectives.append({"id": "connect", "text": f"Connect to {name}", "event": "connect", "server": sid})
        if raw.get("firewall", {}).get("enabled"):
            objectives.append({"id": "fw", "text": f"Breach the {raw['firewall']['label']} firewall", "event": "firewall", "server": sid})
        objectives.append({"id": "login", "text": f"Log in as {user['name']}", "event": "login", "server": sid, "user": user["name"],
                           "hint": f"login {user['name']} {user['password']}  (see ~/{sid}_access.txt)"})
        time_limit, heat_rate = None, None

        def read(i, text, path):
            objectives.append({"id": i, "text": text, "event": "read", "server": sid, "path": path})

        def dl(i, text, f):
            objectives.append({"id": i, "text": text, "event": "download", "server": sid, "file": f})

        if kind == "INFILTRATION":
            files["target.dat"] = body
            read("read", "Read target.dat", f"{P}/target.dat")
            dl("dl", "Download target.dat", "target.dat")
        elif kind == "RECOVERY":
            files["part_a.dat"] = body
            files["part_b.dat"] = ["## PART B", "second half of the record", f"checksum: {enc}"]
            files["manifest.txt"] = ["MANIFEST", "part_a.dat + part_b.dat"]
            read("manifest", "Read manifest.txt", f"{P}/manifest.txt")
            dl("dl_a", "Download part_a.dat", "part_a.dat")
            dl("dl_b", "Download part_b.dat", "part_b.dat")
        elif kind == "DECRYPTION":
            ctype, ckey = spec["cipher"]
            files["vault.enc"] = {"content": "[ENCRYPTED]", "encrypted": {"type": ctype, "key": ckey, "level": min(3, tier), "plain": body,
                                                                         "hints": [f"Cipher: {ctype}.", "Try the obvious keys first."]}}
            objectives.append({"id": "decrypt", "text": "Decrypt vault.enc", "event": "decrypt", "server": sid, "path": f"{P}/vault.enc"})
            read("read", "Read the decrypted vault.enc", f"{P}/vault.enc")
        elif kind == "TRACE":
            files["alert.log"] = ["09:01 repeating packet detected", "09:02 source masked", f"09:03 note: {spec['facts'][0]}"]
            read("alert", "Read alert.log", f"{P}/alert.log")
            objectives.append({"id": "trace", "text": f"Trace the signal on {name}", "event": "trace", "server": sid})
        else:   # ESCAPE
            files["keys.dat"] = body
            dl("dl", "Download keys.dat", "keys.dat")
            objectives.append({"id": "leave", "text": "Disconnect before NEXUS catches you", "event": "disconnect"})
            time_limit, heat_rate = 240 + 20 * (5 - tier), 0.3 + 0.12 * tier
        files[".stash"] = {"content": [f"A scrap of the client's note: '{spec['facts'][1]}'"], "secret": True}
        objectives.append({"id": "stash", "text": "Find the hidden stash file", "event": "read", "server": sid, "path": f"{P}/.stash", "optional": True,
                           "bonus": {"xp": TIER_XP[tier - 1] // 12, "credits": TIER_CREDITS[tier - 1] // 12}})
        scale = 1 + e.player.level / 60
        xp, cr = int(TIER_XP[tier - 1] * scale), int(TIER_CREDITS[tier - 1] * scale)
        quick = 40 * len(objectives) + 90
        mission = {
            "id": f"contract_{spec['n']:05d}", "number": CONTRACT_NUMBER, "title": f"CONTRACT #{spec['n']}: {spec['subject'].upper()}", "type": kind,
            "difficulty": tier, "chapter": 0, "main": False, "contract": True, "required_level": 1, "min_reputation": 0, "requires": ["mission_003"],
            "description": f"A procedurally generated job for {spec['client']}. Endless work for operators who want more.",
            "goal": f"{kind.title()} job on {name}.", "reward": {"xp": xp, "credits": cr, "reputation": 1, "items": []},
            "hint": f"Credentials are in ~/{sid}_access.txt.", "on_start": {"discover": [sid], "files": {
                f"{sid}_access.txt": [name, f"user: {user['name']}", f"pass: {user['password']}", f"task: contract #{spec['n']}"]}},
            "story_start": [f"Your fixer pings you: \"{spec['client'].capitalize()} wants {spec['subject']} from {name}. Quiet job. Good pay.\""],
            "story_end": ["Job done. The client pays without asking questions — that's how you know it was a good one."],
            "objectives": objectives,
            "bonus_goals": [{"id": "clean", "text": "Finish without a single mistake", "cond": "no_losses", "reward": {"xp": xp // 8, "credits": cr // 8}},
                            {"id": "quick", "text": f"Finish in under {quick} seconds", "cond": "time_under", "value": quick, "reward": {"xp": xp // 10, "credits": cr // 10}}],
            "on_complete": {},
        }
        if time_limit:
            mission["time_limit"], mission["heat_rate"] = time_limit, heat_rate
        return mission, files

    # --------------------------------------------------- test / helpers --
    def script(self) -> list[str]:
        """Command list that completes the current contract (used by tests)."""
        spec = self.spec()
        raw = self.e.data.servers[spec["server"]]
        user = raw["auth"]["users"][0]
        P, sid, kind = "/jobs/contract", spec["server"], spec["type"]
        cmds = [f"connect {sid}"]
        if raw.get("firewall", {}).get("enabled"):
            cmds.append("firewall")
        cmds.append(f"login {user['name']} {user['password']}")
        if kind == "INFILTRATION":
            cmds += [f"cat {P}/target.dat", f"download {P}/target.dat"]
        elif kind == "RECOVERY":
            cmds += [f"cat {P}/manifest.txt", f"download {P}/part_a.dat", f"download {P}/part_b.dat"]
        elif kind == "DECRYPTION":
            cmds += [f"decrypt {P}/vault.enc", f"cat {P}/vault.enc"]
        elif kind == "TRACE":
            cmds += [f"cat {P}/alert.log", "trace"]
        else:
            cmds += [f"download {P}/keys.dat", "disconnect"]
        cmds.append(f"cat {P}/.stash")
        return cmds
