# Changelog

## 2.3.0 — Invite-only login (Discord server + access key)

### Added
- **Invite-only online login**: with `DISCORD_GUILD_ID` set on the server, a player must be on your Discord server (and have
  `DISCORD_ROLE_ID`, if set) and enter an **access key** that an admin created. Checked at every login; leaving/being banned
  blocks the next login, revoking a key logs its owner out at once. Keys bind to the first Discord account that uses them.
- ONLINE page: access-key field (shown only for invite-only servers), clear refusal messages (invalid / revoked / belongs to another
  account / not on the Discord server / missing role) and optional "Open Discord server" button (`DISCORD_URL` in `nexus/version.py`).
- Admin tool `python -m server.keys create|list|revoke|unbind` and `/admin/keys` API (protected by `NEXUS_ADMIN_TOKEN`).
- Servers without `DISCORD_GUILD_ID` keep working exactly as before (open login).

### Changed
- Login is now two steps (`POST /auth/begin`, then the browser login); older game versions are refused on invite-only servers.
- Sessions on invite-only servers last 30 days (`NEXUS_SESSION_DAYS`) so membership is re-checked regularly.

### Tests
- `tests/test_keys.py` (24 server tests incl. faked Discord answers for member / role / not a member), `tests/ui_keys.py` (ONLINE page against an invite-only server).

## 2.2.3 — Banner fix & new update window

### Changed
- **New update window**: version hero (installed -> new build with animated chevrons), formatted release notes, REQUIRED/OPTIONAL badge,
  three clear stages (download with size, speed and ETA -> checksum verification -> installer), retry button on errors, fade-in.
  Release notes are HTML-escaped before display.

### Fixed
- **Level-up (and every other) banner never went away.** The fade-in raised the opacity again on every frame while the
  fade-out lowered it, so the opacity got stuck at ~88% and clicking/Space/Esc could not dismiss it either. Fade-in and
  fade-out are now separate states; skipping moves on to the next queued banner.

## 2.2.2 — Boot camp, mission fixes, big speed-up

### Added
- **BOOT CAMP** (mission 000): a short interactive tutorial before mission 001 (help, connect, scan, ls, cd/cat, hidden files,
  download, hint, disconnect). It starts automatically on a new profile, pays a small reward, does not count as a mission in
  statistics or leaderboards, hands over to mission 001 and can be skipped with `mission abort`.

### Fixed
- **Objectives were lost when done out of order** (e.g. `download manifest.txt` before `cat manifest.txt` in mission 3: the download
  was silently ignored and the objective could not be completed that way). The mission engine now remembers what you did
  and credits it as soon as the objective in front of it is done. Affects every mission.
- Random events could take a mission away from you: a host needed by the current or next story mission could drop off the grid
  or have its firewall re-armed between breach and login. Needed hosts are now protected, and starting a mission brings its hosts back online.
- `hint` now always names the current step (objectives without a written hint get a generic one); mission 3 got a download hint.
- The `disconnect` event reported no server; `mission info 0` handled wrongly.

### Performance
- The full-window CRT overlay repainted every pixel row 16x per second and forced the whole window to repaint with it
  (about 140% CPU while idle). Scanlines/vignette/alert glow are now cached pixmaps and only the moving band is repainted: ~5% CPU idle.
- Main menu: matrix rain uses pre-rendered glyphs, the title is a cached pixmap and only repaints while glitching (menu CPU roughly -65%).
- Market: no more O(n^2) database access (about 4800 queries per refresh); inventory, upgrades, equipment and mission status
  are cached in memory. Market page switch 92 ms -> 3 ms, achievements 217 ms -> <1 ms.
- Pages that nobody is looking at are no longer rebuilt on every engine signal (`mission_changed` 2.3 ms -> 0.2 ms per signal).
- Bell counter uses a COUNT query instead of fetching 60 rows every second.

### Tests
- `tests/test_v22.py`: out-of-order objectives, boot camp, 40 randomised full runs (tutorial -> mission 6 with mistakes, time and random events).
- `tests/ui_campaign.py`: the real window and terminal from first launch through mission 6, plus a responsiveness check.

