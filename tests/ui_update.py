"""UI test for the update dialog: renders every state to PNG and drives the staged progress without any network."""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ["NEXUS_NO_AUDIO"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication

from ui.update_dialog import UpdateDialog, format_bytes, notes_to_html
from ui.widgets import build_stylesheet, load_custom_fonts

OUT = Path(os.environ.get("NEXUS_SHOTS", tempfile.mkdtemp(prefix="nexus_shots_")))
OUT.mkdir(exist_ok=True)
app = QApplication([])
load_custom_fonts()
app.setStyleSheet(build_stylesheet(12))

NOTES = """## 2.9.0 — Something new

### Added
- **BOOT CAMP**: a short interactive tutorial with `help` and `connect`
- Faster menus

### Fixed
- Banner <script>alert(1)</script> never went away
Plain line with **bold** text
"""
RELEASE = {"version": "2.9.0", "notes": NOTES, "name": "NEXUS-Setup.exe", "url": "https://github.com/x/y", "sha256_url": None, "page": ""}


def pump(ms):
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("ok:", msg)


# ---- pure helpers
html_out = notes_to_html(NOTES)
check("<script>" not in html_out and "&lt;script&gt;" in html_out, "release notes are HTML-escaped (no injection from a release body)")
check("BOOT CAMP" in html_out and "&#9656;" in html_out, "bullets and bold are rendered")
check(format_bytes(5 * 1024 * 1024) == "5.0 MB" and format_bytes(2048) == "2 KB", "byte formatting")
check("No release notes" in notes_to_html(""), "empty notes handled")

# ---- required dialog
dlg = UpdateDialog(RELEASE, None, required=True)
dlg.show()
pump(600)
dlg.grab().save(str(OUT / "update_required.png"))
check(dlg.later.text() == "QUIT GAME", "required update offers QUIT GAME, not LATER")
dlg.keyPressEvent(type("E", (), {"key": lambda s: 0x01000000})())          # ESC
check(dlg.isVisible(), "ESC does not dismiss a required update")

# ---- staged progress (simulated download)
dlg.go.setEnabled(False)
dlg.later.setEnabled(False)
dlg.hero.speed = 3.0
dlg.bar.show()
dlg.stats.show()
dlg._t0 = time.monotonic() - 2
dlg.status.setText("[1/3]  DOWNLOADING INSTALLER")
dlg._on_progress(12_000_000, 38_000_000)
pump(300)
dlg.grab().save(str(OUT / "update_downloading.png"))
check("11.4 MB / 36.2 MB" in dlg.stats.text() and "ETA" in dlg.stats.text(), "download shows size, speed and ETA")
dlg._on_progress(38_000_000, 38_000_000)
check("VERIFYING" in dlg.status.text(), "stage 2 is the checksum verification")
dlg._failed("Checksum mismatch: the download is damaged.")
pump(200)
dlg.grab().save(str(OUT / "update_failed.png"))
check(dlg.go.isEnabled() and "TRY AGAIN" in dlg.go.text() and dlg.later.isEnabled(), "failure offers retry")
dlg.close()

# ---- optional dialog
opt = UpdateDialog(RELEASE, None, required=False)
opt.show()
pump(500)
opt.grab().save(str(OUT / "update_optional.png"))
check(opt.later.text() == "LATER", "optional update offers LATER")
opt.keyPressEvent(type("E", (), {"key": lambda s: 0x01000000})())
pump(100)
check(not opt.isVisible(), "ESC dismisses an optional update")
print("UPDATE DIALOG UI OK ->", OUT)
