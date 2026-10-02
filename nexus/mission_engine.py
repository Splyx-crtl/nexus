"""Mission state machine driven by game events (see missions/*.json)."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from .simulation import ROLE_LEVELS

if TYPE_CHECKING:
    from .game_engine import GameEngine

_RESERVED = {"id", "text", "event", "optional", "bonus", "hint", "hidden", "qty", "any_server"}
PERFECT_HEAT = 25
FAIL_REP_PENALTY = 2
_STATE_EVENTS = ("connect", "login", "item", "flag", "firewall", "route", "decrypt", "heat_below")
_SEEN_LIMIT = 80                 # remembered player actions per mission


class MissionEngine:
    def __init__(self, engine: "GameEngine"):
        self.e = engine
        self.defs: list[dict] = list(engine.data.missions)          # copies: contracts are added per operator at runtime
        self.by_id: dict[str, dict] = dict(engine.data.missions_by_id)
        self._cache: dict | None = None      # in-memory record of the active mission
        self._tick_count = 0

    # ------------------------------------------------------------ state ---
    def is_complete(self, mid: str) -> bool:
        return self.e.db.mission_status(mid) == "completed"

    def lock_reason(self, m: dict) -> str:
        """Human readable reason why a mission is locked ('' when available)."""
        e = self.e
        missing = [r for r in m.get("requires", []) if not self.is_complete(r)]
        if missing:
            return "COMPLETE: " + ", ".join(f"{self.by_id[r]['number']:03d}" for r in missing)
        if m.get("required_level", 1) > e.player.level:
            return f"REQUIRES LEVEL {m['required_level']}"
        if m.get("min_reputation", 0) > e.player.reputation:
            return f"REQUIRES REPUTATION {m['min_reputation']}"
        for item in m.get("requires_items", []):
            if not e.player.has(item):
                return f"REQUIRES: {e.data.items[item]['name']}"
        if m.get("requires_flag") and not e.db.get_flag(m["requires_flag"]):
            return "REQUIRES: a hidden condition"
        return ""

    def requirements_met(self, m: dict) -> bool:
        return not self.lock_reason(m)

    def status(self, mid: str) -> str:
        rec = self.e.db.get_mission(mid)
        if rec and rec["status"] in ("active", "completed"):
            return rec["status"]
        if not self.requirements_met(self.by_id[mid]):
            return "locked"
        return "failed" if rec and rec["status"] == "failed" else "available"

    def result(self, mid: str) -> str:
        rec = self.e.db.get_mission(mid)
        return rec["result"] if rec else ""

    def active(self) -> dict | None:
        mid = self.e.db.active_mission_id()
        return self.by_id.get(mid) if mid else None

    def available(self) -> list[dict]:
        return [m for m in self.defs if not m.get("contract") and self.status(m["id"]) in ("available", "failed")]

    # -- dynamic (contract) missions
    def register_dynamic(self, mission: dict) -> None:
        self.unregister_prefix(mission["id"].split("_")[0] + "_")
        self.defs.append(mission)
        self.by_id[mission["id"]] = mission

    def unregister_prefix(self, prefix: str) -> None:
        self.defs = [m for m in self.defs if not m["id"].startswith(prefix)]
        for key in [k for k in self.by_id if k.startswith(prefix)]:
            del self.by_id[key]

    def by_number(self, number: int) -> dict | None:
        return next((m for m in self.defs if m["number"] == number), None)

    def progress(self, mid: str | None = None) -> dict:
        """Mutable progress dict of the active mission (cached; flushed by save())."""
        mid = mid or (self.active() or {}).get("id")
        if not mid:
            return {}
        if self._cache is None or self._cache["id"] != mid:
            rec = self.e.db.get_mission(mid)
            self._cache = {"id": mid, "progress": dict(rec["progress"]) if rec else {}}
        return self._cache["progress"]

    def save(self) -> None:
        if self._cache:
            rec = self.e.db.get_mission(self._cache["id"])
            if rec and rec["status"] == "active":
                self.e.db.save_mission(self._cache["id"], "active", self._cache["progress"])

    # ------------------------------------------------------ view helpers ---
    def objectives_view(self, mid: str) -> list[dict]:
        m = self.by_id[mid]
        status = self.status(mid)
        if status == "completed":
            done = {o["id"] for o in m["objectives"]}
        elif status == "active":
            done = set(self.progress(mid).get("done", []))
        else:
            done = set()
        view, current_marked = [], False
        for obj in m["objectives"]:
            is_done = obj["id"] in done
            current = False
            if not is_done and not obj.get("optional") and not current_marked and status == "active":
                current = current_marked = True
            view.append({"id": obj["id"], "text": self.e.fmt(obj["text"]), "done": is_done,
                         "optional": bool(obj.get("optional")), "current": current})
        bonus_done = set(self.progress(mid).get("bonus_done", [])) if status == "active" else set(
            (self.e.db.get_mission(mid) or {}).get("progress", {}).get("bonus_done", []))
        for goal in m.get("bonus_goals", []):
            view.append({"id": goal["id"], "text": goal["text"], "done": goal["id"] in bonus_done, "optional": True,
                         "current": False, "bonus_goal": True})
        return view

    def time_left(self) -> float | None:
        m = self.active()
        if not m or not m.get("time_limit"):
            return None
        return max(0.0, m["time_limit"] - self.progress().get("elapsed", 0.0))

    def hint(self) -> str:
        m = self.active()
        if not m:
            return "No active mission. Use 'mission list'."
        prog = self.progress()
        if prog.get("awaiting_choice"):
            return "Make your decision with 'choose <number>'."
        for obj in m["objectives"]:
            if obj["id"] not in prog.get("done", []) and not obj.get("optional"):
                return self.e.fmt(obj.get("hint") or self._default_hint(obj) or m.get("hint", "Check your terminal tools: help"))
        return m.get("hint", "")

    @staticmethod
    def _default_hint(obj: dict) -> str:
        """Generic hint for objectives without a hand-written one, so 'hint' always names the current step."""
        ev = obj.get("event")
        if ev == "download" and obj.get("file"):
            return f"Type: download {obj['file']}  (connected to the server that holds it)"
        if ev == "read" and obj.get("path"):
            return f"Read the file {obj['path']} with 'cat'."
        if ev == "connect" and obj.get("server"):
            return f"Type: connect {obj['server']}"
        return ""

    def choice_options(self, m: dict | None = None) -> list[dict]:
        m = m or self.active()
        if not m or not m.get("choice"):
            return []
        return [o for o in m["choice"]["options"] if not o.get("requires") or self.e.check_requirement(o["requires"])]

    # ------------------------------------------------------------ start ---
    def start(self, mid: str) -> tuple[bool, str]:
        m = self.by_id.get(mid)
        if not m:
            return False, "UNKNOWN MISSION"
        if self.active():
            return False, f"MISSION {self.active()['number']:03d} IS ALREADY ACTIVE (use 'mission abort')"
        if self.status(mid) not in ("available", "failed"):
            return False, "MISSION NOT AVAILABLE"
        prev = self.e.db.get_mission(mid)
        self.e.db.save_mission(mid, "active", {"done": [], "peak_heat": self.e.heat, "losses": 0, "elapsed": 0.0,
                                               "awaiting_choice": False, "bonus_xp": 0, "bonus_credits": 0},
                               started_at=time.time(), attempts=(prev["attempts"] + 1) if prev else 1)
        self._cache = None
        start = m.get("on_start", {})
        for sid in start.get("discover", []):
            self.e.world.discover(sid)
        for sid in {o.get("server") for o in m["objectives"] if o.get("server")}:
            self.e.world.set_online(sid)             # a host that dropped off the grid earlier must not block a mission
        for item, qty in start.get("ensure_items", {}).items():
            missing = qty - self.e.player.qty(item)
            if missing > 0:
                self.e.grant_item(item, missing, announce=False)
                self.e.say("Recovered missing assets from the NEXUS cache.", "dim")
        for item in start.get("items", []):
            self.e.grant_item(item, 1)
        for path, content in start.get("files", {}).items():
            self.e.db.put_local_file(path, content if isinstance(content, str) else "\n".join(content), source=mid)
        for flag, value in start.get("flags", {}).items():
            self.e.set_flag(flag, value)
        for msg in start.get("messages", []):
            self.e.send_message(msg["from"], msg["text"])
        self.e.bump("missions_started")
        self.progress()["peak_heat"] = self.e.heat
        self._fire(m, "start")
        self.sync_states()
        self.e.mission_changed.emit()
        self.e.state_changed.emit()
        return True, m["id"]

    def abort(self) -> bool:
        m = self.active()
        if not m:
            return False
        self.e.db.save_mission(m["id"], "available", {})
        self._cache = None
        self.e.mission_changed.emit()
        return True

    # ------------------------------------------------------------ events ---
    def on_event(self, etype: str, kw: dict) -> None:
        m = self.active()
        if not m:
            return
        prog = self.progress()
        if prog.get("awaiting_choice"):
            return
        done: list = prog.setdefault("done", [])
        # Remember what the player did: an action performed a step "too early" (e.g. downloading a file before
        # reading it) must still count once the objective in front of it is done, instead of being lost.
        seen: list = prog.setdefault("seen", [])
        seen.append({"type": etype, "kw": {k: v for k, v in kw.items() if isinstance(v, (str, int, float, bool))}, "used": False})
        del seen[:-_SEEN_LIMIT]
        for obj in m["objectives"]:
            if obj["id"] in done or not obj.get("optional"):
                continue
            if self._match(obj, etype, kw):             # optional objectives never wait for their predecessors
                self._mark_done(m, obj)
        self.sync_states()

    def _claim_seen(self, obj: dict) -> bool:
        """Consume the oldest remembered event that satisfies a required action objective."""
        for rec in self.progress().get("seen", []):
            if not rec["used"] and self._match(obj, rec["type"], rec["kw"]):
                rec["used"] = True
                return True
        return False

    def _match(self, obj: dict, etype: str, kw: dict) -> bool:
        if obj.get("event") != etype:
            return False
        for key, value in obj.items():
            if key in _RESERVED:
                continue
            if key.startswith("contains_"):
                if str(value).lower() not in str(kw.get(key[9:], "")).lower():
                    return False
            elif isinstance(value, list):
                if kw.get(key) not in value:
                    return False
            elif key == "path":
                if str(kw.get("path", "")).lower() != str(value).lower():
                    return False
            elif kw.get(key) != value:
                return False
        return True

    def _state_ok(self, obj: dict) -> bool:
        ev, w, p = obj.get("event"), self.e.world, self.e.player
        sid = obj.get("server")
        if ev == "connect":
            return w.current == sid
        if ev == "login":
            return w.current == sid and w.role(sid) >= ROLE_LEVELS.get(obj.get("role", "user"), 1)
        if ev == "item":
            return p.qty(obj["item"]) >= obj.get("qty", 1)
        if ev == "flag":
            return bool(self.e.db.get_flag(obj["flag"]))
        if ev == "firewall":
            return w.is_breached(sid)
        if ev == "route":
            return w.is_routed(sid)
        if ev == "decrypt":
            return "path" in obj and w.is_decrypted(sid, obj["path"])
        if ev == "heat_below":
            return self.e.heat <= obj.get("max", 25)
        return False

    def sync_states(self) -> None:
        """Auto-complete state-type objectives (connected, logged in, has item...) in order."""
        m = self.active()
        if not m:
            return
        prog = self.progress()
        if prog.get("awaiting_choice"):
            return
        done: list = prog.setdefault("done", [])
        progressed = True
        while progressed:
            progressed = False
            for obj in m["objectives"]:
                if obj["id"] in done:
                    continue
                if obj.get("optional"):
                    continue
                if obj.get("event") in _STATE_EVENTS:
                    if self._state_ok(obj):
                        self._mark_done(m, obj)
                        progressed = True
                elif self._claim_seen(obj):
                    self._mark_done(m, obj)
                    progressed = True
                break  # only the first pending required objective can progress
        self._check_complete(m)

    def _mark_done(self, m: dict, obj: dict) -> None:
        prog = self.progress()
        if obj["id"] in prog["done"]:
            return
        prog["done"].append(obj["id"])
        if obj.get("optional"):
            bonus = obj.get("bonus", {})
            prog["bonus_xp"] = prog.get("bonus_xp", 0) + bonus.get("xp", 0)
            prog["bonus_credits"] = prog.get("bonus_credits", 0) + bonus.get("credits", 0)
            self.e.say(f"[+] BONUS OBJECTIVE: {self.e.fmt(obj['text'])}", "ok")
        else:
            self.e.say(f"[✔] OBJECTIVE COMPLETE: {self.e.fmt(obj['text'])}", "ok")
        self.e.sound.emit("notify")
        self.save()
        self._fire(m, f"objective:{obj['id']}")
        self.e.mission_changed.emit()

    def _check_complete(self, m: dict) -> None:
        prog = self.progress()
        if prog.get("awaiting_choice"):
            return
        required = [o["id"] for o in m["objectives"] if not o.get("optional")]
        if not all(o in prog.get("done", []) for o in required):
            return
        if m.get("choice") and self.choice_options(m):
            prog["awaiting_choice"] = True
            self.save()
            self.e.say("", "normal")
            self.e.say("[!] DECISION REQUIRED", "warn")
            self.e.say(self.e.fmt(m["choice"]["prompt"]), "story")
            for i, opt in enumerate(self.choice_options(m), 1):
                self.e.say(f"  [{i}] {self.e.fmt(opt['text'])}", "info")
            self.e.say("Use: choose <number>", "dim")
            self.e.mission_changed.emit()
            return
        self.complete(m, None)

    # ------------------------------------------------------------ choice ---
    def choose(self, number: int) -> tuple[bool, str]:
        m = self.active()
        if not m or not self.progress().get("awaiting_choice"):
            return False, "NO DECISION PENDING"
        options = self.choice_options(m)
        if not 1 <= number <= len(options):
            return False, f"CHOOSE A NUMBER BETWEEN 1 AND {len(options)}"
        option = options[number - 1]
        self.e.db.set_decision(m["choice"].get("key", m["id"]), option["id"], m["id"])
        self.e.set_flag(f"choice:{m['choice'].get('key', m['id'])}", option["id"])
        self.complete(m, option)
        return True, option["id"]

    # ---------------------------------------------------------- complete ---
    def complete(self, m: dict, option: dict | None) -> None:
        if m.get("tutorial"):
            self._complete_tutorial(m)
            return
        e = self.e
        prog = self.progress(m["id"])
        perfect = prog.get("peak_heat", 0) <= PERFECT_HEAT and prog.get("losses", 0) == 0
        mult = 1.25 if perfect else 1.0
        reward = m.get("reward", {})
        xp = int(reward.get("xp", 0) * mult) + prog.get("bonus_xp", 0)
        credits = int(reward.get("credits", 0) * mult) + prog.get("bonus_credits", 0)
        rep = reward.get("reputation", 0)
        opt_reward = (option or {}).get("reward", {})
        xp += opt_reward.get("xp", 0)
        credits += opt_reward.get("credits", 0)
        rep += opt_reward.get("reputation", 0)
        result = "PERFECT" if perfect else "SUCCESS"
        peak = prog.get("peak_heat", 0)
        # completion bonus goals (time / no mistakes / low alert)
        bonus_lines: list[str] = []
        prog["bonus_done"] = []
        for goal in m.get("bonus_goals", []):
            cond, value = goal.get("cond"), goal.get("value", 0)
            met = ((cond == "time_under" and prog.get("elapsed", 0) <= value) or
                   (cond == "no_losses" and prog.get("losses", 0) == 0) or
                   (cond == "max_heat" and peak <= value))
            if met:
                prog["bonus_done"].append(goal["id"])
                xp += goal.get("reward", {}).get("xp", 0)
                credits += goal.get("reward", {}).get("credits", 0)
                bonus_lines.append(f"[+] BONUS GOAL: {goal['text']}  +{goal.get('reward', {}).get('xp', 0)} XP  +${goal.get('reward', {}).get('credits', 0):,}")
                e.bump("bonus_goals_done")

        e.db.save_mission(m["id"], "completed", prog, result=result, completed_at=time.time())
        self._cache = None
        e.player.count_mission(True)
        e.bump("missions_completed")
        if perfect:
            e.bump("perfect_missions")
        if m.get("contract"):
            e.bump("contracts_done")
        if prog.get("losses", 0) == 0:
            e.bump("clean_missions")
        if m.get("difficulty", 1) >= 3:
            e.bump("hard_missions")
        e.bump(f"missions_{m.get('type', 'story').lower()}")

        # Rewards (collect achievements unlocked by this completion for the banner)
        before = set(e.db.get_achievements())
        e.grant_xp(xp, announce=False)
        e.grant_credits(credits, announce=False)
        if rep:
            e.player.add_reputation(rep)
        for item in reward.get("items", []) + opt_reward.get("items", []):
            e.grant_item(item, 1)
        on_complete = m.get("on_complete", {})
        for flag, value in {**on_complete.get("flags", {}), **(option or {}).get("flags", {})}.items():
            e.set_flag(flag, value)
        for sid in on_complete.get("discover", []) + (option or {}).get("discover", []):
            e.world.discover(sid)
        for contact, delta in (option or {}).get("trust", {}).items():
            e.change_trust(contact, delta)
        for contact, delta in on_complete.get("trust", {}).items():
            e.change_trust(contact, delta)
        for msg in on_complete.get("messages", []) + (option or {}).get("messages", []):
            e.send_message(msg["from"], msg["text"])
        e.achievements.check()
        unlocked = [a for a in e.db.get_achievements() if a not in before]

        # Presentation
        e.say("", "normal")
        e.say(f"=== MISSION {m['number']:03d} COMPLETE — {m['title']} [{result}] ===", "ok")
        for line in m.get("story_end", []):
            e.say(e.fmt(line), "story")
        if option and option.get("result"):
            e.say(e.fmt(option["result"]), "story")
        for line in bonus_lines:
            e.say(line, "ok")
        e.say(f"REWARD: +{xp} XP   +${credits:,}   REP {rep:+d}   (peak alert {peak:.0f}%)", "info")
        lines = ["MISSION COMPLETE", f"{m['number']:03d} // {m['title']}", f"+{xp} XP", f"+${credits:,}"]
        if perfect:
            lines.append("PERFECT OPERATION  x1.25")
        for ach_id in unlocked:
            ach = next(a for a in e.data.achievements if a["id"] == ach_id)
            lines.append(f"ACHIEVEMENT UNLOCKED: {ach['name']}")
        e.banner.emit("complete", lines, {})
        e.sound.emit("complete")
        self._fire(m, "complete")

        if option and option.get("banner"):
            e.banner.emit(option["banner"].get("kind", "alert"), [e.fmt(x) for x in option["banner"].get("lines", [])], option["banner"])
        # ending trigger
        if option and option.get("ending"):
            e.trigger_ending(option["ending"])

        # announce what unlocked
        for nxt in self.available():
            if m["id"] in nxt.get("requires", []):
                e.say(f"NEW MISSION AVAILABLE: {nxt['number']:03d} \"{nxt['title']}\"  ->  mission start {nxt['number']}", "warn")
        e.check_chapters()
        e.snapshot_history()
        e.mission_changed.emit()
        e.state_changed.emit()
        e.maybe_autosave(force=True)

    def _complete_tutorial(self, m: dict) -> None:
        """The guided tutorial pays a small reward but is not a real mission: it never counts in statistics,
        ratings or leaderboards. It hands over to the next mission directly."""
        e = self.e
        reward = m.get("reward", {})
        e.db.save_mission(m["id"], "completed", self.progress(m["id"]), result="TRAINED", completed_at=time.time())
        self._cache = None
        e.grant_xp(reward.get("xp", 0), announce=False)
        e.grant_credits(reward.get("credits", 0), announce=False)
        on_complete = m.get("on_complete", {})
        for flag, value in on_complete.get("flags", {}).items():
            e.set_flag(flag, value)
        e.say("", "normal")
        e.say(f"=== {m['title']} COMPLETE ===", "ok")
        for line in m.get("story_end", []):
            e.say(e.fmt(line), "story")
        e.say(f"REWARD: +{reward.get('xp', 0)} XP   +${reward.get('credits', 0):,}", "info")
        e.banner.emit("complete", ["TRAINING COMPLETE", f"+{reward.get('xp', 0)} XP", f"+${reward.get('credits', 0):,}"], {})
        e.sound.emit("complete")
        nxt = on_complete.get("start_next")
        if nxt and nxt in self.by_id and not self.active():
            started, _ = self.start(nxt)
            if started:                                  # print the briefing the way 'mission start' does
                for item in e.commands._print_briefing(self.by_id[nxt]):
                    text = item.text or "".join(t for t, _ in (getattr(item, "spans", None) or []))
                    e.say(text, getattr(item, "style", "normal"))
        e.mission_changed.emit()
        e.state_changed.emit()
        e.maybe_autosave(force=True)

    # -------------------------------------------------------------- fail ---
    def fail(self, reason: str) -> None:
        m = self.active()
        if not m:
            return
        e = self.e
        e.db.save_mission(m["id"], "failed", {})
        self._cache = None
        e.player.count_mission(False)
        e.bump("missions_failed")
        e.player.add_reputation(-FAIL_REP_PENALTY)
        fee = int(e.player.credits * 0.05)
        if fee:
            e.player.add_credits(-fee)
        e.say("", "normal")
        e.say(f"=== MISSION {m['number']:03d} FAILED — {reason} ===", "err")
        e.say(f"Containment fee: -${fee:,}. Retry with 'mission start {m['number']}'.", "warn")
        e.banner.emit("failure", ["MISSION FAILED", reason, f"-${fee:,}"], {})
        e.sound.emit("error")
        e.achievements.check()
        e.mission_changed.emit()
        e.state_changed.emit()

    # --------------------------------------------------------- hooks ------
    def note_heat(self, heat: float) -> None:
        if self.active():
            prog = self.progress()
            prog["peak_heat"] = max(prog.get("peak_heat", 0), heat)

    def note_loss(self) -> None:
        if self.active():
            prog = self.progress()
            prog["losses"] = prog.get("losses", 0) + 1

    def tick(self, dt: float) -> None:
        m = self.active()
        if not m:
            return
        prog = self.progress()
        prog["elapsed"] = prog.get("elapsed", 0.0) + dt
        self._tick_count += 1
        if self._tick_count % 5 == 0:
            self.save()
        limit = m.get("time_limit")
        if limit and prog["elapsed"] >= limit and not prog.get("awaiting_choice"):
            self.fail("TIME LIMIT EXCEEDED")

    def _fire(self, m: dict, when: str) -> None:
        for moment in m.get("moments", []):
            if moment.get("when") != when:
                continue
            for line in moment.get("lines", []):
                self.e.say(self.e.fmt(line), moment.get("style", "story"))
            if "banner" in moment:
                b = moment["banner"]
                self.e.banner.emit(b.get("kind", "alert"), [self.e.fmt(x) for x in b.get("lines", [])], b)
            if "message" in moment:
                self.e.send_message(moment["message"]["from"], moment["message"]["text"])
            if "sound" in moment:
                self.e.sound.emit(moment["sound"])
