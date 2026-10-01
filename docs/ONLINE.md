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
   The only scope the game uses is `identify` (Discord username only; no e-mail, no servers, no messages).

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
| `GET /auth/start?state=` · `GET /auth/callback` · `POST /auth/poll` | browser login; the game polls until the token is ready |
| `GET /me` · `POST /me/share` · `DELETE /me` | profile, privacy, erase account |
| `POST /scores` · `GET /leaderboard?board=level\|missions\|credits\|weekly\|perfect` | scores and rankings |
| `GET /friends` · `POST /friends/request` · `POST /friends/respond` · `DELETE /friends/{name}` | friends |
| `POST /presence` | heartbeat + status (online = seen in the last 2 minutes) |

## Next steps (ideas)

Co-op contracts for two players (server-assigned sub-tasks over WebSockets), weekly community challenges with a shared seed,
clan boards. Those need the server to hand out and verify the tasks.
