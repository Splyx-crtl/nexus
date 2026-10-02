"""Structural checks for a v3 mission, beyond what ``Mission.__post_init__`` already enforces. Returns every problem found
instead of raising on the first one, so an author (or the generator) sees the whole list at once. Does NOT check that a
mission is actually solvable — that needs a live shell and is ``solver.py``'s job."""
from __future__ import annotations

from .mission import Mission, Objective
from .scenarios import SCENARIOS

KNOWN_EVENTS = {
    "command", "command_not_found", "command_locked", "cd", "ls", "create", "delete", "mkdir", "chmod", "copy", "move",
    "file_read", "file_identified", "grep_match", "found", "man_read", "process_killed", "host_discovered", "ping",
    "http_fetch", "sudo_list", "sudo_denied", "sudo_used", "ssh_login", "ssh_failed", "scp", "session_start", "session_end",
}


def validate_objective(mission_id: str, index: int, o: Objective) -> list[str]:
    problems = []
    where = f"{mission_id}: objective {index} ({o.event})"
    if o.event not in KNOWN_EVENTS:
        problems.append(f"{where}: unknown event name (not emitted anywhere in nexus/shell) — typo, or add it to KNOWN_EVENTS "
                        f"once a command actually emits it")
    for key in o.match:
        if key.endswith(("__contains", "__glob")) and "__" in key[:-10]:
            problems.append(f"{where}: suspicious match key {key!r}")
    if not o.text:
        problems.append(f"{where}: no player-facing 'text' — the objectives list would show a blank line")
    if not o.hints:
        problems.append(f"{where}: no hints (warning, not blocking — fine for a first draft, but C6's hint system needs them)")
    return problems


def validate_mission(m: Mission) -> list[str]:
    """[] when the mission is structurally sound. Construction-time errors already raised via MissionError; this catches
    the rest: unknown scenario, dangling requirements, duplicate objective ids, and the per-objective checks above."""
    problems: list[str] = []
    if m.scenario not in SCENARIOS:
        problems.append(f"{m.id}: unknown scenario {m.scenario!r} (not registered in nexus/campaign/scenarios.py)")
    if not m.solution:
        problems.append(f"{m.id}: no reference 'solution' — the solver bot cannot prove this mission is completable")
    seen_ids = set()
    for i, o in enumerate(m.objectives):
        oid = o.id or f"{m.id}#{i}"
        if oid in seen_ids:
            problems.append(f"{m.id}: duplicate objective id {oid!r}")
        seen_ids.add(oid)
        problems.extend(validate_objective(m.id, i, o))
    if m.reward_xp < 0:
        problems.append(f"{m.id}: reward_xp must not be negative")
    return problems


def validate_all(missions: list[Mission]) -> dict[str, list[str]]:
    """{mission_id: [problems]} for every mission that has at least one problem, plus cross-mission checks
    (duplicate ids/numbers, 'requires' pointing at a mission that doesn't exist)."""
    by_id = {m.id for m in missions}
    numbers: dict[int, list[str]] = {}
    out: dict[str, list[str]] = {}
    for m in missions:
        problems = validate_mission(m)
        numbers.setdefault(m.number, []).append(m.id)
        for req in m.requires:
            if req not in by_id:
                problems.append(f"{m.id}: requires unknown mission {req!r}")
        if problems:
            out[m.id] = problems
    for number, ids in numbers.items():
        if len(ids) > 1:
            for mid in ids:
                out.setdefault(mid, []).append(f"{mid}: level number {number} is shared with {[i for i in ids if i != mid]}")
    return out
