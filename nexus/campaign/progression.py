"""A2: the 3.0.0 progression constants — a separate table from ``nexus/config.py``'s 2.x numbers, which stay
untouched for the shipped 2.x game (docs/story/02-acts-and-levels.md §5's own note). 200 levels, the nine-act rank
table from docs/story/02-acts-and-levels.md §3, and the proposed XP curve from §5 (``80 + 15 * level``, "an
engineering default, not a creative decision — tune later via playtesting, G1").
"""
from __future__ import annotations

MAX_LEVEL = 200

# (level at which the rank takes effect, rank name) — matches the "Rank earned" column of the acts table. A rank is
# earned at the END of the act named, so it reads from the level right after that act's milestone.
RANKS: list[tuple[int, str]] = [
    (1, "SCRIPT KIDDIE"),
    (21, "TRACER"),
    (46, "NETRUNNER"),
    (71, "CRYPTOSMITH"),
    (96, "GHOST"),
    (121, "ENGINEER"),
    (146, "SENTINEL"),
    (186, "ARCHITECT"),
    (200, "NEXUS"),
]


def xp_for_level(level: int) -> int:
    """XP required to advance from ``level`` to ``level + 1``."""
    return 80 + 15 * max(1, level)


def rank_for_level(level: int) -> str:
    rank = RANKS[0][1]
    for min_level, name in RANKS:
        if level >= min_level:
            rank = name
    return rank
