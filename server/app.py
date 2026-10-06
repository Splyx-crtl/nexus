"""NEXUS online service: Discord login, leaderboards, friends and presence.

Run locally:   NEXUS_DEV_LOGIN=1 python -m uvicorn server.app:app --port 8000
Production:    see docs/ONLINE.md (Discord application, environment variables, HTTPS).

It stores only: Discord id, display name, the last submitted score numbers, friend links and a short presence text
(plus, for invite-only servers, the hashes of the access keys and which Discord account redeemed which key).

Invite-only mode (docs/ONLINE.md): when DISCORD_GUILD_ID is set, a player needs (1) to be on your Discord server (and to have
DISCORD_ROLE_ID, if set) and (2) a key that an admin created. Keys are checked at every login.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import date, timedelta

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field, StrictInt

try:                                              # in the Docker image the file is copied next to this one
    from . import ed25519, staff_auth
except ImportError:
    from nexus import ed25519
    from server import staff_auth
from .players import ACCOUNT_STATUSES, EditError, clean_details, key_status as _key_status, mask_key, validate_edit
from .validation import Rejected, cumulative_xp, validate

DB_PATH = os.environ.get("NEXUS_DB", os.path.join(os.path.dirname(__file__), "nexus_online.db"))
DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://127.0.0.1:8000").rstrip("/")
DEV_LOGIN = os.environ.get("NEXUS_DEV_LOGIN", "") == "1"
GUILD_ID = os.environ.get("DISCORD_GUILD_ID", "").strip()          # the Discord server players must be on
ROLE_ID = os.environ.get("DISCORD_ROLE_ID", "").strip()            # optional role on that server
ADMIN_TOKEN = os.environ.get("NEXUS_ADMIN_TOKEN", "").strip()      # protects /admin/*; unset = no admin API
ADMIN_USER = os.environ.get("NEXUS_ADMIN_USER", "").strip()        # optional: admin login for the panel inside the game
ADMIN_PASSWORD = os.environ.get("NEXUS_ADMIN_PASSWORD", "")        # (kept only on the server, never in the game); 12+ characters
ADMIN_LOGIN = bool(ADMIN_USER) and len(ADMIN_PASSWORD) >= 12
ADMIN_SESSION_MINUTES = 60
STAFF_SESSION_MINUTES = 60
STAFF_INVITE_DAYS = 7
OPEN_LOGIN = os.environ.get("NEXUS_OPEN_LOGIN", "") == "1"         # explicit opt-out: anybody may register without a key
# A key is required before an account can be created: always on a real Discord server (secure by default), on request elsewhere.
GATED = bool(GUILD_ID) or os.environ.get("NEXUS_REQUIRE_KEY", "") == "1" or (bool(DISCORD_CLIENT_ID) and not DEV_LOGIN and not OPEN_LOGIN)
SESSION_DAYS = int(os.environ.get("NEXUS_SESSION_DAYS", "30"))     # gated servers re-check membership at least this often
KEY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"                  # no 0/O/1/I
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()     # optional: weekly winners are posted into your Discord server
DISCORD_TEAM_WEBHOOK_URL = os.environ.get("DISCORD_TEAM_WEBHOOK_URL", "").strip()   # optional, separate channel: player reports and bans (F4)
CHALLENGES = [("xp", "XP RUSH", "Earn the most XP this week."),
              ("missions", "OPERATOR", "Complete the most missions this week."),
              ("credits", "PAYDAY", "Earn the most credits this week."),
              ("perfect", "GHOST", "Finish the most missions without a single mistake this week.")]
LICENSE_DAYS = int(os.environ.get("NEXUS_LICENSE_DAYS", "30"))      # how long a signed licence lets the game run offline before it must renew
_seed_hex = os.environ.get("NEXUS_LICENSE_SEED", "").strip()
LICENSE_SEED = bytes.fromhex(_seed_hex) if re.fullmatch(r"[0-9a-fA-F]{64}", _seed_hex) else b""      # secret: the key the licences are signed with
ONLINE_WINDOW = 120            # seconds since last heartbeat that count as "online"
STATE_TTL = 600
BOARDS = {"level": "level DESC, xp_total DESC", "missions": "missions DESC, level DESC", "credits": "credits_earned DESC",
          "weekly": "weekly_xp DESC", "perfect": "perfect DESC, missions DESC"}

app = FastAPI(title="NEXUS online", version="1.0.0")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, discord_id TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
    name_lc TEXT NOT NULL, created_at REAL, last_seen REAL DEFAULT 0, status TEXT DEFAULT '', share INTEGER DEFAULT 1);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_name ON users(name_lc);
CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at REAL);
CREATE TABLE IF NOT EXISTS auth_states (state TEXT PRIMARY KEY, token TEXT, created_at REAL, key_id INTEGER, error TEXT);
CREATE TABLE IF NOT EXISTS access_keys (id INTEGER PRIMARY KEY AUTOINCREMENT, key_hash TEXT UNIQUE NOT NULL, tail TEXT NOT NULL,
    label TEXT DEFAULT '', created_at REAL, revoked INTEGER DEFAULT 0, discord_id TEXT, redeemed_at REAL);
CREATE TABLE IF NOT EXISTS scores (user_id INTEGER PRIMARY KEY, level INTEGER, xp_total INTEGER, missions INTEGER, credits_earned INTEGER,
    perfect INTEGER, playtime INTEGER, ng_plus INTEGER, rank TEXT, updated_at REAL, week TEXT, week_base_xp INTEGER);
CREATE TABLE IF NOT EXISTS friends (user_id INTEGER, friend_id INTEGER, status TEXT, created_at REAL, PRIMARY KEY (user_id, friend_id));
CREATE TABLE IF NOT EXISTS week_results (week TEXT NOT NULL, user_id INTEGER NOT NULL,
    base_xp INTEGER, base_missions INTEGER, base_credits INTEGER, base_perfect INTEGER,
    xp INTEGER, missions INTEGER, credits INTEGER, perfect INTEGER, PRIMARY KEY (week, user_id));
CREATE TABLE IF NOT EXISTS announcements (week TEXT PRIMARY KEY, posted_at REAL);
CREATE TABLE IF NOT EXISTS edits (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, ops TEXT NOT NULL, created_at REAL, applied_at REAL);
CREATE TABLE IF NOT EXISTS admin_audit (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, action TEXT, user_id INTEGER, key_id INTEGER, detail TEXT);
CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, reporter_id INTEGER NOT NULL, target_name TEXT NOT NULL,
    message TEXT NOT NULL, created_at REAL, status TEXT DEFAULT 'open', resolved_by INTEGER, resolved_at REAL, resolution_note TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS staff (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, username_lc TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL, role TEXT NOT NULL, totp_secret TEXT NOT NULL, totp_confirmed INTEGER DEFAULT 0,
    approved INTEGER DEFAULT 0, created_at REAL, created_by INTEGER, key_limit INTEGER DEFAULT 0, keys_created INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS staff_sessions (token TEXT PRIMARY KEY, staff_id INTEGER NOT NULL, created_at REAL, expires_at REAL);
CREATE TABLE IF NOT EXISTS staff_invites (code TEXT PRIMARY KEY, role TEXT NOT NULL, created_by INTEGER, created_at REAL,
    expires_at REAL, used_by INTEGER, used_at REAL);
"""

# Columns added after the first release: databases created earlier get them without losing any data.
NEW_COLUMNS = {
    "auth_states": {"key_id": "INTEGER", "error": "TEXT"},
    "users": {"account_status": "TEXT DEFAULT 'active'", "status_reason": "TEXT DEFAULT ''", "last_login": "REAL DEFAULT 0",
              "login_count": "INTEGER DEFAULT 0"},
    "access_keys": {"expires_at": "REAL", "device_id": "TEXT", "device_at": "REAL"},
    "scores": {"details": "TEXT DEFAULT '{}'"},
}


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    for table, columns in NEW_COLUMNS.items():
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for col, decl in columns.items():
            if col not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
    conn.commit()
    conn.close()


init_db()


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA synchronous=NORMAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------------ helpers --
_hits: dict[str, list[float]] = {}


def rate_limit(key: str, limit: int = 90, window: int = 60) -> None:
    now = time.time()
    hits = [t for t in _hits.get(key, []) if now - t < window]
    if len(hits) >= limit:
        raise HTTPException(429, "Too many requests.")
    hits.append(now)
    _hits[key] = hits


def current_user(authorization: str = Header(default="")) -> sqlite3.Row:
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(401, "Not logged in.")
    rate_limit(token)
    with db() as conn:
        row = conn.execute("SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token=?", (token,)).fetchone()
    if row is None:
        raise HTTPException(401, "Session expired — please log in again.")
    if problem := account_problem(row):
        raise HTTPException(401, problem)
    if GATED:
        with db() as conn:
            session = conn.execute("SELECT created_at FROM sessions WHERE token=?", (token,)).fetchone()
            key = conn.execute("SELECT revoked FROM access_keys WHERE discord_id=? ORDER BY revoked, id DESC", (row["discord_id"],)).fetchone()
        if session and time.time() - session["created_at"] > SESSION_DAYS * 86400:
            raise HTTPException(401, "Session expired — please log in again.")
        if key is None or key["revoked"]:
            raise HTTPException(401, "Your access key is no longer valid.")
    return row


