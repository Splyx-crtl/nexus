"""Reputation: a 0-100 standing that colours prices, missions and NPC attitudes."""
from __future__ import annotations

STATUSES = [
    (0, "UNPROVEN"),
    (20, "RECOGNIZED"),
    (40, "RELIABLE OPERATOR"),
    (60, "TRUSTED OPERATOR"),
    (80, "ELITE ASSET"),
    (95, "LEGEND"),
]


def status(rep: int) -> str:
    name = STATUSES[0][1]
    for threshold, label in STATUSES:
        if rep >= threshold:
            name = label
    return name


def price_multiplier(rep: int) -> float:
    """Better standing = cheaper market (brokers like reliable customers)."""
    if rep < 10:
        return 1.10
    if rep < 40:
        return 1.00
    if rep < 60:
        return 0.97
    if rep < 80:
        return 0.94
    if rep < 95:
        return 0.90
    return 0.85


def describe(rep: int) -> str:
    mult = price_multiplier(rep)
    if mult == 1.0:
        return "Standard market prices."
    pct = round(abs(1 - mult) * 100)
    return f"Market prices {'+' if mult > 1 else '-'}{pct}%."
