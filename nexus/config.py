"""Global configuration, paths and constants for NEXUS // TERMINAL."""
from __future__ import annotations

import sys
from pathlib import Path

APP_NAME = "NEXUS"
APP_FULL_NAME = "NEXUS // TERMINAL"
APP_SUBTITLE = "TACTICAL CYBER OPERATIONS"
from .version import VERSION  # noqa: E402  (re-exported)

# --- Paths -----------------------------------------------------------------
# RESOURCE_DIR holds read-only game data (JSON, assets). When frozen with
# PyInstaller it points into the bundle; USER_DIR (saves, generated sounds)
# always sits next to the executable / project folder so it is writable.
FROZEN = bool(getattr(sys, "frozen", False))
_PROJECT_DIR = Path(__file__).resolve().parent.parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", _PROJECT_DIR)) if FROZEN else _PROJECT_DIR
USER_DIR = Path(sys.executable).resolve().parent if FROZEN else _PROJECT_DIR

DATA_DIR = RESOURCE_DIR / "data"
MISSIONS_DIR = RESOURCE_DIR / "missions"
ASSETS_DIR = RESOURCE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
SOUNDS_DIR = ASSETS_DIR / "sounds"
USER_SOUNDS_DIR = USER_DIR / "assets" / "sounds"   # generated fallback sounds

SAVES_DIR = USER_DIR / "saves"
PROFILES_DIR = SAVES_DIR / "profiles"
SLOTS_DIR = SAVES_DIR / "slots"
SETTINGS_FILE = SAVES_DIR / "settings.json"
ERROR_LOG = SAVES_DIR / "error.log"

# --- Palette ---------------------------------------------------------------
COLORS = {
    "bg": "#03080a",
    "bg_alt": "#07120f",
    "panel": "#08141a",
    "panel_hi": "#0c1e26",
    "border": "#0f3b33",
    "green": "#00ff9c",
    "green_dim": "#13a36b",
    "cyan": "#22d3ee",
    "cyan_dim": "#0e7490",
    "red": "#ff3860",
    "amber": "#ffb020",
    "text": "#b8f5cf",
    "dim": "#4b7a6c",
    "white": "#e8fff4",
    "purple": "#b388ff",
}


def apply_theme(palette: dict) -> None:
    """Mutate the shared colour tables in place so every module sees the new theme."""
    COLORS.update(palette)
    STYLE_COLORS.update({
        "normal": COLORS["text"], "ok": COLORS["green"], "info": COLORS["cyan"], "warn": COLORS["amber"],
        "err": COLORS["red"], "dim": COLORS["dim"], "accent": COLORS["green"], "title": COLORS["white"],
        "system": COLORS["purple"], "zero": COLORS["red"],
    })


# Terminal output styles -> colour
STYLE_COLORS = {
    "normal": COLORS["text"],
    "ok": COLORS["green"],
    "info": COLORS["cyan"],
    "warn": COLORS["amber"],
    "err": COLORS["red"],
    "dim": COLORS["dim"],
    "accent": COLORS["green"],
    "title": COLORS["white"],
    "system": COLORS["purple"],
    "story": "#d6fff0",
    "zero": COLORS["red"],
}

FONT_CANDIDATES = ["Cascadia Mono", "Consolas", "JetBrains Mono", "Fira Code", "Lucida Console", "Courier New"]

# --- Progression -----------------------------------------------------------
MAX_LEVEL = 100
RANKS = [
    (1, "SCRIPT KIDDIE"),
    (5, "TECHNICIAN"),
    (10, "OPERATOR"),
    (20, "SPECIALIST"),
    (30, "ELITE"),
    (50, "NEXUS"),
    (75, "ARCHITECT"),
    (100, "NEXUS PRIME"),
]


def xp_for_level(level: int) -> int:
    """XP required to advance from ``level`` to ``level + 1``."""
    return 100 + 40 * max(1, level)


def rank_for_level(level: int) -> str:
    rank = RANKS[0][1]
    for min_level, name in RANKS:
        if level >= min_level:
            rank = name
    return rank


# --- Gameplay constants ----------------------------------------------------
HEAT_MAX = 100.0
HEAT_DECAY_CONNECTED = 0.25     # per second while connected to a server
HEAT_DECAY_IDLE = 0.8           # per second while offline
EVENT_MIN_INTERVAL = 50         # seconds between random events
EVENT_CHANCE_PER_TICK = 0.03
AUTOSAVE_INTERVAL = 60          # seconds

RESOLUTIONS = ["1100x700", "1280x720", "1366x768", "1600x900", "1920x1080"]

DEFAULT_SETTINGS = {
    "volume_master": 70,
    "volume_sfx": 80,
    "volume_music": 40,
    "text_speed": 3,          # 1 (slow) .. 5 (instant-ish)
    "typing_sound": True,
    "scanlines": True,
    "glitch_effects": True,
    "fullscreen": False,
    "resolution": "1280x720",
    "font_size": 12,
    "autosave_seconds": AUTOSAVE_INTERVAL,
    "random_events": True,
    "last_profile": "",
    "tutorial_seen": False,
    "theme": "default",
    "language": "en",
    "animations": True,
    "seen_tips": [],
}
