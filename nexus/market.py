"""NEXUS MARKET: catalogue, pricing, purchasing and the loadout (equipment) rules."""
from __future__ import annotations

import datetime as dt
import random
from typing import TYPE_CHECKING

from . import reputation

if TYPE_CHECKING:
    from .game_engine import GameEngine

CATEGORIES = ["TOOLS", "UPGRADES", "COSMETICS", "ACCESS", "INTELLIGENCE"]
RARITIES = ["COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY", "NEXUS"]
SLOTS = ["TRACE", "DECRYPT", "FIREWALL", "NETWORK", "UTILITY"]
SLOT_FLAGS = {"DECRYPT": "slot_decrypt", "NETWORK": "slot_network", "UTILITY": "slot_utility"}   # unlocked by chapters
STAT_LABELS = {"trace": "TRACE", "decrypt": "DECRYPT", "firewall": "FIREWALL", "network": "NETWORK",
               "stealth": "STEALTH", "xp": "XP", "income": "CREDITS"}
DAILY_DEAL_DISCOUNT = 0.20


def rarity_rank(r: str) -> int:
    return RARITIES.index(r.upper()) if r.upper() in RARITIES else 0


class Market:
    def __init__(self, engine: "GameEngine"):
        self.e = engine
        self.themes = {t["id"]: t for t in engine.data.themes}

    # ---------------------------------------------------------- catalogue --
    def _item_entries(self) -> list[dict]:
        out = []
        for item_id, it in self.e.data.items.items():
            if it.get("price"):
                out.append({**it, "id": item_id, "kind": it.get("kind", "consumable" if it.get("effect") not in (None, "passive") else "passive")})
        return out

    def _upgrade_entries(self) -> list[dict]:
        p = self.e.player
        out = []
        for uid, up in self.e.data.upgrades.items():
            lvl, cost = p.upgrade_level(uid), p.upgrade_cost(uid)
            out.append({"id": f"upgrade:{uid}", "name": f"{up['name']} (LV {lvl}/{up['max_level']})", "category": "UPGRADES",
                        "rarity": ["COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY", "NEXUS"][min(lvl, 5)],
                        "price": cost or 0, "level": 1 + lvl * 3, "kind": "upgrade", "upgrade_id": uid, "max_level": up["max_level"],
                        "short": up["description"], "description": up["description"], "maxed": cost is None})
        return out

    def _theme_entries(self) -> list[dict]:
        return []   # themes are regular items with kind == "theme" (market.json)

    def catalogue(self, category: str | None = None) -> list[dict]:
        entries = self._item_entries() + self._upgrade_entries()
        if category and category != "ALL":
            entries = [e for e in entries if e["category"] == category]
        ctx = {"deal": self.daily_deal_id(), "equipped": set(self.e.db.get_equipment().values()),
               "rep_mult": reputation.price_multiplier(self.e.player.reputation)}     # computed once, not per entry
        for entry in entries:
            self._decorate(entry, ctx)
        order = {c: i for i, c in enumerate(CATEGORIES)}
        return sorted(entries, key=lambda e: (order.get(e["category"], 99), e.get("level", 1), rarity_rank(e["rarity"]), e["base_price"]))

    def find(self, item_id: str) -> dict | None:
        for entry in self.catalogue():
            if entry["id"] == item_id or entry["name"].lower().replace(" ", "_") == item_id.lower():
                return entry
        return None

    def daily_deal_id(self) -> str | None:
        pool = [i["id"] for i in self._item_entries() if i["category"] in ("TOOLS", "INTELLIGENCE", "ACCESS")
                and not self.e.player.has(i["id"]) and i["price"] <= 60000]
        if not pool:
            return None
        day = self.e.progress.today() if hasattr(self.e, "progress") else dt.date.today()
        return random.Random(day.isoformat()).choice(sorted(pool))

    def price_of(self, entry: dict, ctx: dict | None = None) -> int:
        base = entry["price"]
        mult = ctx["rep_mult"] if ctx else reputation.price_multiplier(self.e.player.reputation)
        if entry["id"] == (ctx["deal"] if ctx else self.daily_deal_id()):
            mult *= 1 - DAILY_DEAL_DISCOUNT
        return max(0, int(round(base * mult)))

    def _decorate(self, entry: dict, ctx: dict | None = None) -> dict:
        p = self.e.player
        if ctx is None:
            ctx = {"deal": self.daily_deal_id(), "equipped": set(self.e.db.get_equipment().values()),
                   "rep_mult": reputation.price_multiplier(p.reputation)}
        entry["base_price"] = entry["price"]
        entry["final_price"] = self.price_of(entry, ctx)
        entry["deal"] = entry["id"] == ctx["deal"]
        entry["rarity"] = entry["rarity"].upper()
        entry["owned"] = self.is_owned(entry)
        entry["locked_level"] = p.level < entry.get("level", 1)
        entry["equipped"] = entry["id"] in ctx["equipped"]
        entry["stats_text"] = ", ".join(f"{STAT_LABELS[k]} +{v}%" for k, v in entry.get("stats", {}).items())
        return entry

    def is_owned(self, entry: dict) -> bool:
        kind = entry.get("kind")
        if kind == "theme":
            return self.e.db.is_unlocked(f"theme:{entry['theme']}")
        if kind == "upgrade":
            return entry.get("maxed", False)
        if kind in ("consumable", "passive", "gear", "access", "intel"):
            return self.e.player.qty(entry["id"]) >= entry.get("max_qty", 99) if entry.get("max_qty", 99) == 1 else False
        return False

    # ----------------------------------------------------------- purchase --
    def purchase(self, item_id: str) -> tuple[bool, str]:
        e, p = self.e, self.e.player
        entry = self.find(item_id)
        if entry is None:
            return False, "UNKNOWN ITEM"
        if entry.get("maxed"):
            return False, "ALREADY AT MAXIMUM LEVEL"
        if entry["locked_level"]:
            return False, f"LEVEL {entry['level']} REQUIRED"
        if entry["kind"] == "intel" and e.db.is_unlocked(f"intel:{entry['id']}"):
            return False, "ALREADY PURCHASED"
        if entry["kind"] != "upgrade" and entry["owned"]:
            return False, "ALREADY OWNED"
        if entry["kind"] in ("consumable", "passive") and p.qty(entry["id"]) >= entry.get("max_qty", 99):
            return False, "YOU CAN'T CARRY ANY MORE"
        price = entry["final_price"]
        if p.credits < price:
            return False, f"INSUFFICIENT CREDITS (need ${price:,})"
        if not e.spend_credits(price):
            return False, "INSUFFICIENT CREDITS"
        kind = entry["kind"]
        if kind == "upgrade":
            p.db.set_upgrade(entry["upgrade_id"], p.upgrade_level(entry["upgrade_id"]) + 1)
            e.bump("upgrades_bought")
            e.inventory_changed.emit()
        elif kind == "theme":
            e.unlock(f"theme:{entry['theme']}")
        else:
            e.grant_item(entry["id"], 1, announce=False)
            if kind == "intel":
                e.db.unlock(f"intel:{entry['id']}")
            self._on_buy(entry)
        e.bump("purchases")
        e.db.add_stat("market_spent", price)
        e.notify("ok", "ITEM PURCHASED", f"{entry['name']}  -${price:,}", sound="purchase")
        e.achievements.check()
        e.inventory_changed.emit()
        e.state_changed.emit()
        return True, f"PURCHASED: {entry['name']}  (-${price:,})"

    def _on_buy(self, entry: dict) -> None:
        fx = entry.get("on_buy")
        if not fx:
            return
        e = self.e
        for flag, value in fx.get("flags", {}).items():
            e.set_flag(flag, value)
        for sid in fx.get("discover", []):
            e.world.discover(sid)
        if "message" in fx:
            e.send_message(fx["message"]["from"], fx["message"]["text"])
        e.server_changed.emit()

    # ------------------------------------------------------------ loadout --
    def slot_unlocked(self, slot: str) -> bool:
        flag = SLOT_FLAGS.get(slot)
        return flag is None or bool(self.e.db.get_flag(flag))

    def equipped(self) -> dict[str, str]:
        return self.e.db.get_equipment()

    def equip(self, item_id: str) -> tuple[bool, str]:
        e = self.e
        item = e.data.items.get(item_id)
        if not item or item.get("kind") != "gear":
            return False, "THAT ITEM CAN'T BE EQUIPPED"
        if not e.player.has(item_id):
            return False, "YOU DON'T OWN THAT ITEM"
        slot = item["slot"]
        if not self.slot_unlocked(slot):
            return False, f"{slot} SLOT IS LOCKED (progress the story)"
        e.db.set_equipment(slot, item_id)
        e.bump("items_equipped")
        e.inventory_changed.emit()
        e.state_changed.emit()
        return True, f"EQUIPPED {item['name']} -> {slot}"

    def unequip(self, slot: str) -> tuple[bool, str]:
        slot = slot.upper()
        if slot not in SLOTS or slot not in self.e.db.get_equipment():
            return False, "NOTHING EQUIPPED IN THAT SLOT"
        self.e.db.set_equipment(slot, None)
        self.e.inventory_changed.emit()
        self.e.state_changed.emit()
        return True, f"{slot} SLOT CLEARED"

    def gear_stat(self, stat: str) -> int:
        total = 0
        for item_id in self.e.db.get_equipment().values():
            total += self.e.data.items.get(item_id, {}).get("stats", {}).get(stat, 0)
        return total

    def total_stats(self) -> dict[str, int]:
        return {k: self.gear_stat(k) for k in STAT_LABELS}
