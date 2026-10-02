"""Single source of truth for the application version and project links."""

VERSION = "2.2.3"
APP_NAME = "NEXUS"
APP_TITLE = "NEXUS // TERMINAL"
APP_TAGLINE = "TACTICAL CYBER OPERATIONS"
BUILD_CHANNEL = "release"
AUTHOR = "Toto"

# Community links (opened in the user's browser only when they click a button; empty = button hidden).
DISCORD_URL = ""
RELEASES_URL = ""

# Online services (Discord login, leaderboards, friends). Empty = the game has no online features at all.
# Set to your deployed server, e.g. "https://nexus.example.com" (see docs/ONLINE.md).
ONLINE_SERVER_URL = "https://nexus-production-b0c9.up.railway.app"

# Auto-update (see README "Updates"): "owner/repository" of the public GitHub repo that hosts your releases.
# Empty = the game never checks for updates and makes no network connection at all.
GITHUB_REPO = "Splyx-crtl/nexus"
UPDATE_REQUIRED = True        # True: an outdated installed game must update before it can be played
if GITHUB_REPO and not RELEASES_URL:
    RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"
