"""UI campaign test: the real window and terminal, mini-game dialogs auto-solved, from the first launch through
the tutorial and missions 1-6 (every objective, download, decision and hand-over), plus a frame-time check."""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ["NEXUS_NO_AUDIO"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from nexus import config
from nexus.audio import SoundManager
from nexus.save_system import SaveSystem, SettingsStore
from ui.dialogs import LoadDialog, PauseMenu, SlotDialog
from ui.main_window import MainWindow
from ui.minigames import AccessDialog, EncryptionDialog, FirewallDialog, RoutingDialog, TraceDialog
from ui.widgets import build_stylesheet, load_custom_fonts

OUT = Path(os.environ.get("NEXUS_SHOTS", tempfile.mkdtemp(prefix="nexus_shots_")))
OUT.mkdir(exist_ok=True)
app = QApplication([])
load_custom_fonts()
tmp = Path(tempfile.mkdtemp(prefix="nexus_flow_"))
settings = SettingsStore(tmp / "settings.json")
settings.values["text_speed"] = 5
app.setStyleSheet(build_stylesheet(12))
saves = SaveSystem(tmp / "profiles", tmp / "slots")
win = MainWindow(settings, saves, SoundManager(None))
win.resize(1366, 768)
win.show()
solved: list[str] = []


def pump(ms):
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def autosolve():
    dlg = app.activeModalWidget()
    if dlg is None or getattr(dlg, "_done", True):
        return
    if isinstance(dlg, FirewallDialog):
        for sym in dlg.p.secret:
            dlg._place(sym)
        dlg._submit()
    elif isinstance(dlg, EncryptionDialog):
        if dlg.p.type == "caesar":
            dlg.slider.setValue(dlg.p.key)
        elif dlg.p.type == "vigenere":
            dlg.key_input.setText(dlg.p.key)
        dlg._confirm()
    elif isinstance(dlg, RoutingDialog):
        dlg.canvas.path = list(dlg.p.optimal_path)
        dlg._go()
    elif isinstance(dlg, AccessDialog):
        for ch in dlg.p.code:
            dlg._key(ch)
        dlg._key("↵")
    elif isinstance(dlg, TraceDialog):
        for _ in range(dlg.cfg.required_hits):
            dlg._hit()
    else:
        return
    solved.append(type(dlg).__name__)


solver = QTimer()
solver.timeout.connect(autosolve)
solver.start(250)


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("ok:", msg)


from tests.campaign_script import CHOICES, SCRIPT

TUTORIAL = ["help", "connect echo", "scan", "ls", "cd training", "cat lesson.txt", "ls -a", "cat .keycard",
            "download field_notes.dat", "hint", "disconnect"]


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("ok:", msg)


win.startup()
pump(2600)
win.first.edit.setText("CAMPAIGN")
win.first._submit()
pump(3600)
win.story._end()
pump(2500)
e = win.engine
if win.tutorial is not None:
    win.tutorial.close_tutorial()
term = win.shell.terminal_page.terminal


def type_cmd(cmd, wait=300):
    term.input.setText(cmd)
    term.input.returnPressed.emit()
    pump(wait)
    while term.busy:
        pump(100)
    win.banner.queue.clear()
    win.banner.hide()
    e.heat = min(e.heat, 30)          # the trace pressure is covered by test_v22; this test is about the interface


check(e.missions.active()["id"] == "mission_000", "boot camp starts automatically")
for cmd in TUTORIAL:
    type_cmd(cmd)
check(e.missions.is_complete("mission_000"), "boot camp finished through the terminal")
for n in range(1, 7):
    check(e.missions.active() and e.missions.active()["number"] == n, f"mission {n} is the active mission")
    for cmd in SCRIPT[n]:
        type_cmd(cmd, wait=500 if cmd.split()[0] in ("firewall", "route", "trace", "decrypt") else 300)
    if n in CHOICES:
        type_cmd(f"choose {CHOICES[n]}")
    check(e.missions.is_complete(f"mission_{n:03d}"), f"mission {n} completed in the real UI")
    if n < 6:
        type_cmd(f"mission start {n + 1}")
check(e.player.completed_missions == 6, "six real missions counted, the tutorial is not one of them")
print("mini-games solved:", solved)

# ------------------------------------------------------------------ banners must disappear (level-up animation bug)
win.banner.queue.clear()
win.banner.hide()
win.banner.push("levelup", ["LEVEL UP", "+1 LEVEL  ->  2"])
check(win.banner.isVisible(), "level-up banner is shown")
deadline = time.time() + 9
while win.banner.isVisible() and time.time() < deadline:
    pump(100)
check(not win.banner.isVisible(), "level-up banner fades out by itself")
win.banner.push("complete", ["MISSION COMPLETE", "+100 XP"])
win.banner.push("levelup", ["LEVEL UP"])
pump(1500)
win.banner._skip()
win.banner._skip()
deadline = time.time() + 3
while win.banner.isVisible() and win.banner.kind == "complete" and time.time() < deadline:
    pump(100)
check(win.banner.kind == "levelup", "skipping a banner moves on to the next queued one")
deadline = time.time() + 9
while win.banner.isVisible() and time.time() < deadline:
    pump(100)
check(not win.banner.isVisible(), "queued banners all disappear")

# ------------------------------------------------------------------ responsiveness
import statistics
frames = []
last = [time.perf_counter()]
tick = QTimer()
tick.setInterval(16)
tick.timeout.connect(lambda: (frames.append((time.perf_counter() - last[0]) * 1000), last.__setitem__(0, time.perf_counter())))
tick.start()
for page in ("operations", "market", "achievements", "inventory", "comms", "network", "terminal"):
    win.shell.show_page(page)
    pump(400)
tick.stop()
worst = max(frames)
print(f"event loop: median gap {statistics.median(frames):.1f} ms, worst gap {worst:.0f} ms over {len(frames)} frames")
check(worst < 250, "no page switch freezes the interface for a quarter of a second")
print("UI CAMPAIGN PASSED")
