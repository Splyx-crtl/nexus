"""MissionRunner: tracks a Mission's objectives against a live Shell in real time, by subscribing to the same event stream
the shell already emits for every command (``nexus/shell/registry.py``'s ``Ctx.event``/``Shell.emit``, consumed via the
``listener`` callback ``Shell.__init__`` already accepts). No polling, no re-parsing of output — objectives complete the
moment the matching event fires, same tick as the command that caused it.
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Callable

from ..shell import commands  # noqa: F401  (registers every bash/ps/cmd command on import — required before any Shell runs)
from ..shell.interp import Shell
from .mission import Mission, Objective
from .scenarios import SCENARIOS


def _matches(data: dict, match: dict) -> bool:
    for key, expected in match.items():
        if key.endswith("__contains"):
            field_name = key[: -len("__contains")]
            value = data.get(field_name)
            if value is None or expected not in value:
                return False
        elif key.endswith("__glob"):
            field_name = key[: -len("__glob")]
            value = data.get(field_name)
            if value is None or not fnmatch.fnmatch(str(value), expected):
                return False
        else:
            if data.get(key) != expected:
                return False
    return True


@dataclass
class ObjectiveState:
    objective: Objective
    hits: int = 0

    @property
    def done(self) -> bool:
        return self.hits >= self.objective.count


@dataclass
class MissionRunner:
    """Attach to a ``Shell`` (via its ``listener``) to track one mission's progress. Build with ``MissionRunner.start(mission)``,
    which also constructs the world/session/shell from the mission's scenario — the normal way to begin a mission in-game."""
    mission: Mission
    shell: Shell
    states: list[ObjectiveState] = field(default_factory=list)
    on_progress: Callable[[ObjectiveState], None] | None = None      # optional: UI hook, called whenever an objective advances
    _chain: Callable[[str, dict], None] | None = None

    def __post_init__(self) -> None:
        self.states = [ObjectiveState(o) for o in self.mission.objectives]
        self._chain = self.shell.listener
        self._bound = self._on_event          # a bound method is a fresh object on every access, so cache one for `is` checks
        self.shell.listener = self._bound

    @classmethod
    def start(cls, mission: Mission, level: Callable[[], int] = lambda: 10**6) -> "MissionRunner":
        build = SCENARIOS.get(mission.scenario)
        if build is None:
            raise KeyError(f"unknown scenario {mission.scenario!r} for mission {mission.id}")
        world, session = build()
        shell = Shell(world, session, level=level)
        return cls(mission, shell)

    def _on_event(self, event: str, data: dict) -> None:
        if self._chain is not None:
            self._chain(event, data)
        for state in self.states:
            if state.done or state.objective.event != event:
                continue
            if _matches(data, state.objective.match):
                state.hits += 1
                if self.on_progress:
                    self.on_progress(state)

    # -- queries, for the UI and the solver bot -----------------------------------------------------------------------
    @property
    def required_states(self) -> list[ObjectiveState]:
        return [s for s in self.states if not s.objective.optional]

    @property
    def bonus_states(self) -> list[ObjectiveState]:
        return [s for s in self.states if s.objective.optional]

    @property
    def is_complete(self) -> bool:
        return all(s.done for s in self.required_states)

    @property
    def missing(self) -> list[ObjectiveState]:
        return [s for s in self.required_states if not s.done]

    def progress(self) -> list[dict]:
        """[{text, done, optional}, ...] in authoring order — what a mission screen would render."""
        return [{"text": s.objective.text, "done": s.done, "optional": s.objective.optional} for s in self.states]

    def detach(self) -> None:
        """Stop tracking (restores whatever listener, if any, was on the shell before)."""
        if self.shell.listener is self._bound:
            self.shell.listener = self._chain
