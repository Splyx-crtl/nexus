"""Game-layer terminal commands: missions, inventory, comms, upgrades, training.

Mixed into CommandProcessor (see commands.py).
"""
from __future__ import annotations

import random
import time
from typing import Iterator

from .minigames import AccessPuzzle, EncryptionPuzzle, FirewallPuzzle, RoutingPuzzle, TraceConfig
from .outputs import Fx, Minigame, Out, Progress, Type, dim, err, info, kv, ok, out, warn
from .save_system import SaveSystem

TRAIN_PHRASES = [
    "THE GRID NEVER SLEEPS", "SIGNAL LOST IN THE STATIC", "TRUST NO ONE IN THE NETWORK",
    "EVERY DOOR HAS A KEY", "GHOSTS LIVE IN THE WIRES", "NEXUS IS WATCHING",
]


DIFF_NAMES = {1: "EASY", 2: "NORMAL", 3: "HARD", 4: "EXPERT", 5: "NEXUS"}


def stars(n: int) -> str:
    return "★" * n + "☆" * (5 - n)


class GameCommandsMixin:
    e: "object"

    # --------------------------------------------------------- missions ---
    def cmd_mission(self, args):
        e, ms = self.e, self.e.missions
        sub = args[0].lower() if args else "status"
        if sub in ("list", "ls", "all"):
            yield Out("== MISSION LOG ==", "title")
            chapters = {c["id"]: c["title"] for c in e.data.chapters}
            flt = args[1].upper() if len(args) > 1 else ""
            by_ch: dict[int, list] = {}
            for m in ms.defs:
                if not m.get("contract"):
                    by_ch.setdefault(m.get("chapter", 0), []).append(m)
            for ch, items in sorted(by_ch.items()):
                lines = []
                for m in items:
                    status = ms.status(m["id"])
                    prereq_missing = any(not ms.is_complete(r) for r in m.get("requires", []))
                    if m.get("secret") and status == "locked" and not all(e.player.has(i) for i in m.get("requires_items", [])):
                        continue                                           # secret series stay invisible
                    diff = DIFF_NAMES[m["difficulty"]]
                    if flt and flt not in (status.upper(), m.get("type", ""), diff):
                        continue
                    if status == "locked" and prereq_missing and not e.flag("show_locked"):
                        lines.append(Out(spans=[(f"  {m['number']:03d}  ", "dim"), ("[LOCKED]", "dim")]))
                        continue
                    style = {"completed": "ok", "active": "warn", "available": "info", "failed": "err"}.get(status, "dim")
                    tail = ms.lock_reason(m) if status == "locked" else status.upper() + (f" ({ms.result(m['id'])})" if status == "completed" else "")
                    lines.append(Out(spans=[(f"  {m['number']:03d}  ", "dim"), (f"{m['title']:<22}", "normal"), (f"{diff:<7}", "warn"),
                                            (f"{m.get('type', 'STORY'):<14}", "dim"), (f"L{m.get('required_level', 1):<3}", "dim"), (tail, style)]))
                if lines:
                    yield Out(f"CHAPTER {ch} — {chapters.get(ch, '')}", "info")
                    for line in lines:
                        yield line
            yield dim("Start with: mission start <number>   Filter: missions available|completed|hard|trace ...")
        elif sub in ("start", "accept"):
            if len(args) < 2 or not args[1].isdigit():
                return (yield err("usage: mission start <number>"))
            m = ms.by_number(int(args[1]))
            if not m:
                return (yield err("UNKNOWN MISSION"))
            success, msg = ms.start(m["id"])
            if not success:
                return (yield err(msg))
            yield from self._print_briefing(m)
        elif sub == "abort":
            if ms.abort():
                yield warn("MISSION ABORTED. Progress for this attempt was discarded.")
            else:
                yield dim("No active mission.")
        elif sub == "info":
            n = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
            m = ms.by_number(n) if n else ms.active()
            if not m:
                return (yield err("usage: mission info <number>"))
            if ms.status(m["id"]) == "locked":
                return (yield err("MISSION LOCKED. Complete previous operations first."))
            yield from self._print_mission_header(m)
        else:
            m = ms.active()
            if not m:
                avail = ms.available()
                yield dim("No active mission.")
                for a in avail:
                    yield info(f"AVAILABLE: {a['number']:03d} \"{a['title']}\" — mission start {a['number']}")
                return
            yield Out(f"== MISSION {m['number']:03d}: {m['title']} ==", "title")
            yield from self._print_objectives(m)
            tl = ms.time_left()
            if tl is not None:
                yield warn(f"TIME REMAINING: {int(tl) // 60:02d}:{int(tl) % 60:02d}")
            if ms.progress().get("awaiting_choice"):
                yield warn("DECISION PENDING — see 'choose'.")
                for i, opt in enumerate(ms.choice_options(m), 1):
                    yield info(f"  [{i}] {e.fmt(opt['text'])}")

    def _print_mission_header(self, m: dict) -> Iterator:
        e = self.e
        reward = m.get("reward", {})
        yield Out(f"MISSION {m['number']:03d} — \"{m['title']}\"", "title")
        yield kv("DIFFICULTY:", f"{DIFF_NAMES[m['difficulty']]}  {stars(m['difficulty'])}", 12, "warn")
        yield kv("TYPE:", f"{m.get('type', 'STORY')}  ·  chapter {m.get('chapter', '?')}  ·  recommended level {m.get('required_level', 1)}", 12, "normal")
        yield kv("REWARD:", f"{reward.get('xp', 0)} XP  ${reward.get('credits', 0):,}", 12, "ok")
        yield kv("OBJECTIVE:", e.fmt(m.get("goal", "")), 12, "normal")
        yield out()
        yield Out(e.fmt(m["description"]), "normal")

    def _print_briefing(self, m: dict) -> Iterator:
        e = self.e
        yield out()
        yield from self._print_mission_header(m)
        yield out()
        for line in m.get("story_start", []):
            yield Type(e.fmt(line), "story")
        yield out()
        yield from self._print_objectives(m)
        if m.get("time_limit"):
            yield warn(f"TIME LIMIT: {m['time_limit'] // 60} min — the clock is running.")
        yield dim("Type 'hint' if you get stuck.")

    def _print_objectives(self, m: dict) -> Iterator:
        yield Out("OBJECTIVES:", "dim")
        for o in self.e.missions.objectives_view(m["id"]):
            mark = "[x]" if o["done"] else ("[>]" if o["current"] else "[ ]")
            style = "ok" if o["done"] else ("warn" if o["current"] else "dim")
            suffix = "  (bonus)" if o["optional"] else ""
            yield Out(f"  {mark} {o['text']}{suffix}", style)

    def cmd_choose(self, args):
        if not args or not args[0].isdigit():
            ms = self.e.missions
            m = ms.active()
            if m and ms.progress().get("awaiting_choice"):
                yield warn("DECISION PENDING:")
                for i, opt in enumerate(ms.choice_options(m), 1):
                    yield info(f"  [{i}] {self.e.fmt(opt['text'])}")
            yield dim("usage: choose <number>")
            return
        success, msg = self.e.missions.choose(int(args[0]))
        if not success:
            yield err(msg)

    def cmd_hint(self, args):
        self.e.bump("hints_used")
        return [info("HINT: " + self.e.missions.hint())]

    # -------------------------------------------------------- inventory ---
    def cmd_inventory(self, args):
        e = self.e
        inv = e.player.inventory()
        yield Out("== INVENTORY ==", "title")
        if not inv:
            yield dim("  (empty)")
        for item_id, qty in inv.items():
            item = e.data.items[item_id]
            yield Out(spans=[(f"  {item['name']:<24}", "ok"), (f"x{qty:<3}", "info"), (item["short"], "dim")])
        yield out()
        files = e.local.files()
        yield kv("LOCAL FILES:", f"{e.local.download_count()} / {e.player.storage_capacity} downloads", 14, "info")
        for path in files:
            yield dim(f"  ~/{path}")

    def cmd_use(self, args):
        if not args:
            return (yield err("usage: use <item>"))
        query = " ".join(args).lower().replace(" ", "_")
        item_id = next((i for i, d in self.e.data.items.items() if query in (i, d["name"].lower().replace(" ", "_"))), None)
        if item_id is None:
            return (yield err(f"unknown item: {query}"))
        yield from self._use_item(item_id, args[1:])

    def _use_item(self, item_id: str, args) -> Iterator:
        e, w, p = self.e, self.e.world, self.e.player
        item = e.data.items[item_id]
        if not p.has(item_id):
            return (yield err(f"You don't have {item['name']}."))
        effect = item.get("effect", "passive")
        used = False
        if effect == "bypass_firewall":
            if w.server is None or not w.server.firewall.get("enabled") or w.is_breached(w.server.id):
                return (yield err("No active firewall to bypass here."))
            yield Out("> INJECTING BYPASS CHIP...", "info")
            yield Progress("BYPASSING", 1200)
            w.set_breached(w.server.id)
            e.event("firewall", server=w.server.id)
            e.server_changed.emit()
            yield ok("FIREWALL BYPASSED. Chip burned out.")
            used = True
        elif effect == "grant_access":
            srv = w.server
            if srv is None or srv.auth.get("mode", "none") == "none" or w.role() >= 1:
                return (yield err("Nothing to unlock here."))
            if srv.firewall.get("enabled") and not w.is_breached(srv.id):
                return (yield err("FIREWALL ACTIVE. Breach it first."))
            if srv.security == "CRITICAL" or srv.requires_item:
                return (yield err("TOKEN REJECTED: security level too high for token access."))
            yield Progress("PRESENTING TOKEN", 900)
            w.set_role(srv.id, 1)
            w.mark_compromised(srv.id)
            e.bump("logins")
            e.event("login", server=srv.id, user="token", role="user")
            e.server_changed.emit()
            yield ok("TOKEN ACCEPTED. User-level access granted.")
            used = True
        elif effect == "cloak":
            left = getattr(self, "_cloak_ready", 0) - time.time()
            if left > 0:
                return (yield err(f"CREDENTIAL RECHARGING ({int(left)}s)."))
            e.reduce_heat(40)
            e.cloak_until = time.time() + 90
            self._cloak_ready = time.time() + 180
            yield ok("ANONYMOUS CREDENTIAL ACTIVE: trace alert -40, detection dampened for 90s.")
        elif effect == "cool":
            e.reduce_heat(50)
            yield ok("HEAT SINK DEPLOYED: trace alert -50.")
            used = True
        elif effect == "assemble":
            need = item.get("assemble_qty", 4)
            if p.qty(item_id) < need:
                return (yield warn(f"Need {need} fragments to reconstruct the key (you have {p.qty(item_id)})."))
            yield Out("> ASSEMBLING DATA FRAGMENTS...", "info")
            yield Progress("RECONSTRUCTING", 1800)
            p.remove_item(item_id, need)
            e.grant_item(item["assemble_into"], 1)
            e.set_flag("quantum_key_built", True)
            yield ok("FRAGMENTS FUSED. A QUANTUM KEY materialises in your inventory.")
            e.inventory_changed.emit()
        else:
            yield info(f"{item['name']}: {item['description']}")
            yield dim("(passive item — it works automatically when relevant)")
        if used:
            p.remove_item(item_id, 1)
            e.bump("items_used")
            e.inventory_changed.emit()
        e.event("use", item=item_id)

    # --------------------------------------------------------- transfers ---
    def cmd_download(self, args):
        e, w = self.e, self.e.world
        if (problem := self._need_conn()):
            return (yield problem)
        if not args:
            return (yield err("usage: download <file>"))
        srv = w.server
        path = w.resolve(args[0])
        node = w.node_at(srv, path)
        if node is None or node.is_dir:
            return (yield err(f"download: {args[0]}: No such file"))
        if not w.can_access(node):
            return (yield err("PERMISSION DENIED"))
        if e.local.download_count() >= e.player.storage_capacity and ("downloads/" + node.name) not in e.local.files():
            return (yield err("LOCAL STORAGE FULL. Remove files with 'rm' or buy the STORAGE upgrade."))
        yield Out(f"> DOWNLOADING {node.name} ({len(node.content)} bytes)...", "info")
        yield Progress("DOWNLOADING", 1400)
        locked = node.encrypted and not w.is_decrypted(srv.id, node.path)
        content = node.content if not node.encrypted else (
            EncryptionPuzzle(self._plain(node.encrypted), node.encrypted["type"], node.encrypted.get("key")).ciphertext
            if locked else self._plain(node.encrypted))
        e.db.put_local_file("downloads/" + node.name, e.fmt(content), source=f"{srv.id}:{path}")
        e.bump("downloads")
        e.add_heat(2 if srv.security in ("HIGH", "CRITICAL") else 0.5, "download")
        yield ok(f"SAVED -> ~/downloads/{node.name}")
        if node.grants_item and w.mark_once(f"grant:{srv.id}:{path}"):
            e.grant_item(node.grants_item, 1)
        e.inventory_changed.emit()
        e.event("download", server=srv.id, path=path, file=node.name)

    def cmd_upload(self, args):
        e, w = self.e, self.e.world
        if (problem := self._need_conn()):
            return (yield problem)
        if w.role() < 1:
            return (yield err("PERMISSION DENIED — login required for uploads."))
        if not args:
            return (yield err("usage: upload <local file>"))
        name = args[0]
        resolved = e.local.resolve(w.local_cwd, name)
        candidates = [resolved, "downloads/" + name, name]
        path = next((c for c in candidates if e.local.read(c) is not None), None)
        if path is None:
            return (yield err(f"upload: {name}: no such local file (check 'ls' on the local node)"))
        yield Out(f"> UPLOADING {path.rsplit('/', 1)[-1]} TO {w.server.name}...", "info")
        yield Progress("UPLOADING", 1500)
        e.bump("uploads")
        e.add_heat(3, "upload")
        yield ok("UPLOAD COMPLETE.")
        e.event("upload", server=w.server.id, file=path.rsplit("/", 1)[-1])

    # --------------------------------------------------------------- map ---
    def cmd_map(self, args):
        e, w = self.e, self.e.world
        known = w.discovered()
        regular = sum(1 for d in e.data.servers.values() if not d.get("hidden"))
        yield Out(f"== NETWORK MAP — {len(known)} nodes discovered ({regular} regular hosts exist) ==", "title")
        seen: set[str] = set()

        def marker(sid: str) -> tuple[str, str]:
            if w.current == sid:
                return "◉", "info"
            if not w.is_online(sid):
                return "○", "err"
            return ("◆", "ok") if w.is_compromised(sid) else ("●", "normal")

        def walk(sid: str, prefix: str, last: bool, root: bool = False):
            seen.add(sid)
            s = w.servers[sid]
            mk, style = marker(sid)
            branch = "" if root else ("└─ " if last else "├─ ")
            yield Out(spans=[(prefix + branch, "dim"), (mk + " ", style), (s.name, style), (f"  {s.ip}", "dim"),
                             (f"  [{s.security}]", "warn" if s.security in ("HIGH", "CRITICAL") else "dim")])
            kids = [k for k in s.links if k in known and k not in seen]
            for i, kid in enumerate(kids):
                if kid in seen:
                    continue
                yield from walk(kid, prefix + ("" if root else ("   " if last else "│  ")), i == len(kids) - 1)

        if "echo" in known:
            yield from walk("echo", "", True, root=True)
        for sid in known:
            if sid not in seen:
                yield from walk(sid, "", True, root=True)
        yield dim("◉ connected   ● known   ◆ compromised   ○ offline")

    # ------------------------------------------------------------- comms ---
    def cmd_contacts(self, args):
        e = self.e
        yield Out("== CONTACTS ==", "title")
        for cid, c in e.data.contacts.items():
            row = e.db.get_contact(cid)
            if not row or not row["met"]:
                continue
            unread = e.db.unread_count(cid)
            bar = "█" * (row["trust"] // 10) + "░" * (10 - row["trust"] // 10)
            yield Out(spans=[(f"  {c['name']:<8}", "ok"), (f"{c['role']:<22}", "dim"), (f"TRUST {bar} {row['trust']:>3}", "info"),
                             (f"   ✉ {unread} new" if unread else "", "warn")])
        yield dim("Talk with: msg <name>")

    def cmd_msg(self, args):
        e = self.e
        if not args:
            return (yield from self.cmd_contacts([]))
        cid = args[0].lower()
        contact = e.data.contacts.get(cid)
        row = e.db.get_contact(cid)
        if not contact or not row or not row["met"]:
            return (yield err(f"No open channel to '{args[0]}'."))
        topics = self._visible_topics(cid)
        if len(args) > 1 and not args[1].isdigit():          # allow 'msg mira nexus' (topic id)
            ids = [t["id"] if t else None for _, t in topics]
            if args[1].lower() in ids:
                args = [args[0], str(ids.index(args[1].lower()) + 1)]
        if len(args) > 1 and args[1].isdigit():
            idx = int(args[1])
            if not 1 <= idx <= len(topics) or topics[idx - 1][1] is None:
                return (yield err("That topic is not available."))
            yield from self._ask_topic(cid, topics[idx - 1][1])
            topics = self._visible_topics(cid)
        else:
            yield Out(f"== CHANNEL: {contact['name']} // {contact['role']} ==", "title")
            for m in e.db.get_messages(cid, 6):
                who = contact["name"] if m["direction"] == "in" else e.player.username
                yield Out(spans=[(f"{who}> ", "info" if m["direction"] == "in" else "ok"), (m["text"], "normal")])
            e.db.mark_read(cid)
            e.comms_changed.emit()
        yield out()
        yield Out(f"TRUST: {e.trust(cid)}/100", "dim")
        for i, (label, topic) in enumerate(topics, 1):
            yield Out(f"  [{i}] {label}", "info" if topic else "dim")
        yield dim(f"Ask with: msg {cid} <number>")

    def _visible_topics(self, cid: str) -> list[tuple[str, dict | None]]:
        e = self.e
        out_list = []
        for t in e.data.contacts[cid].get("topics", []):
            req = t.get("requires")
            if req and not e.check_requirement(req):
                continue
            if t.get("min_trust", 0) > e.trust(cid):
                out_list.append((f"[LOCKED — trust {t['min_trust']} required]", None))
                continue
            label = t["label"] + (f"   (${t['cost']:,})" if t.get("cost") else "")
            out_list.append((label, t))
        return out_list

    def _ask_topic(self, cid: str, topic: dict) -> Iterator:
        e = self.e
        contact = e.data.contacts[cid]
        key = f"topic:{cid}:{topic['id']}"
        first = not e.world.seen_once(key)
        if topic.get("cost") and first and not e.spend_credits(topic["cost"]):
            return (yield err(f"INSUFFICIENT CREDITS (${topic['cost']:,})"))
        e.db.add_message(cid, "out", topic["label"], read=True)
        yield Out(spans=[(f"{e.player.username}> ", "ok"), (topic["label"], "normal")])
        e.world.mark_once(key)
        lines = [self.e.missions.hint()] if topic.get("dynamic_hint") else topic.get("response", [])
        for line in lines:
            line = e.fmt(line)
            e.db.add_message(cid, "in", line, read=True)
            yield Out(spans=[(f"{contact['name']}> ", "info"), (line, "story")])
        if first or topic.get("repeatable"):
            if topic.get("trust"):
                e.change_trust(cid, topic["trust"])
            if first:
                yield from self._effects({**{k: v for k, v in topic.items() if k in ("flags", "items", "discover", "xp", "credits", "message", "banner", "heat")}, "once": False}, key + ":fx")
        e.bump("messages_read")
        e.event("topic", contact=cid, topic=topic["id"])
        e.comms_changed.emit()

    def cmd_history(self, args):
        hist = self.e.history[-30:]
        start = len(self.e.history) - len(hist) + 1
        return [dim(f"{start + i:>4}  {line}") for i, line in enumerate(hist)]

    # ----------------------------------------------------- progression ---
    def cmd_achievements(self, args):
        e = self.e
        have = e.db.get_achievements()
        yield Out(f"== ACHIEVEMENTS {len(have)}/{len(e.data.achievements)} ==", "title")
        for a in e.data.achievements:
            if a["id"] in have:
                yield Out(spans=[("  ★ ", "ok"), (f"{a['name']:<24}", "ok"), (a["description"], "dim")])
            elif a.get("hidden"):
                yield Out("  ? ???", "dim")
            else:
                yield Out(spans=[("  ☆ ", "dim"), (f"{a['name']:<24}", "dim"), (a["description"], "dim")])

    def cmd_stats(self, args):
        e, s = self.e, self.e.db.all_stats()
        rows = [("Playtime", SaveSystem.format_time(e.player.playtime)), ("Missions completed", int(s.get("missions_completed", 0))),
                ("Missions failed", int(s.get("missions_failed", 0))), ("Perfect operations", int(s.get("perfect_missions", 0))),
                ("Connections", int(s.get("connections", 0))), ("Scans", int(s.get("scans", 0))),
                ("Firewalls breached", int(s.get("firewalls_breached", 0))), ("Decryptions", int(s.get("decryptions", 0))),
                ("Routes solved", int(s.get("routes_solved", 0))), ("Access codes cracked", int(s.get("access_solved", 0))),
                ("Traces completed", int(s.get("traces_done", 0))), ("Files read", int(s.get("files_read", 0))),
                ("Secrets found", int(s.get("secrets_found", 0))), ("Events seen", int(s.get("events_seen", 0))),
                ("Commands run", int(s.get("commands_run", 0))), ("Credits earned", f"${int(s.get('credits_earned', 0)):,}")]
        yield Out("== OPERATOR STATISTICS ==", "title")
        for label, value in rows:
            yield kv(label + ":", str(value), 24, "info")

    def cmd_upgrades(self, args):
        e, p = self.e, self.e.player
        yield Out(f"== UPGRADES ==   CREDITS: ${p.credits:,}", "title")
        for i, (uid, up) in enumerate(e.data.upgrades.items(), 1):
            lv = p.upgrade_level(uid)
            bar = "■" * lv + "□" * (up["max_level"] - lv)
            cost = p.upgrade_cost(uid)
            yield Out(spans=[(f"  [{i}] {up['name']:<18}", "ok"), (f"{bar} ", "info"), (f"LV{lv}/{up['max_level']}  ", "dim"),
                             ("MAX" if cost is None else f"${cost:,}", "warn" if cost else "ok"), (f"  {up['description']}", "dim")])
        yield dim("Buy with: upgrade <number|name>")

    def cmd_upgrade(self, args):
        e = self.e
        if not args:
            return (yield from self.cmd_upgrades([]))
        query = " ".join(args).lower().replace(" ", "_")
        ids = list(e.data.upgrades)
        uid = ids[int(query) - 1] if query.isdigit() and 1 <= int(query) <= len(ids) else next(
            (i for i in ids if query in (i, e.data.upgrades[i]["name"].lower().replace(" ", "_"))), None)
        if uid is None:
            return (yield err("UNKNOWN UPGRADE"))
        cost = e.player.upgrade_cost(uid)
        success, msg = e.player.buy_upgrade(uid)
        if success:
            e.db.add_stat("credits_spent", cost)
            e.bump("upgrades_bought")
            e.sound.emit("notify")
            e.state_changed.emit()
            e.inventory_changed.emit()
            yield ok(msg)
        else:
            yield err(msg)

    def cmd_shop(self, args):
        e = self.e
        if not e.flag("shop_open"):
            return (yield err("No black-market contact yet. Keep working missions."))
        yield Out(f"== VECTOR'S BACK ROOM ==   CREDITS: ${e.player.credits:,}", "title")
        for item_id, item in e.data.items.items():
            if item.get("price"):
                own = f"(owned x{e.player.qty(item_id)})" if e.player.qty(item_id) else ""
                yield Out(spans=[(f"  {item_id:<22}", "ok"), (f"${item['price']:>6,}  ", "warn"), (item["short"] + " ", "dim"), (own, "info")])
        yield dim("Buy with: buy <item>")

    def cmd_buy(self, args):
        e = self.e
        if not e.flag("shop_open"):
            return (yield err("The shop is closed."))
        if not args:
            return (yield err("usage: buy <item>"))
        q = "_".join(args).lower()
        item_id = next((i for i, d in e.data.items.items() if d.get("price") and q in (i, d["name"].lower().replace(" ", "_"))), None)
        if item_id is None:
            return (yield err("Not for sale."))
        item = e.data.items[item_id]
        if e.player.qty(item_id) >= item.get("max_qty", 99):
            return (yield warn("You can't carry any more of those."))
        if not e.spend_credits(item["price"]):
            return (yield err(f"INSUFFICIENT CREDITS (${item['price']:,})"))
        e.grant_item(item_id, 1)
        yield ok(f"PURCHASED: {item['name']}")

    # ---------------------------------------------------------- training ---
    def cmd_train(self, args):
        e, p = self.e, self.e.player
        games = ["firewall", "decrypt", "route", "access", "trace"]
        if not args or args[0].lower() not in games:
            yield Out("== TRAINING SIMULATOR ==", "title")
            yield info("Practice mini-games for small XP/credit rewards: " + ", ".join(games))
            return
        kind = args[0].lower()
        rng = e.rng
        if kind == "firewall":
            payload, game = FirewallPuzzle(5, 4, 7 + p.firewall_extra_attempts, rng, p.firewall_reveals_one, "TRAINING-WALL"), "firewall"
        elif kind == "decrypt":
            phrase = rng.choice(TRAIN_PHRASES)
            ctype = rng.choice(["caesar", "atbash", "vigenere"])
            key = rng.randint(3, 22) if ctype == "caesar" else (rng.choice(["NODE", "GRID", "WIRE"]) if ctype == "vigenere" else None)
            hints = {"caesar": ["The shift is between 3 and 22."], "atbash": ["A becomes Z, B becomes Y..."],
                     "vigenere": ["The key is a 4-letter word about networks."]}[ctype]
            payload, game = EncryptionPuzzle(phrase, ctype, key, hints, p.decrypt_free_hints, "TRAINING CIPHER"), "encryption"
        elif kind == "route":
            payload, game = RoutingPuzzle(rng.randrange(1 << 30), min(3, 1 + p.level // 10), p.route_budget_bonus,
                                          p.network_level >= 2, "SIM-TARGET"), "routing"
        elif kind == "access":
            payload, game = AccessPuzzle.generate(random.Random(rng.random()), 4, 4), "access"
        else:
            payload, game = TraceConfig(4, 3 + p.trace_extra_misses, p.trace_speed_factor, 5, "TRAINING STREAM"), "trace"
        res = yield Minigame(game, payload)
        if res and res.get("aborted") and not res.get("success"):
            return (yield dim("Training aborted."))
        self.session_trains += 1
        if res and res.get("success"):
            factor = 1.0 if self.session_trains <= 10 else 0.25
            xp, cr = int((15 + 2 * p.level) * factor), int((30 + 3 * p.level) * factor)
            e.bump("training_wins")
            e.bump("minigames_won")
            e.grant_xp(xp)
            e.grant_credits(cr)
            yield ok("TRAINING PASSED.")
        else:
            e.bump("minigames_lost")
            yield warn("TRAINING FAILED. No penalty — try again.")

    # -------------------------------------------------------------- meta ---
    def cmd_tutorial(self, args):
        yield Out("== NEXUS FIELD MANUAL ==", "title")
        for line in self.e.data.tutorial:
            yield Out(self.e.fmt(line), "story" if line and not line.startswith("#") else "info")
        yield Fx("tutorial")

    def cmd_save(self, args):
        e = self.e
        slot = int(args[0]) if args and args[0].isdigit() and 1 <= int(args[0]) <= 3 else 1
        e.save()
        SaveSystem().save_slot(e.db, slot)
        return [ok(f"GAME SAVED -> slot {slot}. (Autosave is always active.)")]

    def cmd_load(self, args):
        return [Fx("load_menu")]

    def cmd_menu(self, args):
        return [Fx("pause")]

    def cmd_settings(self, args):
        return [Fx("settings")]
