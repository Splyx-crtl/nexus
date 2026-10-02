# NEXUS online service

Optional features: **Discord login, leaderboards, friends list with live status**. The game works fully offline;
online features are off until you deploy the server and put its address into `nexus/version.py`.

```
Game (nexus/online.py)  ──HTTPS──▶  Your server (server/app.py, FastAPI + SQLite)  ──▶  Discord OAuth
```

## 1. Create the Discord application (5 minutes, free)

1. Go to https://discord.com/developers/applications → **New Application** → name it `NEXUS`.
2. **OAuth2** → copy the **Client ID** and **Client Secret** (reset it once to see it).
3. **OAuth2 → Redirects** → add `https://YOUR-SERVER/auth/callback` (exactly your public server address + `/auth/callback`).
   The scope the game uses is `identify` (Discord username only; no e-mail, no messages). On invite-only servers it adds `guilds.members.read`,
   which only answers "is this person on *your* server, and with which roles".

## 2. Run the server

Environment variables:

| Variable | Meaning |
|---|---|
| `DISCORD_CLIENT_ID` / `DISCORD_CLIENT_SECRET` | from step 1 |
| `PUBLIC_URL` | public HTTPS address, e.g. `https://nexus.example.com` |
| `NEXUS_DB` | path of the SQLite file (keep it on a persistent volume) |
| `NEXUS_DEV_LOGIN` | `1` only on your own PC for testing (lets you log in without Discord). **Never in production.** |

Local test (no Discord needed):

```text
pip install -r server/requirements.txt
set NEXUS_DEV_LOGIN=1
python -m uvicorn server.app:app --port 8000
set NEXUS_SERVER_URL=http://127.0.0.1:8000
set NEXUS_DEV_NAME=Toto
python main.py          # ONLINE page → tick the box → LOGIN
```

Production with Docker (any VPS or container host such as Hetzner, Fly.io, Render, Railway):

```text
docker build -f server/Dockerfile -t nexus-online .
docker run -d -p 8000:8000 -v nexus-data:/data -e DISCORD_CLIENT_ID=... -e DISCORD_CLIENT_SECRET=... -e PUBLIC_URL=https://nexus.example.com nexus-online
```

Put it behind HTTPS (Caddy, nginx + Let's Encrypt, or the host's built-in TLS). The game **refuses** plain HTTP to remote hosts.
Typical cost: about 5 € per month for a small VPS, or free tiers for a few players.

## 3. Point the game to it

In `nexus/version.py`: `ONLINE_SERVER_URL = "https://nexus.example.com"`, bump `VERSION`, release (see README → Updates).
Players then see **ONLINE** → *Login with Discord* in the sidebar.

## 4. Invite-only: Discord server + access key (optional, recommended)

With this switched on, nobody can log in unless they (1) are a member of **your Discord server**, (2) have the role you
choose (optional) and (3) hold an **access key** that you created. Everything is checked at every login, so someone who leaves
or is banned from your server cannot log in again, and a revoked key logs its owner out immediately.

### Switch it on (Railway or any host)

1. In Discord: *User Settings → Advanced → Developer Mode* on. Right-click your server icon → **Copy Server ID**.
   Optional: *Server Settings → Roles* → right-click the role → **Copy Role ID**.
2. Set these environment variables on the server and redeploy:

| Variable | Meaning |
|---|---|
| `DISCORD_GUILD_ID` | the server ID. Setting it turns invite-only on (and adds the `guilds.members.read` scope to the login) |
| `DISCORD_ROLE_ID` | optional: players also need this role on that server |
| `NEXUS_ADMIN_USER` · `NEXUS_ADMIN_PASSWORD` | the admin login of the **ADMIN panel inside the game** (password: 12+ characters). They exist only here on the server; the game contains no credentials |
| `NEXUS_ADMIN_TOKEN` | optional: a long random secret (30+ characters) for the command-line tool below. Set the login above, the token, or both. Without any of them nobody can create keys |
| `NEXUS_SESSION_DAYS` | optional: sessions last this long before a new login re-checks membership (default 30) |

   The Discord application from step 1 needs nothing else: no bot, no privileged intents. Players are asked for permission to
   "know which servers they are in" only for your server; the game never sees the others.
