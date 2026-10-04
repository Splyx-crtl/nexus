"""The v3 mission format: plain dataclasses, loadable from JSON, with no behaviour of their own beyond parsing/serialising.
Matching behaviour (checking a mission's objectives against the live shell) lives in ``runner.py`` on purpose, so this module
stays trivial to validate, generate and hand-author.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SIZES = ("mini", "standard", "story", "milestone")
ACTS = tuple(range(1, 10))                 # I..IX, see docs/story/02-acts-and-levels.md
HINT_TIERS = 3                              # nudge, tip, solution — docs/story/02-acts-and-levels.md §2 / 3.0-PROGRESS.md §C6


class MissionError(ValueError):
    """Raised by ``from_dict``/``Mission.__post_init__`` for a structurally broken mission; never raised by the validator,
    which instead collects a list of problems so an author sees all of them at once."""


@dataclass
class Objective:
    """One condition, checked against events the shell emits (``Ctx.event``/``Shell.emit`` — see nexus/shell/registry.py).

    ``match`` compares fields of the event's data dict. A plain value must equal exactly; a key suffixed ``__contains`` checks
    membership/substring; a key suffixed ``__glob`` checks a shell-style wildcard pattern (``fnmatch``). Example, "read any
    file under /var/log on the kali machine": ``{"event": "file_read", "match": {"path__glob": "/var/log/*", "machine": "kali"}}``.
    """
    event: str
    match: dict[str, Any] = field(default_factory=dict)
    text: str = ""                          # shown to the player in the objectives list
    hints: list[str] = field(default_factory=list)      # 0-3 tiers: nudge, tip, solution (docs/story/02-acts-and-levels.md §2)
    optional: bool = False                  # a bonus objective: does not block completion, usually gives extra reward
    count: int = 1                          # how many distinct matching events are needed (default: one is enough)
    id: str = ""                            # optional, for referencing from generators/tests; auto-filled if empty

    def __post_init__(self) -> None:
        if not self.event:
            raise MissionError("an objective needs an 'event' name")
        if self.count < 1:
            raise MissionError("an objective's 'count' must be at least 1")
        if len(self.hints) > HINT_TIERS:
            raise MissionError(f"an objective may have at most {HINT_TIERS} hint tiers, got {len(self.hints)}")


@dataclass
class Mission:
    id: str
    number: int                             # the player-facing level number, 1..200
    act: int                                # 1..9 (I..IX)
    size: str                               # one of SIZES
    title: str
    scenario: str                           # name registered in nexus/campaign/scenarios.py: builds the world/session
    objectives: list[Objective]
    briefing: list[str] = field(default_factory=list)      # "MIRA: ..." / "NEXUS: ..." lines, shown before the mission
    debrief: list[str] = field(default_factory=list)       # shown on completion
    solution: list[str] = field(default_factory=list)      # reference command lines; solver.py proves they complete it
    reward_xp: int = 0
    requires: list[str] = field(default_factory=list)      # ids of missions that must be completed first
    tags: list[str] = field(default_factory=list)          # free-form, e.g. "bash", "windows", "clue:2" (docs/story clue ledger)

    def __post_init__(self) -> None:
        if not self.id:
            raise MissionError("a mission needs an id")
        if self.size not in SIZES:
            raise MissionError(f"{self.id}: size must be one of {SIZES}, got {self.size!r}")
        if self.act not in ACTS:
            raise MissionError(f"{self.id}: act must be 1-9, got {self.act!r}")
        if self.number < 1:
            raise MissionError(f"{self.id}: number must be >= 1")
        if not self.objectives:
            raise MissionError(f"{self.id}: needs at least one objective")

    # -- (de)serialisation ---------------------------------------------------------------------------------------------
    @classmethod
    def from_dict(cls, data: dict) -> "Mission":
        try:
            objectives = [Objective(**o) for o in data.get("objectives", [])]
            return cls(**{**data, "objectives": objectives})
        except TypeError as exc:
            raise MissionError(f"{data.get('id', '?')}: {exc}") from exc

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)

    @property
    def required_objectives(self) -> list[Objective]:
        return [o for o in self.objectives if not o.optional]

    @property
    def bonus_objectives(self) -> list[Objective]:
        return [o for o in self.objectives if o.optional]
