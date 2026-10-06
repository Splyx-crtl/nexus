"""F1's "daily challenge with seed": a deterministic endless op that's the same for every player on the same
calendar day, built on top of F2's endless.py (see that module's own docstring: "ties into the existing F1 backlog
item"). Deliberately pure client-side, no server round-trip - the whole game is offline-first, and a hash of the
date is exactly as fair and exactly as tamper-resistant as a server-issued seed would be here (there's nothing to
cheat: it's a fixed daily puzzle, not a competitive score).
"""
from __future__ import annotations

import hashlib
from datetime import date, timezone, datetime


def today() -> date:
    """UTC, not local time, so every player's "today" lines up regardless of timezone."""
    return datetime.now(timezone.utc).date()


def daily_seed(day: date | None = None) -> int:
    """A deterministic 32-bit seed from a calendar date. Same date -> same seed, always."""
    day = day or today()
    digest = hashlib.sha256(day.isoformat().encode()).hexdigest()
    return int(digest[:8], 16)


def daily_mission_id(day: date | None = None) -> str:
    return f"daily_{(day or today()).isoformat()}"
