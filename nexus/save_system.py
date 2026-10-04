"""Profile / save-slot management and persistent user settings."""
from __future__ import annotations

import json
import shutil
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from .campaign.progression import rank_for_level as _rank_for_level_v3
from .config import DEFAULT_SETTINGS, PROFILES_DIR, SAVES_DIR, SETTINGS_FILE, SLOTS_DIR, rank_for_level
from .database import Database
from .security import safe_filename

SLOT_COUNT = 3


@dataclass
class SaveInfo:
    path: Path
    username: str
    level: int
    rank: str
    playtime: float
    updated_at: float
    completed: int
    kind: str          # "profile" | "slot"
    slot: int = 0

    @property
    def label(self) -> str:
        return f"{self.username}  LV{self.level}  {self.rank}"


class SettingsStore:
    """JSON-backed global settings (volume, display, text speed, ...)."""

    def __init__(self, path: Path = SETTINGS_FILE):
        self.path = path
        self.values: dict = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> None:
        try:
            stored = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                self.values.update({k: v for k, v in stored.items() if k in DEFAULT_SETTINGS})
        except (OSError, json.JSONDecodeError):
            pass

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.values, indent=2), encoding="utf-8")
        except OSError:
            pass

    def get(self, key: str):
        return self.values.get(key, DEFAULT_SETTINGS.get(key))

    def set(self, key: str, value) -> None:
        self.values[key] = value
        self.save()


class SaveSystem:
    """Creates, lists, snapshots and restores operator profiles."""

    def __init__(self, profiles_dir: Path = PROFILES_DIR, slots_dir: Path = SLOTS_DIR):
        self.profiles_dir = profiles_dir
        self.slots_dir = slots_dir
        SAVES_DIR.mkdir(parents=True, exist_ok=True)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.slots_dir.mkdir(parents=True, exist_ok=True)

    # -- reading metadata ----------------------------------------------
    @staticmethod
    def _read_info(path: Path, kind: str, slot: int = 0) -> SaveInfo | None:
        try:
            conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM profile WHERE id=1").fetchone()
            flag_row = conn.execute("SELECT value FROM flags WHERE key='campaign_v3'").fetchone()
            conn.close()
        except sqlite3.Error:
            return None
        if row is None:
            return None
        is_v3 = bool(flag_row and json.loads(flag_row["value"]))
        rank = _rank_for_level_v3(row["level"]) if is_v3 else rank_for_level(row["level"])
        return SaveInfo(path, row["username"], row["level"], rank, row["playtime"],
                        row["updated_at"], row["completed_missions"], kind, slot)

    def list_profiles(self) -> list[SaveInfo]:
        infos = [self._read_info(p, "profile") for p in self.profiles_dir.glob("*.db")]
        return sorted((i for i in infos if i), key=lambda i: i.updated_at, reverse=True)

    def list_slots(self) -> list[SaveInfo]:
        infos = []
        for p in self.slots_dir.glob("*__slot*.db"):
            try:
                slot = int(p.stem.rsplit("__slot", 1)[1])
            except ValueError:
                continue
            info = self._read_info(p, "slot", slot)
            if info:
                infos.append(info)
        return sorted(infos, key=lambda i: i.updated_at, reverse=True)

    def latest_profile(self) -> SaveInfo | None:
        profiles = self.list_profiles()
        return profiles[0] if profiles else None

    # -- profiles ------------------------------------------------------
    def create_profile(self, username: str) -> Database:
        stem = safe_filename(username)
        path = self.profiles_dir / f"{stem}.db"
        counter = 2
        while path.exists():
            path = self.profiles_dir / f"{stem}_{counter}.db"
            counter += 1
        db = Database(path)
        db.create_profile(username)
        return db

    def open_profile(self, path: Path) -> Database:
        db = Database(path)
        if not db.has_profile():
            raise ValueError("Save file has no profile")
        return db

    def delete_profile(self, path: Path) -> None:
        stem = Path(path).stem
        Path(path).unlink(missing_ok=True)
        for slot in self.slots_dir.glob(f"{stem}__slot*.db"):
            slot.unlink(missing_ok=True)

    # -- manual slots --------------------------------------------------
    def slot_path(self, profile_path: Path, slot: int) -> Path:
        return self.slots_dir / f"{Path(profile_path).stem}__slot{slot}.db"

    def save_slot(self, db: Database, slot: int) -> Path:
        """Snapshot the live profile into a manual slot ([ SAVE GAME ])."""
        db.update_profile()  # touch updated_at
        target = self.slot_path(db.path, slot)
        db.backup_to(target)
        return target

    def load_slot(self, slot_path: Path) -> Database:
        """Restore a slot over its parent profile and open it ([ LOAD GAME ])."""
        stem = Path(slot_path).stem.rsplit("__slot", 1)[0]
        target = self.profiles_dir / f"{stem}.db"
        shutil.copyfile(slot_path, target)
        return self.open_profile(target)

    @staticmethod
    def format_time(seconds: float) -> str:
        seconds = int(seconds)
        return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"

    @staticmethod
    def format_date(ts: float) -> str:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