## 2.2.1 — Online server connected

### Changed
- The game now connects to the production online server (Discord login, leaderboards, friends).

## 2.2.0 — Online services (optional)

### Added
- **ONLINE page**: Discord login, leaderboards (level, missions, credits, weekly XP, perfect), friends list with live status, privacy
  switch and account deletion. Opt-in with a consent box; off completely unless a server is configured.
- **Server** (`server/`, FastAPI + SQLite, Dockerfile) with score plausibility checks, rate limits and a dev login for local testing.
- `docs/ONLINE.md`: Discord application setup, deployment, privacy and API.
- Tests that run the real server on localhost and drive it with the game's client.

## 2.1.0 — Replayability & polish (created by Toto)

### Added
- **Endless contracts**: procedural jobs on the side-grid servers, scaled to your level (CONTRACTS tab, `contract` command).
- **Difficulty modes** (easy / normal / hard) and **New Game+** (prestige: keeps level, items, upgrades, achievements; rewards x1.25 per cycle).
- First-time how-to-play tips for all five mini-games.
- **HIGH CONTRAST** theme, text size up to 24, F12 screenshots to `saves/screenshots`.
- About tab: version, author, *Open save folder*, *Open error log*, optional Discord / releases buttons.
- `about`, `difficulty`, `contract`, `newgameplus` commands; ZERO banners play a glitch sound.

### Added (updates)
- Optional **auto-update** via GitHub Releases (`GITHUB_REPO` in `nexus/version.py`), GitHub Actions release workflow, in-place installer upgrade.

### Changed
- Author credit "Toto" in the menu, terminal welcome, installer, file properties and license.

## 2.0.0 — Full application release

### Added
- **Application shell**: sidebar navigation (Terminal, Operations, Network, Market, Loadout, Inventory, Comms, Profile,
  Achievements, Archives, Settings), top bar with status cards, notification centre, animated toasts.
- **New main menu** with the operator card (username, level, rank, XP, credits, reputation, mission progress).
- **First-launch experience** (system check, profile creation) and an **interactive tutorial**.
- **100 levels**, ranks ARCHITECT (75) and NEXUS PRIME (100), big level-up animation with unlock summary.
- **NEXUS MARKET** (tools, upgrades, cosmetics, access, intelligence; six rarities; daily deal; reputation pricing).
- **Loadout** with five gear slots and percentage stats that change the mini-games; slots unlock with chapters.
- **Daily operations** with a 7-day login streak and **weekly challenges** (stored locally).
- **52 missions** in 6 chapters (36 new: side missions, three secret series), 10 mission types, bonus goals,
  required level / reputation / items, chapter finales with story events.
- **ZERO system** with progress-dependent messages, hidden logs, secret commands, hidden servers and secret missions.
- 13 new servers (26 total), a network map with unexplored `?` hosts, more random events (instability, data leak,
  blackout, server migration, ZERO events, secret data).
- **76 achievements** in 7 categories; statistics dashboard with charts; profile page.
- **7 terminal themes** (DEFAULT, CLASSIC GREEN, CYAN, RED ALERT, PURPLE, AMBER, NEXUS) that restyle the whole UI.
- English / German interface; animations toggle; CRT and glitch effects settings.
- New terminal commands: `missions market shop buy loadout equip unequip profile network daily weekly theme`.
- Windows distribution: `build_exe.bat` (PyInstaller, icon + version resource) and `NEXUS-Setup.exe` installer.

### Changed
- Save database schema v2 (equipment, history, unlocks, notifications). **Older saves migrate automatically**; a
  `.v1.bak` backup is written first.
- Faster saving (throttled commits) and cheaper achievement checks.
- Local download storage raised to 20 files (+5 per STORAGE level).

### Fixed
- Loading a manual slot while the profile database was still open.

## 1.0.0
- Initial release: terminal, 16-mission campaign, five mini-games, contacts, inventory, upgrades, achievements, saves.
