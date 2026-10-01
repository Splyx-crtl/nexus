"""Single source of truth for the application version and project links."""

VERSION = "2.1.0"
APP_NAME = "NEXUS"
APP_TITLE = "NEXUS // TERMINAL"
APP_TAGLINE = "TACTICAL CYBER OPERATIONS"
BUILD_CHANNEL = "release"
AUTHOR = "Toto"

# Community links (opened in the user's browser only when they click a button; empty = button hidden).
DISCORD_URL = ""
RELEASES_URL = ""

# Auto-update (see README "Updates"): "owner/repository" of the public GitHub repo that hosts your releases.
# Empty = the game never checks for updates and makes no network connection at all.
GITHUB_REPO = ""
UPDATE_REQUIRED = True        # True: an outdated installed game must update before it can be played
if GITHUB_REPO and not RELEASES_URL:
    RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"
