"""The simulated cyber world: servers, virtual file systems and session state.

Everything here is pure data manipulation - there is no real network access.
"""
from __future__ import annotations

import posixpath
import time
from dataclasses import dataclass, field
from typing import Callable

from .data import GameData
from .database import Database

ROLE_LEVELS = {"public": 0, "user": 1, "admin": 2}
ROLE_NAMES = {0: "guest", 1: "user", 2: "admin"}
SECURITY_HEAT = {"LOW": 0.6, "MEDIUM": 1.0, "HIGH": 1.4, "CRITICAL": 1.9}


@dataclass
class FileNode:
    name: str
    path: str
    is_dir: bool
    content: str = ""
    children: dict[str, "FileNode"] = field(default_factory=dict)
    access: str = "user"
    hidden: bool = False
    secret: bool = False
    encrypted: dict | None = None
    on_read: dict | None = None
    requires: dict | None = None
    grants_item: str | None = None

    @property
    def key(self) -> str:
        return self.path


def _build_node(name: str, path: str, raw, parent_access: str) -> FileNode:
    """Convert raw JSON into a FileNode tree. Dicts with 'content' are files, others directories."""
    if isinstance(raw, (str, list)):
        text = "\n".join(raw) if isinstance(raw, list) else raw
        return FileNode(name, path, False, text, access=parent_access, hidden=name.startswith("."))
    if "content" in raw and isinstance(raw["content"], (str, list)):
        text = raw["content"]
        text = "\n".join(text) if isinstance(text, list) else text
        return FileNode(
            name, path, False, text,
            access=raw.get("access", parent_access),
            hidden=raw.get("hidden", name.startswith(".")),
            secret=raw.get("secret", False),
            encrypted=raw.get("encrypted"),
            on_read=raw.get("on_read"),
            requires=raw.get("requires"),
            grants_item=raw.get("grants_item"),
        )
    access = raw.get("_access", parent_access)
    node = FileNode(name, path, True, access=access, hidden=raw.get("_hidden", name.startswith(".")),
                    requires=raw.get("_requires"), secret=raw.get("_secret", False))
    for child_name, child_raw in raw.items():
        if child_name.startswith("_"):
            continue
        child_path = posixpath.join(path, child_name)
        node.children[child_name] = _build_node(child_name, child_path, child_raw, access)
    return node


class Server:
    """Immutable description of a simulated host."""

    def __init__(self, raw: dict):
        self.raw = raw
        self.id: str = raw["id"]
        self.name: str = raw["name"]
        self.ip: str = raw["ip"]
        self.description: str = raw.get("description", "")
        self.services: list[str] = raw.get("services", [])
        self.ports: list[dict] = raw.get("ports", [])
        self.security: str = raw.get("security", "LOW")
        self.firewall: dict = raw.get("firewall", {"enabled": False})
        self.routing: dict | None = raw.get("routing")
        self.auth: dict = raw.get("auth", {"mode": "none"})
        self.motd: list[str] = raw.get("motd", [])
        self.links: list[str] = raw.get("links", [])
        self.pos: list[float] = raw.get("pos", [0.5, 0.5])
        self.trace: dict | None = raw.get("trace")
        self.requires_item: str | None = raw.get("requires_item")
        self.region: str = raw.get("region", "GRID")
        self.root = _build_node("", "/", raw.get("fs", {}), "user")
        self.root.access = "public"   # the root listing is always visible

    @property
    def heat_mult(self) -> float:
        return SECURITY_HEAT.get(self.security, 1.0)


