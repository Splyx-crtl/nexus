"""Virtual file system for the simulated machines (Linux and Windows flavour).

Pure Python, no Qt, no real files: every path lives in memory. Permissions follow the real model closely enough to be
instructive: owner/group/mode bits on Linux, simplified ACLs (profile folders, protected system folders, per-node ACL) on Windows.
"""
from __future__ import annotations

import fnmatch
import re
import time
from dataclasses import dataclass, field
from typing import Iterator

# errno-like codes with the exact wording of the real tools
ERRORS = {
    "ENOENT": "No such file or directory",
    "EACCES": "Permission denied",
    "EEXIST": "File exists",
    "ENOTDIR": "Not a directory",
    "EISDIR": "Is a directory",
    "ENOTEMPTY": "Directory not empty",
    "EINVAL": "Invalid argument",
    "ELOOP": "Too many levels of symbolic links",
}


class FsError(Exception):
    def __init__(self, code: str, path: str = ""):
        super().__init__(f"{path}: {ERRORS.get(code, code)}" if path else ERRORS.get(code, code))
        self.code, self.path = code, path

    @property
    def text(self) -> str:
        return ERRORS.get(self.code, self.code)


@dataclass
class User:
    name: str
    uid: int = 1000
    gid: int = 1000
    groups: tuple[str, ...] = ()
    home: str = ""
    shell: str = "/bin/bash"
    admin: bool = False                 # root on Linux, member of Administrators on Windows
    password: str = ""                  # plain text on purpose: this is a game world, brute-force tools need something to find
    locked: bool = False

    @property
    def is_root(self) -> bool:
        return self.uid == 0 or self.admin


@dataclass
class Node:
    name: str
    kind: str = "file"                  # file | dir | link
    owner: str = "root"
    group: str = "root"
    mode: int = 0o644
    mtime: float = 0.0
    content: str | bytes = ""
    children: dict[str, "Node"] = field(default_factory=dict)
    target: str = ""                    # symlink target
    acl: dict[str, str] | None = None   # Windows: {user or group: 'r' | 'rw' | 'rwx' | ''}; None = inherit the default rules
    meta: dict = field(default_factory=dict)      # game data: encrypted payload, hash, etc.

    @property
    def is_dir(self) -> bool:
        return self.kind == "dir"

    @property
    def size(self) -> int:
        if self.kind == "dir":
            return 4096
        return len(self.content) if isinstance(self.content, (str, bytes)) else 0


