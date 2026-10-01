"""Loader for the static JSON game data (servers, missions, items, ...)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .config import DATA_DIR, MISSIONS_DIR


class DataError(RuntimeError):
    """Raised when a game data file is missing or malformed."""


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError(f"Cannot load {path.name}: {exc}") from exc


class GameData:
    """All static data, loaded once and shared by every system."""

    def __init__(self, data_dir: Path = DATA_DIR, missions_dir: Path = MISSIONS_DIR):
        self.servers: dict[str, dict] = {s["id"]: s for s in _load_json(data_dir / "servers.json")["servers"]}
        extra = data_dir / "servers_extra.json"
        if extra.exists():
            for server in _load_json(extra)["servers"]:
                self.servers[server["id"]] = server
        users = _load_json(data_dir / "users.json")
        self.contacts: dict[str, dict] = {c["id"]: c for c in users["contacts"]}
        self.operators: list[dict] = users.get("operators", [])
        self.commands: list[dict] = _load_json(data_dir / "commands.json")["commands"]
        self.achievements: list[dict] = _load_json(data_dir / "achievements.json")["achievements"]
        self.items: dict[str, dict] = {i["id"]: i for i in _load_json(data_dir / "items.json")["items"]}
        for item in _load_json(data_dir / "market.json")["items"]:       # NEXUS MARKET catalogue
            self.items[item["id"]] = item
        self.themes: list[dict] = _load_json(data_dir / "themes.json")["themes"]
        self.chapters: list[dict] = _load_json(data_dir / "chapters.json")["chapters"]
        self.challenges: dict = _load_json(data_dir / "challenges.json")
        self.secrets: dict = _load_json(data_dir / "secrets.json")
        self.zero_stages: list[dict] = _load_json(data_dir / "zero.json")["stages"]
        self.upgrades: dict[str, dict] = {u["id"]: u for u in _load_json(data_dir / "items.json")["upgrades"]}
        events = _load_json(data_dir / "events.json")
        self.events: list[dict] = events["events"]
        self.endings: dict[str, dict] = {e["id"]: e for e in _load_json(data_dir / "endings.json")["endings"]}
        self.missions: list[dict] = sorted(
            (_load_json(p) for p in missions_dir.glob("mission_*.json")), key=lambda m: m["number"]
        )
        self.missions_by_id = {m["id"]: m for m in self.missions}
        self.tutorial: list[str] = _load_json(data_dir / "commands.json").get("tutorial", [])


@lru_cache(maxsize=1)
def get_data() -> GameData:
    return GameData()
