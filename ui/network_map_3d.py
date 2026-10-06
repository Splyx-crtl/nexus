"""D2: the 3D network map - a QtQuick3D scene (ui/qml/network_map_3d.qml) driven by this module's data bridge, with
a QWidget wrapper that falls back to the existing flat map (ui/map_view.py's NetworkMapWidget) if Qt Quick 3D can't
initialize (no GPU/driver support, software-only renderer, a QML load error). The bridge mirrors
NetworkMapWidget's own visibility/color rules exactly (same "known" set, same state colors) so the two views are
never visually inconsistent, just a 2D/3D presentation of the identical data - 3D additionally only shows nodes
that are actually discovered (no undiscovered-silhouette affordance in 3D; that stays a 2D-only detail) and only
draws links between two discovered nodes (no dashed "partially known" links; Qt Quick 3D has no stock dashed-line
material, and approximating one wasn't worth it for a link style players will rarely see in 3D).
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QUrl, Signal

from nexus.config import COLORS, RESOURCE_DIR

from .map3d_geometry import link_geometry, node_position

# RESOURCE_DIR (not a plain __file__-relative path), same reasoning as nexus/config.py's ASSETS_DIR/DATA_DIR:
# PyInstaller bundles this .qml as a data file (build_exe.bat/NEXUS.spec's "ui/qml" add-data entry), not as part
# of the compiled Python archive, so it must be looked up the same way every other bundled asset is.
QML_PATH = RESOURCE_DIR / "ui" / "qml" / "network_map_3d.qml"
HEAT_TRACE_THRESHOLD = 70.0       # same number ui/main_window.py's _update_music() uses for the tension mood


def _state_color(engine, sid: str) -> tuple[str, float]:
    """(hex color, glow strength) for one discovered node - mirrors NetworkMapWidget.paintEvent's own state rules."""
    w = engine.world
    if w.current == sid:
        return COLORS["cyan"], 1.0
    if not w.is_online(sid):
        return COLORS["red"], 0.2
    if w.is_compromised(sid):
        return COLORS["green"], 0.5
    return COLORS["text"], 0.25


class Network3DBridge(QObject):
    nodesChanged = Signal()
    linksChanged = Signal()
    traceChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nodes: list[dict] = []
        self._links: list[dict] = []
        self._trace_active = False
        self._current_pos = (0.0, 0.0, 0.0)

    @Property("QVariantList", notify=nodesChanged)
    def nodes(self):
        return self._nodes

    @Property("QVariantList", notify=linksChanged)
    def links(self):
        return self._links

    @Property(bool, notify=traceChanged)
    def traceActive(self):
        return self._trace_active

    @Property(float, notify=traceChanged)
    def currentX(self):
        return self._current_pos[0]

    @Property(float, notify=traceChanged)
    def currentY(self):
        return self._current_pos[1]

    @Property(float, notify=traceChanged)
    def currentZ(self):
        return self._current_pos[2]

    def refresh(self, engine) -> None:
        w = engine.world
        known = set(w.discovered())
        positions: dict[str, tuple[float, float, float]] = {}
        nodes = []
        for sid in known:
            if sid not in engine.data.servers:
                continue
            x2d, y2d = w.servers[sid].pos
            pos = node_position(x2d, y2d, sid)
            positions[sid] = pos
            color, glow = _state_color(engine, sid)
            nodes.append({"id": sid, "x": pos[0], "y": pos[1], "z": pos[2], "color": color, "glow": glow})

        links = []
        drawn: set[frozenset] = set()
        for sid in known:
            if sid not in positions:
                continue
            for other in w.servers[sid].links:
                pair = frozenset((sid, other))
                if other not in positions or pair in drawn:
                    continue
                drawn.add(pair)
                a, b = positions[sid], positions[other]
                geo = link_geometry(a, b)
                active = w.current in (sid, other)
                links.append({
                    "mx": geo["mid"][0], "my": geo["mid"][1], "mz": geo["mid"][2], "length": geo["length"],
                    "qw": geo["quat"][0], "qx": geo["quat"][1], "qy": geo["quat"][2], "qz": geo["quat"][3],
                    "ax": a[0], "ay": a[1], "az": a[2], "bx": b[0], "by": b[1], "bz": b[2],
                    "active": active, "color": COLORS["cyan"] if active else COLORS["dim"],
                })

        self._nodes = nodes
        self._links = links
        self.nodesChanged.emit()
        self.linksChanged.emit()

        self._trace_active = bool(getattr(engine, "heat", 0) >= HEAT_TRACE_THRESHOLD and w.current in positions)
        self._current_pos = positions.get(w.current, (0.0, 0.0, 0.0))
        self.traceChanged.emit()


def try_build_3d_view(engine, parent=None):
    """Attempt to build the Qt Quick 3D scene; returns (widget, bridge) on success or (None, None) on any failure
    (missing Qt Quick 3D support, a software-only renderer that can't load it, a QML error). Never raises - the
    caller falls back to the flat 2D map, which always works."""
    try:
        from PySide6.QtQuickWidgets import QQuickWidget
        quick = QQuickWidget(parent)
        quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        bridge = Network3DBridge(quick)
        quick.rootContext().setContextProperty("bridge", bridge)
        quick.setSource(QUrl.fromLocalFile(str(QML_PATH)))
        if quick.status() == QQuickWidget.Status.Error:
            for e in quick.errors():
                print("3D network map QML error:", e.toString())
            quick.deleteLater()
            return None, None
        bridge.refresh(engine)
        return quick, bridge
    except Exception as exc:                     # pragma: no cover - exact failure depends on the local GPU/driver
        print("3D network map unavailable, falling back to the flat map:", exc)
        return None, None
