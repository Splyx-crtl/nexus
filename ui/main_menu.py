"""Main menu: animated background, title, navigation buttons and the operator status card."""
from __future__ import annotations

import random

from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from nexus import reputation
from nexus.config import APP_SUBTITLE, COLORS, VERSION
from nexus.version import AUTHOR, DISCORD_URL
from nexus.i18n import tr

from .widgets import GlitchTitle, NeonBar, NeonButton, hline, mono_font

MENU_ITEMS = ["continue", "operations", "terminal", "network", "market", "loadout", "profile", "achievements", "archives", "campaign30", "settings", "exit"]


class BackgroundCanvas(QWidget):
    """Falling code columns + drifting network nodes (theme coloured)."""

    CHARS = "0123456789ABCDEF<>/|\\:;=+*#"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rng = random.Random()
        self.cols: list[dict] = []
        self.animated = True
        self.nodes: list[list[float]] = [[self.rng.random(), self.rng.random(), self.rng.uniform(-.03, .03), self.rng.uniform(-.03, .03)] for _ in range(26)]
        self._glyphs: dict[tuple, QPixmap] = {}
        self.timer = QTimer(self, interval=50)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _ensure(self) -> None:
        count = max(10, self.width() // 22)
        while len(self.cols) < count:
            self.cols.append({"y": self.rng.uniform(-30, 0), "speed": self.rng.uniform(0.25, 0.9),
                              "trail": self.rng.randint(8, 20), "chars": [self.rng.choice(self.CHARS) for _ in range(24)]})
        del self.cols[count:]

    def _tick(self) -> None:
        if not self.isVisible() or not self.animated:
            return
        self._ensure()
        rows = self.height() // 18 + 24
        for col in self.cols:
            col["y"] += col["speed"]
            if self.rng.random() < 0.08:
                col["chars"][self.rng.randrange(len(col["chars"]))] = self.rng.choice(self.CHARS)
            if col["y"] - col["trail"] > rows:
                col.update({"y": self.rng.uniform(-20, 0), "speed": self.rng.uniform(0.25, 0.9), "trail": self.rng.randint(8, 20)})
        for n in self.nodes:
            n[0] = (n[0] + n[2] * 0.05) % 1.0
            n[1] = (n[1] + n[3] * 0.05) % 1.0
        self.update()

    LEVELS = 8                       # alpha steps of the fading trail; the bright head is level LEVELS

    def _glyph(self, ch: str, level: int) -> QPixmap:
        """Pre-rendered character: drawing ~400 glyphs per frame with drawText is what made the menu eat a CPU core."""
        dpr = self.devicePixelRatioF()
        key = (ch, level, COLORS["green"], dpr)
        pm = self._glyphs.get(key)
        if pm is None:
            font = mono_font(12)
            fm = QFontMetrics(font)
            pm = QPixmap(int(16 * dpr), int(20 * dpr))
            pm.setDevicePixelRatio(dpr)
            pm.fill(Qt.GlobalColor.transparent)
            g = QColor(COLORS["green"])
            painter = QPainter(pm)
            painter.setFont(font)
            if level >= self.LEVELS:
                painter.setPen(QColor(220, 255, 240, 120))
            else:
                painter.setPen(QColor(g.red(), g.green(), g.blue(), int(60 * (level + 1) / self.LEVELS)))
            painter.drawText(0, fm.ascent() + 1, ch)
            painter.end()
            if len(self._glyphs) > 800:
                self._glyphs.clear()
            self._glyphs[key] = pm
        return pm

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(COLORS["bg"]))
        w, h = self.width(), self.height()
        self._ensure()
        c = QColor(COLORS["cyan"])
        asc = QFontMetrics(mono_font(12)).ascent() + 1
        for i, col in enumerate(self.cols):
            x = i * 22 + 4
            head = int(col["y"])
            chars, trail = col["chars"], col["trail"]
            for t in range(trail):
                row = head - t
                if row < 0 or row * 18 > h:
                    continue
                level = self.LEVELS if t == 0 else max(0, min(self.LEVELS - 1, int(self.LEVELS * (1 - t / trail))))
                p.drawPixmap(x, row * 18 - asc, self._glyph(chars[row % len(chars)], level))
        pts = [QPointF(n[0] * w, n[1] * h) for n in self.nodes]
        for i, a in enumerate(pts):
            for b in pts[i + 1:]:
                d = (a - b).manhattanLength()
                if d < 230:
                    p.setPen(QPen(QColor(c.red(), c.green(), c.blue(), int(55 * (1 - d / 230))), 1))
                    p.drawLine(a, b)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(c.red(), c.green(), c.blue(), 110))
            p.drawEllipse(a, 2.5, 2.5)


