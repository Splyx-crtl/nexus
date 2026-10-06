"""D2: the 3D network map (ui/network_map_3d.py, ui/qml/network_map_3d.qml). Needs a real Qt Quick 3D-capable
window, so this is a standalone script like the other tests/ui_*.py harnesses, not part of the unittest run.

Run:  set QT_QPA_PLATFORM=windows  &  .venv\\Scripts\\python tests\\ui_map3d.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ["NEXUS_NO_AUDIO"] = "1"
os.environ["NEXUS_LICENSE_PUBKEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

app = QApplication([])

from nexus.game_engine import GameEngine
from nexus.save_system import SaveSystem, SettingsStore
from ui.network_map_3d import try_build_3d_view

OUT = Path(os.environ.get("NEXUS_SHOTS", tempfile.mkdtemp(prefix="nexus_shots_")))
OUT.mkdir(exist_ok=True)

tmp = Path(tempfile.mkdtemp())
settings = SettingsStore(tmp / "settings.json")
saves = SaveSystem(tmp / "profiles", tmp / "slots")
db = saves.create_profile("tester")
engine = GameEngine(db, settings)
engine.player._set(level=25, credits=100_000)

failures: list[str] = []


def check(cond, msg):
    print(("ok: " if cond else "FAIL: ") + msg)
    if not cond:
        failures.append(msg)


# discover a handful of servers so the scene has real nodes/links to show
ids = list(engine.data.servers.keys())[:12]
for sid in ids:
    engine.world.discover(sid)
linked = [sid for sid in ids if engine.world.servers[sid].links]
if linked:
    engine.world.current = linked[0]
engine.heat = 85

widget, bridge = try_build_3d_view(engine)
check(widget is not None and bridge is not None, "Qt Quick 3D loads in this environment")
check(len(bridge.nodes) == len(ids), "every discovered server becomes a 3D node")
check(len(bridge.links) >= 1, "at least one link drawn between discovered, linked servers")
check(all({"x", "y", "z", "color", "glow"} <= set(n) for n in bridge.nodes), "every node carries position/color/glow")
current_node = next(n for n in bridge.nodes if n["id"] == engine.world.current)
from nexus.config import COLORS
check(current_node["color"] == COLORS["cyan"] and current_node["glow"] == 1.0, "the current node is colored/glowing distinctly")
check(any(l["active"] for l in bridge.links), "the link touching the current node is marked active")
check(bridge.traceActive, "high heat activates the trace wave")
engine.heat = 10
bridge.refresh(engine)
check(not bridge.traceActive, "low heat deactivates the trace wave")

widget.resize(900, 650)
widget.show()


def finish():
    widget.grab().save(str(OUT / "map3d.png"))
    print("MAP3D FAILED" if failures else "MAP3D OK — screenshot in", OUT)
    app.quit()


QTimer.singleShot(1200, finish)
app.exec()
sys.exit(1 if failures else 0)
