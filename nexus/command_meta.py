"""Terminal commands for the v2 systems: market, loadout, profile, daily/weekly, themes, network."""
from __future__ import annotations

from typing import Iterator

from . import reputation
from .config import rank_for_level
from .market import CATEGORIES, SLOTS, STAT_LABELS
from .outputs import Fx, Out, Prompt, dim, err, info, kv, ok, out, warn
from .save_system import SaveSystem

RARITY_STYLE = {"COMMON": "normal", "UNCOMMON": "ok", "RARE": "info", "EPIC": "system", "LEGENDARY": "warn", "NEXUS": "title"}
DIFF_NAME = {1: "EASY", 2: "NORMAL", 3: "HARD", 4: "EXPERT", 5: "NEXUS"}


def bar(value: float, total: float, width: int = 20) -> str:
    filled = int(width * min(1.0, value / total)) if total else 0
    return "█" * filled + "░" * (width - filled)


class MetaCommandsMixin:
    # ----------------------------------------------------------- missions ---
    def cmd_missions(self, args):
        return self.cmd_mission(["list"] + list(args))

    # ------------------------------------------------------------- market ---
    def cmd_market(self, args):
        e = self.e
        sub = args[0].upper() if args else ""
        if sub == "INFO" and len(args) > 1:
            entry = e.market.find(args[1])
            if not entry:
                return (yield err("UNKNOWN ITEM"))
            yield Out(f"{entry['name']}  [{entry['rarity']}]", RARITY_STYLE.get(entry["rarity"], "normal"))
            yield kv("CATEGORY:", entry["category"], 12, "normal")
            yield kv("PRICE:", f"${entry['final_price']:,}" + (f"  (base ${entry['base_price']:,})" if entry["final_price"] != entry["base_price"] else ""), 12, "warn")
            yield kv("LEVEL:", str(entry.get("level", 1)), 12, "normal")
            if entry.get("stats_text"):
                yield kv("STATS:", entry["stats_text"], 12, "info")
            if entry.get("slot"):
                yield kv("SLOT:", entry["slot"], 12, "info")
            yield Out(entry["description"], "story")
            return
        categories = CATEGORIES if sub not in CATEGORIES else [sub]
        deal = e.market.daily_deal_id()
        yield Out(f"== NEXUS MARKET ==   CREDITS: ${e.player.credits:,}   REPUTATION: {e.player.reputation} ({reputation.status(e.player.reputation)}) — {reputation.describe(e.player.reputation)}", "title")
        if deal:
            d = e.market.find(deal)
            yield Out(f"TODAY'S DEAL: {d['name']} -20%  ->  ${d['final_price']:,}", "warn")
        for cat in categories:
            yield out()
            yield Out(f"[{cat}]", "info")
            for entry in e.market.catalogue(cat):
                tag = "OWNED" if entry["owned"] and entry["kind"] != "upgrade" else ("MAX" if entry.get("maxed") else (f"LV{entry['level']}" if entry["locked_level"] else ""))
                price = "—" if entry.get("maxed") or (entry["owned"] and entry["kind"] != "upgrade") else f"${entry['final_price']:,}"
                yield Out(spans=[(f"  {entry['id']:<22}", "dim"), (f"{entry['name']:<30}", RARITY_STYLE.get(entry["rarity"], "normal")),
                                 (f"{entry['rarity']:<10}", "dim"), (f"{price:>10}  ", "warn"), (tag, "err" if tag.startswith("LV") else "ok")])
        yield dim("Buy with: buy <id>   Details: market info <id>   Categories: market tools|upgrades|cosmetics|access|intelligence")

    def cmd_shop(self, args):
        return self.cmd_market(args)

    def cmd_buy(self, args):
        if not args:
            return (yield err("usage: buy <item id>   (see 'market')"))
        success, msg = self.e.market.purchase("_".join(args))
        yield (ok if success else err)(msg)

    # ------------------------------------------------------------ loadout ---
    def cmd_loadout(self, args):
        e = self.e
        eq = e.market.equipped()
        yield Out("== LOADOUT ==", "title")
        for slot in SLOTS:
            if not e.market.slot_unlocked(slot):
                yield Out(spans=[(f"  {slot:<9}", "dim"), ("[LOCKED — progress the story]", "err")])
                continue
            item = e.data.items.get(eq.get(slot, ""))
            if item:
                yield Out(spans=[(f"  {slot:<9}", "info"), (f"{item['name']:<26}", RARITY_STYLE.get(item["rarity"].upper(), "normal")), (item.get("short", ""), "dim")])
            else:
                yield Out(spans=[(f"  {slot:<9}", "info"), ("(empty)", "dim")])
        totals = e.market.total_stats()
        yield out()
        yield Out("TOTAL BONUSES: " + "  ".join(f"{STAT_LABELS[k]} +{v}%" for k, v in totals.items() if v) if any(totals.values()) else "TOTAL BONUSES: none", "ok")
        gear = [i for i, q in e.player.inventory().items() if e.data.items[i].get("kind") == "gear" and i not in eq.values()]
        if gear:
            yield dim("In your inventory: " + ", ".join(gear))
        yield dim("equip <item id>   unequip <slot>")

    def cmd_equip(self, args):
        if not args:
            return (yield err("usage: equip <item id>"))
        item_id = next((i for i in self.e.player.inventory() if "_".join(args).lower() in (i, self.e.data.items[i]["name"].lower().replace(" ", "_"))), None)
        success, msg = self.e.market.equip(item_id or "_".join(args))
        yield (ok if success else err)(msg)

    def cmd_unequip(self, args):
        if not args:
            return (yield err("usage: unequip <slot>"))
        success, msg = self.e.market.unequip(args[0])
        yield (ok if success else err)(msg)

    # ------------------------------------------------------------ profile ---
    def cmd_profile(self, args):
        e, p = self.e, self.e.player
        s = e.db.all_stats()
        done, failed = p.completed_missions, p.failed_missions
        rate = f"{100 * done / (done + failed):.0f}%" if done + failed else "—"
        yield Out("== PROFILE ==", "title")
        yield kv("USERNAME:", p.username.upper(), 18)
        yield kv("LEVEL:", f"{p.level} / 100", 18)
        yield kv("RANK:", p.rank, 18)
        yield kv("XP:", f"{p.xp} / {p.xp_needed}  {bar(p.xp, p.xp_needed, 16)}", 18, "info")
        yield kv("CREDITS:", f"${p.credits:,}", 18, "warn")
        yield kv("REPUTATION:", f"{p.reputation}  —  {reputation.status(p.reputation)}", 18, "info")
        yield out()
        yield Out("STATISTICS:", "dim")
        yield kv("MISSIONS COMPLETED:", str(done), 22, "normal")
        yield kv("MISSIONS FAILED:", str(failed), 22, "normal")
        yield kv("SUCCESS RATE:", rate, 22, "normal")
        yield kv("TOTAL XP:", f"{int(s.get('xp_earned', 0)):,}", 22, "normal")
        yield kv("TOTAL CREDITS:", f"${int(s.get('credits_earned', 0)):,}", 22, "normal")
        solved = int(sum(s.get(k, 0) for k in ("firewalls_breached", "decryptions", "routes_solved", "access_solved", "traces_done")))
        yield kv("PUZZLES SOLVED:", str(solved), 22, "normal")
        yield kv("ACHIEVEMENTS:", f"{len(e.db.get_achievements())} / {len(e.data.achievements)}", 22, "normal")
        yield kv("PLAYTIME:", SaveSystem.format_time(p.playtime), 22, "normal")
        mm = sum(1 for m in e.data.missions if e.missions.is_complete(m["id"]))
        yield kv("MISSION PROGRESS:", f"{mm} / {len(e.data.missions)}", 22, "normal")

    # ------------------------------------------------------------ network ---
    def cmd_network(self, args):
        e, w = self.e, self.e.world
        regions: dict[str, list[str]] = {}
        for sid, s in w.servers.items():
            regions.setdefault(s.region, []).append(sid)
        yield Out("== NEXUS NETWORK ==", "title")
        for region, ids in sorted(regions.items()):
            known = [i for i in ids if w.is_discovered(i)]
            hidden_total = sum(1 for i in ids if e.data.servers[i].get("hidden"))
            label = f"{len(known)}/{len(ids) - hidden_total}" if hidden_total != len(ids) else f"{len(known)}/?"
            yield Out(spans=[(f"  {region:<10}", "info"), (f"{label:>6}  ", "dim"), (", ".join(w.servers[i].name for i in known) or "unexplored", "normal" if known else "dim")])
        yield out()
        yield from self.cmd_map([])

    # -------------------------------------------------------- daily/weekly ---
    def cmd_daily(self, args):
        e = self.e
        if args and args[0].lower() == "claim":
            for line in e.progress.claim_daily():
                yield ok(line)
            return
        d = e.progress.daily()
        yield Out(f"== DAILY OPERATIONS — {d['date']} ==", "title")
        for op in d["ops"]:
            mark = "CLAIMED" if op["claimed"] else ("READY" if op["done"] else "")
            yield Out(spans=[(f"  {bar(op['progress'], op['target'], 12)} ", "info"), (f"{op['progress']}/{op['target']}  ", "dim"),
                             (f"{op['text']:<40}", "normal"), (f"${op['reward'].get('credits', 0):,} +{op['reward'].get('xp', 0)}xp  ", "warn"), (mark, "ok")])
        st = d["streak"]
        yield out()
        yield Out(f"LOGIN STREAK: {st['streak']} day(s)   today: {'claimed' if st['claimed_today'] else 'available (day ' + str(st['next_day']) + ')'}", "info")
        cal = "   ".join(f"D{r['day']}:{'RARE ITEM' if r.get('rare_item') else '$' + format(r['credits'], ',')}" for r in st["calendar"])
        yield dim(cal)
        yield dim("Collect everything with: daily claim")

    def cmd_weekly(self, args):
        e = self.e
        if args and args[0].lower() == "claim":
            for line in e.progress.claim_weekly():
                yield ok(line)
            return
        w = e.progress.weekly()
        yield Out(f"== WEEKLY CHALLENGES — {w['week']} ==", "title")
        for op in w["ops"]:
            r = op["reward"]
            extra = f" +{e.data.items[r['item']]['name']}" if r.get("item") else ""
            mark = "CLAIMED" if op["claimed"] else ("READY" if op["done"] else "")
            yield Out(spans=[(f"  {bar(op['progress'], op['target'], 12)} ", "info"), (f"{op['progress']}/{op['target']}  ", "dim"),
                             (f"{op['text']:<38}", "normal"), (f"${r.get('credits', 0):,} +{r.get('xp', 0)}xp{extra}  ", "warn"), (mark, "ok")])
        yield dim("Collect finished challenges with: weekly claim")

    # ------------------------------------------------------------- themes ---
    def cmd_theme(self, args):
        e = self.e
        unlocked = set(e.db.unlocks("theme:"))
        if not args:
            yield Out("== TERMINAL THEMES ==", "title")
            current = e.settings_value("theme") if e.settings else "default"
            for t in e.data.themes:
                owned = t.get("free") or f"theme:{t['id']}" in unlocked
                style = "ok" if owned else "dim"
                where = ""
                if not owned:
                    where = "  (market)" if any(i.get("theme") == t["id"] for i in e.data.items.values()) else "  (achievement)"
                yield Out(spans=[(f"  {'●' if t['id'] == current else ' '} {t['id']:<12}", style), (t["name"], style), (where if not owned else "", "dim")])
            yield dim("Use: theme <id>")
            return
        tid = args[0].lower()
        theme = next((t for t in e.data.themes if t["id"] == tid), None)
        if not theme:
            return (yield err("UNKNOWN THEME"))
        if not (theme.get("free") or f"theme:{tid}" in unlocked):
            return (yield err("THEME LOCKED — buy it in the market or unlock it with an achievement."))
        if e.settings:
            e.settings.set("theme", tid)
        yield ok(f"THEME SET: {theme['name']}")
        yield Fx("theme", tid)

    # ---------------------------------------------------------- contracts ---
    def cmd_contract(self, args):
        e = self.e
        sub = args[0].lower() if args else ""
        c = e.contracts
        if not c.available():
            return (yield err("Contracts unlock after mission 003."))
        if sub == "new":
            success, msg = c.generate()
            yield (ok if success else err)(msg)
            if not success:
                return
        elif sub == "start":
            if not c.spec():
                return (yield err("No contract yet — use: contract new"))
            yield from self.cmd_mission(["start", "900"])
            return
        spec = c.spec()
        if not spec:
            return (yield dim("No contract yet. Use 'contract new' for an endless procedural job."))
        m = e.missions.by_id[c.mission_id()]
        yield Out(f"== {m['title']} ==", "title")
        yield kv("STATUS:", c.status().upper(), 10, "info")
        yield kv("TYPE:", f"{spec['type']}  ·  tier {spec['tier']}", 10, "normal")
        yield kv("TARGET:", e.data.servers[spec["server"]]["name"], 10, "normal")
        yield kv("REWARD:", f"{m['reward']['xp']} XP  ${m['reward']['credits']:,}", 10, "ok")
        yield dim("Start it with: contract start   ·   When finished: contract new")

    # --------------------------------------------------------- difficulty ---
    def cmd_difficulty(self, args):
        e = self.e
        if args:
            if not e.set_difficulty(args[0].lower()):
                return (yield err("usage: difficulty easy|normal|hard"))
            yield ok(f"DIFFICULTY SET: {e.difficulty.upper()}")
        d = e.DIFFICULTY[e.difficulty]
        yield kv("DIFFICULTY:", e.difficulty.upper(), 14, "warn")
        yield kv("TRACE ALERT:", f"x{d['heat'] * (1 + 0.1 * e.ng_plus):.2f}", 14, "normal")
        yield kv("REWARDS:", f"x{e.reward_mult:.2f}", 14, "normal")
        if e.ng_plus:
            yield kv("NEW GAME+:", str(e.ng_plus), 14, "info")
        yield dim("easy: gentler alert, rewards x0.85   hard: sharper alert, rewards x1.2")

    # -------------------------------------------------------- new game + ---
    def cmd_newgameplus(self, args):
        e = self.e
        if not e.db.get_flag("campaign_complete"):
            return (yield err("Finish the campaign (mission 016) first."))
        yield warn("NEW GAME+ restarts the story and resets mission progress. Level, credits, items, upgrades and achievements are kept.")
        answer = yield Prompt("Type YES to begin: ")
        if (answer or "").strip().upper() != "YES":
            return (yield dim("Cancelled."))
        success, msg = e.start_new_game_plus()
        yield (ok if success else err)(msg)

    # --------------------------------------------------------------- about ---
    def cmd_about(self, args):
        from .version import AUTHOR, DISCORD_URL, VERSION
        yield Out(f"NEXUS // TERMINAL v{VERSION}", "title")
        yield kv("CREATED BY:", AUTHOR, 12, "ok")
        if DISCORD_URL:
            yield kv("DISCORD:", DISCORD_URL, 12, "info")
        yield dim("Everything in NEXUS is a simulation.")
