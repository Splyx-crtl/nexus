"""Update check against GitHub Releases.

This is the ONLY module in NEXUS that talks to the internet, and it is deliberately tiny:

* it only ever contacts ``github.com`` hosts over HTTPS (anything else is refused, including redirects),
* it only reads the latest release of the configured repository and downloads that release's installer,
* it sends no game data, no save data and no personal data (just a User-Agent with the version number).

The simulated game world never uses it. If ``GITHUB_REPO`` is empty the whole feature is off.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from .version import GITHUB_REPO, VERSION

API_URL = "https://api.github.com/repos/{repo}/releases/latest"
ALLOWED_HOSTS = ("api.github.com", "github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com",
                 "github-releases.githubusercontent.com")
ASSET_PATTERN = re.compile(r"^NEXUS-Setup.*\.exe$", re.IGNORECASE)


def parse_version(text: str) -> tuple[int, ...]:
    """'v2.10.1' -> (2, 10, 1). Non-numeric parts are ignored."""
    nums = re.findall(r"\d+", text.split("-")[0])
    return tuple(int(n) for n in nums[:4]) or (0,)


def is_newer(candidate: str, current: str = VERSION) -> bool:
    return parse_version(candidate) > parse_version(current)


def _check_url(url: str) -> None:
    parts = urllib.parse.urlparse(url)
    if parts.scheme != "https" or (parts.hostname or "") not in ALLOWED_HOSTS:
        raise ValueError(f"blocked URL (only HTTPS github.com hosts are allowed): {url}")


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open(url: str, timeout: float):
    _check_url(url)
    opener = urllib.request.build_opener(_SafeRedirect)
    request = urllib.request.Request(url, headers={"User-Agent": f"NEXUS-updater/{VERSION}", "Accept": "application/vnd.github+json"})
    return opener.open(request, timeout=timeout)


def _http_get_json(url: str, timeout: float = 5.0) -> dict:
    with _open(url, timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _http_get_text(url: str, timeout: float = 5.0) -> str:
    with _open(url, timeout) as response:
        return response.read().decode("utf-8", "replace")


def pick_release(data: dict) -> dict | None:
    """Turn a GitHub 'latest release' JSON into {version, notes, url, name, sha256_url} (or None)."""
    tag = str(data.get("tag_name", ""))
    if not tag or data.get("draft") or data.get("prerelease"):
        return None
    assets = data.get("assets", [])
    asset = next((a for a in assets if ASSET_PATTERN.match(a.get("name", ""))), None)
    if asset is None:
        return None
    sha = next((a for a in assets if a.get("name", "").lower() == asset["name"].lower() + ".sha256"), None)
    return {"version": tag.lstrip("vV"), "notes": str(data.get("body", ""))[:1500], "name": asset["name"],
            "url": asset["browser_download_url"], "sha256_url": sha["browser_download_url"] if sha else None,
            "page": data.get("html_url", "")}


def check_for_update(repo: str = GITHUB_REPO, fetch: Callable[[str], dict] = _http_get_json) -> dict | None:
    """Returns release info if a newer version exists, else None. Never raises (offline = no update)."""
    if not repo:
        return None
    try:
        release = pick_release(fetch(API_URL.format(repo=repo)))
        if release:
            _check_url(release["url"])
        return release if release and is_newer(release["version"]) else None
    except (OSError, ValueError, KeyError, json.JSONDecodeError, urllib.error.URLError):
        return None


def download(release: dict, dest: Path, progress: Callable[[int, int], None] | None = None, timeout: float = 20.0) -> Path:
    """Download the installer to ``dest`` (verifying SHA-256 when the release provides one)."""
    expected = None
    if release.get("sha256_url"):
        expected = _http_get_text(release["sha256_url"]).split()[0].strip().lower()
    dest.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with _open(release["url"], timeout) as response, dest.open("wb") as fh:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        while chunk := response.read(256 * 1024):
            fh.write(chunk)
            digest.update(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    if expected and digest.hexdigest().lower() != expected:
        dest.unlink(missing_ok=True)
        raise ValueError("Checksum mismatch: the download is damaged or was tampered with.")
    return dest
