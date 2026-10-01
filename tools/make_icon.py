"""Renders assets/nexus.svg into assets/nexus.png and assets/nexus.ico (run once; results are committed)."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

app = QApplication([])
renderer = QSvgRenderer(str(ROOT / "assets" / "nexus.svg"))
for size, name in ((256, "nexus.png"), (256, "nexus.ico")):
    img = QImage(QSize(size, size), QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    renderer.render(p)
    p.end()
    ok = img.save(str(ROOT / "assets" / name))
    print(name, ok)
sys.exit(0)
