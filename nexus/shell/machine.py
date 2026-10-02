"""Simulated hosts, the world they live in, and player sessions on them. Data only: no real networking happens anywhere."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from .fs import VFS, User


@dataclass
class Service:
    port: int
    name: str                         # ssh, http, ftp, smb, rdp ...
    version: str = ""                 # "OpenSSH 7.2p2" ...
    state: str = "open"               # open | closed | filtered
    proto: str = "tcp"
    banner: str = ""
    data: dict = field(default_factory=dict)       # game data: credentials, pages, shares ...


@dataclass
class Process:
    pid: int
    user: str
    name: str
    cmd: str = ""
    cpu: float = 0.0
    mem: float = 0.1


@dataclass
class Machine:
    id: str
    hostname: str
    ip: str
    os: str = "linux"                                   # linux | windows
    fs: VFS | None = None
    users: dict[str, User] = field(default_factory=dict)
    services: list[Service] = field(default_factory=list)
    processes: list[Process] = field(default_factory=list)
    neighbors: list[str] = field(default_factory=list)  # ids of machines that can be reached from here
    installed: set[str] | None = None                   # None = all commands of the OS; otherwise only these (plus the core set)
    security: str = "LOW"
    description: str = ""
    domain: str = ""
    motd: str = ""
    shell: str = ""                                     # default shell for logins: bash | powershell | cmd
    logs: list[str] = field(default_factory=list)       # lines other tools (auth.log viewers, event logs) can show
    data: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.fs is None:
            self.fs = VFS("posix" if self.os == "linux" else "windows")
        if not self.shell:
            self.shell = "bash" if self.os == "linux" else "powershell"

    def user(self, name: str) -> User | None:
        if self.os == "linux":
            return self.users.get(name)
        low = name.lower()
        return next((u for key, u in self.users.items() if key.lower() == low), None)

    def add_user(self, user: User) -> User:
        self.users[user.name] = user
        self.fs.groups_of[user.name] = user.groups
        return user

    def service(self, port: int) -> Service | None:
        return next((s for s in self.services if s.port == port), None)

    def check_login(self, name: str, password: str) -> User | None:
        u = self.user(name)
        if u is None or u.locked:
            return None
        return u if u.password == password else None


class World:
    """All machines of a scenario and the rules for who can see whom."""

    def __init__(self, machines: list[Machine] | None = None, clock: Callable[[], float] = time.time):
        self.machines: dict[str, Machine] = {}
        self.clock = clock
        self.flags: dict[str, object] = {}                # free game state (discovered hosts, alarms ...)
        self.discovered: set[str] = set()
        for m in machines or []:
            self.add(m)

    def add(self, machine: Machine) -> Machine:
        self.machines[machine.id] = machine
        return machine

    def find(self, ref: str) -> Machine | None:
        """By id, hostname or IP address (case-insensitive for names)."""
        low = ref.lower()
        for m in self.machines.values():
            if low in (m.id.lower(), m.hostname.lower(), m.ip, (m.hostname + "." + m.domain).lower() if m.domain else "-"):
                return m
        return None

    def reachable_from(self, source: Machine, ref: str) -> Machine | None:
        """A target the player's machine may talk to: itself, its neighbours, and anything already discovered."""
        target = self.find(ref)
        if target is None:
            return None
        if target.id == source.id or target.id in source.neighbors or source.id in target.neighbors or target.id in self.discovered:
            return target
        return None


@dataclass
class Job:
    number: int
    pid: int
    command: str
    done: bool = True


@dataclass
class Session:
    """One logged-in shell: who, where, with which variables. The player's own machine starts a session at game start;
    `ssh` pushes a new session on top (exit pops it)."""
    machine: Machine
    user: User
    shell: str = "bash"                                  # bash | powershell | cmd
    cwd: str = ""
    env: dict[str, str] = field(default_factory=dict)
    history: list[str] = field(default_factory=list)
    last_status: int = 0
    jobs: list[Job] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)
    parent: "Session | None" = None                      # the session we came from (ssh chain)
    pid: int = 1000

    def __post_init__(self) -> None:
        if not self.cwd:
            self.cwd = self.user.home or ("/" if self.machine.os == "linux" else "C:\\")
        if not self.env:
            self.env = default_env(self.machine, self.user, self.shell)

    @property
    def fs(self) -> VFS:
        return self.machine.fs

    def prompt(self) -> str:
        if self.shell == "bash":
            home = self.user.home
            shown = self.cwd
            if home and (shown == home or shown.startswith(home.rstrip("/") + "/")):
                shown = "~" + shown[len(home):]
            end = "#" if self.user.is_root else "$"
            return f"┌──({self.user.name}㉿{self.machine.hostname})-[{shown}]\n└─{end} "
        if self.shell == "powershell":
            return f"PS {self.cwd}> "
        return f"{self.cwd}>"


def default_env(machine: Machine, user: User, shell: str) -> dict[str, str]:
    if machine.os == "linux":
        return {"HOME": user.home or "/", "USER": user.name, "LOGNAME": user.name, "SHELL": user.shell or "/bin/bash", "HOSTNAME": machine.hostname,
                "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "PWD": user.home or "/", "LANG": "en_US.UTF-8",
                "TERM": "xterm-256color", "UID": str(user.uid), "IFS": " \t\n", "OLDPWD": ""}
    return {"USERNAME": user.name, "USERPROFILE": user.home or f"C:\\Users\\{user.name}", "COMPUTERNAME": machine.hostname.upper(),
            "SystemRoot": "C:\\Windows", "SystemDrive": "C:", "TEMP": f"C:\\Users\\{user.name}\\AppData\\Local\\Temp", "OS": "Windows_NT",
            "PATH": "C:\\Windows\\System32;C:\\Windows;C:\\Windows\\System32\\WindowsPowerShell\\v1.0", "HOMEDRIVE": "C:",
            "HOMEPATH": f"\\Users\\{user.name}", "USERDOMAIN": machine.domain or machine.hostname.upper(), "ProgramFiles": "C:\\Program Files"}
