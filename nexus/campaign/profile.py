"""A2: the v3 save/profile adapter. Deliberately built on the EXISTING generic SQLite tables in ``nexus/database.py``
(``profile``, ``missions``, ``decisions``, ``flags``, ``world``) rather than a new schema migration — they already
cover everything the roadmap's A2 item asks for (character, mode, language, level 200, learning progress), once read
through this adapter:

- **Level** is not a separate XP-driven curve in v3. The campaign is strictly linear — ``Mission.number`` IS the
  level, one mission per number, 1..200 (see mission.py's own docstring) — so "current level" is simply "the number
  of the next not-yet-completed mission whose prerequisites are met," derived live from the ``missions`` table
  rather than stored independently. ``profile.level`` is still written on every completion (for cheap reads, e.g.
  a menu card), but it is a cache of that derived value, never the source of truth.
- **XP** (``profile.xp``) is cosmetic in v3: a running total of ``reward_xp`` across completed missions, shown as a
  sense of progress, not something that gates anything (unlike 2.x's ``nexus/player.py``, where XP literally drives
  level-ups against ``nexus/config.py``'s curve — that system stays untouched for 2.x saves).
- **Command unlocks** need no storage at all: ``nexus/shell/registry.py``'s ``unlock_level`` is checked live against
  the derived level above, exactly as the solver bot already does.
- **Clues / the secret ending / decisions** read the ``tags`` of completed ``Mission`` objects (``"clue:N"``,
  ``"secret-ending-track"``, ``"decision:N"``) against the ``missions`` table's completion status, and feed
  ``nexus/campaign/endings.py``'s ``reachable_endings()`` — this is the live wiring that module's own docstring
  said was still missing.
- **Character / mode** go in the generic ``world``/``flags`` kv tables; **language** already has a home in
  ``SettingsStore`` (``nexus/config.py``'s ``DEFAULT_SETTINGS["language"]``), app-level rather than per-profile,
  which is correct since the setting is chosen before any profile exists.

A v3 profile is distinguished from a 2.x one by a single flag, ``campaign_v3`` — docs/3.0-PROGRESS.md's A3 decision
("full replacement, no classic mode, old saves archived not migrated") is implemented as: a profile without this
flag is a 2.x save and is left to the existing 2.x code path entirely; ``migrate.py`` (this package) handles
archiving one and creating a fresh v3 profile in its place.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from . import endings
from .progression import MAX_LEVEL, rank_for_level

if TYPE_CHECKING:
    from ..database import Database
    from .mission import Mission


class CampaignProfile:
    """Adapter between a ``Database`` and the v3 campaign (``nexus.campaign.content.ALL_MISSIONS``)."""

    def __init__(self, db: "Database"):
        self.db = db

    # -- level / xp / rank --------------------------------------------------------------------------------------
    @property
    def level(self) -> int:
        return self.db.get_profile().get("level") or 1

    @property
    def xp(self) -> int:
        return self.db.get_profile().get("xp") or 0

    @property
    def username(self) -> str:
        return self.db.get_profile().get("username") or ""

    @property
    def rank(self) -> str:
        return rank_for_level(self.level)

    @property
    def completed_count(self) -> int:
        return self.db.get_profile().get("completed_missions") or 0

    # -- mission progress -----------------------------------------------------------------------------------------
    def completed_mission_ids(self) -> set[str]:
        return {mid for mid, m in self.db.all_missions().items() if m["status"] == "completed"}

    def is_completed(self, mission_id: str) -> bool:
        return self.db.mission_status(mission_id) == "completed"

    def is_unlocked(self, mission: "Mission") -> bool:
        """Every prerequisite already completed — does not mean it IS the next mission, just that it could be
        played (useful for a future free-replay/mission-select screen, C7)."""
        done = self.completed_mission_ids()
        return all(r in done for r in mission.requires)

    def next_mission(self, all_missions: list["Mission"]) -> "Mission | None":
        """The one mission the player should be doing right now: the lowest-numbered incomplete mission whose
        prerequisites are all met. ``None`` once all 200 are done."""
        done = self.completed_mission_ids()
        candidates = [m for m in all_missions if m.id not in done and all(r in done for r in m.requires)]
        return min(candidates, key=lambda m: m.number) if candidates else None

    def complete_mission(self, mission: "Mission", all_missions: list["Mission"]) -> None:
        """Record a mission as done, add its XP, and advance ``level`` to the next unlocked mission's number (or
        MAX_LEVEL once the campaign is finished)."""
        if self.is_completed(mission.id):
            return
        self.db.save_mission(mission.id, "completed", {}, completed_at=time.time())
        profile = self.db.get_profile()
        self.db.update_profile(
            completed_missions=(profile.get("completed_missions") or 0) + 1,
            xp=(profile.get("xp") or 0) + mission.reward_xp,
        )
        nxt = self.next_mission(all_missions)
        self.db.update_profile(level=nxt.number if nxt else MAX_LEVEL)

    def is_campaign_complete(self, all_missions: list["Mission"]) -> bool:
        return self.next_mission(all_missions) is None

    # -- clues / endings (C5 live wiring) --------------------------------------------------------------------------
    def found_clues(self, all_missions: list["Mission"]) -> set[int]:
        done = self.completed_mission_ids()
        return {int(t.split(":")[1]) for m in all_missions if m.id in done for t in m.tags if t.startswith("clue:")}

    def secret_ending_unlocked(self, all_missions: list["Mission"]) -> bool:
        done = self.completed_mission_ids()
        return any(m.id in done and "secret-ending-track" in m.tags for m in all_missions)

    def reachable_endings(self, all_missions: list["Mission"]) -> list[endings.Ending]:
        return endings.reachable_endings(self.found_clues(all_missions), self.secret_ending_unlocked(all_missions))

    def set_ending(self, ending_id: str) -> None:
        self.db.update_profile(ending=ending_id)

    # -- decisions (decision:1 .. decision:8) ----------------------------------------------------------------------
    def record_decision(self, tag: str, answer: str, mission_id: str = "") -> None:
        self.db.set_decision(tag, answer, mission_id)

    def get_decision(self, tag: str) -> str | None:
        return self.db.get_decisions().get(tag)

    # -- mode / character (A6, C6) ----------------------------------------------------------------------------------
    def get_mode(self) -> str:
        """'guided' | 'medium' | 'hardcore' — docs/story/02-acts-and-levels.md §2."""
        return self.db.get_flag("campaign_mode", "guided")

    def set_mode(self, mode: str) -> None:
        self.db.set_flag("campaign_mode", mode)

    def get_character(self) -> dict:
        return self.db.get_world("character") or {"name": "", "look": ""}

    def set_character(self, name: str, look: str = "") -> None:
        self.db.set_world("character", {"name": name, "look": look})

    # -- v3 identity ------------------------------------------------------------------------------------------------
    @staticmethod
    def is_v3(db: "Database") -> bool:
        return bool(db.get_flag("campaign_v3"))

    @staticmethod
    def init_v3(db: "Database", username: str) -> "CampaignProfile":
        db.create_profile(username)
        db.update_profile(level=1, xp=0, completed_missions=0)
        db.set_flag("campaign_v3", True)
        return CampaignProfile(db)