class World:
    """Runtime state of the simulated network plus the player's connection."""

    def __init__(self, data: GameData, db: Database):
        self.data = data
        self.db = db
        self.servers: dict[str, Server] = {sid: Server(raw) for sid, raw in data.servers.items()}
        self.condition: Callable[[dict], bool] = lambda req: True   # set by the engine
        self.current: str | None = db.get_world("current")
        self.roles: dict[str, int] = db.get_world("roles", {})
        self.cwd: str = db.get_world("cwd", "/")
        self.local_cwd: str = ""
        if self.current and self.current not in self.servers:
            self.current = None

    # -- persistent sets --------------------------------------------------
    def _get_set(self, key: str) -> list:
        return self.db.get_world(key, [])

    def _add_to_set(self, key: str, value) -> bool:
        items = self._get_set(key)
        if value in items:
            return False
        items.append(value)
        self.db.set_world(key, items)
        return True

    def discovered(self) -> list[str]:
        return self._get_set("discovered")

    def is_discovered(self, sid: str) -> bool:
        return sid in self._get_set("discovered")

    def discover(self, sid: str) -> bool:
        return sid in self.servers and self._add_to_set("discovered", sid)

    def is_breached(self, sid: str) -> bool:
        return sid in self._get_set("breached")

    def set_breached(self, sid: str) -> None:
        self._add_to_set("breached", sid)

    def rearm_firewall(self, sid: str) -> bool:
        items = self._get_set("breached")
        if sid in items:
            items.remove(sid)
            self.db.set_world("breached", items)
            return True
        return False

    def is_routed(self, sid: str) -> bool:
        return sid in self._get_set("routed")

    def set_routed(self, sid: str) -> None:
        self._add_to_set("routed", sid)

    def is_decrypted(self, sid: str, path: str) -> bool:
        return f"{sid}:{path}" in self._get_set("decrypted")

    def set_decrypted(self, sid: str, path: str) -> None:
        self._add_to_set("decrypted", f"{sid}:{path}")

    def mark_compromised(self, sid: str) -> None:
        self._add_to_set("compromised", sid)

    def is_compromised(self, sid: str) -> bool:
        return sid in self._get_set("compromised")

    def mark_once(self, key: str) -> bool:
        """Returns True the first time ``key`` is seen (for one-shot rewards)."""
        return self._add_to_set("once", key)

    def seen_once(self, key: str) -> bool:
        return key in self._get_set("once")

    # -- online / offline ---------------------------------------------------
    def offline_map(self) -> dict[str, float]:
        now = time.time()
        raw = self.db.get_world("offline", {})
        live = {k: v for k, v in raw.items() if v > now}
        if live != raw:
            self.db.set_world("offline", live)
        return live

    def is_online(self, sid: str) -> bool:
        return sid not in self.offline_map()

    def set_online(self, sid: str) -> None:
        raw = self.offline_map()
        if raw.pop(sid, None) is not None:
            self.db.set_world("offline", raw)

    def set_offline(self, sid: str, seconds: float) -> None:
        raw = self.offline_map()
        raw[sid] = time.time() + seconds
        self.db.set_world("offline", raw)

    # -- lookup -------------------------------------------------------------
    def find(self, query: str) -> Server | None:
        q = query.strip().lower()
        for server in self.servers.values():
            if q in (server.id.lower(), server.name.lower(), server.ip):
                return server
        return None

    @property
    def server(self) -> Server | None:
        return self.servers.get(self.current) if self.current else None

    # -- session --------------------------------------------------------------
    def role(self, sid: str | None = None) -> int:
        sid = sid or self.current
        return self.roles.get(sid, 0) if sid else 0

    def set_role(self, sid: str, role: int) -> None:
        self.roles[sid] = max(self.roles.get(sid, 0), role)
        self._persist_session()

    def connect(self, sid: str) -> None:
        self.current = sid
        self.cwd = "/"
        server = self.servers[sid]
        self.roles[sid] = 1 if server.auth.get("mode", "none") == "none" else 0
        self._persist_session()

    def disconnect(self) -> None:
        self.current = None
        self.roles = {}
        self.cwd = "/"
        self._persist_session()

    def logout(self) -> None:
        if self.current:
            self.roles[self.current] = 0
            self.cwd = "/"
            self._persist_session()

    def _persist_session(self) -> None:
        self.db.set_world("current", self.current)
        self.db.set_world("roles", self.roles)
        self.db.set_world("cwd", self.cwd)

    def set_cwd(self, path: str) -> None:
        self.cwd = path
        self.db.set_world("cwd", path)

    # -- remote file system ---------------------------------------------------
    def resolve(self, path: str, cwd: str | None = None) -> str:
        cwd = cwd or self.cwd
        path = path.replace("\\", "/")
        full = path if path.startswith("/") else posixpath.join(cwd, path)
        return posixpath.normpath(full) or "/"

    def node_at(self, server: Server, path: str) -> FileNode | None:
        node = server.root
        for part in [p for p in path.split("/") if p]:
            if not node.is_dir or part not in node.children:
                return None
            node = node.children[part]
            if node.requires and not self.condition(node.requires):
                return None
        return node

    def list_dir(self, server: Server, path: str, show_hidden: bool = False) -> list[FileNode] | None:
        node = self.node_at(server, path)
        if node is None or not node.is_dir:
            return None
        out = []
        for child in node.children.values():
            if child.requires and not self.condition(child.requires):
                continue
            if child.hidden and not show_hidden:
                continue
            out.append(child)
        return sorted(out, key=lambda n: (not n.is_dir, n.name.lower()))

    def can_access(self, node: FileNode, role: int | None = None) -> bool:
        role = self.role() if role is None else role
        return ROLE_LEVELS.get(node.access, 1) <= role or node.access == "public"

    def all_files(self, server: Server) -> list[FileNode]:
        found: list[FileNode] = []

        def walk(node: FileNode):
            for child in node.children.values():
                if child.requires and not self.condition(child.requires):
                    continue
                if child.is_dir:
                    walk(child)
                else:
                    found.append(child)

        walk(server.root)
        return found

    def count_secrets(self) -> int:
        return sum(1 for s in self.servers.values() for f in self.all_files(s) if f.secret)


class LocalFS:
    """The operator's own machine: a tiny virtual home directory stored in SQLite."""

    HOME = "~"

    def __init__(self, db: Database):
        self.db = db

    def files(self) -> dict[str, dict]:
        return self.db.get_local_files()

    def resolve(self, cwd: str, path: str) -> str:
        path = path.strip()
        if path in ("", "~", "/"):
            return ""
        if path.startswith("~/"):
            path = path[2:]
        elif not path.startswith("/") and cwd:
            path = posixpath.join(cwd, path)
        norm = posixpath.normpath(path.lstrip("/"))
        return "" if norm in (".", "") else norm

    def list_dir(self, path: str) -> list[tuple[str, bool]]:
        prefix = path + "/" if path else ""
        entries: dict[str, bool] = {}
        for full in self.files():
            if not full.startswith(prefix):
                continue
            rest = full[len(prefix):]
            head, _, tail = rest.partition("/")
            entries[head] = entries.get(head, False) or bool(tail)
        if not path:
            entries.setdefault("downloads", True)
        return sorted(entries.items(), key=lambda e: (not e[1], e[0].lower()))

    def is_dir(self, path: str) -> bool:
        if path in ("", "downloads"):
            return True
        prefix = path + "/"
        return any(f.startswith(prefix) for f in self.files())

    def read(self, path: str) -> str | None:
        entry = self.files().get(path)
        return entry["content"] if entry else None

    def download_count(self) -> int:
        return sum(1 for p in self.files() if p.startswith("downloads/"))