def account_problem(row) -> str:
    """Why an account may not play right now ('' when it may). ``row`` = a users row."""
    status = row["account_status"] or "active"
    reason = f" Reason: {row['status_reason']}" if row["status_reason"] else ""
    if status == "banned":
        return "This account has been banned." + reason
    if status == "disabled":
        return "This account has been deactivated by an administrator." + reason
    return ""


def clean_name(name: str) -> str:
    return "".join(c for c in name if c.isprintable())[:32].strip() or "operator"


def login_user(conn: sqlite3.Connection, discord_id: str, name: str) -> str:
    """Create/refresh the user and return a fresh session token."""
    name = clean_name(name)
    row = conn.execute("SELECT id FROM users WHERE discord_id=?", (discord_id,)).fetchone()
    if row is None:
        unique, n = name, 1
        while conn.execute("SELECT 1 FROM users WHERE name_lc=?", (unique.lower(),)).fetchone():
            n += 1
            unique = f"{name}{n}"
        cur = conn.execute("INSERT INTO users(discord_id, name, name_lc, created_at) VALUES(?,?,?,?)", (discord_id, unique, unique.lower(), time.time()))
        user_id = cur.lastrowid
    else:
        user_id = row["id"]
    conn.execute("UPDATE users SET last_login=?, login_count=COALESCE(login_count, 0)+1 WHERE id=?", (time.time(), user_id))
    token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO sessions(token, user_id, created_at) VALUES(?,?,?)", (token, user_id, time.time()))
    return token


def finish_state(conn: sqlite3.Connection, state: str, token: str) -> None:
    conn.execute("DELETE FROM auth_states WHERE created_at < ?", (time.time() - STATE_TTL,))
    conn.execute("INSERT OR REPLACE INTO auth_states(state, token, created_at) VALUES(?,?,?)", (state, token, time.time()))


def valid_state(state: str) -> str:
    if not (16 <= len(state) <= 80) or not state.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(400, "Invalid state.")
    return state


# --------------------------------------------------------------------- keys --
def normalize_key(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (text or "").upper())


def hash_key(text: str) -> str:
    return hashlib.sha256(normalize_key(text).encode()).hexdigest()


def new_key() -> str:
    body = "".join(secrets.choice(KEY_ALPHABET) for _ in range(15))
    return f"NX-{body[:5]}-{body[5:10]}-{body[10:]}"


def client_ip(request: Request) -> str:
    return (request.client.host if request.client else "?")


def key_problem(row) -> str:
    """Why a key row cannot be used right now ('' when it can)."""
    if row is None:
        return "That key is not valid. Check it for typos or ask the staff on the Discord server."
    if row["revoked"]:
        return "This key has been revoked."
    if _key_status(dict(row), time.time()) == "expired":
        return "This key has expired. Ask the staff for a new one."
    return ""


def member_problem(status: int, member: dict | None) -> str:
    """Server-membership rules for a login. ``status``/``member`` = Discord's answer for the guild member of the player."""
    if status != 200 or not isinstance(member, dict):
        return "You are not on the NEXUS Discord server. Join it first, then log in again."
    if ROLE_ID and ROLE_ID not in [str(r) for r in member.get("roles", [])]:
        return "You do not have the required role on the NEXUS Discord server."
    return ""


def bind_key(conn: sqlite3.Connection, key_id: int, discord_id: str) -> str:
    """Attach a key to the Discord account that redeems it. Returns an error text or ''."""
    row = conn.execute("SELECT * FROM access_keys WHERE id=?", (key_id,)).fetchone()
    if problem := key_problem(row):
        return problem
    if row["discord_id"] and row["discord_id"] != discord_id:
        return "This key has already been used by another account."
    if not row["discord_id"]:
        other = conn.execute("SELECT 1 FROM access_keys WHERE discord_id=? AND revoked=0 AND id!=?", (discord_id, key_id)).fetchone()
        if other:
            return "Your Discord account already uses another key."
        conn.execute("UPDATE access_keys SET discord_id=?, redeemed_at=? WHERE id=?", (discord_id, time.time(), key_id))
    return ""


def fail_state(conn: sqlite3.Connection, state: str, message: str) -> None:
    conn.execute("UPDATE auth_states SET error=? WHERE state=?", (message, state))


def state_row(conn: sqlite3.Connection, state: str):
    return conn.execute("SELECT * FROM auth_states WHERE state=? AND token IS NULL AND error IS NULL AND created_at > ?",
                        (state, time.time() - STATE_TTL)).fetchone()


# ------------------------------------------------------------------ licence --
DEVICE_RE = re.compile(r"^[A-Za-z0-9\-]{16,64}$")


def clean_device(device: str) -> str:
    if not DEVICE_RE.match(device or ""):
        raise HTTPException(422, "Invalid device id.")
    return device


def bind_device(conn: sqlite3.Connection, row, device: str) -> str:
    """The first installation that activates a key owns it; the same installation may renew it any time. Returns an error text or ''."""
    if row["device_id"] and row["device_id"] != device:
        return "This key has already been used on another computer. Ask the staff to free it."
    if not row["device_id"]:
        conn.execute("UPDATE access_keys SET device_id=?, device_at=? WHERE id=?", (device, time.time(), row["id"]))
    return ""


def sign_licence(key_id: int, device: str) -> tuple[str, int]:
    now = int(time.time())
    payload = json.dumps({"v": 1, "kid": key_id, "dev": device, "iat": now, "exp": now + LICENSE_DAYS * 86400}, separators=(",", ":")).encode()
    signature = ed25519.sign(LICENSE_SEED, payload)
    b64 = lambda raw: base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    return f"{b64(payload)}.{b64(signature)}", now + LICENSE_DAYS * 86400


class ActivateBody(BaseModel):
    key: str = Field(max_length=64)
    device: str = Field(max_length=64)


@app.post("/license/activate")
def license_activate(body: ActivateBody, request: Request):
    """Activates (or renews) the game on one computer: checks the key on the server and returns a signed licence the game can verify offline.
    Deactivated, deleted, expired and already used keys get nothing, and banned accounts are refused too."""
    if not LICENSE_SEED:
        raise HTTPException(503, "Game activation is not set up on this server yet.")
    rate_limit("license:" + client_ip(request), limit=12, window=60)                # also slows down key guessing
    device = clean_device(body.device)
    with db() as conn:
        row = conn.execute("SELECT * FROM access_keys WHERE key_hash=?", (hash_key(body.key),)).fetchone() if normalize_key(body.key) else None
        if problem := key_problem(row):
            raise HTTPException(403, problem)
        if problem := bind_device(conn, row, device):
            raise HTTPException(403, problem)
        owner = conn.execute("SELECT * FROM users WHERE discord_id=?", (row["discord_id"],)).fetchone() if row["discord_id"] else None
        if owner is not None and (problem := account_problem(owner)):
            raise HTTPException(403, problem)
        token, expires = sign_licence(row["id"], device)
    return {"token": token, "expires": expires, "days": LICENSE_DAYS}


# --------------------------------------------------------------------- auth --
@app.get("/health")
def health():
    return {"ok": True, "dev_login": DEV_LOGIN, "discord": bool(DISCORD_CLIENT_ID), "gated": GATED, "admin": bool(ADMIN_TOKEN or ADMIN_LOGIN),
            "license": bool(LICENSE_SEED)}


class BeginBody(BaseModel):
    state: str
    key: str = Field(default="", max_length=64)
    device: str = Field(default="", max_length=64)          # the activated game installation (older games send none)


@app.post("/auth/begin")
def auth_begin(body: BeginBody, request: Request):
    """Step 1 of a login: the game announces the login attempt (and the access key on invite-only servers)."""
    rate_limit("begin:" + client_ip(request), limit=12, window=60)          # also slows down key guessing
    valid_state(body.state)
    key_id = None
    if GATED:
        with db() as conn:
            row = conn.execute("SELECT * FROM access_keys WHERE key_hash=?", (hash_key(body.key),)).fetchone() if normalize_key(body.key) else None
        if problem := key_problem(row):
            raise HTTPException(403, problem)
        if body.device:
            with db() as conn:
                if problem := bind_device(conn, row, clean_device(body.device)):
                    raise HTTPException(403, problem)
        key_id = row["id"]
    with db() as conn:
        conn.execute("INSERT OR REPLACE INTO auth_states(state, token, created_at, key_id, error) VALUES(?,NULL,?,?,NULL)", (body.state, time.time(), key_id))
    return {"ok": True, "gated": GATED}


