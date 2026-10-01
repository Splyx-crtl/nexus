"""SQLite persistence layer. One database file == one operator profile."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    username TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    xp INTEGER NOT NULL DEFAULT 0,
    credits INTEGER NOT NULL DEFAULT 500,
    reputation INTEGER NOT NULL DEFAULT 10,
    completed_missions INTEGER NOT NULL DEFAULT 0,
    failed_missions INTEGER NOT NULL DEFAULT 0,
    playtime REAL NOT NULL DEFAULT 0,
    ending TEXT DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS inventory (item_id TEXT PRIMARY KEY, qty INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS missions (
    mission_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    progress TEXT NOT NULL DEFAULT '{}',
    result TEXT DEFAULT '',
    attempts INTEGER NOT NULL DEFAULT 0,
    started_at REAL,
    completed_at REAL
);
CREATE TABLE IF NOT EXISTS achievements (id TEXT PRIMARY KEY, unlocked_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS decisions (key TEXT PRIMARY KEY, value TEXT, mission_id TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS upgrades (id TEXT PRIMARY KEY, level INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS flags (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value REAL NOT NULL);
CREATE TABLE IF NOT EXISTS contacts (id TEXT PRIMARY KEY, trust INTEGER NOT NULL, met INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact TEXT NOT NULL,
    direction TEXT NOT NULL,
    text TEXT NOT NULL,
    ts REAL NOT NULL,
    read INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, content TEXT NOT NULL, source TEXT DEFAULT '', ts REAL);
CREATE TABLE IF NOT EXISTS world (key TEXT PRIMARY KEY, value TEXT);
"""


# Schema migrations: version -> SQL. Applied in order to every older save (a .bak copy is kept).
MIGRATIONS = {
    2: """
    CREATE TABLE IF NOT EXISTS equipment (slot TEXT PRIMARY KEY, item_id TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, level INTEGER, xp_total REAL,
        credits_earned REAL, missions INTEGER, playtime REAL, achievements INTEGER
    );
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, kind TEXT, title TEXT, text TEXT
    );
    CREATE TABLE IF NOT EXISTS unlocks (key TEXT PRIMARY KEY, ts REAL NOT NULL);
    """,
}