3. The game must be released with the new login screen (version 2.3.0 or newer). Older versions are refused with a clear message.

### Hand out keys

**In the game:** click **ADMIN** at the bottom of the sidebar, log in with `NEXUS_ADMIN_USER` / `NEXUS_ADMIN_PASSWORD`, then
create keys (label + amount), copy them (shown only once), and revoke or free keys from the list. The admin session lives only in
memory and ends after 60 minutes or on LOG OUT. Wrong passwords are rate limited (6 tries per minute per address).
Anyone can open the panel, but without the right login they see nothing: the check happens on the server.

**On the command line** (needs `NEXUS_ADMIN_TOKEN`):

```text
set NEXUS_SERVER_URL=https://YOUR-SERVER
set NEXUS_ADMIN_TOKEN=the-same-secret
python -m server.keys create "Alice" -n 1      make a key (shown once, only a hash is stored)
python -m server.keys list                     who uses which key (unused / in use / revoked)
python -m server.keys revoke 7                 block key #7 and log its owner out
python -m server.keys unbind 7                 free key #7 from its Discord account (player switched accounts)
```

Send the key to the player in a private message. In the game: **ONLINE → paste the key → Login with Discord**.
A key binds to the first Discord account that logs in with it; sharing it does not work. One Discord account can use one key.

Keys look like `NX-7K2QF-9WMXA-3HTRB` (case and dashes do not matter when typing). Wrong guesses are rate limited per address.

## What is stored on the server

* Discord user id and display name, session tokens,
* last submitted score: level, XP, missions, credits earned, perfect missions, playtime, rank, New Game+ count,
* friend links and a short presence text ("Mission 007 · LOCKDOWN").

Never: save files, local paths, e-mail addresses, passwords. Players can hide themselves (ACCOUNT → privacy) or
delete everything (ACCOUNT → *Delete my online account*, which calls `DELETE /me`).

If you run this publicly you are the data controller: add a short privacy notice and an imprint/contact where your players
can find it (Discord server, README, store page). Ask a professional if unsure (GDPR).

## Cheating — an honest limit

Scores are computed on the player's PC. `server/validation.py` rejects impossible values (level out of range, XP not matching the level,
values going backwards, huge jumps, submissions faster than every 15 s), but a determined cheater can still submit
believable numbers. Treat the leaderboards as *for fun*. For competitive rankings the server would have to run the game logic itself.

## API overview

| Endpoint | Purpose |
|---|---|
| `POST /auth/begin` · `GET /auth/start?state=` · `GET /auth/callback` · `POST /auth/poll` | login: the game announces the attempt (and the key), the browser does Discord, the game polls until the token is ready (or the refusal reason arrives) |
| `POST /admin/login` · `POST/GET /admin/keys` · `POST /admin/keys/{id}/revoke\|unbind` | key management, only with `Authorization: Bearer <NEXUS_ADMIN_TOKEN or the session token of /admin/login>` |
| `GET /me` · `POST /me/share` · `DELETE /me` | profile, privacy, erase account |
| `POST /scores` · `GET /leaderboard?board=level\|missions\|credits\|weekly\|perfect` | scores and rankings |
| `GET /friends` · `POST /friends/request` · `POST /friends/respond` · `DELETE /friends/{name}` | friends |
| `POST /presence` | heartbeat + status (online = seen in the last 2 minutes) |

## Next steps (ideas)

Co-op contracts for two players (server-assigned sub-tasks over WebSockets), weekly community challenges with a shared seed,
clan boards. Those need the server to hand out and verify the tasks.