@app.get("/auth/start")
def auth_start(state: str):
    valid_state(state)
    if not DISCORD_CLIENT_ID:
        raise HTTPException(503, "Discord login is not configured on this server.")
    with db() as conn:
        if GATED:
            if state_row(conn, state) is None:                               # the game must call /auth/begin (with the key) first
                raise HTTPException(400, "Start the login from inside the game and enter your access key first.")
        else:
            conn.execute("INSERT OR REPLACE INTO auth_states(state, token, created_at) VALUES(?,NULL,?)", (state, time.time()))
    scope = "identify%20guilds.members.read" if GUILD_ID else "identify"
    url = ("https://discord.com/oauth2/authorize?response_type=code&scope=" + scope +
           f"&client_id={DISCORD_CLIENT_ID}&state={state}&redirect_uri={PUBLIC_URL}/auth/callback")
    return RedirectResponse(url)


def _page(title: str, text: str, ok: bool, status: int = 200) -> HTMLResponse:
    color = "#00ff9c" if ok else "#ff3860"
    return HTMLResponse(f"<body style='font-family:monospace;background:#03080a;color:{color}'><h2>{title}</h2>{text}</body>", status_code=status)


@app.get("/auth/callback", response_class=HTMLResponse)
def auth_callback(code: str = "", state: str = "", error: str = ""):
    valid_state(state)
    if error or not code:
        return HTMLResponse("<h2>Login cancelled.</h2>You can close this window.", status_code=400)
    with db() as conn:
        row = conn.execute("SELECT * FROM auth_states WHERE state=? AND token IS NULL AND error IS NULL AND created_at > ?", (state, time.time() - STATE_TTL)).fetchone()
        if not row:
            raise HTTPException(400, "Unknown or expired login attempt.")
    member = None
    member_status = 0
    try:
        with httpx.Client(timeout=10) as client:
            tok = client.post("https://discord.com/api/oauth2/token", data={
                "client_id": DISCORD_CLIENT_ID, "client_secret": DISCORD_CLIENT_SECRET, "grant_type": "authorization_code",
                "code": code, "redirect_uri": f"{PUBLIC_URL}/auth/callback"})
            tok.raise_for_status()
            bearer = {"Authorization": f"Bearer {tok.json()['access_token']}"}
            me = client.get("https://discord.com/api/users/@me", headers=bearer)
            me.raise_for_status()
            profile = me.json()
            if GUILD_ID:
                reply = client.get(f"https://discord.com/api/users/@me/guilds/{GUILD_ID}/member", headers=bearer)
                member_status = reply.status_code
                member = reply.json() if reply.status_code == 200 else None
    except (httpx.HTTPError, KeyError, ValueError):
        raise HTTPException(502, "Discord did not accept the login.")
    problem = member_problem(member_status, member) if GUILD_ID else ""
    with db() as conn:
        if not problem and GATED:
            problem = bind_key(conn, row["key_id"], str(profile["id"])) if row["key_id"] else "No access key was given."
        if problem:
            fail_state(conn, state, problem)
            return _page("NEXUS login refused.", f"{problem}<br>You can close this window.", False, 403)
        existing = conn.execute("SELECT * FROM users WHERE discord_id=?", (str(profile["id"]),)).fetchone()
        if existing is not None and (problem := account_problem(existing)):
            fail_state(conn, state, problem)
            return _page("NEXUS login refused.", f"{problem}<br>You can close this window.", False, 403)
        token = login_user(conn, str(profile["id"]), profile.get("global_name") or profile.get("username") or "operator")
        finish_state(conn, state, token)
    return _page("NEXUS login successful.", "You can close this window and return to the game.", True)


@app.get("/auth/dev", response_class=HTMLResponse)
def auth_dev(name: str, state: str):
    """Local testing only (NEXUS_DEV_LOGIN=1): log in as any name without Discord (the key rules still apply when gated)."""
    if not DEV_LOGIN:
        raise HTTPException(404, "Not found.")
    valid_state(state)
    with db() as conn:
        discord_id = f"dev:{name.lower()}"
        if GATED:
            row = state_row(conn, state)
            if row is None:
                raise HTTPException(400, "Start the login from inside the game and enter your access key first.")
            if problem := (bind_key(conn, row["key_id"], discord_id) if row["key_id"] else "No access key was given."):
                fail_state(conn, state, problem)
                return HTMLResponse(problem, status_code=403)
        existing = conn.execute("SELECT * FROM users WHERE discord_id=?", (discord_id,)).fetchone()
        if existing is not None and (problem := account_problem(existing)):
            fail_state(conn, state, problem)
            return HTMLResponse(problem, status_code=403)
        token = login_user(conn, discord_id, name)
        finish_state(conn, state, token)
    return HTMLResponse("dev login ok")


class PollBody(BaseModel):
    state: str


@app.post("/auth/poll")
def auth_poll(body: PollBody):
    valid_state(body.state)
    with db() as conn:
        row = conn.execute("SELECT token, error FROM auth_states WHERE state=?", (body.state,)).fetchone()
        if row is not None and row["error"]:
            conn.execute("DELETE FROM auth_states WHERE state=?", (body.state,))
            raise HTTPException(403, row["error"])                           # the game shows this text to the player
        if row is None or row["token"] is None:
            raise HTTPException(202, "pending")
        conn.execute("DELETE FROM auth_states WHERE state=?", (body.state,))      # the token is handed out exactly once
        return {"token": row["token"]}


@app.post("/auth/logout")
def logout(user=Depends(current_user), authorization: str = Header(default="")):
    with db() as conn:
        conn.execute("DELETE FROM sessions WHERE token=?", (authorization.removeprefix("Bearer ").strip(),))
    return {"ok": True}


# ------------------------------------------------------------------ profile --
def week_key() -> str:
    y, w, _ = date.today().isocalendar()
    return f"{y}-W{w:02d}"


@app.get("/me")
def me(user=Depends(current_user)):
    with db() as conn:
        score = conn.execute("SELECT * FROM scores WHERE user_id=?", (user["id"],)).fetchone()
        edits = pending_edits(conn, user["id"])
    shown = {k: v for k, v in dict(score).items() if k != "details"} if score else None
    return {"name": user["name"], "share": bool(user["share"]), "score": shown, "edits": edits}


