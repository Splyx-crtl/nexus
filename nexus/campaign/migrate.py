"""A3: "on first 3.0.0 launch, archive old profiles, start fresh" — the user's decision recorded in
docs/3.0-PROGRESS.md §1: full replacement, no classic mode, old saves archived (not migrated — a 2.x profile has no
mission/level data that maps onto the all-new v3 campaign)."""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from ..database import Database
from ..save_system import SaveSystem
from .profile import CampaignProfile


def _move_with_retry(src: Path, dest: Path, attempts: int = 10, delay: float = 0.1) -> None:
    """Windows can briefly hold a just-closed SQLite file locked (antivirus/indexer), so a move right after
    ``Database.close()`` occasionally raises PermissionError even though the connection is genuinely closed —
    a few short retries clear it without surfacing a user-facing error for what is a transient OS delay."""
    for attempt in range(attempts):
        try:
            shutil.move(str(src), str(dest))
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay)


def ensure_v3_profile(saves: SaveSystem, username: str, archive_dir: Path | None = None) -> Database:
    """Return a v3 ``Database`` ready to play. If the latest profile on disk is a pre-3.0 save, it is moved into
    ``archive_dir`` (default: a sibling ``archive_2x/`` of the profiles directory) untouched, and a brand-new v3
    profile is created under ``username`` in its place. If the latest profile is already v3, it is returned as-is
    (``username`` is ignored in that case — the existing operator continues)."""
    archive_dir = archive_dir or (saves.profiles_dir.parent / "archive_2x")
    latest = saves.latest_profile()
    if latest is not None:
        db = saves.open_profile(latest.path)
        if CampaignProfile.is_v3(db):
            return db
        db.close()
        archive_dir.mkdir(parents=True, exist_ok=True)
        dest = archive_dir / latest.path.name
        counter = 2
        while dest.exists():
            dest = archive_dir / f"{latest.path.stem}_{counter}{latest.path.suffix}"
            counter += 1
        _move_with_retry(latest.path, dest)
    db = saves.create_profile(username)
    CampaignProfile.init_v3(db, username)
    return db


def has_pending_2x_profile(saves: SaveSystem) -> bool:
    """True if the latest profile on disk predates 3.0.0 and still needs the archive-and-restart flow — the signal
    a first-run screen should use to show the "your old save is being archived" notice."""
    latest = saves.latest_profile()
    if latest is None:
        return False
    db = saves.open_profile(latest.path)
    try:
        return not CampaignProfile.is_v3(db)
    finally:
        db.close()
