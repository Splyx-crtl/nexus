"""v2 UI smoke test: first launch, menu, all shell pages, tutorial, level-up banner, themes. Saves screenshots."""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ["NEXUS_NO_AUDIO"] = "1"
os.environ["NEXUS_LICENSE_PUBKEY"] = ""                      # these scripts test other things: no game key needed (tests/ui_license.py covers it)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication

from nexus.audio import SoundManager
from nexus.save_system import SaveSystem, SettingsStore
from tests.campaign_script import SCRIPT
from tests.driver import run
from ui.app_shell import KEYS
from ui.main_window import MainWindow
from ui.widgets import build_stylesheet, load_custom_fonts

OUT = Path(os.environ.get("NEXUS_SHOTS", tempfile.mkdtemp(prefix="nexus_shots_")))
OUT.mkdir(exist_ok=True)
app = QApplication([])
load_custom_fonts()
tmp = Path(tempfile.mkdtemp(prefix="nexus_v2_"))
settings = SettingsStore(tmp / "settings.json")
settings.values["text_speed"] = 5
app.setStyleSheet(build_stylesheet(12))
saves = SaveSystem(tmp / "profiles", tmp / "slots")
win = MainWindow(settings, saves, SoundManager(None))
win.resize(1366, 768)
win.show()


def pump(ms):
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def shot(name):
    win.grab().save(str(OUT / f"v2_{name}.png"))
    print("shot", name)


# ---- first launch
win.startup()
pump(900)
shot("first_boot")
pump(2200)
shot("first_form")
win.first.edit.setText("NOVA")
win.first._submit()
pump(3200)                                   # fade + loading
win.story._end()
pump(1500)
assert win.shell is not None and win.engine.player.username == "NOVA"
pump(1500)
shot("tutorial_1")
win.shell.terminal_page.terminal.run_command("help")
pump(2500)
shot("tutorial_after_help")
for _ in range(9):
    win.tutorial._next() if win.tutorial.isVisible() and win.tutorial.next.isEnabled() else None
    pump(300)
if win.tutorial.isVisible():
    win.tutorial.close_tutorial()

# ---- progress headlessly, then look at every page
e = win.engine
for n in (1, 2, 3):
    run(e, f"mission start {n}")
    for cmd in SCRIPT[n]:
        run(e, cmd)
        e.heat = 0
win.banner.queue.clear()
win.banner.hide()
e.player._set(level=14, credits=62000, reputation=62)
run(e, "buy trace_booster")
run(e, "equip trace_booster")
run(e, "buy firewall_analyzer")
run(e, "equip firewall_analyzer")
e.progress.claim_daily()
e.snapshot_history()
for key in KEYS:
    win.shell.show_page(key)
    pump(500)
    shot(f"page_{key}")

# ---- menu
win.to_menu()
pump(1200)
shot("menu")

# ---- level-up banner
win.on_menu_action("terminal")
pump(900)
e.grant_xp(3000, announce=False, bonus=False)
pump(1800)
shot("levelup")
win.banner.queue.clear()
win.banner.hide()

# ---- theme switch
e.player._set(credits=99999)
run(e, "buy theme_amber")
settings.set("theme", "amber")
win.reload_ui()
pump(800)
win.shell.show_page("profile")
pump(600)
shot("theme_amber_profile")
win.to_menu()
pump(900)
shot("theme_amber_menu")
settings.set("theme", "default")
settings.set("language", "de")
win.reload_ui()
pump(800)
shot("lang_de_menu")
settings.set("language", "en")
win.reload_ui()
win.close()
print("UI V2 SMOKE DONE")
