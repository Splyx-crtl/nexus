"""Daily operations, weekly challenges and the login streak (all stored locally)."""
from __future__ import annotations

import datetime as dt
import random
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .game_engine import GameEngine

TRACKED_STATS = [
    "missions_completed", "decryptions", "credits_earned", "clean_missions", "firewalls_breached", "scans",
    "connections", "files_read", "traces_done", "routes_solved", "downloads", "minigames_won", "hard_missions",
    "perfect_missions", "secrets_found",
]


class ProgressManager:
    def __init__(self, engine: "GameEngine"):
        self.e = engine
        self.cfg = engine.data.challenges
        self.today: Callable[[], dt.date] = dt.date.today      # injectable for tests

    # ------------------------------------------------------------ helpers --
    def _stats(self) -> dict[str, float]:
        stats = self.e.db.all_stats()
        return {k: stats.get(k, 0) for k in TRACKED_STATS}

    @staticmethod
    def _week_key(day: dt.date) -> str:
        year, week, _ = day.isocalendar()
        return f"{year}-W{week:02d}"

    def _roll(self, key: str, period: str, pool: list[dict], count: int) -> dict:
        """Create (or load) the state of the current day/week."""
        state = self.e.db.get_world(key)
        if state and state.get("period") == period:
            return state
        rng = random.Random(f"{key}:{period}:{self.e.player.username}")
        picks = rng.sample(pool, min(count, len(pool)))
        scale = 1 + self.e.player.level // 25
        ops = []
        for op in picks:
            target = op["target"]
            if op.get("scale"):
                target = int(target * (1 + op["scale"] * (scale - 1)) // 1)
            ops.append({"id": op["id"], "target": max(1, target)})
        state = {"period": period, "ops": ops, "baseline": self._stats(), "claimed": []}
        if state_prev := self.e.db.get_world(key):
            state["streak"] = state_prev.get("streak", 0)
            state["last_claim"] = state_prev.get("last_claim", "")
        self.e.db.set_world(key, state)
        return state

    def _view(self, state: dict, pool: list[dict]) -> list[dict]:
        stats, by_id = self._stats(), {o["id"]: o for o in pool}
        view = []
        for op in state["ops"]:
            base = by_id[op["id"]]
            progress = int(min(op["target"], stats.get(base["stat"], 0) - state["baseline"].get(base["stat"], 0)))
            text = base["text"].replace("{n}", f"{op['target']:,}")
            view.append({"id": op["id"], "text": text, "progress": max(0, progress), "target": op["target"],
                         "done": progress >= op["target"], "claimed": op["id"] in state["claimed"],
                         "reward": base["reward"]})
        return view

    # ----------------------------------------------------------------- daily --
    def daily_state(self) -> dict:
        return self._roll("daily", self.today().isoformat(), self.cfg["daily"], 3)

    def daily(self) -> dict:
        state = self.daily_state()
        streak_info = self.streak_info(state)
        return {"date": state["period"], "ops": self._view(state, self.cfg["daily"]), "streak": streak_info}

    def streak_info(self, state: dict | None = None) -> dict:
        state = state or self.daily_state()
        today = self.today()
        last = state.get("last_claim", "")
        streak = state.get("streak", 0)
        claimed_today = last == today.isoformat()
        if last and not claimed_today and last != (today - dt.timedelta(days=1)).isoformat():
            streak = 0                                        # streak broken
        next_day = ((streak) % 7) + 1 if not claimed_today else ((streak - 1) % 7) + 1
        rewards = self.cfg["streak"]
        return {"streak": streak, "claimed_today": claimed_today, "next_day": next_day, "calendar": rewards}

    def claim_daily(self) -> list[str]:
        """Claim every finished operation plus today's streak reward. Returns message lines."""
        e = self.e
        state = self.daily_state()
        lines: list[str] = []
        for op in self._view(state, self.cfg["daily"]):
            if op["done"] and not op["claimed"]:
                state["claimed"].append(op["id"])
                e.grant_credits(op["reward"].get("credits", 0), announce=False, bonus=False)
                e.grant_xp(op["reward"].get("xp", 0), announce=False, bonus=False)
                lines.append(f"DAILY OPERATION COMPLETE: {op['text']}  +${op['reward'].get('credits', 0):,}  +{op['reward'].get('xp', 0)} XP")
                e.bump("daily_ops_done")
        info = self.streak_info(state)
        if not info["claimed_today"]:
            streak = info["streak"] + 1
            day = ((streak - 1) % 7) + 1
            reward = next(r for r in self.cfg["streak"] if r["day"] == day)
            e.grant_credits(reward["credits"], announce=False, bonus=False)
            text = f"LOGIN STREAK DAY {day}: +${reward['credits']:,}"
            if reward.get("rare_item"):
                item = next((i for i in self.cfg["rare_pool"] if not e.player.has(i)), None)
                if item:
                    e.grant_item(item, 1, announce=False)
                    text += f"  +RARE ITEM: {e.data.items[item]['name']}"
                else:
                    e.grant_credits(5000, announce=False, bonus=False)
                    text += "  +$5,000 (all rare items owned)"
            lines.append(text)
            state["streak"], state["last_claim"] = streak, self.today().isoformat()
            e.bump("daily_claims")
        e.db.set_world("daily", state)
        if lines:
            e.sound.emit("achievement")
            e.notify_toast("ok", "DAILY REWARDS", lines[-1])
            e.state_changed.emit()
        return lines or ["Nothing to claim yet."]

    # ---------------------------------------------------------------- weekly --
    def weekly_state(self) -> dict:
        return self._roll("weekly", self._week_key(self.today()), self.cfg["weekly"], 4)

    def weekly(self) -> dict:
        state = self.weekly_state()
        return {"week": state["period"], "ops": self._view(state, self.cfg["weekly"])}

    def claim_weekly(self) -> list[str]:
        e = self.e
        state = self.weekly_state()
        lines = []
        for op in self._view(state, self.cfg["weekly"]):
            if op["done"] and not op["claimed"]:
                state["claimed"].append(op["id"])
                r = op["reward"]
                e.grant_credits(r.get("credits", 0), announce=False, bonus=False)
                e.grant_xp(r.get("xp", 0), announce=False, bonus=False)
                extra = ""
                if r.get("item"):
                    e.grant_item(r["item"], 1, announce=False)
                    extra = f"  +{e.data.items[r['item']]['name']}"
                if r.get("achievement"):
                    e.achievements.unlock(r["achievement"])
                lines.append(f"WEEKLY CHALLENGE COMPLETE: {op['text']}  +${r.get('credits', 0):,}  +{r.get('xp', 0)} XP{extra}")
                e.bump("weekly_claims")
        e.db.set_world("weekly", state)
        if lines:
            e.sound.emit("achievement")
            e.notify_toast("ok", "WEEKLY REWARD", lines[-1])
            e.state_changed.emit()
        return lines or ["Nothing to claim yet."]

    def claimable_count(self) -> int:
        d = sum(1 for o in self.daily()["ops"] if o["done"] and not o["claimed"])
        w = sum(1 for o in self.weekly()["ops"] if o["done"] and not o["claimed"])
        return d + w + (0 if self.streak_info()["claimed_today"] else 1)
