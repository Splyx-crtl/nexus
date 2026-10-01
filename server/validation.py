"""Plausibility checks for submitted scores.

IMPORTANT: scores come from the player's own computer, so they can never be fully trusted. These checks only stop
obviously impossible values (level 999, going backwards, huge jumps). Truly secure rankings would need the server to
run the game logic itself. Keep this in mind when you decide what the leaderboard may reward.
"""
from __future__ import annotations

MAX_LEVEL = 100
MAX_MISSIONS = 100_000          # contracts are endless, so this is generous
MIN_SUBMIT_INTERVAL = 15        # seconds between two score submissions
MAX_XP_PER_SECOND = 120         # generous upper bound for earned XP per second between submissions
MAX_CREDITS_PER_SECOND = 600


def cumulative_xp(level: int) -> int:
    """Total XP needed to reach ``level`` (same curve as the game: 100 + 40 * level per level)."""
    return sum(100 + 40 * l for l in range(1, max(1, level)))


class Rejected(ValueError):
    pass


def validate(new: dict, old: dict | None, seconds_since_last: float | None) -> dict:
    """Return the cleaned score dict or raise ``Rejected`` with a user-friendly reason."""
    try:
        clean = {k: int(new[k]) for k in ("level", "xp_total", "missions", "credits_earned", "perfect", "playtime", "ng_plus")}
    except (KeyError, TypeError, ValueError):
        raise Rejected("Malformed score data.")
    rank = str(new.get("rank", ""))[:24]
    if any(v < 0 for v in clean.values()):
        raise Rejected("Negative values are not allowed.")
    if not 1 <= clean["level"] <= MAX_LEVEL:
        raise Rejected("Level out of range.")
    if clean["missions"] > MAX_MISSIONS or clean["perfect"] > clean["missions"]:
        raise Rejected("Mission counts are inconsistent.")
    if clean["xp_total"] < int(0.9 * cumulative_xp(clean["level"])):
        raise Rejected("XP does not match the level.")
    if clean["ng_plus"] > 50:
        raise Rejected("New Game+ count out of range.")
    if old:
        if seconds_since_last is not None and seconds_since_last < MIN_SUBMIT_INTERVAL:
            raise Rejected("Too many submissions — slow down.")
        elapsed = max(1.0, seconds_since_last or 1.0)
        for key in ("xp_total", "missions", "credits_earned", "playtime", "level"):
            if clean[key] < old[key]:
                raise Rejected(f"{key} cannot go backwards.")
        if clean["xp_total"] - old["xp_total"] > 20_000 + MAX_XP_PER_SECOND * elapsed:
            raise Rejected("XP gain is implausibly large.")
        if clean["credits_earned"] - old["credits_earned"] > 40_000 + MAX_CREDITS_PER_SECOND * elapsed:
            raise Rejected("Credit gain is implausibly large.")
    clean["rank"] = rank
    return clean
