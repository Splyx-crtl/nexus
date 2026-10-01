"""HUD side panel: operator card, connection, trace alert, active mission."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from nexus.config import COLORS
from nexus.simulation import ROLE_NAMES

from .widgets import NeonBar, NeonButton, Panel, mono_font


def _label(text: str = "", obj: str = "") -> QLabel:
    lab = QLabel(text)
    if obj:
        lab.setObjectName(obj)
    return lab


class DashboardPanel(QWidget):
    save_requested = Signal()
    load_requested = Signal()

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(8)

        # --- operator
        op = Panel("OPERATOR")
        self.name = _label("", "h1")
        self.name.setFont(mono_font(18, True))
        self.rank = _label("", "h2")
        self.xp_bar = NeonBar(COLORS["green"], 25, 16)
        self.xp_bar.setToolTip("Experience towards the next level")
        self.credits = _label()
        self.rep_bar = NeonBar(COLORS["cyan"], 25, 10)
        self.rep_bar.setToolTip("Reputation (0-100): earned by completing missions cleanly")
        for w in (self.name, self.rank, self.xp_bar, self.credits, _label("REPUTATION", "dim"), self.rep_bar):
            op.body.addWidget(w)
        lay.addWidget(op)

        # --- connection
        con = Panel("CONNECTION")
        self.server = _label()
        self.server_info = _label("", "dim")
        self.server_info.setWordWrap(True)
        self.heat_label = _label("TRACE ALERT", "dim")
        self.heat_bar = NeonBar(COLORS["green"], 25, 16)
        self.heat_bar.setToolTip("At 100% you are burned and the mission fails. Disconnect to cool down faster.")
        for w in (self.server, self.server_info, self.heat_label, self.heat_bar):
            con.body.addWidget(w)
        lay.addWidget(con)

        # --- mission
        ms = Panel("ACTIVE MISSION")
        self.m_title = _label("", "h2")
        self.m_title.setWordWrap(True)
        self.m_timer = _label("", "warn")
        self.m_obj = _label()
        self.m_obj.setWordWrap(True)
        for w in (self.m_title, self.m_timer, self.m_obj):
            ms.body.addWidget(w)
        lay.addWidget(ms)

        # --- stats / save
        st = Panel("RECORD")
        self.record = _label("", "dim")
        st.body.addWidget(self.record)
        row = QHBoxLayout()
        self.save_btn = NeonButton("SAVE GAME", "Save into a manual slot (Ctrl+S / F5)")
        self.load_btn = NeonButton("LOAD GAME", "Load a saved operation", "cyan")
        row.addWidget(self.save_btn)
        row.addWidget(self.load_btn)
        st.body.addLayout(row)
        self.save_btn.clicked.connect(self.save_requested)
        self.load_btn.clicked.connect(self.load_requested)
        lay.addWidget(st)
        lay.addStretch(1)

        engine.state_changed.connect(self.refresh_state)
        engine.heat_changed.connect(self._heat)
        engine.mission_changed.connect(self.refresh_mission)
        engine.server_changed.connect(self.refresh_state)
        self.refresh_state()
        self.refresh_mission()

    # ---------------------------------------------------------------- refresh
    def _heat(self, heat: float) -> None:
        color = COLORS["green"] if heat < 40 else COLORS["amber"] if heat < 70 else COLORS["red"]
        self.heat_bar.set_color(color)
        self.heat_bar.set_value(heat, 100, f"{heat:.0f}%")

    def refresh_state(self) -> None:
        e, p = self.engine, self.engine.player
        self.name.setText(p.username.upper())
        self.rank.setText(f"{p.rank}  ·  LV {p.level}")
        self.xp_bar.set_value(p.xp, p.xp_needed, f"{p.xp} / {p.xp_needed} XP")
        self.credits.setText(f"CREDITS  ${p.credits:,}")
        self.rep_bar.set_value(p.reputation, 100)
        srv = e.world.server
        if srv:
            role = ROLE_NAMES[e.world.role()]
            fw = srv.firewall
            fw_txt = "none" if not fw.get("enabled") else ("BREACHED" if e.world.is_breached(srv.id) else "ACTIVE")
            self.server.setText(f"● {srv.name}")
            self.server.setStyleSheet(f"color:{COLORS['cyan']}; font-weight:bold;")
            self.server_info.setText(f"{srv.ip}  ·  {srv.security}\nsession: {role}  ·  firewall: {fw_txt}")
        else:
            self.server.setText("○ LOCAL NODE (offline)")
            self.server.setStyleSheet(f"color:{COLORS['dim']};")
            self.server_info.setText("Use 'connect <host>' to open a connection.")
        self._heat(e.heat)
        tl = e.missions.time_left()
        self.m_timer.setText("" if tl is None else f"⏱ TIME LEFT  {int(tl) // 60:02d}:{int(tl) % 60:02d}")
        stats = e.db.all_stats()
        self.record.setText(
            f"missions   {p.completed_missions} done · {p.failed_missions} failed\n"
            f"perfect    {int(stats.get('perfect_missions', 0))}\n"
            f"achievements  {len(e.db.get_achievements())}/{len(e.data.achievements)}")

    def refresh_mission(self) -> None:
        e = self.engine
        m = e.missions.active()
        if not m:
            avail = e.missions.available()
            self.m_title.setText("NO ACTIVE MISSION")
            self.m_obj.setText(f"Next: mission start {avail[0]['number']}  — \"{avail[0]['title']}\"" if avail else "Campaign complete.")
            return
        self.m_title.setText(f"{m['number']:03d} // {m['title']}")
        lines = []
        for o in e.missions.objectives_view(m["id"]):
            mark = "✔" if o["done"] else ("▶" if o["current"] else "·")
            color = COLORS["green"] if o["done"] else (COLORS["amber"] if o["current"] else COLORS["dim"])
            lines.append(f'<span style="color:{color}">{mark} {o["text"]}{" (bonus)" if o["optional"] else ""}</span>')
        if e.missions.progress().get("awaiting_choice"):
            lines.append(f'<span style="color:{COLORS["red"]}">! DECISION PENDING — type: choose &lt;n&gt;</span>')
        self.m_obj.setText("<br>".join(lines))
