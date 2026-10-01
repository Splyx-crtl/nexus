"""Sandbox guard rails.

NEXUS is a pure simulation. This module keeps it that way:

* every address the player can touch must live inside the fictional
  ``10.42.0.0/16`` game network,
* anything that looks like a real address/host name is refused by the
  terminal,
* a static audit can verify that the code base never imports a networking
  module.
"""
from __future__ import annotations

import ast
import ipaddress
import re
from pathlib import Path

SIM_NETWORK = ipaddress.ip_network("10.42.0.0/16")

_IPV4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}(:\d+)?$")
_HOST_RE = re.compile(r"^(https?://|ftp://|ssh://)?[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}(/.*)?$", re.I)

FORBIDDEN_MODULES = {
    "socket", "ssl", "requests", "urllib", "urllib3", "http", "httpx", "aiohttp", "ftplib",
    "smtplib", "telnetlib", "paramiko", "scapy", "subprocess", "xmlrpc", "websockets", "asyncssh",
}


def is_virtual_ip(text: str) -> bool:
    """True when ``text`` is an IPv4 address inside the fictional game network."""
    try:
        return ipaddress.ip_address(text.split(":")[0]) in SIM_NETWORK
    except ValueError:
        return False


def looks_like_real_address(text: str) -> bool:
    """True for anything that resembles a real IP / URL that is NOT a game address."""
    text = text.strip()
    if _IPV4_RE.match(text):
        return not is_virtual_ip(text)
    # Game server names never contain dots, so a dotted name is an outside host.
    return bool(_HOST_RE.match(text))


def sanitize_name(name: str, max_len: int = 20) -> str:
    """Operator callsigns: letters, digits, dash, underscore only."""
    cleaned = re.sub(r"[^A-Za-z0-9_\- ]", "", name or "").strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned[:max_len] or "OPERATOR"


def safe_filename(name: str) -> str:
    """File-system safe stem for save files (prevents path traversal)."""
    stem = re.sub(r"[^A-Za-z0-9_\-]", "_", name).strip("_")
    return (stem or "operator")[:32].lower()


def validate_world(servers: dict[str, dict]) -> list[str]:
    """Return a list of problems found in the static server data."""
    problems: list[str] = []
    seen_ips: set[str] = set()
    for sid, server in servers.items():
        ip = server.get("ip", "")
        if not is_virtual_ip(ip):
            problems.append(f"{sid}: IP {ip!r} is outside the simulation network")
        if ip in seen_ips:
            problems.append(f"{sid}: duplicate IP {ip}")
        seen_ips.add(ip)
        for link in server.get("links", []):
            if link not in servers:
                problems.append(f"{sid}: link to unknown server {link!r}")
    return problems


# The two reviewed exceptions: the GitHub update check (nexus/updater.py) and the optional online service client (nexus/online.py).
NETWORK_ALLOWED_FILES = {"updater.py", "online.py"}
NETWORK_ALLOWED_MODULES = {"urllib", "ssl"}


def audit_package(*roots: Path) -> list[str]:
    """Statically scan python sources for forbidden networking imports."""
    findings: list[str] = []
    for root in roots:
        for path in Path(root).rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError) as exc:
                findings.append(f"{path}: unreadable ({exc})")
                continue
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    top = name.split(".")[0]
                    if path.name in NETWORK_ALLOWED_FILES and path.parent.name == "nexus" and top in NETWORK_ALLOWED_MODULES:
                        continue
                    if top in FORBIDDEN_MODULES:
                        findings.append(f"{path}:{node.lineno}: forbidden import {name}")
    return findings
