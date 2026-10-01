"""PROFILE: operator card, statistics tiles and the charts dashboard."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from nexus import reputation
from nexus.config import COLORS
from nexus.i18n import tr
from nexus.save_system import SaveSystem

from .charts import BarChart, DonutChart, LineChart, StatTile
from .widgets import NeonBar, NeonButton, StatCard, hline


class ProfilePage(QWidget):
    save_requested = Signal()
    load_requested = Signal()
    new_operator_requested = Signal()
    command_requested = Signal(str)

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        title = QLabel(f"// {tr('profile')}")
        title.setObjectName("h1")
        outer.addWidget(title)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll, 1)
        holder = QWidget()
        scroll.setWidget(holder)
        lay = QVBoxLayout(holder)
        lay.setSpacing(12)

        top = QHBoxLayout()
        card = QFrame()
        card.setObjectName("panel")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 14, 18, 14)
        self.name = QLabel("")
        self.name.setStyleSheet(f"color:{COLORS['green']}; font-size: 26px; font-weight:bold; letter-spacing: 3px;")
        self.rank = QLabel("")
        self.rank.setObjectName("h2")
        self.xp_bar = NeonBar(COLORS["green"], 30, 16)
        self.credits = QLabel("")
        self.credits.setStyleSheet(f"color:{COLORS['amber']}; font-size: 16px; font-weight:bold;")
        self.rep = QLabel("")
        self.rep_bar = NeonBar(COLORS["cyan"], 30, 10)
        self.mission_bar = NeonBar(COLORS["purple"], 30, 10)
        self.mission_lbl = QLabel("")
        self.mission_lbl.setObjectName("dim")
        for w in (self.name, self.rank, self.xp_bar, self.credits, self.rep, self.rep_bar, self.mission_lbl, self.mission_bar):
            cl.addWidget(w)
        row = QHBoxLayout()
        for key, sig, variant in (("save_game", self.save_requested, ""), ("load_game", self.load_requested, "cyan"),
                                  ("new_operator", self.new_operator_requested, "cyan")):
            btn = NeonButton(tr(key), variant=variant)
            btn.clicked.connect(sig)
            row.addWidget(btn)
        cl.addLayout(row)
        self.ng_btn = NeonButton("NEW GAME+", "Restart the story keeping level, items and achievements (campaign must be finished)", "cyan")
        self.ng_btn.clicked.connect(lambda: self.command_requested.emit("newgameplus"))
        cl.addWidget(self.ng_btn)
        self.diff_lbl = QLabel("")
        self.diff_lbl.setObjectName("dim")
        cl.addWidget(self.diff_lbl)
        top.addWidget(card, 2)

        tiles = QGridLayout()
        tiles.setSpacing(8)
        self.tiles: dict[str, StatCard] = {}
        for i, key in enumerate(["MISSIONS COMPLETED", "MISSIONS FAILED", "SUCCESS RATE", "TOTAL XP", "TOTAL CREDITS", "PUZZLES SOLVED",
                                 "ACHIEVEMENTS", "PLAYTIME"]):
            tile = StatCard(key)
            self.tiles[key] = tile
            tiles.addWidget(tile, i // 2, i % 2)
        top.addLayout(tiles, 2)
        lay.addLayout(top)

        head = QLabel(f"// {tr('statistics')}")
        head.setObjectName("h2")
        lay.addWidget(head)
        grid = QGridLayout()
        grid.setSpacing(10)
        self.c_xp = LineChart("XP OVER TIME", COLORS["green"])
        self.c_credits = LineChart("CREDITS EARNED", COLORS["amber"], fmt=lambda v: f"${int(v):,}")
        self.c_missions = BarChart("MISSIONS COMPLETED BY TYPE", COLORS["cyan"])
        self.c_success = DonutChart("SUCCESS RATE", COLORS["green"])
        self.c_play = LineChart("PLAYTIME (minutes)", COLORS["purple"], fmt=lambda v: f"{int(v)} min")
        self.c_ach = DonutChart("ACHIEVEMENTS", COLORS["amber"])
        for i, chart in enumerate((self.c_xp, self.c_credits, self.c_missions, self.c_success, self.c_play, self.c_ach)):
            grid.addWidget(chart, i // 3, i % 3)
        lay.addLayout(grid)
        lay.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        e, p = self.engine, self.engine.player
        s = e.db.all_stats()
        self.name.setText(p.username.upper())
        self.rank.setText(f"{p.rank}   ·   {tr('level')} {p.level} / 100")
        self.xp_bar.set_value(p.xp, p.xp_needed, f"{p.xp} / {p.xp_needed} XP")
        self.credits.setText(f"{tr('credits')}  ${p.credits:,}")
        self.rep.setText(f"{tr('reputation')}  {p.reputation}  —  {reputation.status(p.reputation)}")
        self.rep_bar.set_value(p.reputation, 100)
        done = sum(1 for m in e.data.missions if e.missions.is_complete(m["id"]))
        self.mission_lbl.setText(f"{tr('mission_progress')}  {done} / {len(e.data.missions)}")
        self.mission_bar.set_value(done, len(e.data.missions))
        self.ng_btn.setVisible(bool(e.db.get_flag("campaign_complete")))
        self.diff_lbl.setText(f"DIFFICULTY {e.difficulty.upper()}" + (f"  ·  NEW GAME+ {e.ng_plus}" if e.ng_plus else "") + f"  ·  rewards x{e.reward_mult:.2f}")
        failed = p.failed_missions
        rate = 100 * p.completed_missions / (p.completed_missions + failed) if p.completed_missions + failed else 0
        solved = int(sum(s.get(k, 0) for k in ("firewalls_breached", "decryptions", "routes_solved", "access_solved", "traces_done")))
        values = {
            "MISSIONS COMPLETED": str(p.completed_missions), "MISSIONS FAILED": str(failed),
            "SUCCESS RATE": f"{rate:.0f}%" if p.completed_missions + failed else "—",
            "TOTAL XP": f"{int(s.get('xp_earned', 0)):,}", "TOTAL CREDITS": f"${int(s.get('credits_earned', 0)):,}",
            "PUZZLES SOLVED": str(solved), "ACHIEVEMENTS": f"{len(e.db.get_achievements())} / {len(e.data.achievements)}",
            "PLAYTIME": SaveSystem.format_time(p.playtime),
        }
        for key, tile in self.tiles.items():
            tile.set(values[key])
        hist = e.db.get_history()

        def series(field: str, current: float) -> list[float]:
            vals = [0.0] + [float(h[field] or 0) for h in hist] + [float(current)]
            return vals

        self.c_xp.set_values(series("xp_total", s.get("xp_earned", 0)))
        self.c_credits.set_values(series("credits_earned", s.get("credits_earned", 0)))
        self.c_play.set_values([v / 60 for v in series("playtime", p.playtime)])
        types = ["INFILTRATION", "DECRYPTION", "INVESTIGATION", "TRACE", "FIREWALL", "RECOVERY", "DEFENSE", "ESCAPE", "INTELLIGENCE", "STORY"]
        self.c_missions.set_items([(t[:5], s.get(f"missions_{t.lower()}", 0)) for t in types])
        self.c_success.set_ratio(p.completed_missions, p.completed_missions + failed, f"{p.completed_missions}/{p.completed_missions + failed}")
        self.c_ach.set_ratio(len(e.db.get_achievements()), len(e.data.achievements), f"{len(e.db.get_achievements())}/{len(e.data.achievements)}")
