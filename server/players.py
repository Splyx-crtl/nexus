"""Pure helpers for the admin player database: validating admin edits, cleaning the extra save details a game sends,
and the account/key status rules. No web framework and no database in here, so it is easy to test."""
from __future__ import annotations

import re
from typing import Any

from .validation import MAX_LEVEL

ACCOUNT_STATUSES = ("active", "disabled", "banned")
RESETS = ("missions", "inventory", "heat")
MAX_CREDITS = 1_000_000_000
SAFE_ID = re.compile(r"^[A-Za-z0-9_.:\-]{1,48}$")


class EditError(ValueError):
    """The admin asked for something that is not allowed; the text is shown to the admin as-is."""


def xp_for_level(level: int) -> int:
    """XP needed to go from ``level`` to the next one (same curve as the game)."""
    return 100 + 40 * max(1, level)


def _int(value: Any, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
        raise EditError(f"{name} must be a whole number.")
    value = int(value)
    if not low <= value <= high:
        raise EditError(f"{name} must be between {low:,} and {high:,}.")
    return value


def validate_edit(data: dict, score: dict | None) -> dict:
    """Turn the admin's request into a clean set of changes ('ops'). ``score`` = the player's stored score row (or None)."""
    unknown = set(data) - {"level", "xp", "credits", "reputation", "reset", "reason"}
    if unknown:
        raise EditError("Unknown field: " + ", ".join(sorted(unknown)))
    ops: dict[str, Any] = {}
    if data.get("level") is not None:
        ops["level"] = _int(data["level"], "Level", 1, MAX_LEVEL)
        ops["xp"] = 0
    if data.get("xp") is not None:
        level = ops.get("level") or (score or {}).get("level")
        if not level:
            raise EditError("This player has not synced a save yet.")
        ops["level"] = level
        ops["xp"] = _int(data["xp"], "XP", 0, xp_for_level(level) - 1)
    if data.get("credits") is not None:
        ops["credits"] = _int(data["credits"], "Credits", 0, MAX_CREDITS)
    if data.get("reputation") is not None:
        ops["reputation"] = _int(data["reputation"], "Reputation", 0, 100)
    resets = data.get("reset") or []
    if not isinstance(resets, list) or any(r not in RESETS for r in resets):
        raise EditError("Unknown reset. Allowed: " + ", ".join(RESETS) + ".")
    if resets:
        ops["reset"] = sorted(set(resets))
    if not ops:
        raise EditError("Nothing to change.")
    if score is None:
        raise EditError("This player has not synced a save yet, so there is nothing to edit.")
    return ops


def clean_details(raw: Any) -> dict:
    """The optional save details a game sends with its score (balance, reputation, achievements, unlocks, counters).
    Anything malformed is dropped silently: a strange value must never block a player's leaderboard sync."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    for key, high in (("credits", MAX_CREDITS), ("reputation", 100), ("heat", 100)):
        value = raw.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out[key] = max(0, min(high, int(value)))
    for key in ("achievements", "unlocks"):
        items = raw.get(key)
        if isinstance(items, list):
            out[key] = [i for i in items if isinstance(i, str) and SAFE_ID.match(i)][:250]
    stats = raw.get("stats")
    if isinstance(stats, dict):
        out["stats"] = {k: max(0, min(10**12, int(v))) for k, v in list(stats.items())[:120]
                        if isinstance(k, str) and SAFE_ID.match(k) and isinstance(v, (int, float)) and not isinstance(v, bool)}
    return out


def key_status(row: dict, now: float) -> str:
    """unused / in use / revoked / expired. Expiry only matters for redeeming: a key that is already in use keeps working."""
    if row["revoked"]:
        return "revoked"
    if row["discord_id"]:
        return "in use"
    if row.get("expires_at") and row["expires_at"] < now:
        return "expired"
    return "unused"


def mask_key(tail: str) -> str:
    return f"NX-*****-*****-{tail}"
