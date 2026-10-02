"""Client for the optional NEXUS online service (Discord login, leaderboards, friends, presence).

Second (and last) module that uses the network, next to updater.py. Rules:
* nothing happens unless the server URL is configured AND the player opted in (settings ``online_enabled``),
* it only talks to the configured server (HTTPS; plain HTTP only for localhost testing),
* it only sends: the session token, display-relevant score numbers (level, XP, missions, credits, rank) and a short status text.
  Never save files, file names, local paths or the operator's real identity.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid

from .version import ONLINE_SERVER_URL, VERSION


class OnlineError(Exception):
    """A problem that can be shown to the player as-is. ``status`` = the HTTP status when the server answered (403 = refused)."""

    def __init__(self, message: str = "", status: int = 0):
        super().__init__(message)
        self.status = status


def server_url() -> str:
    return (os.environ.get("NEXUS_SERVER_URL") or ONLINE_SERVER_URL).rstrip("/")


def _validate_base(url: str) -> None:
    parts = urllib.parse.urlparse(url)
    local = (parts.hostname or "") in ("127.0.0.1", "localhost")
    if parts.scheme not in ("https", "http") or (parts.scheme == "http" and not local) or not parts.hostname:
        raise OnlineError("The online server must use HTTPS.")


class OnlineClient:
    def __init__(self, settings, base_url: str | None = None):
        self.settings = settings
        self.base = (base_url if base_url is not None else server_url()).rstrip("/")

    # -------------------------------------------------------------- state --
    @property
    def configured(self) -> bool:
        return bool(self.base)

    @property
    def enabled(self) -> bool:
        return self.configured and bool(self.settings.get("online_enabled"))

    @property
    def token(self) -> str:
        return self.settings.get("online_token") or ""

    @property
    def logged_in(self) -> bool:
        return self.enabled and bool(self.token)

    # ---------------------------------------------------------------- http --
    def _call(self, method: str, path: str, payload: dict | None = None, auth: bool = True, timeout: float = 8.0) -> dict:
        if not self.configured:
            raise OnlineError("Online services are not configured.")
        _validate_base(self.base)
        headers = {"User-Agent": f"NEXUS/{VERSION}", "Accept": "application/json"}
        if auth:
            if not self.token:
                raise OnlineError("Not logged in.")
            headers["Authorization"] = f"Bearer {self.token}"
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8") or "{}"
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = json.loads(exc.read().decode("utf-8")).get("detail", "")
            except (ValueError, OSError):
                pass
            if exc.code == 401:
                self.settings.set("online_token", "")
                raise OnlineError(str(detail) or "Your session expired. Please log in again.", 401)
            raise OnlineError(str(detail) or f"Server error {exc.code}", exc.code)
        except (urllib.error.URLError, OSError, TimeoutError):
            raise OnlineError("Can't reach the NEXUS server. Check your connection.")
        except ValueError:
            raise OnlineError("Unexpected answer from the server.")

    # --------------------------------------------------------------- login --
    def new_login(self, dev_name: str = "") -> tuple[str, str]:
        """Returns (state, url). Open the url in the browser, then poll with the state."""
        state = uuid.uuid4().hex
        if dev_name:                                         # local testing against NEXUS_DEV_LOGIN=1
            return state, f"{self.base}/auth/dev?name={urllib.parse.quote(dev_name)}&state={state}"
        return state, f"{self.base}/auth/start?state={state}"

    def server_info(self) -> dict:
        """Public server facts (no login): whether it is invite-only and needs an access key."""
        return self._call("GET", "/health", auth=False)

    @property
    def key(self) -> str:
        return self.settings.get("online_key") or ""

    def begin_login(self, state: str, key: str = "") -> None:
        """Step 1 of a login: announce the attempt and the access key (raises OnlineError with the reason if the key is refused)."""
        self._call("POST", "/auth/begin", {"state": state, "key": key.strip()}, auth=False)
        if key.strip():
            self.settings.set("online_key", key.strip())

    def poll_login(self, state: str) -> bool:
        """True once the browser login finished (the token is then stored)."""
        answer = self._call("POST", "/auth/poll", {"state": state}, auth=False)
        token = answer.get("token")
        if token:
            self.settings.set("online_token", token)
            return True
        return False

    def logout(self) -> None:
        try:
            self._call("POST", "/auth/logout")
        except OnlineError:
            pass
        self.settings.set("online_token", "")

    # ----------------------------------------------------------------- api --
    def me(self) -> dict:
        return self._call("GET", "/me")

    def set_share(self, share: bool) -> dict:
        return self._call("POST", "/me/share", {"share": share})

    def delete_account(self) -> None:
        self._call("DELETE", "/me")
        self.settings.set("online_token", "")

    def submit_scores(self, snapshot: dict) -> dict:
        return self._call("POST", "/scores", snapshot)

    def leaderboard(self, board: str = "level", limit: int = 50) -> dict:
        return self._call("GET", f"/leaderboard?board={urllib.parse.quote(board)}&limit={int(limit)}")

    def friends(self) -> dict:
        return self._call("GET", "/friends")

    def friend_request(self, name: str) -> dict:
        return self._call("POST", "/friends/request", {"name": name})

    def friend_respond(self, name: str, accept: bool) -> dict:
        return self._call("POST", "/friends/respond", {"name": name, "accept": accept})

    def friend_remove(self, name: str) -> dict:
        return self._call("DELETE", f"/friends/{urllib.parse.quote(name)}")

    def presence(self, status: str) -> dict:
        return self._call("POST", "/presence", {"status": status[:60]})


def snapshot(engine) -> dict:
    """The only data that ever leaves the machine: aggregate score numbers."""
    s = engine.db.all_stats()
    p = engine.player
    return {"level": p.level, "xp_total": int(s.get("xp_earned", 0)), "missions": int(p.completed_missions),
            "credits_earned": int(s.get("credits_earned", 0)), "perfect": int(s.get("perfect_missions", 0)),
            "playtime": int(p.playtime), "ng_plus": int(engine.ng_plus), "rank": p.rank}


def presence_text(engine) -> str:
    m = engine.missions.active()
    if m and not m.get("contract"):
        return f"Mission {m['number']:03d} · {m['title']}"[:60]
    if m:
        return "Contract job"
    return f"In the menus · LV {engine.player.level}"
