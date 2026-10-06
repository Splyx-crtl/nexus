"""A5: a performance baseline - startup, page switching, command output. Not a CI gate, just a repeatable way to
get real numbers and notice if something later makes the game feel slower than it used to.

Run:  set QT_QPA_PLATFORM=windows  &  .venv\\Scripts\\python tools\\benchmark.py
"""
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ["NEXUS_NO_AUDIO"] = "1"
os.environ["NEXUS_LICENSE_PUBKEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

t_import_start = time.perf_counter()
from PySide6.QtWidgets import QApplication

app = QApplication([])
from nexus.audio import SoundManager
from nexus.save_system import SaveSystem, SettingsStore
from ui.main_window import MainWindow
from ui.widgets import build_stylesheet, load_custom_fonts

t_import_done = time.perf_counter()

tmp = Path(tempfile.mkdtemp(prefix="nexus_bench_"))
settings = SettingsStore(tmp / "settings.json")
settings.values["text_speed"] = 5
saves = SaveSystem(tmp / "profiles", tmp / "slots")


def pump(ms=50):
    end = time.perf_counter() + ms / 1000
    while time.perf_counter() < end:
        app.processEvents()
        time.sleep(0.002)


def timed(label, fn, repeats=1):
    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        pump(20)
        samples.append((time.perf_counter() - t0) * 1000)
    ms = statistics.mean(samples)
    print(f"{label:<45} {ms:8.1f} ms" + (f"   (n={repeats}, median {statistics.median(samples):.1f})" if repeats > 1 else ""))
    return ms


load_custom_fonts()
app.setStyleSheet(build_stylesheet(12))

t0 = time.perf_counter()
win = MainWindow(settings, saves, SoundManager(None))
t_window_built = (time.perf_counter() - t0) * 1000
print(f"{'MainWindow construction':<45} {t_window_built:8.1f} ms")

t0 = time.perf_counter()
win.startup()
pump(400)
t_startup = (time.perf_counter() - t0) * 1000
print(f"{'startup() to first-launch screen visible':<45} {t_startup:8.1f} ms")

win.first.edit.setText("BENCH")
t0 = time.perf_counter()
win.first._submit()
pump(3600)          # this includes ~6.1s of deliberate cinematic/typing-effect pacing, not processing time -
win.story._end()    # the number below is dominated by intentional pauses, not a performance measurement
pump(2500)
t_new_profile = (time.perf_counter() - t0) * 1000
print(f"{'new profile -> intro -> terminal ready (mostly scripted pacing, not perf)':<45} {t_new_profile:8.1f} ms")

shell = win.shell
PAGES = ["terminal", "market", "loadout", "inventory", "network", "profile", "achievements", "settings"]
page_times = []
for page in PAGES:
    ms = timed(f"page switch: {page}", lambda p=page: shell.show_page(p))
    page_times.append(ms)
print(f"{'page switch (mean of ' + str(len(PAGES)) + ')':<45} {statistics.mean(page_times):8.1f} ms")

shell.show_page("terminal")
pump(300)
term = shell.terminal_page.terminal
cmd_times = []
for cmd in ["help", "scan echo", "ls", "whoami", "status"]:
    t0 = time.perf_counter()
    term.input.setText(cmd)
    term.input.returnPressed.emit()
    pump(150)
    while term.busy:
        pump(100)
    cmd_times.append((time.perf_counter() - t0) * 1000)
print(f"{'command output (mean of ' + str(len(cmd_times)) + ')':<45} {statistics.mean(cmd_times):8.1f} ms")

print(f"\n{'(import time, not counted above)':<45} {(t_import_done - t_import_start) * 1000:8.1f} ms")
win.close()
