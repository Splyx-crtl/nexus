"""Renders every mini-game dialog (non-modal) and saves screenshots for visual review."""
import os
import random
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ["NEXUS_NO_AUDIO"] = "1"
os.environ["NEXUS_LICENSE_PUBKEY"] = ""                      # these scripts test other things: no game key needed (tests/ui_license.py covers it)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication, QWidget

from nexus.minigames import AccessPuzzle, EncryptionPuzzle, FirewallPuzzle, RoutingPuzzle, TraceConfig
from ui.minigames import AccessDialog, EncryptionDialog, FirewallDialog, RoutingDialog, TraceDialog
from ui.widgets import build_stylesheet, load_custom_fonts

OUT = Path(os.environ.get("NEXUS_SHOTS", tempfile.mkdtemp(prefix="nexus_shots_")))
OUT.mkdir(exist_ok=True)
app = QApplication([])
load_custom_fonts()
app.setStyleSheet(build_stylesheet(12))
host = QWidget()
host.resize(1280, 720)
host.show()


def pump(ms):
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def snap(dialog, name):
    dialog.show()
    pump(700)
    dialog.grab().save(str(OUT / f"mg_{name}.png"))
    print("shot", name)
    dialog.close()


rng = random.Random(3)
fw = FirewallDialog(host, FirewallPuzzle(6, 4, 6, rng, True, "VAULT-GATE"))
fw._place(0); fw._place(1); fw._place(2); fw._place(3); fw._submit(); fw._place(4); fw._place(5); fw._place(1)
snap(fw, "firewall")
enc = EncryptionDialog(host, EncryptionPuzzle("PROJECT LAZARUS MEMO\nSUBJECTS ARE PROCESSES", "caesar", 7, ["The shift is a single digit.", "Seven."], 1, "LAZARUS.ENC"))
enc.slider.setValue(5)
snap(enc, "encryption")
rt = RoutingDialog(host, RoutingPuzzle(42, 2, 0, False, "GHOSTNET"))
for n in rt.p.optimal_path[1:3]:
    rt.canvas.path.append(n)
rt.canvas.path_changed.emit()
snap(rt, "routing")
ac = AccessDialog(host, AccessPuzzle.generate(random.Random(5), 4, 4))
ac._key("4"); ac._key("2")
snap(ac, "access")
tr = TraceDialog(host, TraceConfig(5, 3, 1.0, 6, "TUNNEL TRAFFIC"))
snap(tr, "trace")
