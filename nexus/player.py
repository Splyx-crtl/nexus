"""Operator profile: level, XP, credits, reputation, inventory and upgrades."""
from __future__ import annotations

from .config import MAX_LEVEL, rank_for_level, xp_for_level
from .data import GameData
from .database import Database


class Player:
    def __init__(self, db: Database, data: GameData):
        self.db = db
        self.data = data
        self._p = db.get_profile()

    # -- profile fields --------------------------------------------------
    def _set(self, **fields) -> None:
        self._p.update(fields)
        self.db.update_profile(**fields)

    username = property(lambda s: s._p["username"])
    level = property(lambda s: s._p["level"])
    xp = property(lambda s: s._p["xp"])
    credits = property(lambda s: s._p["credits"])
    reputation = property(lambda s: s._p["reputation"])
    completed_missions = property(lambda s: s._p["completed_missions"])
    failed_missions = property(lambda s: s._p["failed_missions"])
    playtime = property(lambda s: s._p["playtime"])
    ending = property(lambda s: s._p.get("ending") or "")

    @property
    def rank(self) -> str:
        return rank_for_level(self.level)

    @property
    def xp_needed(self) -> int:
        return xp_for_level(self.level)

    def add_xp(self, amount: int) -> list[int]:
        """Add XP; returns the list of levels reached (empty if none)."""
        amount = int(amount)
        if amount <= 0:
            return []
        xp, level, gained = self.xp + amount, self.level, []
        while level < MAX_LEVEL and xp >= xp_for_level(level):
            xp -= xp_for_level(level)
            level += 1
            gained.append(level)
        self._set(xp=xp, level=level)
        return gained

    def add_credits(self, amount: int) -> None:
        self._set(credits=max(0, self.credits + int(amount)))

    def spend_credits(self, amount: int) -> bool:
        if amount > self.credits:
            return False
        self._set(credits=self.credits - int(amount))
        return True

    def add_reputation(self, amount: int) -> None:
        self._set(reputation=max(0, min(100, self.reputation + int(amount))))

    def add_playtime(self, seconds: float) -> None:
        self._p["playtime"] = self.playtime + seconds  # flushed on save

    def flush(self) -> None:
        self.db.update_profile(playtime=self._p["playtime"])

    def count_mission(self, success: bool) -> None:
        key = "completed_missions" if success else "failed_missions"
        self._set(**{key: self._p[key] + 1})

    def set_ending(self, ending_id: str) -> None:
        self._set(ending=ending_id)

    # -- inventory -------------------------------------------------------
    def inventory(self) -> dict[str, int]:
        return self.db.get_inventory()

    def qty(self, item_id: str) -> int:
        return self.db.item_qty(item_id)

    def has(self, item_id: str, qty: int = 1) -> bool:
        return self.qty(item_id) >= qty

    def add_item(self, item_id: str, qty: int = 1) -> int:
        """Add items respecting the per-item cap. Returns the amount actually granted."""
        cap = self.data.items.get(item_id, {}).get("max_qty", 99)
        current = self.qty(item_id)
        granted = max(0, min(qty, cap - current))
        if granted:
            self.db.set_item(item_id, current + granted)
        return granted

    def remove_item(self, item_id: str, qty: int = 1) -> bool:
        current = self.qty(item_id)
        if current < qty:
            return False
        self.db.set_item(item_id, current - qty)
        return True

    # -- upgrades --------------------------------------------------------
    def upgrade_level(self, upgrade_id: str) -> int:
        return self.db.get_upgrade(upgrade_id)

    def upgrade_cost(self, upgrade_id: str) -> int | None:
        up = self.data.upgrades[upgrade_id]
        level = self.upgrade_level(upgrade_id)
        return None if level >= up["max_level"] else up["costs"][level]

    def buy_upgrade(self, upgrade_id: str) -> tuple[bool, str]:
        if upgrade_id not in self.data.upgrades:
            return False, "UNKNOWN UPGRADE"
        cost = self.upgrade_cost(upgrade_id)
        if cost is None:
            return False, "ALREADY AT MAXIMUM LEVEL"
        if not self.spend_credits(cost):
            return False, f"INSUFFICIENT CREDITS (need ${cost:,})"
        self.db.set_upgrade(upgrade_id, self.upgrade_level(upgrade_id) + 1)
        return True, f"{self.data.upgrades[upgrade_id]['name']} upgraded to level {self.upgrade_level(upgrade_id)}"

    # -- loadout gear ------------------------------------------------------
    def gear(self, stat: str) -> int:
        """Sum of a percentage stat over all equipped gear."""
        return sum(self.data.items.get(i, {}).get("stats", {}).get(stat, 0) for i in self.db.get_equipment().values())

    # -- upgrade + gear effects (single source of truth for all systems) --
    def _lv(self, upgrade_id: str) -> int:
        return self.upgrade_level(upgrade_id)

    @property
    def anim_factor(self) -> float:          # TERMINAL SPEED: shorter animations
        return 1.0 / (1.0 + 0.25 * self._lv("terminal_speed"))

    @property
    def firewall_extra_attempts(self) -> int:  # FIREWALL ANALYSIS + FIREWALL gear
        return (self._lv("firewall_analysis") + 1) // 2 + self.gear("firewall") // 15

    @property
    def firewall_reveals_one(self) -> bool:
        return self._lv("firewall_analysis") >= 5 or self.gear("firewall") >= 40

    @property
    def heat_factor(self) -> float:           # ENCRYPTION + STEALTH: less heat from mistakes
        return max(0.2, 1.0 - 0.1 * self._lv("encryption") - self.gear("stealth") / 100)

    @property
    def trace_speed_factor(self) -> float:    # TRACE upgrade + TRACE gear: slower stream
        factor = (1.0 - 0.08 * self._lv("trace")) * (0.8 if self.has("trace_module") else 1.0)
        return max(0.3, factor * (1.0 - self.gear("trace") / 100))

    @property
    def trace_extra_misses(self) -> int:
        return self._lv("trace") // 2 + (1 if self.has("trace_module") else 0) + self.gear("trace") // 20

    @property
    def route_budget_bonus(self) -> int:      # NETWORK upgrade + NETWORK gear
        return self._lv("network_access") // 2 + self.gear("network") // 20

    @property
    def network_level(self) -> int:
        return self._lv("network_access") + self.gear("network") // 25

    @property
    def storage_capacity(self) -> int:        # STORAGE: local file slots
        return 20 + 5 * self._lv("storage")

    @property
    def decrypt_free_hints(self) -> int:      # DECRYPTION + DECRYPT gear
        return self._lv("decryption") + (1 if self.has("encryption_key") else 0) + self.gear("decrypt") // 20

    @property
    def xp_multiplier(self) -> float:
        return 1.0 + self.gear("xp") / 100

    @property
    def income_multiplier(self) -> float:
        return 1.0 + self.gear("income") / 100
