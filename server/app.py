"""NEXUS online service: Discord login, leaderboards, friends and presence.

Run locally:   NEXUS_DEV_LOGIN=1 python -m uvicorn server.app:app --port 8000
Production:    see docs/ONLINE.md (Discord application, environment variables, HTTPS).

It stores only: Discord id, display name, the last submitted score numbers, friend links and a short presence text
(plus, for invite-only servers, the hashes of the access keys and which Discord account redeemed which key).

Invite-only mode (docs/ONLINE.md): when DISCORD_GUILD_ID is set, a player needs (1) to be on your Discord server (and to have
DISCORD_ROLE_ID, if set) and (2) a key that an admin created. Keys are checked at every login.
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import date

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from .validation import Rejected, validate

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
GATED = bool(GUILD_ID) or os.environ.get("NEXUS_REQUIRE_KEY", "") == "1"      # invite-only: a key is required to log in
SESSION_DAYS = int(os.environ.get("NEXUS_SESSION_DAYS", "30"))     # gated servers re-check membership at least this often
KEY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"                  # no 0/O/1/I
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
"""


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(auth_states)")}          # databases created before the key system
    for col, decl in (("key_id", "INTEGER"), ("error", "TEXT")):
        if col not in cols:
            conn.execute(f"ALTER TABLE auth_states ADD COLUMN {col} {decl}")
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
    if GATED:
        with db() as conn:
            session = conn.execute("SELECT created_at FROM sessions WHERE token=?", (token,)).fetchone()
            key = conn.execute("SELECT revoked FROM access_keys WHERE discord_id=? ORDER BY revoked, id DESC", (row["discord_id"],)).fetchone()
        if session and time.time() - session["created_at"] > SESSION_DAYS * 86400:
            raise HTTPException(401, "Session expired — please log in again.")
        if key is None or key["revoked"]:
            raise HTTPException(401, "Your access key is no longer valid.")
    return row


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
        return "This key already belongs to another Discord account."
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


# --------------------------------------------------------------------- auth --
@app.get("/health")
def health():
    return {"ok": True, "dev_login": DEV_LOGIN, "discord": bool(DISCORD_CLIENT_ID), "gated": GATED, "admin": bool(ADMIN_TOKEN or ADMIN_LOGIN)}


class BeginBody(BaseModel):
    state: str
    key: str = Field(default="", max_length=64)


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
    return {"name": user["name"], "share": bool(user["share"]), "score": dict(score) if score else None}


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
        for table, col in (("sessions", "user_id"), ("scores", "user_id"), ("friends", "user_id"), ("friends", "friend_id"), ("users", "id")):
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


@app.post("/scores")
def submit_score(body: ScoreBody, user=Depends(current_user)):
    with db() as conn:
        old = conn.execute("SELECT * FROM scores WHERE user_id=?", (user["id"],)).fetchone()
        elapsed = (time.time() - old["updated_at"]) if old else None
        try:
            clean = validate(body.model_dump(), dict(old) if old else None, elapsed)
        except Rejected as exc:
            raise HTTPException(422, str(exc))
        wk = week_key()
        base = old["week_base_xp"] if old and old["week"] == wk else (old["xp_total"] if old else clean["xp_total"])
        conn.execute("""INSERT INTO scores(user_id, level, xp_total, missions, credits_earned, perfect, playtime, ng_plus, rank, updated_at, week, week_base_xp)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET level=excluded.level, xp_total=excluded.xp_total,
                        missions=excluded.missions, credits_earned=excluded.credits_earned, perfect=excluded.perfect, playtime=excluded.playtime,
                        ng_plus=excluded.ng_plus, rank=excluded.rank, updated_at=excluded.updated_at, week=excluded.week, week_base_xp=excluded.week_base_xp""",
                     (user["id"], clean["level"], clean["xp_total"], clean["missions"], clean["credits_earned"], clean["perfect"], clean["playtime"],
                      clean["ng_plus"], clean["rank"], time.time(), wk, base))
    return {"ok": True}


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


class NewKeys(BaseModel):
    label: str = Field(default="", max_length=60)
    count: int = Field(default=1, ge=1, le=50)


def key_status(row) -> str:
    return "revoked" if row["revoked"] else ("in use" if row["discord_id"] else "unused")


@app.post("/admin/keys", dependencies=[Depends(admin_only)])
def admin_create_keys(body: NewKeys):
    """Create keys. The plain text is returned exactly once; only a hash is stored."""
    made = []
    with db() as conn:
        for _ in range(body.count):
            key = new_key()
            cur = conn.execute("INSERT INTO access_keys(key_hash, tail, label, created_at) VALUES(?,?,?,?)",
                               (hash_key(key), key[-5:], body.label.strip(), time.time()))
            made.append({"id": cur.lastrowid, "key": key, "label": body.label.strip()})
    return {"keys": made}


@app.get("/admin/keys", dependencies=[Depends(admin_only)])
def admin_list_keys():
    with db() as conn:
        rows = conn.execute("SELECT k.*, u.name AS user_name FROM access_keys k LEFT JOIN users u ON u.discord_id = k.discord_id ORDER BY k.id").fetchall()
    return {"keys": [{"id": r["id"], "key": f"NX-*****-*****-{r['tail']}", "label": r["label"], "status": key_status(r), "user": r["user_name"],
                      "created_at": r["created_at"], "redeemed_at": r["redeemed_at"]} for r in rows]}


def _end_sessions(conn: sqlite3.Connection, discord_id: str | None) -> None:
    if discord_id:
        conn.execute("DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE discord_id=?)", (discord_id,))


@app.post("/admin/keys/{key_id}/revoke", dependencies=[Depends(admin_only)])
def admin_revoke_key(key_id: int):
    """Blocks the key for good and logs its owner out immediately."""
    with db() as conn:
        row = conn.execute("SELECT * FROM access_keys WHERE id=?", (key_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "No such key.")
        conn.execute("UPDATE access_keys SET revoked=1 WHERE id=?", (key_id,))
        _end_sessions(conn, row["discord_id"])
    return {"id": key_id, "status": "revoked"}


@app.post("/admin/keys/{key_id}/unbind", dependencies=[Depends(admin_only)])
def admin_unbind_key(key_id: int):
    """Frees a key from its Discord account (e.g. the player switched accounts) and logs the old owner out."""
    with db() as conn:
        row = conn.execute("SELECT * FROM access_keys WHERE id=?", (key_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "No such key.")
        conn.execute("UPDATE access_keys SET discord_id=NULL, redeemed_at=NULL WHERE id=?", (key_id,))
        _end_sessions(conn, row["discord_id"])
    return {"id": key_id, "status": "unused"}