class Database:
    """Thin, explicit wrapper around one SQLite profile file."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existed = self.path.exists() and self.path.stat().st_size > 0
        self._last_commit = 0.0
        self._dirty = False
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA synchronous=NORMAL")       # fast commits; still safe against app crashes
        self.conn.executescript(SCHEMA)
        self.migrated_from: int | None = None
        self._migrate(existed)

    def _migrate(self, existed: bool) -> None:
        """Bring any older save up to SCHEMA_VERSION without losing data."""
        row = self.conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        version = json.loads(row["value"]) if row else (1 if existed else 0)
        if version < SCHEMA_VERSION and existed:
            self.migrated_from = version
            backup = self.path.with_suffix(f".v{version}.bak")
            if not backup.exists():
                try:
                    self.backup_to(backup)
                except (sqlite3.Error, OSError):
                    pass
        for target in range(version + 1, SCHEMA_VERSION + 1):
            if target in MIGRATIONS:
                self.conn.executescript(MIGRATIONS[target])
        self._set_meta("schema_version", SCHEMA_VERSION)
        self.conn.commit()

    # -- lifecycle -----------------------------------------------------
    def _commit(self) -> None:
        """Throttled commit: at most one fsync per half second (flush() forces it)."""
        now = time.monotonic()
        if now - self._last_commit >= 0.5:
            self.conn.commit()
            self._last_commit, self._dirty = now, False
        else:
            self._dirty = True

    def flush(self) -> None:
        if self._dirty:
            self.conn.commit()
            self._dirty = False
            self._last_commit = time.monotonic()

    def close(self) -> None:
        try:
            self.conn.commit()
            self.conn.close()
        except sqlite3.Error:
            pass

    def backup_to(self, target: Path | str) -> None:
        """Consistent copy of the live database (used for manual save slots)."""
        self.conn.commit()
        dest = sqlite3.connect(str(target))
        try:
            self.conn.backup(dest)
        finally:
            dest.close()

    # -- generic helpers -----------------------------------------------
    def _set_meta(self, key: str, value: Any) -> None:
        self.conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)", (key, json.dumps(value)))

    def get_meta(self, key: str, default: Any = None) -> Any:
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def set_meta(self, key: str, value: Any) -> None:
        self._set_meta(key, value)
        self._commit()

    def _kv_get(self, table: str, key: str, default: Any = None) -> Any:
        row = self.conn.execute(f"SELECT value FROM {table} WHERE key=?", (key,)).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except (TypeError, json.JSONDecodeError):
            return default

    def _kv_set(self, table: str, key: str, value: Any) -> None:
        self.conn.execute(f"INSERT OR REPLACE INTO {table}(key, value) VALUES(?, ?)", (key, json.dumps(value)))
        self._commit()

    # -- profile -------------------------------------------------------
    def create_profile(self, username: str) -> dict:
        now = time.time()
        self.conn.execute(
            "INSERT OR IGNORE INTO profile(id, username, created_at, updated_at) VALUES(1, ?, ?, ?)",
            (username, now, now),
        )
        self._commit()
        return self.get_profile()

    def has_profile(self) -> bool:
        return self.conn.execute("SELECT 1 FROM profile WHERE id=1").fetchone() is not None

    def get_profile(self) -> dict:
        row = self.conn.execute("SELECT * FROM profile WHERE id=1").fetchone()
        return dict(row) if row else {}

    _PROFILE_FIELDS = {
        "username", "level", "xp", "credits", "reputation", "completed_missions",
        "failed_missions", "playtime", "ending",
    }

    def update_profile(self, **fields: Any) -> None:
        fields = {k: v for k, v in fields.items() if k in self._PROFILE_FIELDS}
        fields["updated_at"] = time.time()
        sets = ", ".join(f"{k}=?" for k in fields)
        self.conn.execute(f"UPDATE profile SET {sets} WHERE id=1", list(fields.values()))
        self._commit()

    # -- flags / stats / world ----------------------------------------
    def get_flag(self, key: str, default: Any = None) -> Any:
        return self._kv_get("flags", key, default)

    def set_flag(self, key: str, value: Any = True) -> None:
        self._kv_set("flags", key, value)

    def all_flags(self) -> dict[str, Any]:
        return {r["key"]: json.loads(r["value"]) for r in self.conn.execute("SELECT * FROM flags")}

    def get_stat(self, key: str, default: float = 0) -> float:
        row = self.conn.execute("SELECT value FROM stats WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_stat(self, key: str, value: float) -> None:
        self.conn.execute("INSERT OR REPLACE INTO stats(key, value) VALUES(?, ?)", (key, value))
        self._commit()

    def add_stat(self, key: str, amount: float = 1) -> float:
        value = self.get_stat(key) + amount
        self.set_stat(key, value)
        return value

    def all_stats(self) -> dict[str, float]:
        return {r["key"]: r["value"] for r in self.conn.execute("SELECT * FROM stats")}

    def get_world(self, key: str, default: Any = None) -> Any:
        return self._kv_get("world", key, default)

    def set_world(self, key: str, value: Any) -> None:
        self._kv_set("world", key, value)

    # -- inventory -----------------------------------------------------
    def get_inventory(self) -> dict[str, int]:
        return {r["item_id"]: r["qty"] for r in self.conn.execute("SELECT * FROM inventory WHERE qty > 0")}

    def set_item(self, item_id: str, qty: int) -> None:
        if qty <= 0:
            self.conn.execute("DELETE FROM inventory WHERE item_id=?", (item_id,))
        else:
            self.conn.execute("INSERT OR REPLACE INTO inventory(item_id, qty) VALUES(?, ?)", (item_id, qty))
        self._commit()

    # -- upgrades ------------------------------------------------------
    def get_upgrade(self, upgrade_id: str) -> int:
        row = self.conn.execute("SELECT level FROM upgrades WHERE id=?", (upgrade_id,)).fetchone()
        return row["level"] if row else 0

    def set_upgrade(self, upgrade_id: str, level: int) -> None:
        self.conn.execute("INSERT OR REPLACE INTO upgrades(id, level) VALUES(?, ?)", (upgrade_id, level))
        self._commit()

    # -- missions ------------------------------------------------------
    def active_mission_id(self) -> str | None:
        row = self.conn.execute("SELECT mission_id FROM missions WHERE status='active' LIMIT 1").fetchone()
        return row["mission_id"] if row else None

    def get_mission(self, mission_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM missions WHERE mission_id=?", (mission_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["progress"] = json.loads(data["progress"] or "{}")
        return data

    def save_mission(self, mission_id: str, status: str, progress: dict, result: str = "",
                     started_at: float | None = None, completed_at: float | None = None,
                     attempts: int | None = None) -> None:
        old = self.get_mission(mission_id)
        started = started_at if started_at is not None else (old or {}).get("started_at")
        completed = completed_at if completed_at is not None else (old or {}).get("completed_at")
        att = attempts if attempts is not None else (old or {}).get("attempts", 0)
        self.conn.execute(
            "INSERT OR REPLACE INTO missions(mission_id, status, progress, result, attempts, started_at, completed_at)"
            " VALUES(?, ?, ?, ?, ?, ?, ?)",
            (mission_id, status, json.dumps(progress), result, att, started, completed),
        )
        self._commit()

    def all_missions(self) -> dict[str, dict]:
        out = {}
        for row in self.conn.execute("SELECT * FROM missions"):
            data = dict(row)
            data["progress"] = json.loads(data["progress"] or "{}")
            out[data["mission_id"]] = data
        return out

    # -- decisions -----------------------------------------------------
    def set_decision(self, key: str, value: str, mission_id: str = "") -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO decisions(key, value, mission_id, ts) VALUES(?, ?, ?, ?)",
            (key, value, mission_id, time.time()),
        )
        self._commit()

    def get_decisions(self) -> dict[str, str]:
        return {r["key"]: r["value"] for r in self.conn.execute("SELECT * FROM decisions")}

    # -- achievements --------------------------------------------------
    def unlock_achievement(self, ach_id: str) -> bool:
        cur = self.conn.execute("INSERT OR IGNORE INTO achievements(id, unlocked_at) VALUES(?, ?)", (ach_id, time.time()))
        self._commit()
        return cur.rowcount > 0

    def get_achievements(self) -> dict[str, float]:
        return {r["id"]: r["unlocked_at"] for r in self.conn.execute("SELECT * FROM achievements")}

    # -- contacts / messages -------------------------------------------
    def get_contact(self, contact_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM contacts WHERE id=?", (contact_id,)).fetchone()
        return dict(row) if row else None

    def set_contact(self, contact_id: str, trust: int, met: int = 1) -> None:
        self.conn.execute("INSERT OR REPLACE INTO contacts(id, trust, met) VALUES(?, ?, ?)", (contact_id, trust, met))
        self._commit()

    def all_contacts(self) -> dict[str, dict]:
        return {r["id"]: dict(r) for r in self.conn.execute("SELECT * FROM contacts")}

    def add_message(self, contact: str, direction: str, text: str, read: bool = False) -> None:
        self.conn.execute(
            "INSERT INTO messages(contact, direction, text, ts, read) VALUES(?, ?, ?, ?, ?)",
            (contact, direction, text, time.time(), 1 if read else 0),
        )
        self._commit()

    def get_messages(self, contact: str, limit: int = 60) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM messages WHERE contact=? ORDER BY id DESC LIMIT ?", (contact, limit)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def unread_count(self, contact: str | None = None) -> int:
        if contact:
            row = self.conn.execute(
                "SELECT COUNT(*) c FROM messages WHERE contact=? AND direction='in' AND read=0", (contact,)
            ).fetchone()
        else:
            row = self.conn.execute("SELECT COUNT(*) c FROM messages WHERE direction='in' AND read=0").fetchone()
        return row["c"]

    def mark_read(self, contact: str) -> None:
        self.conn.execute("UPDATE messages SET read=1 WHERE contact=?", (contact,))
        self._commit()

    # -- local files ---------------------------------------------------
    def get_local_files(self) -> dict[str, dict]:
        return {r["path"]: dict(r) for r in self.conn.execute("SELECT * FROM files ORDER BY path")}

    def put_local_file(self, path: str, content: str, source: str = "") -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO files(path, content, source, ts) VALUES(?, ?, ?, ?)",
            (path, content, source, time.time()),
        )
        self._commit()

    def delete_local_file(self, path: str) -> None:
        self.conn.execute("DELETE FROM files WHERE path=?", (path,))
        self._commit()

    # -- equipment (loadout) ---------------------------------------------
    def get_equipment(self) -> dict[str, str]:
        return {r["slot"]: r["item_id"] for r in self.conn.execute("SELECT * FROM equipment")}

    def set_equipment(self, slot: str, item_id: str | None) -> None:
        if item_id is None:
            self.conn.execute("DELETE FROM equipment WHERE slot=?", (slot,))
        else:
            self.conn.execute("INSERT OR REPLACE INTO equipment(slot, item_id) VALUES(?, ?)", (slot, item_id))
        self._commit()

    # -- unlocks (themes, market access, secret content) -------------------
    def unlock(self, key: str) -> bool:
        cur = self.conn.execute("INSERT OR IGNORE INTO unlocks(key, ts) VALUES(?, ?)", (key, time.time()))
        self._commit()
        return cur.rowcount > 0

    def is_unlocked(self, key: str) -> bool:
        return self.conn.execute("SELECT 1 FROM unlocks WHERE key=?", (key,)).fetchone() is not None

    def unlocks(self, prefix: str = "") -> list[str]:
        rows = self.conn.execute("SELECT key FROM unlocks WHERE key LIKE ? ORDER BY ts", (prefix + "%",)).fetchall()
        return [r["key"] for r in rows]

    # -- history (statistics charts) ---------------------------------------
    def add_history(self, level: int, xp_total: float, credits_earned: float, missions: int,
                    playtime: float, achievements: int) -> None:
        self.conn.execute(
            "INSERT INTO history(ts, level, xp_total, credits_earned, missions, playtime, achievements) VALUES(?,?,?,?,?,?,?)",
            (time.time(), level, xp_total, credits_earned, missions, playtime, achievements))
        self._commit()

    def get_history(self, limit: int = 200) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in reversed(rows)]

    # -- notification log --------------------------------------------------
    def add_notification(self, kind: str, title: str, text: str) -> None:
        self.conn.execute("INSERT INTO notifications(ts, kind, title, text) VALUES(?,?,?,?)", (time.time(), kind, title, text))
        self.conn.execute("DELETE FROM notifications WHERE id NOT IN (SELECT id FROM notifications ORDER BY id DESC LIMIT 200)")
        self._commit()

    def get_notifications(self, limit: int = 60) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM notifications ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
