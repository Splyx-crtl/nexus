"""NETWORK: graphical map of the simulated NEXUS network. Areas unlock with progress."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QListWidget, QVBoxLayout, QWidget

from nexus.config import COLORS
from nexus.i18n import tr

from .widgets import NeonButton, mono_font

REGION_COLORS = {"OUTER": "text", "CORE": "green", "VAULT": "purple", "SHADOW": "purple", "TRANSIT": "cyan", "LAB": "amber",
                 "SPACE": "cyan", "GRID": "red", "ARCHIVE": "amber", "BUNKER": "red", "PORT": "cyan", "POWER": "amber",
                 "TELECOM": "cyan", "FINANCE": "green", "INDUSTRY": "amber", "BIOTECH": "green", "SURVEY": "cyan",
                 "DEFENSE": "red", "LAW": "purple", "MEDICAL": "red", "HIDDEN": "white"}


class NetworkMapWidget(QWidget):
    node_selected = Signal(str)

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.selected: str | None = None
        self.hover: str | None = None
        self.phase = 0.0
        self.setMouseTracking(True)
        self.setMinimumHeight(300)
        timer = QTimer(self, interval=60)
        timer.timeout.connect(self._tick)
        timer.start()

    def _tick(self) -> None:
        if self.isVisible():
            self.phase = (self.phase + 0.08) % (2 * math.pi)
            self.update()

    def _pos(self, sid: str) -> QPointF:
        x, y = self.engine.world.servers[sid].pos
        return QPointF(36 + x * (self.width() - 72), 26 + y * (self.height() - 56))

    def _visible_nodes(self) -> list[str]:
        """Discovered hosts plus silhouettes of the not-yet-found regular hosts (hidden hosts stay invisible)."""
        w = self.engine.world
        known = set(w.discovered())
        return [sid for sid, d in self.engine.data.servers.items() if sid in known or not d.get("hidden")]

    def _node_at(self, point: QPointF) -> str | None:
        for sid in self._visible_nodes():
            if (self._pos(sid) - point).manhattanLength() < 20:
                return sid
        return None

    def mouseMoveEvent(self, ev) -> None:
        node = self._node_at(ev.position())
        if node != self.hover:
            self.hover = node
            self.setCursor(Qt.CursorShape.PointingHandCursor if node else Qt.CursorShape.ArrowCursor)
            w = self.engine.world
            if node and w.is_discovered(node):
                s = w.servers[node]
                self.setToolTip(f"{s.name}\n{s.ip}\nSecurity: {s.security}\nRegion: {s.region}")
            elif node:
                self.setToolTip("UNEXPLORED — find it through scans, missions or intel")
            else:
                self.setToolTip("")

    def mousePressEvent(self, ev) -> None:
        node = self._node_at(ev.position())
        if node:
            self.selected = node
            self.node_selected.emit(node)
            self.update()

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.engine.world
        known = set(w.discovered())
        nodes = self._visible_nodes()
        p.fillRect(self.rect(), QColor(COLORS["bg_alt"]))
        p.setPen(QPen(QColor(COLORS["panel"]), 1))
        for gx in range(0, self.width(), 40):
            p.drawLine(gx, 0, gx, self.height())
        for gy in range(0, self.height(), 40):
            p.drawLine(0, gy, self.width(), gy)
        drawn: set[frozenset] = set()
        for sid in nodes:
            for other in w.servers[sid].links:
                pair = frozenset((sid, other))
                if other not in nodes or pair in drawn or not (sid in known or other in known):
                    continue
                drawn.add(pair)
                both = sid in known and other in known
                active = w.current in (sid, other)
                color = COLORS["cyan"] if active else (COLORS["border"] if both else COLORS["panel_hi"])
                p.setPen(QPen(QColor(color), 2 if active else 1, Qt.PenStyle.SolidLine if both else Qt.PenStyle.DotLine))
                p.drawLine(self._pos(sid), self._pos(other))
        for sid in nodes:
            srv = w.servers[sid]
            pos = self._pos(sid)
            if sid not in known:                                      # silhouette of an undiscovered host
                p.setPen(QPen(QColor(COLORS["dim"]), 1, Qt.PenStyle.DashLine))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(pos, 8, 8)
                p.setFont(mono_font(9, True))
                p.drawText(QRectF(pos.x() - 8, pos.y() - 8, 16, 16), Qt.AlignmentFlag.AlignCenter, "?")
                if sid == self.selected:
                    p.setPen(QPen(QColor(COLORS["amber"]), 1, Qt.PenStyle.DashLine))
                    p.drawEllipse(pos, 15, 15)
                continue
            online = w.is_online(sid)
            if w.current == sid:
                color = QColor(COLORS["cyan"])
            elif not online:
                color = QColor(COLORS["red"])
            elif w.is_compromised(sid):
                color = QColor(COLORS["green"])
            else:
                color = QColor(COLORS["text"])
            radius = 9 + (3 * math.sin(self.phase) if w.current == sid else 0)
            glow = QColor(color)
            glow.setAlpha(50)
            p.setBrush(glow)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(pos, radius + 7, radius + 7)
            p.setBrush(QColor(COLORS["bg"]))
            p.setPen(QPen(color, 2))
            p.drawEllipse(pos, radius, radius)
            region = QColor(COLORS[REGION_COLORS.get(srv.region, "text")])
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(region)
            p.drawEllipse(pos, 3, 3)
            if sid == self.selected:
                p.setPen(QPen(QColor(COLORS["amber"]), 1, Qt.PenStyle.DashLine))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(pos, radius + 12, radius + 12)
            if srv.security in ("HIGH", "CRITICAL"):
                p.setPen(QColor(COLORS["amber"] if srv.security == "HIGH" else COLORS["red"]))
                p.setFont(mono_font(8, True))
                p.drawText(QRectF(pos.x() + radius, pos.y() - radius - 6, 12, 12), Qt.AlignmentFlag.AlignCenter, "!")
            p.setPen(color)
            p.setFont(mono_font(9))
            p.drawText(QRectF(pos.x() - 60, pos.y() + radius + 4, 120, 14), Qt.AlignmentFlag.AlignCenter, srv.name)
        p.setFont(mono_font(8))
        x = 10
        for text, col in [("connected", COLORS["cyan"]), ("compromised", COLORS["green"]), ("known", COLORS["text"]), ("offline", COLORS["red"]), ("? unexplored", COLORS["dim"])]:
            p.setPen(QColor(col))
            p.drawText(x, self.height() - 8, ("● " if not text.startswith("?") else "") + text)
            x += 105


class MapPanel(QWidget):
    """Full NETWORK page: map + region list + node details."""

    def __init__(self, engine, run_command, parent=None):
        super().__init__(parent)
        self.engine, self.run_command = engine, run_command
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        head = QHBoxLayout()
        title = QLabel(f"// {tr('network')}")
        title.setObjectName("h1")
        self.count = QLabel("")
        self.count.setObjectName("dim")
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self.count)
        lay.addLayout(head)
        body = QHBoxLayout()
        self.map = NetworkMapWidget(engine)
        body.addWidget(self.map, 3)
        side = QVBoxLayout()
        self.regions = QListWidget()
        self.regions.setMaximumHeight(210)
        side.addWidget(self.regions)
        card = QFrame()
        card.setObjectName("panel")
        cl = QVBoxLayout(card)
        self.info = QLabel("Select a node to inspect it.")
        self.info.setWordWrap(True)
        cl.addWidget(self.info, 1)
        row = QHBoxLayout()
        self.connect_btn = NeonButton("CONNECT", "Open a connection to the selected host (runs 'connect' in the terminal)")
        self.scan_btn = NeonButton("SCAN", "Scan the selected host", "cyan")
        self.connect_btn.setEnabled(False)
        self.scan_btn.setEnabled(False)
        row.addWidget(self.connect_btn)
        row.addWidget(self.scan_btn)
        cl.addLayout(row)
        side.addWidget(card, 1)
        body.addLayout(side, 2)
        lay.addLayout(body, 1)
        self.map.node_selected.connect(self._select)
        self.connect_btn.clicked.connect(lambda: self.run_command(f"connect {self.map.selected}", True))
        self.scan_btn.clicked.connect(lambda: self.run_command(f"scan {self.map.selected}", True))
        engine.server_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        e = self.engine
        w = e.world
        total = sum(1 for d in e.data.servers.values() if not d.get("hidden"))
        hidden_found = sum(1 for sid in w.discovered() if e.data.servers[sid].get("hidden"))
        self.count.setText(f"{len(w.discovered())} hosts discovered" + (f"  (+{hidden_found} hidden)" if hidden_found else "") + f"  ·  {total} regular hosts exist")
        regions: dict[str, list[str]] = {}
        for sid, s in w.servers.items():
            if not e.data.servers[sid].get("hidden") or w.is_discovered(sid):
                regions.setdefault(s.region, []).append(sid)
        self.regions.clear()
        for region, ids in sorted(regions.items()):
            known = sum(1 for i in ids if w.is_discovered(i))
            self.regions.addItem(f"{region:<10} {known}/{len(ids)}")
        self.map.update()
        if self.map.selected:
            self._select(self.map.selected)

    def _select(self, sid: str) -> None:
        w = self.engine.world
        s = w.servers[sid]
        if not w.is_discovered(sid):
            self.info.setText(f"UNEXPLORED SECTOR\nRegion: {s.region}\n\nFind this host through scans of its neighbours, missions or market intel.")
            self.connect_btn.setEnabled(False)
            self.scan_btn.setEnabled(False)
            return
        fw = "none" if not s.firewall.get("enabled") else ("breached" if w.is_breached(sid) else "ACTIVE")
        state = "ONLINE" if w.is_online(sid) else "OFFLINE"
        self.info.setText(f"{s.name}  ·  {s.ip}  ·  {state}\nRegion {s.region}  ·  security {s.security}  ·  firewall {fw}\nServices: {', '.join(s.services)}\n\n{s.description}")
        self.connect_btn.setEnabled(True)
        self.scan_btn.setEnabled(True)
