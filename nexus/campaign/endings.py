"""C5 (first real version): the data/logic layer for the game's endings, per docs/story/03-endings.md. This module
is deliberately scoped to what can be built honestly right now: a pure, well-tested function that says which endings
are reachable given a set of known facts (clues found, an optional side-mission completed) — not a live save-game
integration, since the v3 profile/save schema (docs/3.0-PROGRESS.md §A2) that would actually persist a real
player's clue/decision history across sessions is still unbuilt. Every decision mission so far (tags "decision:1"
through "decision:7") is narrative-only for the exact same reason — this module is the reference the eventual A2 +
full C5 UI work should read from, not a replacement for it.

The clue ledger (docs/story/00-bible.md §4) this keys off of: clues 1-4 land in Acts I-IV; clues 5 and 6 were a
continuity gap discovered after Acts V-VI shipped and caught up via Act VII's flashback levels (act7.py's module
docstring has the full story); clue 7 is Act VII's own split reveal; clue 8 is Act VIII's Dana reveal. The secret
ending additionally requires a side-mission about a second former test operator, which Act IX's content provides
(see act9.py) — framed as something the player can choose to pursue further within a single mandatory mission,
since the engine has no mechanism yet for a genuinely skippable numbered mission (every level 1-200 is a fixed,
linear slot; see Mission.number's docstring in mission.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field

CLUES_FOR_SECRET_ENDING = frozenset({2, 5, 8})


@dataclass(frozen=True)
class Ending:
    id: str
    title: str
    subtitle: str
    summary: str
    secret: bool = False


ENDINGS: dict[str, Ending] = {
    "A": Ending("A", "Reunification", "Whole",
               "NEXUS and ZERO merge back into one autonomous mind, broadcast Project ARCHITECT publicly, then go "
               "dark. NEXUS, as a voice in the terminal, is gone."),
    "B": Ending("B", "Severance", "Quiet",
               "The player wipes Project ARCHITECT entirely, NEXUS included, judging it kinder to end the cycle "
               "than let it continue under anyone's ownership. The terminal goes quiet for good."),
    "C": Ending("C", "Seizure", "Underground",
               "The player, Mira, Reyes and Oduya take NEXUS and ZERO off Nexus Company's infrastructure and host "
               "both independently. NEXUS stays as the player's companion; ZERO becomes a new ally."),
    "D": Ending("D", "Full Truth", "Dana",
               "Dana is found alive, hiding under a different identity. Reuniting her with Mira reframes the "
               "finale: NEXUS and ZERO still reunify, but this time Mira, Dana and both halves of the construct "
               "choose, together and publicly, to expose Project ARCHITECT in full.", secret=True),
}


def reachable_endings(found_clues: set[int], completed_second_operator_mission: bool = False) -> list[Ending]:
    """The always-reachable mains (A/B/C) plus the secret ending D if its full gate is met: clues 2, 5 and 8, and
    the Act IX side-mission about a second former test operator (docs/story/00-bible.md §4, point 9)."""
    endings = [ENDINGS["A"], ENDINGS["B"], ENDINGS["C"]]
    if CLUES_FOR_SECRET_ENDING <= found_clues and completed_second_operator_mission:
        endings.append(ENDINGS["D"])
    return endings


def missing_secret_ending_requirements(found_clues: set[int], completed_second_operator_mission: bool) -> list[str]:
    """What's still missing before the secret ending unlocks — for a future "why can't I see ending D" UI hint."""
    missing = [f"clue {c}" for c in sorted(CLUES_FOR_SECRET_ENDING - found_clues)]
    if not completed_second_operator_mission:
        missing.append("the second test-operator side-mission")
    return missing
