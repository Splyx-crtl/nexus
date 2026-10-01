# Changelog

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