def pending_edits(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    """Changes an administrator made on the server that the player's game has not applied to the save yet."""
    rows = conn.execute("SELECT id, ops FROM edits WHERE user_id=? AND applied_at IS NULL ORDER BY id", (user_id,)).fetchall()
    return [{"id": r["id"], "ops": json.loads(r["ops"])} for r in rows]


@app.post("/me/edits/{edit_id}/ack")
def ack_edit(edit_id: int, user=Depends(current_user)):
    """The game applied an administrator's change to the local save."""
    with db() as conn:
        done = conn.execute("UPDATE edits SET applied_at=? WHERE id=? AND user_id=? AND applied_at IS NULL", (time.time(), edit_id, user["id"])).rowcount
    if not done:
        raise HTTPException(404, "No such pending change.")
    return {"ok": True}


class ShareBody(BaseModel):
    share: bool


@app.post("/me/share")
def set_share(body: ShareBody, user=Depends(current_user)):
    with db() as conn:
        conn.execute("UPDATE users SET share=? WHERE id=?", (1 if body.share else 0, user["id"]))
    return {"share": body.share}


@app.delete("/me")
def delete_me(user=Depends(current_user)):
    """Delete the account and every stored row about it (GDPR-style erasure)."""
    with db() as conn:
        uid = user["id"]
        for table, col in (("sessions", "user_id"), ("scores", "user_id"), ("week_results", "user_id"), ("edits", "user_id"), ("friends", "user_id"), ("friends", "friend_id"), ("users", "id")):
            conn.execute(f"DELETE FROM {table} WHERE {col}=?", (uid,))
    return {"deleted": True}


class ScoreBody(BaseModel):
    level: int
    xp_total: int
    missions: int
    credits_earned: int
    perfect: int = 0
    playtime: int = 0
    ng_plus: int = 0
    rank: str = Field(default="", max_length=24)
    details: dict = Field(default_factory=dict)         # optional: balance, reputation, achievements, unlocks, counters (see players.clean_details)


@app.post("/scores")
def submit_score(body: ScoreBody, user=Depends(current_user)):
    with db() as conn:
        waiting = pending_edits(conn, user["id"])
        if waiting:                                     # the game must apply the administrator's change first; its old numbers would undo it
            return {"ok": True, "ignored": True, "edits": waiting}
        old = conn.execute("SELECT * FROM scores WHERE user_id=?", (user["id"],)).fetchone()
        elapsed = (time.time() - old["updated_at"]) if old else None
        try:
            clean = validate(body.model_dump(), dict(old) if old else None, elapsed)
        except Rejected as exc:
            raise HTTPException(422, str(exc))
        wk = week_key()
        base = old["week_base_xp"] if old and old["week"] == wk else (old["xp_total"] if old else clean["xp_total"])
        details = json.dumps(clean_details(body.details), separators=(",", ":"))
        conn.execute("""INSERT INTO scores(user_id, level, xp_total, missions, credits_earned, perfect, playtime, ng_plus, rank, updated_at, week, week_base_xp, details)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET level=excluded.level, xp_total=excluded.xp_total,
                        missions=excluded.missions, credits_earned=excluded.credits_earned, perfect=excluded.perfect, playtime=excluded.playtime,
                        ng_plus=excluded.ng_plus, rank=excluded.rank, updated_at=excluded.updated_at, week=excluded.week, week_base_xp=excluded.week_base_xp,
                        details=excluded.details""",
                     (user["id"], clean["level"], clean["xp_total"], clean["missions"], clean["credits_earned"], clean["perfect"], clean["playtime"],
                      clean["ng_plus"], clean["rank"], time.time(), wk, base, details))
        record_week(conn, user["id"], wk, old, clean)
        announce_last_week(conn)
    return {"ok": True, "edits": []}


# -------------------------------------------------------------- leaderboard --
@app.get("/leaderboard")
def leaderboard(board: str = "level", limit: int = 50, user=Depends(current_user)):
    if board not in BOARDS:
        raise HTTPException(400, "Unknown board.")
    limit = max(1, min(limit, 100))
    value = {"level": "level", "missions": "missions", "credits": "credits_earned", "weekly": "weekly_xp", "perfect": "perfect"}[board]
    sql = f"""SELECT u.id, u.name, s.level, s.rank, s.missions, s.credits_earned, s.perfect, s.ng_plus,
                     CASE WHEN s.week = ? THEN s.xp_total - s.week_base_xp ELSE 0 END AS weekly_xp
              FROM scores s JOIN users u ON u.id = s.user_id WHERE u.share = 1 ORDER BY {BOARDS[board]}, u.name_lc"""
    with db() as conn:
        rows = [dict(r) for r in conn.execute(sql, (week_key(),))]
    for i, r in enumerate(rows, 1):
        r["position"], r["value"] = i, r[value]
        r["me"] = r.pop("id") == user["id"]
    mine = next((r for r in rows if r["me"]), None)
    return {"board": board, "entries": rows[:limit], "me": mine, "total": len(rows)}


# -------------------------------------------------------- weekly challenge --
def challenge_for(week: str) -> tuple[str, str, str]:
    """The challenge of an ISO week ('2026-W40'): rotates through CHALLENGES, so everybody gets the same one."""
    number = int(week.split("-W")[1])
    return CHALLENGES[number % len(CHALLENGES)]


def previous_week() -> str:
    y, w, _ = (date.today() - timedelta(days=7)).isocalendar()
    return f"{y}-W{w:02d}"


def record_week(conn: sqlite3.Connection, user_id: int, week: str, old, clean: dict) -> None:
    """Keep the player's start-of-week numbers and the current ones; the weekly result is the difference."""
    cur = (clean["xp_total"], clean["missions"], clean["credits_earned"], clean["perfect"])
    row = conn.execute("SELECT 1 FROM week_results WHERE week=? AND user_id=?", (week, user_id)).fetchone()
    if row is None:
        base = (old["xp_total"], old["missions"], old["credits_earned"], old["perfect"]) if old else cur
        conn.execute("INSERT INTO week_results VALUES(?,?,?,?,?,?,?,?,?,?)", (week, user_id, *base, *cur))
    else:
        conn.execute("UPDATE week_results SET xp=?, missions=?, credits=?, perfect=? WHERE week=? AND user_id=?", (*cur, week, user_id))


def week_table(conn: sqlite3.Connection, week: str, metric: str) -> list[dict]:
    rows = conn.execute(f"""SELECT u.id, u.name, w.{metric} - w.base_{metric} AS value FROM week_results w
                            JOIN users u ON u.id = w.user_id WHERE w.week=? AND u.share=1
                            ORDER BY value DESC, u.name_lc""", (week,)).fetchall()
    out = [dict(r) for r in rows]
    for i, r in enumerate(out, 1):
        r["position"] = i
    return out


def send_webhook(text: str, url: str | None = None) -> None:
    """Post a message into a Discord channel via webhook (server -> Discord only). Replaceable in tests.
    ``url`` defaults to the public weekly-winners webhook, read live (not bound at def time) so tests and real
    deployments can set ``DISCORD_WEBHOOK_URL`` after import and have it take effect."""
    if url is None:
        url = DISCORD_WEBHOOK_URL
    if not url:
        return

    def work():
        try:
            httpx.post(url, json={"content": text[:1900], "allowed_mentions": {"parse": []}}, timeout=8)
        except httpx.HTTPError:
            pass

    threading.Thread(target=work, daemon=True).start()


def notify_team(text: str) -> None:
    """F4: a separate, optional channel for staff-facing events (new reports, bans) - deliberately not the same
    webhook as the public weekly-winners announcement."""
    send_webhook(text, DISCORD_TEAM_WEBHOOK_URL)


def announce_last_week(conn: sqlite3.Connection) -> None:
    """Once per week (the first request after the rollover) tell the Discord server who won the last challenge."""
    if not DISCORD_WEBHOOK_URL:
        return
    week = previous_week()
    if conn.execute("INSERT OR IGNORE INTO announcements VALUES(?, ?)", (week, time.time())).rowcount == 0:
        return
    metric, title, _ = challenge_for(week)
    table = [r for r in week_table(conn, week, metric) if r["value"] > 0][:3]
    if not table:
        return
    medals = ("🥇", "🥈", "🥉")
    lines = [f"{medals[i]} **{r['name']}** — {r['value']:,} {metric}" for i, r in enumerate(table)]
    send_webhook(f"**NEXUS weekly challenge {title} ({week}) — results**\n" + "\n".join(lines))


@app.get("/challenge")
def challenge(user=Depends(current_user)):
    week = week_key()
    metric, title, text = challenge_for(week)
    now = time.time()
    next_monday = (date.today() + timedelta(days=7 - date.today().weekday()))
    ends_in = int(time.mktime(next_monday.timetuple()) - now)
    with db() as conn:
        announce_last_week(conn)
        rows = week_table(conn, week, metric)
        total = conn.execute(f"SELECT COALESCE(SUM(w.{metric} - w.base_{metric}), 0) FROM week_results w WHERE w.week=?", (week,)).fetchone()[0]
    for r in rows:
        r["me"] = r.pop("id") == user["id"]
    mine = next((r for r in rows if r["me"]), None)
    return {"week": week, "metric": metric, "title": title, "text": text, "ends_in": max(0, ends_in),
            "entries": rows[:20], "me": mine, "players": len(rows), "community_total": int(total)}


# ------------------------------------------------------------------- reports (F4) --
class ReportBody(BaseModel):
    target_name: str = Field(min_length=1, max_length=32)
    message: str = Field(min_length=1, max_length=500)


@app.post("/report")
def submit_report(body: ReportBody, user=Depends(current_user)):
    """A player flags another player's name/messages for staff attention. Rate-limited separately from the
    general API limit so a handful of reports a day is never a problem, but spamming the queue is."""
    rate_limit("report:" + str(user["id"]), limit=5, window=3600)
    target = "".join(c for c in body.target_name if c.isprintable()).strip()
    message = "".join(c for c in body.message if c.isprintable()).strip()
    if not target or not message:
        raise HTTPException(422, "Report needs a target name and a message.")
    with db() as conn:
        cur = conn.execute("INSERT INTO reports(reporter_id, target_name, message, created_at) VALUES(?,?,?,?)",
                            (user["id"], target, message, time.time()))
    notify_team(f"**New player report** from {user['name']}\nTarget: {target}\n{message[:300]}")
    return {"ok": True, "id": cur.lastrowid}


# ------------------------------------------------------------------ friends --
def _find(conn: sqlite3.Connection, name: str):
    return conn.execute("SELECT * FROM users WHERE name_lc=?", (name.strip().lower(),)).fetchone()


def _friend_view(conn, row, level=None) -> dict:
    s = conn.execute("SELECT level, rank FROM scores WHERE user_id=?", (row["id"],)).fetchone()
    online = bool(row["share"]) and time.time() - (row["last_seen"] or 0) < ONLINE_WINDOW
    return {"name": row["name"], "online": online, "status": row["status"] if online else "", "level": s["level"] if s else None, "rank": s["rank"] if s else ""}


@app.get("/friends")
def friends(user=Depends(current_user)):
    with db() as conn:
        out = {"friends": [], "incoming": [], "outgoing": []}
        for r in conn.execute("SELECT * FROM friends WHERE (user_id=? OR friend_id=?)", (user["id"], user["id"])):
            other_id = r["friend_id"] if r["user_id"] == user["id"] else r["user_id"]
            other = conn.execute("SELECT * FROM users WHERE id=?", (other_id,)).fetchone()
            if other is None:
                continue
            if r["status"] == "accepted":
                out["friends"].append(_friend_view(conn, other))
            elif r["user_id"] == user["id"]:
                out["outgoing"].append({"name": other["name"]})
            else:
                out["incoming"].append({"name": other["name"]})
        out["friends"].sort(key=lambda f: (not f["online"], f["name"].lower()))
        return out


class NameBody(BaseModel):
    name: str


class RespondBody(BaseModel):
    name: str
    accept: bool


@app.post("/friends/request")
def friend_request(body: NameBody, user=Depends(current_user)):
    with db() as conn:
        other = _find(conn, body.name)
        if other is None or other["id"] == user["id"]:
            raise HTTPException(404, "No operator with that name.")
        existing = conn.execute("SELECT * FROM friends WHERE (user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?)",
                                (user["id"], other["id"], other["id"], user["id"])).fetchone()
        if existing:
            if existing["status"] == "pending" and existing["user_id"] == other["id"]:          # they already asked us: accept
                conn.execute("UPDATE friends SET status='accepted' WHERE user_id=? AND friend_id=?", (other["id"], user["id"]))
                return {"status": "accepted"}
            raise HTTPException(409, "Already friends or request pending.")
        conn.execute("INSERT INTO friends(user_id, friend_id, status, created_at) VALUES(?,?,'pending',?)", (user["id"], other["id"], time.time()))
    return {"status": "pending"}


@app.post("/friends/respond")
def friend_respond(body: RespondBody, user=Depends(current_user)):
    with db() as conn:
        other = _find(conn, body.name)
        if other is None:
            raise HTTPException(404, "No operator with that name.")
        row = conn.execute("SELECT 1 FROM friends WHERE user_id=? AND friend_id=? AND status='pending'", (other["id"], user["id"])).fetchone()
        if row is None:
            raise HTTPException(404, "No such request.")
        if body.accept:
            conn.execute("UPDATE friends SET status='accepted' WHERE user_id=? AND friend_id=?", (other["id"], user["id"]))
        else:
            conn.execute("DELETE FROM friends WHERE user_id=? AND friend_id=?", (other["id"], user["id"]))
    return {"ok": True}


@app.delete("/friends/{name}")
def friend_remove(name: str, user=Depends(current_user)):
    with db() as conn:
        other = _find(conn, name)
        if other:
            conn.execute("DELETE FROM friends WHERE (user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?)",
                         (user["id"], other["id"], other["id"], user["id"]))
    return {"ok": True}


class PresenceBody(BaseModel):
    status: str = Field(default="", max_length=60)


@app.post("/presence")
def presence(body: PresenceBody, user=Depends(current_user)):
    with db() as conn:
        conn.execute("UPDATE users SET last_seen=?, status=? WHERE id=?", (time.time(), "".join(c for c in body.status if c.isprintable()), user["id"]))
    return {"ok": True}


# -------------------------------------------------------------------- admin --
_admin_sessions: dict[str, float] = {}          # session token -> expiry (memory only: a server restart means logging in again)


def admin_only(request: Request, authorization: str = Header(default="")) -> None:
    """Admin API for key management. Accepts NEXUS_ADMIN_TOKEN or a session from /admin/login. Disabled (404) when neither is
    configured; wrong tries are rate limited."""
    if not (ADMIN_TOKEN or ADMIN_LOGIN):
        raise HTTPException(404, "Not found.")
    rate_limit("admin:" + client_ip(request), limit=60, window=60)
    given = authorization.removeprefix("Bearer ").strip()
    now = time.time()
    for token in [t for t, exp in _admin_sessions.items() if exp < now]:
        del _admin_sessions[token]
    if ADMIN_TOKEN and secrets.compare_digest(given.encode(), ADMIN_TOKEN.encode()):
        return
    if given in _admin_sessions:
        return
    raise HTTPException(401, "Admin login required.")


def _staff_session(conn: sqlite3.Connection, token: str) -> sqlite3.Row | None:
    conn.execute("DELETE FROM staff_sessions WHERE expires_at < ?", (time.time(),))
    return conn.execute("""SELECT st.* FROM staff_sessions s JOIN staff st ON st.id = s.staff_id
                           WHERE s.token=? AND s.expires_at >= ?""", (token, time.time())).fetchone()


def admin_or_staff(request: Request, authorization: str = Header(default="")) -> sqlite3.Row | None:
    """F3: accepts either the legacy single admin credential (full, unlimited access - unchanged) or a staff
    session token. Returns None for the legacy path, or the staff row for a staff session, so callers that care
    about per-staff limits (like key creation) can tell the two apart."""
    rate_limit("admin:" + client_ip(request), limit=60, window=60)
    given = authorization.removeprefix("Bearer ").strip()
    if ADMIN_TOKEN and secrets.compare_digest(given.encode(), ADMIN_TOKEN.encode()):
        return None
    now = time.time()
    for token in [t for t, exp in _admin_sessions.items() if exp < now]:
        del _admin_sessions[token]
    if given in _admin_sessions:
        return None
    with db() as conn:
        row = _staff_session(conn, given)
    if row is not None:
        return row
    raise HTTPException(401, "Admin login required.")


def require_role(min_role: str):
    """F3: a staff session whose role is at least ``min_role`` (docs/3.0-PROGRESS.md: Developer > Owner > Moderator
    > Helper). Never accepts the legacy admin credential - that path has no role and should only be used for
    /admin/staff/bootstrap and, unchanged, every pre-existing admin_only endpoint."""
    def dep(authorization: str = Header(default="")) -> sqlite3.Row:
        given = authorization.removeprefix("Bearer ").strip()
        with db() as conn:
            row = _staff_session(conn, given)
        if row is None:
            raise HTTPException(401, "Staff login required.")
        if staff_auth.role_rank(row["role"]) < staff_auth.role_rank(min_role):
            raise HTTPException(403, "Your role doesn't allow this.")
        return row
    return dep


class AdminLogin(BaseModel):
    user: str = Field(max_length=80)
    password: str = Field(max_length=200)


@app.post("/admin/login")
def admin_login(body: AdminLogin, request: Request):
    """Login of the admin panel inside the game. The credentials live only in the server's environment."""
    if not ADMIN_LOGIN:
        raise HTTPException(404, "Not found.")
    rate_limit("adminlogin:" + client_ip(request), limit=6, window=60)           # slows down password guessing
    user_ok = secrets.compare_digest(body.user.strip().encode(), ADMIN_USER.encode())
    pass_ok = secrets.compare_digest(body.password.encode(), ADMIN_PASSWORD.encode())
    if not (user_ok and pass_ok):
        time.sleep(0.4)
        raise HTTPException(401, "Wrong user name or password.")
    token = secrets.token_urlsafe(32)
    _admin_sessions[token] = time.time() + ADMIN_SESSION_MINUTES * 60
    return {"token": token, "minutes": ADMIN_SESSION_MINUTES}


@app.post("/admin/logout", dependencies=[Depends(admin_only)])
def admin_logout(authorization: str = Header(default="")):
    _admin_sessions.pop(authorization.removeprefix("Bearer ").strip(), None)
    return {"ok": True}


def audit(conn: sqlite3.Connection, action: str, user_id: int | None = None, key_id: int | None = None, detail: str = "") -> None:
    """Every change an administrator makes is written down (who it affected, what, when)."""
    conn.execute("INSERT INTO admin_audit(ts, action, user_id, key_id, detail) VALUES(?,?,?,?,?)", (time.time(), action, user_id, key_id, detail[:400]))


def key_status(row) -> str:
    return _key_status(dict(row), time.time())


def like_pattern(text: str) -> str:
    return "%" + text.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


class NewKeys(BaseModel):
    label: str = Field(default="", max_length=60)
    count: int = Field(default=1, ge=1, le=50)
    expires_days: int = Field(default=0, ge=0, le=3650)          # 0 = never expires; otherwise it can only be redeemed within that time


@app.post("/admin/keys")
def admin_create_keys(body: NewKeys, staff=Depends(admin_or_staff)):
    """Create keys. The plain text is returned exactly once; only a hash is stored. Accepts either the legacy
    admin credential (unlimited, unchanged) or a staff session, which is subject to F3's optional per-staff quota."""
    if staff is not None and staff["key_limit"] > 0 and staff["keys_created"] + body.count > staff["key_limit"]:
        raise HTTPException(403, f"Key limit reached ({staff['keys_created']}/{staff['key_limit']}).")
    made = []
    expires = time.time() + body.expires_days * 86400 if body.expires_days else None
    with db() as conn:
        for _ in range(body.count):
            key = new_key()
            cur = conn.execute("INSERT INTO access_keys(key_hash, tail, label, created_at, expires_at) VALUES(?,?,?,?,?)",
                               (hash_key(key), key[-5:], body.label.strip(), time.time(), expires))
            made.append({"id": cur.lastrowid, "key": key, "label": body.label.strip(), "expires_at": expires})
        detail = f"{body.count} key(s), label '{body.label.strip()}', expires in {body.expires_days or 'never'} days"
        if staff is not None:
            detail += f" — by staff #{staff['id']} ({staff['username']})"
            new_total = staff["keys_created"] + body.count
            conn.execute("UPDATE staff SET keys_created=? WHERE id=?", (new_total, staff["id"]))
            if staff["key_limit"] > 0 and new_total >= staff["key_limit"]:
                notify_team(f"**{staff['username']}** has reached their key-creation limit ({new_total}/{staff['key_limit']}).")
        audit(conn, "keys.create", detail=detail)
    return {"keys": made}


KEY_FILTERS = {
    "revoked": "k.revoked = 1",
    "in use": "k.revoked = 0 AND (k.discord_id IS NOT NULL OR k.device_id IS NOT NULL)",
    "expired": "k.revoked = 0 AND k.discord_id IS NULL AND k.device_id IS NULL AND k.expires_at IS NOT NULL AND k.expires_at < :now",
    "unused": "k.revoked = 0 AND k.discord_id IS NULL AND k.device_id IS NULL AND (k.expires_at IS NULL OR k.expires_at >= :now)",
}


@app.get("/admin/keys", dependencies=[Depends(admin_only)])
def admin_list_keys(search: str = "", status: str = "", page: int = 1, per_page: int = 200, newest_first: bool = False):
    """Keys with search (label, last characters, player name, id), status filter and pagination. Never contains a full key."""
    if status and status not in KEY_FILTERS:
        raise HTTPException(400, "Unknown status filter.")
    per_page, page = max(1, min(per_page, 200)), max(1, page)
    params: dict = {"now": time.time()}
    where = ["1=1"]
    if status:
        where.append(KEY_FILTERS[status])
    if search.strip():
        params["like"] = like_pattern(search)
        params["tail"] = normalize_key(search)[-5:]
        where.append("(LOWER(k.label) LIKE :like ESCAPE '\\' OR LOWER(COALESCE(u.name, '')) LIKE :like ESCAPE '\\' "
                      "OR (:tail != '' AND k.tail = :tail) OR CAST(k.id AS TEXT) = :exact)")
        params["exact"] = search.strip()
    base = "FROM access_keys k LEFT JOIN users u ON u.discord_id = k.discord_id WHERE " + " AND ".join(where)
    order = "DESC" if newest_first else "ASC"
    with db() as conn:
        total = conn.execute("SELECT COUNT(*) " + base, params).fetchone()[0]
        rows = conn.execute(f"SELECT k.*, u.name AS user_name, u.id AS user_id " + base + f" ORDER BY k.id {order} LIMIT :lim OFFSET :off",
                            {**params, "lim": per_page, "off": (page - 1) * per_page}).fetchall()
        counts = {name: conn.execute("SELECT COUNT(*) FROM access_keys k WHERE " + clause, {"now": params["now"]}).fetchone()[0]
                  for name, clause in KEY_FILTERS.items()}
    keys = [{"id": r["id"], "key": mask_key(r["tail"]), "label": r["label"], "status": key_status(r), "user": r["user_name"], "user_id": r["user_id"],
             "created_at": r["created_at"], "redeemed_at": r["redeemed_at"], "expires_at": r["expires_at"], "device": bool(r["device_id"])} for r in rows]
    return {"keys": keys, "total": total, "page": page, "pages": max(1, -(-total // per_page)), "counts": counts}


def _end_sessions(conn: sqlite3.Connection, discord_id: str | None) -> None:
    if discord_id:
        conn.execute("DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE discord_id=?)", (discord_id,))


def _key_or_404(conn: sqlite3.Connection, key_id: int):
    row = conn.execute("SELECT * FROM access_keys WHERE id=?", (key_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "No such key.")
    return row


@app.post("/admin/keys/{key_id}/revoke", dependencies=[Depends(admin_only)])
def admin_revoke_key(key_id: int):
    """Deactivates the key and logs its owner out immediately. It can be activated again later."""
    with db() as conn:
        row = _key_or_404(conn, key_id)
        conn.execute("UPDATE access_keys SET revoked=1 WHERE id=?", (key_id,))
        _end_sessions(conn, row["discord_id"])
        audit(conn, "key.deactivate", key_id=key_id)
    return {"id": key_id, "status": "revoked"}


@app.post("/admin/keys/{key_id}/activate", dependencies=[Depends(admin_only)])
def admin_activate_key(key_id: int):
    """Switches a deactivated key back on (its owner can log in again)."""
    with db() as conn:
        row = _key_or_404(conn, key_id)
        if not row["revoked"]:
            raise HTTPException(409, "This key is not deactivated.")
        conn.execute("UPDATE access_keys SET revoked=0 WHERE id=?", (key_id,))
        audit(conn, "key.activate", key_id=key_id)
        status = key_status(conn.execute("SELECT * FROM access_keys WHERE id=?", (key_id,)).fetchone())
    return {"id": key_id, "status": status}


@app.post("/admin/keys/{key_id}/unbind", dependencies=[Depends(admin_only)])
def admin_unbind_key(key_id: int):
    """Frees a key from its Discord account (e.g. the player switched accounts) and logs the old owner out."""
    with db() as conn:
        row = _key_or_404(conn, key_id)
        conn.execute("UPDATE access_keys SET discord_id=NULL, redeemed_at=NULL, device_id=NULL, device_at=NULL WHERE id=?", (key_id,))
        _end_sessions(conn, row["discord_id"])
        audit(conn, "key.free", key_id=key_id)
        status = key_status(conn.execute("SELECT * FROM access_keys WHERE id=?", (key_id,)).fetchone())
    return {"id": key_id, "status": status}


class ExpiryBody(BaseModel):
    days: int = Field(ge=0, le=3650)          # from now; 0 = never expires


@app.post("/admin/keys/{key_id}/expiry", dependencies=[Depends(admin_only)])
def admin_key_expiry(key_id: int, body: ExpiryBody):
    with db() as conn:
        _key_or_404(conn, key_id)
        conn.execute("UPDATE access_keys SET expires_at=? WHERE id=?", (time.time() + body.days * 86400 if body.days else None, key_id))
        audit(conn, "key.expiry", key_id=key_id, detail=f"{body.days or 'never'} days")
        status = key_status(conn.execute("SELECT * FROM access_keys WHERE id=?", (key_id,)).fetchone())
    return {"id": key_id, "status": status}


@app.delete("/admin/keys/{key_id}", dependencies=[Depends(admin_only)])
def admin_delete_key(key_id: int):
    """Deletes the key for good. Its owner is logged out and cannot play until they get a new key (the account itself stays)."""
    with db() as conn:
        row = _key_or_404(conn, key_id)
        _end_sessions(conn, row["discord_id"])
        conn.execute("DELETE FROM access_keys WHERE id=?", (key_id,))
        audit(conn, "key.delete", key_id=key_id, detail=f"tail {row['tail']}")
    return {"id": key_id, "deleted": True}


# ------------------------------------------------------------ player database --
PLAYER_FILTERS = {
    "active": "COALESCE(u.account_status, 'active') = 'active'",
    "disabled": "u.account_status = 'disabled'",
    "banned": "u.account_status = 'banned'",
    "online": "u.last_seen > :online_since",
    "no key": "NOT EXISTS (SELECT 1 FROM access_keys k WHERE k.discord_id = u.discord_id AND k.revoked = 0)",
}
PLAYER_SORTS = {"name": "u.name_lc", "level": "COALESCE(s.level, 0)", "xp": "COALESCE(s.xp_total, 0)", "earned": "COALESCE(s.credits_earned, 0)",
                "registered": "u.created_at", "last login": "COALESCE(u.last_login, 0)", "playtime": "COALESCE(s.playtime, 0)"}


def _details(row) -> dict:
    try:
        return json.loads(row["details"] or "{}")
    except (TypeError, ValueError):
        return {}


def _player_key(conn: sqlite3.Connection, discord_id: str):
    return conn.execute("SELECT * FROM access_keys WHERE discord_id=? ORDER BY revoked, id DESC", (discord_id,)).fetchone()


def player_summary(conn: sqlite3.Connection, r) -> dict:
    key = _player_key(conn, r["discord_id"])
    details = _details(r)
    online = bool(r["last_seen"]) and time.time() - r["last_seen"] < ONLINE_WINDOW
    return {"id": r["id"], "name": r["name"], "account_status": r["account_status"] or "active", "online": online,
            "key": ({"id": key["id"], "key": mask_key(key["tail"]), "label": key["label"], "status": key_status(key)} if key else None),
            "registered": r["created_at"], "last_login": r["last_login"] or None, "last_seen": r["last_seen"] or None,
            "level": r["level"], "rank": r["rank"], "xp_total": r["xp_total"], "credits": details.get("credits"), "credits_earned": r["credits_earned"],
            "missions": r["missions"], "playtime": r["playtime"], "synced_at": r["updated_at"]}


PLAYER_SELECT = """SELECT u.*, s.level, s.rank, s.xp_total, s.missions, s.credits_earned, s.perfect, s.playtime, s.ng_plus, s.updated_at, s.details
                   FROM users u LEFT JOIN scores s ON s.user_id = u.id"""


@app.get("/admin/players", dependencies=[Depends(admin_only)])
def admin_players(search: str = "", status: str = "", sort: str = "registered", direction: str = "desc", page: int = 1, per_page: int = 25):
    """The player database: search by name or account id, filter by status, sort, paginate."""
    if status and status not in PLAYER_FILTERS:
        raise HTTPException(400, "Unknown filter.")
    if sort not in PLAYER_SORTS:
        raise HTTPException(400, "Unknown sort column.")
    per_page, page = max(1, min(per_page, 100)), max(1, page)
    now = time.time()
    params: dict = {"online_since": now - ONLINE_WINDOW}
    where = ["1=1"]
    if status:
        where.append(PLAYER_FILTERS[status])
    if search.strip():
        text = search.strip()
        params["like"] = like_pattern(text)
        params["exact"] = text
        where.append("(u.name_lc LIKE :like ESCAPE '\\' OR CAST(u.id AS TEXT) = :exact OR u.discord_id = :exact)")
    clause = " WHERE " + " AND ".join(where)
    order = "ASC" if direction.lower() == "asc" else "DESC"
    with db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM users u LEFT JOIN scores s ON s.user_id = u.id" + clause, params).fetchone()[0]
        rows = conn.execute(PLAYER_SELECT + clause + f" ORDER BY {PLAYER_SORTS[sort]} {order}, u.id LIMIT :lim OFFSET :off",
                            {**params, "lim": per_page, "off": (page - 1) * per_page}).fetchall()
        players = [player_summary(conn, r) for r in rows]
        counts = {"all": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]}
        for name, filt in PLAYER_FILTERS.items():
            counts[name] = conn.execute("SELECT COUNT(*) FROM users u WHERE " + filt, {"online_since": params["online_since"]}).fetchone()[0]
    return {"players": players, "total": total, "page": page, "pages": max(1, -(-total // per_page)), "counts": counts}


def _player_or_404(conn: sqlite3.Connection, user_id: int):
    row = conn.execute(PLAYER_SELECT + " WHERE u.id=?", (user_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "No such player.")
    return row


@app.get("/admin/players/{user_id}", dependencies=[Depends(admin_only)])
def admin_player(user_id: int):
    """Everything the server knows about one player (never a session token or a full key)."""
    with db() as conn:
        r = _player_or_404(conn, user_id)
        out = player_summary(conn, r)
        details = _details(r)
        score = conn.execute("SELECT perfect, ng_plus FROM scores WHERE user_id=?", (user_id,)).fetchone()
        out.update({
            "discord_id": r["discord_id"], "status_reason": r["status_reason"] or "", "login_count": r["login_count"] or 0, "share": bool(r["share"]),
            "presence": r["status"] if out["online"] else "",
            "perfect": score["perfect"] if score else None, "ng_plus": score["ng_plus"] if score else None,
            "reputation": details.get("reputation"), "heat": details.get("heat"),
            "achievements": details.get("achievements", []), "unlocks": details.get("unlocks", []), "stats": details.get("stats", {}),
            "friends": conn.execute("SELECT COUNT(*) FROM friends WHERE (user_id=? OR friend_id=?) AND status='accepted'", (user_id, user_id)).fetchone()[0],
            "pending_edits": pending_edits(conn, user_id),
            "weeks": [dict(w) for w in conn.execute("SELECT week, xp - base_xp AS xp, missions - base_missions AS missions, credits - base_credits AS credits, "
                                                    "perfect - base_perfect AS perfect FROM week_results WHERE user_id=? ORDER BY week DESC LIMIT 6", (user_id,))],
            "audit": [dict(a) for a in conn.execute("SELECT ts, action, detail FROM admin_audit WHERE user_id=? ORDER BY id DESC LIMIT 15", (user_id,))],
        })
    return out


class EditBody(BaseModel):
    level: StrictInt | None = None                      # strict: "7", 7.5 and true are refused instead of being converted
    xp: StrictInt | None = None
    credits: StrictInt | None = None
    reputation: StrictInt | None = None
    reset: list[str] = Field(default_factory=list, max_length=5)
    reason: str = Field(default="", max_length=200)


@app.post("/admin/players/{user_id}/edit", dependencies=[Depends(admin_only)])
def admin_edit_player(user_id: int, body: EditBody):
    """Change a player. The change is stored in the database right away (so the admin sees it and it survives a restart) and
    queued for the player's game, which applies it to the local save at its next sync and then confirms it."""
    with db() as conn:
        _player_or_404(conn, user_id)
        score = conn.execute("SELECT * FROM scores WHERE user_id=?", (user_id,)).fetchone()
        try:
            ops = validate_edit(body.model_dump(exclude={"reason"}, exclude_none=True), dict(score) if score else None)
        except EditError as exc:
            raise HTTPException(422, str(exc))
        fields, details = {}, _details(score)
        if "level" in ops:
            fields["level"], fields["xp_total"] = ops["level"], cumulative_xp(ops["level"]) + ops["xp"]
        for key in ("credits", "reputation"):
            if key in ops:
                details[key] = ops[key]
        for reset in ops.get("reset", []):
            if reset == "missions":
                fields["missions"], fields["perfect"] = 0, 0
            elif reset == "heat":
                details["heat"] = 0
        fields["details"] = json.dumps(details, separators=(",", ":"))
        conn.execute("UPDATE scores SET " + ", ".join(f"{k}=?" for k in fields) + " WHERE user_id=?", (*fields.values(), user_id))
        cur = conn.execute("INSERT INTO edits(user_id, ops, created_at) VALUES(?,?,?)", (user_id, json.dumps(ops), time.time()))
        fresh = conn.execute("SELECT * FROM scores WHERE user_id=?", (user_id,)).fetchone()
        wk = week_key()                                               # the weekly challenge counts from here, so an edit is no "progress"
        conn.execute("UPDATE week_results SET base_xp=?, base_missions=?, base_credits=?, base_perfect=?, xp=?, missions=?, credits=?, perfect=? "
                     "WHERE week=? AND user_id=?", (fresh["xp_total"], fresh["missions"], fresh["credits_earned"], fresh["perfect"],
                                                    fresh["xp_total"], fresh["missions"], fresh["credits_earned"], fresh["perfect"], wk, user_id))
        audit(conn, "player.edit", user_id=user_id, detail=json.dumps(ops) + (f" — {body.reason.strip()}" if body.reason.strip() else ""))
    return {"ok": True, "edit_id": cur.lastrowid, "ops": ops}


class StatusBody(BaseModel):
    status: str
    reason: str = Field(default="", max_length=200)


@app.post("/admin/players/{user_id}/status", dependencies=[Depends(admin_only)])
def admin_player_status(user_id: int, body: StatusBody):
    """Activate / deactivate / ban an account. Deactivated and banned players are logged out at once and cannot log in again."""
    if body.status not in ACCOUNT_STATUSES:
        raise HTTPException(422, "Status must be one of: " + ", ".join(ACCOUNT_STATUSES) + ".")
    with db() as conn:
        player = _player_or_404(conn, user_id)
        reason = "".join(c for c in body.reason if c.isprintable()).strip() if body.status != "active" else ""
        conn.execute("UPDATE users SET account_status=?, status_reason=? WHERE id=?", (body.status, reason, user_id))
        # no need to delete the sessions: current_user() refuses them at once and tells the player why
        audit(conn, "player." + body.status, user_id=user_id, detail=reason)
    if body.status == "banned":
        notify_team(f"**Player banned**: {player['name']}" + (f" — {reason}" if reason else ""))
    return {"ok": True, "status": body.status}


@app.get("/admin/audit", dependencies=[Depends(admin_only)])
def admin_audit(limit: int = 50):
    with db() as conn:
        rows = conn.execute("SELECT a.ts, a.action, a.user_id, a.key_id, a.detail, u.name AS user FROM admin_audit a LEFT JOIN users u ON u.id = a.user_id "
                            "ORDER BY a.id DESC LIMIT ?", (max(1, min(limit, 200)),)).fetchall()
    return {"entries": [dict(r) for r in rows]}


# -------------------------------------------------------------- reports (F4) --
@app.get("/admin/reports", dependencies=[Depends(admin_only)])
def admin_list_reports(status: str = "open", page: int = 1, per_page: int = 50):
    per_page, page = max(1, min(per_page, 200)), max(1, page)
    where, params = "1=1", {}
    if status:
        where, params = "r.status=:status", {"status": status}
    with db() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM reports r WHERE {where}", params).fetchone()[0]
        rows = conn.execute(f"""SELECT r.*, u.name AS reporter_name FROM reports r LEFT JOIN users u ON u.id = r.reporter_id
                                WHERE {where} ORDER BY r.id DESC LIMIT :lim OFFSET :off""",
                            {**params, "lim": per_page, "off": (page - 1) * per_page}).fetchall()
    return {"reports": [dict(r) for r in rows], "total": total, "page": page, "pages": max(1, -(-total // per_page))}


class ResolveReportBody(BaseModel):
    note: str = Field(default="", max_length=400)


@app.post("/admin/reports/{report_id}/resolve", dependencies=[Depends(admin_only)])
def admin_resolve_report(report_id: int, body: ResolveReportBody):
    # resolved_by stays NULL until F3 gives staff their own accounts - today's admin auth is a single shared login
    with db() as conn:
        row = conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "No such report.")
        conn.execute("UPDATE reports SET status='resolved', resolved_at=?, resolution_note=? WHERE id=?",
                     (time.time(), body.note.strip(), report_id))
        audit(conn, "report.resolve", detail=f"report #{report_id}: {body.note.strip()}")
    return {"ok": True, "id": report_id, "status": "resolved"}


# -------------------------------------------------------------- staff accounts (F3) --
# Deliberately layered ON TOP of the existing single admin credential, never replacing it: every admin_only
# endpoint above keeps working exactly as before. This section adds named staff logins with roles and mandatory
# TOTP, for servers that want more than one person with access and an audit trail of who did what.
def _staff_public(row: sqlite3.Row) -> dict:
    """A staff row with the secrets (password_hash, totp_secret) stripped - the only shape ever returned to a client."""
    d = dict(row)
    d.pop("password_hash", None)
    d.pop("totp_secret", None)
    return d


class StaffBootstrap(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=12, max_length=200)


@app.post("/admin/staff/bootstrap", dependencies=[Depends(admin_only)])
def staff_bootstrap(body: StaffBootstrap):
    """Create the very first staff account (role 'developer', self-approved). Only works once - as soon as any
    staff account exists, use invites instead. Gated behind the legacy admin credential so this can't be used to
    create a rogue account on a server you don't already control."""
    with db() as conn:
        if conn.execute("SELECT COUNT(*) FROM staff").fetchone()[0] > 0:
            raise HTTPException(409, "Staff accounts already exist - use an invite instead.")
        secret = staff_auth.new_totp_secret()
        cur = conn.execute("""INSERT INTO staff(username, username_lc, password_hash, role, totp_secret, approved, created_at)
                              VALUES(?,?,?,?,?,1,?)""",
                           (body.username.strip(), body.username.strip().lower(), staff_auth.hash_password(body.password),
                            "developer", secret, time.time()))
    return {"id": cur.lastrowid, "username": body.username.strip(), "role": "developer",
            "totp_secret": secret, "otpauth_uri": staff_auth.provisioning_uri(secret, body.username.strip())}


class StaffInvite(BaseModel):
    role: str


@app.post("/admin/staff/invite")
def staff_invite(body: StaffInvite, caller=Depends(require_role("moderator"))):
    if body.role not in staff_auth.INVITABLE_ROLES:
        raise HTTPException(422, "Role must be one of: " + ", ".join(staff_auth.INVITABLE_ROLES) + ".")
    if staff_auth.role_rank(body.role) >= staff_auth.role_rank(caller["role"]):
        raise HTTPException(403, "You can only invite a role below your own.")
    code = "INV-" + secrets.token_urlsafe(16)
    with db() as conn:
        conn.execute("INSERT INTO staff_invites(code, role, created_by, created_at, expires_at) VALUES(?,?,?,?,?)",
                     (code, body.role, caller["id"], time.time(), time.time() + STAFF_INVITE_DAYS * 86400))
        audit(conn, "staff.invite", detail=f"role={body.role} by {caller['username']}")
    return {"code": code, "role": body.role, "expires_in_days": STAFF_INVITE_DAYS}


class StaffRedeem(BaseModel):
    code: str
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=12, max_length=200)


@app.post("/admin/staff/redeem")
def staff_redeem(body: StaffRedeem):
    """Public (the invite code itself is the credential - same pattern as a player access key). The account is
    created but not yet active: an Owner+ must approve it (docs: "Login-Genehmigung durch Owner")."""
    rate_limit("staffredeem:" + body.code[:12], limit=10, window=3600)
    username_lc = body.username.strip().lower()
    with db() as conn:
        invite = conn.execute("SELECT * FROM staff_invites WHERE code=?", (body.code,)).fetchone()
        if invite is None or invite["used_by"] is not None or invite["expires_at"] < time.time():
            raise HTTPException(400, "Invalid, used or expired invite code.")
        if conn.execute("SELECT 1 FROM staff WHERE username_lc=?", (username_lc,)).fetchone():
            raise HTTPException(409, "That username is already taken.")
        secret = staff_auth.new_totp_secret()
        cur = conn.execute("""INSERT INTO staff(username, username_lc, password_hash, role, totp_secret, approved, created_at, created_by)
                              VALUES(?,?,?,?,?,0,?,?)""",
                           (body.username.strip(), username_lc, staff_auth.hash_password(body.password),
                            invite["role"], secret, time.time(), invite["created_by"]))
        conn.execute("UPDATE staff_invites SET used_by=?, used_at=? WHERE code=?", (cur.lastrowid, time.time(), body.code))
    notify_team(f"**New staff signup pending approval**: {body.username.strip()} ({invite['role']})")
    return {"id": cur.lastrowid, "username": body.username.strip(), "role": invite["role"], "approved": False,
            "totp_secret": secret, "otpauth_uri": staff_auth.provisioning_uri(secret, body.username.strip())}


class StaffLogin(BaseModel):
    username: str
    password: str
    totp_code: str


@app.post("/admin/staff/login")
def staff_login(body: StaffLogin, request: Request):
    rate_limit("stafflogin:" + client_ip(request), limit=10, window=60)
    with db() as conn:
        row = conn.execute("SELECT * FROM staff WHERE username_lc=?", (body.username.strip().lower(),)).fetchone()
        if row is None or not staff_auth.verify_password(body.password, row["password_hash"]):
            time.sleep(0.4)
            raise HTTPException(401, "Wrong user name or password.")
        if not row["approved"]:
            raise HTTPException(403, "This account is awaiting Owner approval.")
        if not staff_auth.verify_totp(row["totp_secret"], body.totp_code, time.time()):
            time.sleep(0.4)
            raise HTTPException(401, "Wrong or expired authenticator code.")
        if not row["totp_confirmed"]:
            conn.execute("UPDATE staff SET totp_confirmed=1 WHERE id=?", (row["id"],))
        token = secrets.token_urlsafe(32)
        conn.execute("INSERT INTO staff_sessions(token, staff_id, created_at, expires_at) VALUES(?,?,?,?)",
                     (token, row["id"], time.time(), time.time() + STAFF_SESSION_MINUTES * 60))
    return {"token": token, "minutes": STAFF_SESSION_MINUTES, "role": row["role"], "username": row["username"]}


@app.post("/admin/staff/logout")
def staff_logout(authorization: str = Header(default="")):
    with db() as conn:
        conn.execute("DELETE FROM staff_sessions WHERE token=?", (authorization.removeprefix("Bearer ").strip(),))
    return {"ok": True}


@app.get("/admin/staff")
def staff_list(caller=Depends(require_role("owner"))):
    with db() as conn:
        rows = conn.execute("SELECT * FROM staff ORDER BY id").fetchall()
    return {"staff": [_staff_public(r) for r in rows]}


def _staff_or_404(conn: sqlite3.Connection, staff_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM staff WHERE id=?", (staff_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "No such staff account.")
    return row


@app.post("/admin/staff/{staff_id}/approve")
def staff_approve(staff_id: int, caller=Depends(require_role("owner"))):
    with db() as conn:
        target = _staff_or_404(conn, staff_id)
        conn.execute("UPDATE staff SET approved=1 WHERE id=?", (staff_id,))
        audit(conn, "staff.approve", detail=f"{target['username']} approved by {caller['username']}")
    return {"ok": True, "id": staff_id, "approved": True}


class StaffRoleBody(BaseModel):
    role: str


@app.post("/admin/staff/{staff_id}/role")
def staff_set_role(staff_id: int, body: StaffRoleBody, caller=Depends(require_role("owner"))):
    if body.role not in staff_auth.INVITABLE_ROLES:
        raise HTTPException(422, "Role must be one of: " + ", ".join(staff_auth.INVITABLE_ROLES) + ".")
    with db() as conn:
        target = _staff_or_404(conn, staff_id)
        if target["id"] == caller["id"]:
            raise HTTPException(403, "You cannot change your own role.")
        if target["role"] == "developer":
            raise HTTPException(403, "The developer account's role can't be changed here.")
        conn.execute("UPDATE staff SET role=? WHERE id=?", (body.role, staff_id))
        audit(conn, "staff.role", detail=f"{target['username']}: {target['role']} -> {body.role}, by {caller['username']}")
    return {"ok": True, "id": staff_id, "role": body.role}


class StaffKeyLimitBody(BaseModel):
    limit: int = Field(ge=0, le=100_000)


@app.post("/admin/staff/{staff_id}/key-limit")
def staff_set_key_limit(staff_id: int, body: StaffKeyLimitBody, caller=Depends(require_role("owner"))):
    with db() as conn:
        _staff_or_404(conn, staff_id)
        conn.execute("UPDATE staff SET key_limit=? WHERE id=?", (body.limit, staff_id))
        audit(conn, "staff.key_limit", detail=f"staff #{staff_id}: limit={body.limit}, by {caller['username']}")
    return {"ok": True, "id": staff_id, "key_limit": body.limit}


@app.delete("/admin/staff/{staff_id}")
def staff_delete(staff_id: int, caller=Depends(require_role("owner"))):
    with db() as conn:
        target = _staff_or_404(conn, staff_id)
        if target["id"] == caller["id"]:
            raise HTTPException(403, "You cannot delete your own account.")
        if target["role"] == "developer":
            raise HTTPException(403, "The developer account can't be deleted here.")
        conn.execute("DELETE FROM staff WHERE id=?", (staff_id,))
        conn.execute("DELETE FROM staff_sessions WHERE staff_id=?", (staff_id,))
        audit(conn, "staff.delete", detail=f"{target['username']} deleted by {caller['username']}")
    return {"ok": True, "id": staff_id}
