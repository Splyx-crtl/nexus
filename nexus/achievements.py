"""Achievement evaluation (conditions are declared in data/achievements.json)."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .game_engine import GameEngine


class AchievementManager:
    def __init__(self, engine: "GameEngine"):
        self.engine = engine
        self.defs = engine.data.achievements

    def unlocked(self) -> dict[str, float]:
        return self.engine.db.get_achievements()

    def _met(self, cond: dict, ctx: dict | None = None) -> bool:
        e = self.engine
        ctx = ctx or {}
        if "stat" in cond:
            stats = ctx.get("stats")
            value = stats.get(cond["stat"], 0) if stats is not None else e.db.get_stat(cond["stat"])
            return value >= cond.get("gte", 1)
        if "flag" in cond:
            flags = ctx.get("flags")
            return bool(flags.get(cond["flag"]) if flags is not None else e.db.get_flag(cond["flag"]))
        if "mission" in cond:
            return e.missions.is_complete(cond["mission"])
        if "level" in cond:
            return e.player.level >= cond["level"]
        if "credits" in cond:
            return e.player.credits >= cond["credits"]
        if "upgrade_max" in cond:
            return any(e.player.upgrade_level(u) >= d["max_level"] for u, d in e.data.upgrades.items())
        if "trust" in cond:
            return any(c["trust"] >= cond["trust"] for c in e.db.all_contacts().values())
        if "contacts_met" in cond:
            return sum(1 for c in e.db.all_contacts().values() if c["met"]) >= cond["contacts_met"]
        if "discovered" in cond:
            return len(e.world.discovered()) >= cond["discovered"]
        if "slots_filled" in cond:
            return len(e.db.get_equipment()) >= cond["slots_filled"]
        if "themes" in cond:
            return len(e.db.unlocks("theme:")) >= cond["themes"]
        if "reputation" in cond:
            return e.player.reputation >= cond["reputation"]
        if "endings" in cond:
            return len(e.db.get_world("endings", [])) >= cond["endings"]
        if "ending" in cond:
            return cond["ending"] in e.db.get_world("endings", [])
        return False

    def check(self) -> list[dict]:
        """Evaluate all locked achievements; returns the newly unlocked definitions."""
        have = self.unlocked()
        fresh = []
        ctx = {"stats": self.engine.db.all_stats(), "flags": self.engine.db.all_flags()}   # one query each, not 76
        for ach in self.defs:
            if ach["id"] in have:
                continue
            if self._met(ach["condition"], ctx) and self.engine.db.unlock_achievement(ach["id"]):
                fresh.append(ach)
        for ach in fresh:
            self.engine.on_achievement(ach)
        return fresh

    def unlock(self, ach_id: str) -> bool:
        """Force-unlock (used for special/secret achievements)."""
        ach = next((a for a in self.defs if a["id"] == ach_id), None)
        if ach and self.engine.db.unlock_achievement(ach_id):
            self.engine.on_achievement(ach)
            return True
        return False
