"""The solver bot: proves a mission is actually completable by replaying its authored reference ``solution`` (a list of
command lines) against a fresh instance of its scenario, and checking every required objective fired. This is "der Bot, der
jede Mission löst" from docs/3.0-PROGRESS.md §C2 — run it after writing or editing any mission, and in CI once there is one.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .mission import Mission
from .runner import MissionRunner


@dataclass
class SolveResult:
    mission_id: str
    ok: bool
    missing: list[str] = field(default_factory=list)     # objective texts that never fired
    error: str | None = None                             # set if a solution line crashed the shell/threw an exception
    transcript: list[tuple[str, str]] = field(default_factory=list)    # (command, combined stdout+stderr) for debugging

    def __bool__(self) -> bool:
        return self.ok


def solve(mission: Mission, level=None) -> SolveResult:
    """Run ``mission.solution`` line by line and check the mission completed. A line that fails (non-zero exit) does not
    stop the run — a solution is allowed to probe or fail a step before correcting itself, same as a real player — but a
    Python exception while running it is treated as a bug and reported immediately.

    ``level`` defaults to the mission's own ``number``: this proves the mission is solvable by a player who has progressed
    *exactly* to this level, no further — not by someone who (like an unrestricted test harness) already has every command
    unlocked. That distinction matters: a mission whose solution needs a command gated to a higher level than the mission's
    own number is unsolvable for a real player, and would only have been caught by this, not by an unlimited-level run."""
    level = level or (lambda: mission.number)
    try:
        runner = MissionRunner.start(mission, level=level)
    except KeyError as exc:
        return SolveResult(mission.id, False, error=str(exc))
    transcript: list[tuple[str, str]] = []
    try:
        for line in mission.solution:
            result = runner.shell.run(line)
            transcript.append((line, result.text))
    except Exception as exc:                                          # a crash in the engine itself, not a wrong command
        return SolveResult(mission.id, False, error=f"{type(exc).__name__}: {exc}", transcript=transcript)
    missing = [s.objective.text or s.objective.event for s in runner.missing]
    return SolveResult(mission.id, runner.is_complete, missing=missing, transcript=transcript)


def solve_all(missions: list[Mission], level=None) -> dict[str, SolveResult]:
    """{mission_id: SolveResult} for every mission — the batch check a pre-release test (or CI) should run."""
    return {m.id: solve(m, level=level) for m in missions}