class VFS:
    """A tree of Nodes with absolute canonical paths (``/etc/passwd`` or ``C:\\Users\\bob``)."""

    MAX_LINKS = 8

    def __init__(self, flavor: str = "posix", clock=time.time):
        if flavor not in ("posix", "windows"):
            raise ValueError("flavor must be 'posix' or 'windows'")
        self.flavor = flavor
        self.clock = clock
        self.sep = "/" if flavor == "posix" else "\\"
        self.case_sensitive = flavor == "posix"
        self.root = Node("", "dir", "root", "root", 0o755, clock())
        self.groups_of: dict[str, tuple[str, ...]] = {}      # filled by the machine: user name -> groups
        if flavor == "windows":
            self.root.children = {}

    # ------------------------------------------------------------------ paths
    def _key(self, name: str) -> str:
        return name if self.case_sensitive else name.lower()

    def split(self, path: str) -> list[str]:
        """Path -> list of components (drive letter kept as first component on Windows)."""
        if self.flavor == "windows":
            path = path.replace("/", "\\")
            parts = [p for p in path.split("\\") if p != ""]
            return parts
        return [p for p in path.split("/") if p != ""]

    def absolute(self, path: str, cwd: str = "") -> list[str]:
        """Canonical component list for ``path`` relative to ``cwd`` ('.' and '..' resolved, symlinks NOT followed here)."""
        if self.flavor == "windows":
            p = path.replace("/", "\\")
            if re.match(r"^[A-Za-z]:", p):
                comps = self.split(p)
            elif p.startswith("\\"):
                base = self.split(cwd)
                comps = [base[0] if base else "C:"] + self.split(p)       # \dir = on the current drive
            else:
                comps = self.split(cwd) + self.split(p)
            if comps and re.match(r"^[A-Za-z]:$", comps[0]):
                comps[0] = comps[0].upper()
        else:
            comps = (self.split(cwd) if not path.startswith("/") else []) + self.split(path)
        out: list[str] = []
        for comp in comps:
            if comp == ".":
                continue
            if comp == "..":
                if out and not (self.flavor == "windows" and len(out) == 1 and re.match(r"^[A-Za-z]:$", out[0])):
                    out.pop()
                continue
            out.append(comp)
        return out

    def join(self, comps: list[str]) -> str:
        if self.flavor == "windows":
            if not comps:
                return "\\"
            drive = comps[0]
            return drive + "\\" + "\\".join(comps[1:]) if len(comps) > 1 else drive + "\\"
        return "/" + "/".join(comps)

    def norm(self, path: str, cwd: str = "") -> str:
        return self.join(self.absolute(path, cwd))

    def basename(self, path: str) -> str:
        comps = self.split(path)
        return comps[-1] if comps else self.sep

    def dirname(self, path: str) -> str:
        comps = self.absolute(path)
        return self.join(comps[:-1]) if comps else self.sep

    # ------------------------------------------------------------- permissions
    def _in_group(self, user: User, group: str) -> bool:
        return group in user.groups or group == user.name

    def can(self, user: User | None, node: Node, perm: str, path: str = "") -> bool:
        """perm: 'r', 'w' or 'x'. ``user`` None = the system itself (always allowed)."""
        if user is None:
            return True
        if self.flavor == "posix":
            if user.is_root:
                return perm != "x" or node.is_dir or bool(node.mode & 0o111)
            shift = 6 if node.owner == user.name else (3 if self._in_group(user, node.group) else 0)
            return bool((node.mode >> shift) & {"r": 4, "w": 2, "x": 1}[perm])
        # Windows: simplified but recognisable
        if user.is_root or user.name.lower() == "system":
            return True
        if node.acl is not None:
            for who, rights in node.acl.items():
                if who.lower() == user.name.lower() or who.lower() in (g.lower() for g in user.groups) or who.lower() == "everyone":
                    return perm in rights
            return False
        low = path.lower()
        mine = f"\\users\\{user.name.lower()}"
        if "\\users\\" in low and mine not in low and not low.endswith("\\users") and "\\users\\public" not in low:
            return False                                       # other people's profile folders
        if perm == "w" and (low.startswith(("c:\\windows", "c:\\program files")) or low == "c:\\"):
            return False
        return True

    # ------------------------------------------------------------------ lookup
    def _child(self, node: Node, name: str) -> Node | None:
        if self.case_sensitive:
            return node.children.get(name)
        for key, child in node.children.items():
            if key.lower() == name.lower():
                return child
        return None

    def _walk(self, comps: list[str], follow_last: bool, depth: int = 0) -> tuple[Node | None, str]:
        """Walk from the root. Returns (node or None, canonical path string)."""
        node, path = self.root, []
        queue = list(comps)
        while queue:
            name = queue.pop(0)
            if not node.is_dir:
                raise FsError("ENOTDIR", self.join(path))
            child = self._child(node, name)
            if child is None:
                return None, self.join(path + [name] + queue)
            if child.kind == "link" and (queue or follow_last):
                depth += 1
                if depth > self.MAX_LINKS:
                    raise FsError("ELOOP", self.join(path + [name]))
                target = self.absolute(child.target, self.join(path))
                queue = target + queue
                node, path = self.root, []
                continue
            node, path = child, path + [child.name if child.name else name]
        return node, self.join(path)

    def lookup(self, path: str, cwd: str = "", follow: bool = True) -> Node | None:
        node, _ = self._walk(self.absolute(path, cwd), follow)
        return node

    def exists(self, path: str, cwd: str = "") -> bool:
        try:
            return self.lookup(path, cwd) is not None
        except FsError:
            return False

    def _need_search(self, user: User | None, comps: list[str], path_for_error: str) -> None:
        """Every directory on the way must be searchable (x) like in a real file system."""
        node, walked = self.root, []
        for name in comps[:-1]:
            if not self.can(user, node, "x", self.join(walked) or self.sep):
                raise FsError("EACCES", path_for_error)
            nxt = self._child(node, name)
            if nxt is None or not nxt.is_dir:
                return
            node, walked = nxt, walked + [name]
        if comps and not self.can(user, node, "x", self.join(walked) or self.sep):
            raise FsError("EACCES", path_for_error)

    # ----------------------------------------------------------------- reading
    def stat(self, user: User | None, path: str, cwd: str = "", follow: bool = True) -> Node:
        comps = self.absolute(path, cwd)
        shown = path
        self._need_search(user, comps, shown)
        node, canon = self._walk(comps, follow)
        if node is None:
            raise FsError("ENOENT", shown)
        return node

    def read(self, user: User | None, path: str, cwd: str = "") -> str | bytes:
        node = self.stat(user, path, cwd)
        if node.is_dir:
            raise FsError("EISDIR", path)
        if not self.can(user, node, "r", self.norm(path, cwd)):
            raise FsError("EACCES", path)
        return node.content

    def listdir(self, user: User | None, path: str, cwd: str = "") -> list[Node]:
        node = self.stat(user, path, cwd)
        if not node.is_dir:
            raise FsError("ENOTDIR", path)
        if not self.can(user, node, "r", self.norm(path, cwd)):
            raise FsError("EACCES", path)
        return sorted(node.children.values(), key=lambda n: n.name.lower())

    def walk(self, path: str, cwd: str = "") -> Iterator[tuple[str, Node]]:
        """Depth-first iterator over (canonical path, node), the start node included. System access (no permission checks)."""
        start = self.lookup(path, cwd)
        if start is None:
            return
        base = self.norm(path, cwd)

        def rec(p: str, n: Node):
            yield p, n
            if n.is_dir:
                for child in sorted(n.children.values(), key=lambda c: c.name.lower()):
                    yield from rec(self.join(self.absolute(child.name, p)) if p else child.name, child)
        yield from rec(base, start)

    # ----------------------------------------------------------------- writing
    def _parent_for(self, user: User | None, path: str, cwd: str) -> tuple[Node, str, str]:
        comps = self.absolute(path, cwd)
        if not comps:
            raise FsError("EEXIST", path)
        self._need_search(user, comps, path)
        parent, _ = self._walk(comps[:-1], True)
        if parent is None:
            raise FsError("ENOENT", path)
        if not parent.is_dir:
            raise FsError("ENOTDIR", path)
        return parent, comps[-1], self.join(comps[:-1])

    def write(self, user: User | None, path: str, data: str | bytes, cwd: str = "", append: bool = False, mode: int = 0o644) -> Node:
        parent, name, parent_path = self._parent_for(user, path, cwd)
        existing = self._child(parent, name)
        full = self.norm(path, cwd)
        if existing is not None:
            if existing.kind == "link":
                existing = self.lookup(path, cwd)
                if existing is None:
                    raise FsError("ENOENT", path)
            if existing.is_dir:
                raise FsError("EISDIR", path)
            if not self.can(user, existing, "w", full):
                raise FsError("EACCES", path)
            if append and isinstance(existing.content, str) and isinstance(data, str):
                existing.content += data
            else:
                existing.content = data
            existing.mtime = self.clock()
            return existing
        if not self.can(user, parent, "w", parent_path):
            raise FsError("EACCES", path)
        owner = user.name if user else "root"
        group = (user.groups[0] if user and user.groups else owner)
        node = Node(name, "file", owner, group, mode, self.clock(), data)
        parent.children[name if self.case_sensitive else name] = node
        parent.mtime = self.clock()
        return node

    def mkdir(self, user: User | None, path: str, cwd: str = "", parents: bool = False, mode: int = 0o755) -> Node:
        comps = self.absolute(path, cwd)
        if parents:
            node, walked = self.root, []
            for name in comps:
                child = self._child(node, name)
                if child is None:
                    if not self.can(user, node, "w", self.join(walked) or self.sep):
                        raise FsError("EACCES", path)
                    child = Node(name, "dir", user.name if user else "root", (user.groups[0] if user and user.groups else "root"), mode, self.clock())
                    node.children[name] = child
                elif not child.is_dir:
                    raise FsError("ENOTDIR", path)
                node, walked = child, walked + [name]
            return node
        parent, name, parent_path = self._parent_for(user, path, cwd)
        if self._child(parent, name) is not None:
            raise FsError("EEXIST", path)
        if not self.can(user, parent, "w", parent_path):
            raise FsError("EACCES", path)
        node = Node(name, "dir", user.name if user else "root", (user.groups[0] if user and user.groups else "root"), mode, self.clock())
        parent.children[name] = node
        parent.mtime = self.clock()
        return node

    def remove(self, user: User | None, path: str, cwd: str = "", recursive: bool = False) -> None:
        parent, name, parent_path = self._parent_for(user, path, cwd)
        node = self._child(parent, name)
        if node is None:
            raise FsError("ENOENT", path)
        if not self.can(user, parent, "w", parent_path):
            raise FsError("EACCES", path)
        if node.is_dir and node.children and not recursive:
            raise FsError("ENOTEMPTY", path)
        for key in [k for k in parent.children if self._key(k) == self._key(name)]:
            del parent.children[key]
        parent.mtime = self.clock()

    def rename(self, user: User | None, src: str, dst: str, cwd: str = "") -> None:
        node = self.stat(user, src, cwd, follow=False)
        if self.lookup(dst, cwd) is not None and self.lookup(dst, cwd).is_dir:
            dst = self.join(self.absolute(dst, cwd) + [node.name])
        sparent, sname, sparent_path = self._parent_for(user, src, cwd)
        dparent, dname, dparent_path = self._parent_for(user, dst, cwd)
        if not self.can(user, sparent, "w", sparent_path) or not self.can(user, dparent, "w", dparent_path):
            raise FsError("EACCES", dst)
        for key in [k for k in sparent.children if self._key(k) == self._key(sname)]:
            del sparent.children[key]
        node.name = dname
        dparent.children[dname] = node

    def copy(self, user: User | None, src: str, dst: str, cwd: str = "", recursive: bool = False) -> None:
        node = self.stat(user, src, cwd)
        if node.is_dir and not recursive:
            raise FsError("EISDIR", src)
        target = self.lookup(dst, cwd)
        if target is not None and target.is_dir:
            dst = self.join(self.absolute(dst, cwd) + [node.name])
        if node.is_dir:
            self.mkdir(user, dst, cwd)
            for child in self.listdir(user, src, cwd):
                self.copy(user, self.join(self.absolute(src, cwd) + [child.name]), self.join(self.absolute(dst, cwd) + [child.name]), "", True)
            return
        if not self.can(user, node, "r", self.norm(src, cwd)):
            raise FsError("EACCES", src)
        copy = self.write(user, dst, node.content, cwd)
        copy.mode = node.mode
        copy.meta = dict(node.meta)

    def symlink(self, user: User | None, target: str, path: str, cwd: str = "") -> Node:
        parent, name, parent_path = self._parent_for(user, path, cwd)
        if self._child(parent, name) is not None:
            raise FsError("EEXIST", path)
        if not self.can(user, parent, "w", parent_path):
            raise FsError("EACCES", path)
        node = Node(name, "link", user.name if user else "root", "root", 0o777, self.clock(), target=target)
        parent.children[name] = node
        return node

    def chmod(self, user: User | None, path: str, mode: int, cwd: str = "") -> None:
        node = self.stat(user, path, cwd)
        if user is not None and not user.is_root and node.owner != user.name:
            raise FsError("EACCES", path)       # real message is "Operation not permitted"; the shell layer words it
        node.mode = mode

    def chown(self, user: User | None, path: str, owner: str | None, group: str | None, cwd: str = "") -> None:
        node = self.stat(user, path, cwd)
        if user is not None and not user.is_root:
            raise FsError("EACCES", path)
        if owner:
            node.owner = owner
        if group:
            node.group = group

    # -------------------------------------------------------------------- glob
    def glob(self, pattern: str, cwd: str = "", user: User | None = None) -> list[str]:
        """Expand a shell pattern against this file system. Returns paths in the same style as the pattern (relative stays relative)."""
        if not any(ch in pattern for ch in "*?["):
            return [pattern]
        absolute = pattern.startswith(self.sep) or (self.flavor == "windows" and re.match(r"^[A-Za-z]:", pattern) is not None)
        comps = self.split(pattern)
        results: list[str] = []

        def rec(node: Node, built: list[str], remaining: list[str], shown: list[str]) -> None:
            if not remaining:
                results.append(("/" if absolute and self.flavor == "posix" else "") + self.sep.join(shown) if shown else pattern)
                return
            head, rest = remaining[0], remaining[1:]
            if not node.is_dir:
                return
            if user is not None and not self.can(user, node, "r", self.join(built)):
                return
            if not any(ch in head for ch in "*?["):
                child = self._child(node, head)
                if child is not None:
                    rec(child, built + [child.name], rest, shown + [head])
                return
            for name in sorted(node.children, key=str.lower):
                if name.startswith(".") and not head.startswith("."):
                    continue
                if fnmatch.fnmatchcase(name if self.case_sensitive else name.lower(), head if self.case_sensitive else head.lower()):
                    rec(node.children[name], built + [name], rest, shown + [name])

        start_node, start_built = self.root, []
        if not absolute:
            cwd_comps = self.absolute("", cwd) if cwd else []
            node = self.root
            for comp in cwd_comps:
                node = self._child(node, comp) or node
            start_node, start_built = node, cwd_comps
        rec(start_node, start_built, comps, [])
        return results or [pattern]

    # ----------------------------------------------------------------- loading
    def load(self, tree: dict, base: str = "", owner: str = "root", group: str = "root") -> None:
        """Populate from nested dicts: str/list = file content; dict with 'content' = file with options; other dict = directory.
        Options: owner, group, mode (int or octal string), hidden is just a leading dot, link, acl, meta. Keys starting with '_' are directory options."""
        root_comps = self.absolute(base) if base else []
        node = self.root
        for comp in root_comps:
            child = self._child(node, comp)
            if child is None:
                child = Node(comp, "dir", owner, group, 0o755, self.clock())
                node.children[comp] = child
            node = child
        self._load_into(node, tree, owner, group)

    def _load_into(self, parent: Node, tree: dict, owner: str, group: str) -> None:
        d_owner, d_group = tree.get("_owner", owner), tree.get("_group", group)
        if "_mode" in tree:
            parent.mode = _mode(tree["_mode"])
        parent.owner, parent.group = d_owner, d_group
        if "_acl" in tree:
            parent.acl = dict(tree["_acl"])
        for name, raw in tree.items():
            if name.startswith("_"):
                continue
            if isinstance(raw, (str, bytes)):
                parent.children[name] = Node(name, "file", d_owner, d_group, 0o644, self.clock(), raw)
            elif isinstance(raw, list):
                parent.children[name] = Node(name, "file", d_owner, d_group, 0o644, self.clock(), "\n".join(raw) + ("\n" if raw else ""))
            elif "link" in raw:
                parent.children[name] = Node(name, "link", d_owner, d_group, 0o777, self.clock(), target=raw["link"])
            elif "content" in raw:
                content = raw["content"]
                if isinstance(content, list):
                    content = "\n".join(content) + "\n"
                parent.children[name] = Node(name, "file", raw.get("owner", d_owner), raw.get("group", d_group), _mode(raw.get("mode", 0o644)), self.clock(),
                                             content, acl=dict(raw["acl"]) if raw.get("acl") else None, meta=dict(raw.get("meta", {})))
            else:
                child = Node(name, "dir", d_owner, d_group, 0o755, self.clock())
                parent.children[name] = child
                self._load_into(child, raw, d_owner, d_group)


def _mode(value) -> int:
    if isinstance(value, int):
        return value
    return int(str(value), 8)


def mode_string(node: Node) -> str:
    """-rwxr-xr-- style permission string."""
    kind = {"dir": "d", "link": "l"}.get(node.kind, "-")
    bits = ""
    for shift in (6, 3, 0):
        m = (node.mode >> shift) & 7
        bits += ("r" if m & 4 else "-") + ("w" if m & 2 else "-") + ("x" if m & 1 else "-")
    return kind + bits