class OperatorCard(QFrame):
    """Username, level, rank, XP, credits, reputation and mission progress."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.setMinimumWidth(300)
        self.setMaximumWidth(360)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(5)
        tag = QLabel("// OPERATOR")
        tag.setObjectName("h2")
        self.name = QLabel("—")
        self.name.setStyleSheet(f"color:{COLORS['green']}; font-size: 24px; font-weight:bold; letter-spacing: 3px;")
        self.rank = QLabel("")
        self.rank.setStyleSheet(f"color:{COLORS['cyan']}; font-weight:bold; letter-spacing: 2px;")
        self.xp_bar = NeonBar(COLORS["green"], 24, 14)
        self.credits = QLabel("")
        self.credits.setStyleSheet(f"color:{COLORS['amber']}; font-size: 15px; font-weight:bold;")
        self.rep = QLabel("")
        self.rep_bar = NeonBar(COLORS["cyan"], 24, 8)
        self.prog = QLabel("")
        self.prog.setObjectName("dim")
        self.prog_bar = NeonBar(COLORS["purple"], 24, 8)
        for w in (tag, self.name, self.rank, self.xp_bar, self.credits, hline(), self.rep, self.rep_bar, self.prog, self.prog_bar):
            lay.addWidget(w)

    def update_from(self, engine) -> None:
        p = engine.player
        self.name.setText(p.username.upper())
        self.rank.setText(f"{tr('level')} {p.level}  ·  {p.rank}")
        self.xp_bar.set_value(p.xp, p.xp_needed, f"{p.xp} / {p.xp_needed} {tr('xp')}")
        self.credits.setText(f"{tr('credits')}  ${p.credits:,}")
        self.rep.setText(f"{tr('reputation')}  {p.reputation}  —  {reputation.status(p.reputation)}")
        self.rep_bar.set_value(p.reputation, 100)
        done = sum(1 for m in engine.data.missions if engine.missions.is_complete(m["id"]))
        total = len(engine.data.missions)
        self.prog.setText(f"{tr('mission_progress')}  {done} / {total}")
        self.prog_bar.set_value(done, total)


class MainMenu(QWidget):
    action = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bg = BackgroundCanvas(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.title = GlitchTitle("NEXUS", APP_SUBTITLE)
        self.title.setMinimumHeight(170)
        self.title.setMaximumWidth(1100)
        outer.addSpacing(8)
        outer.addWidget(self.title, 0, Qt.AlignmentFlag.AlignHCenter)

        mid = QHBoxLayout()
        mid.setContentsMargins(40, 0, 40, 0)
        mid.addStretch(1)
        col = QVBoxLayout()
        col.setSpacing(3)
        self.buttons: dict[str, NeonButton] = {}
        tips = {"continue": "Resume your operation in the terminal", "operations": "Missions, daily operations and weekly challenges",
                "terminal": "Open the command terminal", "network": "The map of the simulated network",
                "market": "NEXUS MARKET: tools, upgrades, cosmetics, access, intel", "loadout": "Equip gear into five slots",
                "profile": "Operator profile, statistics and charts", "achievements": "Your achievements",
                "archives": "Lore, endings and logs",
                "campaign30": "The new 200-level campaign: a real bash/PowerShell/cmd shell, no minigames (in progress)",
                "settings": "Audio, text speed, display, theme, language", "exit": "Quit to desktop"}
        for key in MENU_ITEMS:
            btn = NeonButton(f"[ {tr(key)} ]", tips[key], "danger" if key == "exit" else "")
            btn.setMinimumWidth(320)
            btn.setFixedHeight(34)
            btn.clicked.connect(lambda _=False, k=key: self.action.emit(k))
            col.addWidget(btn)
            self.buttons[key] = btn
        mid.addLayout(col)
        mid.addSpacing(30)
        self.card = OperatorCard()
        mid.addWidget(self.card, 0, Qt.AlignmentFlag.AlignTop)
        mid.addStretch(1)
        outer.addLayout(mid, 1)

        foot = QHBoxLayout()
        foot.setContentsMargins(16, 0, 16, 10)
        self.version = QLabel(f"NEXUS v{VERSION}  ·  created by {AUTHOR}")
        self.version.setStyleSheet(f"color:{COLORS['green_dim']}; font-weight:bold;")
        self.sim = QLabel(tr("sim_only"))
        self.sim.setObjectName("dim")
        self.sim.setAlignment(Qt.AlignmentFlag.AlignCenter)
        foot.addWidget(self.version)
        foot.addWidget(self.sim, 1)
        if DISCORD_URL:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            discord = NeonButton("DISCORD", DISCORD_URL, "cyan")
            discord.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(DISCORD_URL)))
            foot.addWidget(discord)
        else:
            foot.addWidget(QLabel(""))
        outer.addLayout(foot)
        for lab in (self.version, self.sim):
            lab.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def resizeEvent(self, ev) -> None:
        self.bg.setGeometry(self.rect())
        self.bg.lower()
        super().resizeEvent(ev)

    def retranslate(self) -> None:
        for key, btn in self.buttons.items():
            btn.setText(f"[ {tr(key)} ]")
        self.sim.setText(tr("sim_only"))

    def set_engine(self, engine) -> None:
        enabled = engine is not None
        for key, btn in self.buttons.items():
            if key not in ("exit", "campaign30"):      # campaign30 has its own, independent v3 profile
                btn.setEnabled(enabled)
        if enabled:
            self.card.update_from(engine)
            active = engine.missions.active()
            self.buttons["continue"].setText(f"[ {tr('continue')} ]")
