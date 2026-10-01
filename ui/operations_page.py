"""OPERATIONS: mission board, daily operations (+ login streak) and weekly challenges."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QScrollArea, QTabWidget, QVBoxLayout, QWidget)

from nexus.config import COLORS
from nexus.i18n import tr

from .mission_screen import MissionPanel
from .widgets import NeonBar, NeonButton


class ChallengeCard(QFrame):
    def __init__(self, op: dict, weekly: bool, engine):
        super().__init__()
        self.setObjectName("card")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        col = QVBoxLayout()
        title = QLabel(op["text"])
        title.setStyleSheet("font-weight:bold;")
        bar = NeonBar(COLORS["green"] if op["done"] else COLORS["cyan"], 24, 10)
        bar.set_value(op["progress"], op["target"], f"{op['progress']:,} / {op['target']:,}")
        col.addWidget(title)
        col.addWidget(bar)
        lay.addLayout(col, 1)
        r = op["reward"]
        parts = [f"${r.get('credits', 0):,}", f"+{r.get('xp', 0)} XP"]
        if r.get("item"):
            parts.append(engine.data.items[r["item"]]["name"])
        if r.get("achievement"):
            parts.append("achievement")
        reward = QLabel("  ·  ".join(parts))
        reward.setStyleSheet(f"color:{COLORS['amber']};")
        lay.addWidget(reward)
        state = QLabel("CLAIMED" if op["claimed"] else ("READY" if op["done"] else "IN PROGRESS"))
        state.setMinimumWidth(100)
        state.setStyleSheet(f"color:{COLORS['green'] if op['done'] else COLORS['dim']}; font-weight:bold;")
        lay.addWidget(state)


class StreakStrip(QFrame):
    def __init__(self, info: dict):
        super().__init__()
        self.setObjectName("card")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        head = QLabel(f"LOGIN STREAK  {info['streak']} day(s)")
        head.setObjectName("h2")
        lay.addWidget(head)
        lay.addStretch(1)
        current = info["next_day"]
        for r in info["calendar"]:
            day = r["day"]
            claimed = (day < current) or (day == current and info["claimed_today"])
            active = day == current
            text = f"D{day}\n" + ("RARE" if r.get("rare_item") else f"${r['credits']:,}")
            box = QLabel(text)
            box.setMinimumSize(64, 46)
            box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            color = COLORS["green"] if claimed else (COLORS["amber"] if active else COLORS["dim"])
            box.setStyleSheet(f"color:{color}; border:1px solid {color}; background:{COLORS['bg_alt']};")
            lay.addWidget(box)


class ChallengePage(QWidget):
    def __init__(self, engine, weekly: bool, parent=None):
        super().__init__(parent)
        self.engine, self.weekly = engine, weekly
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        self.header = QLabel("")
        self.header.setObjectName("h2")
        lay.addWidget(self.header)
        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        holder = QWidget()
        holder.setLayout(self.body)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(holder)
        lay.addWidget(scroll, 1)
        row = QHBoxLayout()
        self.info = QLabel("")
        self.info.setWordWrap(True)
        self.btn = NeonButton(tr("claim"), "Collect all finished rewards")
        self.btn.clicked.connect(self._claim)
        row.addWidget(self.info, 1)
        row.addWidget(self.btn)
        lay.addLayout(row)
        engine.state_changed.connect(self._soft)
        self.refresh()

    def _soft(self) -> None:
        pass   # progress is recomputed on refresh() (page show / claim) to keep the 1 s tick cheap

    def refresh(self) -> None:
        e = self.engine
        while self.body.count():
            w = self.body.takeAt(0).widget()
            if w:
                w.deleteLater()
        data = e.progress.weekly() if self.weekly else e.progress.daily()
        self.header.setText(f"// {'WEEKLY CHALLENGES' if self.weekly else 'DAILY OPERATIONS'}  —  {data['week'] if self.weekly else data['date']}")
        if not self.weekly:
            self.body.addWidget(StreakStrip(data["streak"]))
        for op in data["ops"]:
            self.body.addWidget(ChallengeCard(op, self.weekly, e))
        self.body.addStretch(1)
        claimable = any(o["done"] and not o["claimed"] for o in data["ops"]) or (not self.weekly and not data["streak"]["claimed_today"])
        self.btn.setEnabled(claimable)
        self.info.setText("Rewards are collected locally — nothing leaves your machine." if claimable else "Nothing to claim right now.")

    def _claim(self) -> None:
        lines = self.engine.progress.claim_weekly() if self.weekly else self.engine.progress.claim_daily()
        self.refresh()
        self.info.setText(lines[-1] if lines else "")


class ContractPage(QWidget):
    """Endless procedural contracts."""

    def __init__(self, engine, run_command, parent=None):
        super().__init__(parent)
        self.engine, self.run_command = engine, run_command
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        head = QLabel("// CONTRACTS — endless procedural jobs")
        head.setObjectName("h2")
        lay.addWidget(head)
        self.card = QLabel("")
        self.card.setWordWrap(True)
        self.card.setStyleSheet(f"background:{COLORS['panel']}; border:1px solid {COLORS['border']}; padding: 14px;")
        self.card.setMinimumHeight(170)
        self.card.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(self.card)
        row = QHBoxLayout()
        self.new_btn = NeonButton("NEW CONTRACT", "Generate a fresh job (replaces an unstarted contract)", "cyan")
        self.start_btn = NeonButton("START CONTRACT", "Start the current contract in the terminal")
        self.new_btn.clicked.connect(self._new)
        self.start_btn.clicked.connect(lambda: self.run_command("contract start", True))
        row.addWidget(self.new_btn)
        row.addWidget(self.start_btn)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)
        self.info = QLabel("")
        self.info.setObjectName("dim")
        lay.addWidget(self.info)
        self.refresh()

    def _new(self) -> None:
        ok, msg = self.engine.contracts.generate()
        self.refresh()
        self.info.setText(msg)

    def refresh(self) -> None:
        e = self.engine
        c = e.contracts
        if not c.available():
            self.card.setText("Contracts unlock after mission 003 (BLACKVAULT).")
            self.new_btn.setEnabled(False)
            self.start_btn.setEnabled(False)
            return
        spec = c.spec()
        status = c.status()
        self.new_btn.setEnabled(status != "active")
        self.start_btn.setEnabled(bool(spec) and status in ("available", "failed"))
        if not spec:
            self.card.setText("No contract yet.\n\nPress NEW CONTRACT: a random job (infiltration, recovery, decryption, trace or escape) on one of the side-grid servers, scaled to your level. Finish it, then take another — forever.")
            return
        m = e.missions.by_id[c.mission_id()]
        done = e.db.get_stat("contracts_done")
        lines = [f"<b style='color:{COLORS['green']}; font-size:15px'>{m['title']}</b>",
                 f"<span style='color:{COLORS['cyan']}'>{status.upper()}</span> &nbsp; {spec['type']} · tier {spec['tier']} · {e.data.servers[spec['server']]['name']}",
                 f"<br>{m['story_start'][0]}", f"<br><span style='color:{COLORS['amber']}'>REWARD {m['reward']['xp']} XP · ${m['reward']['credits']:,}</span>",
                 f"<span style='color:{COLORS['dim']}'>Contracts completed: {int(done)}</span>"]
        for o in e.missions.objectives_view(m["id"]):
            lines.append(f"{'✔' if o['done'] else '·'} {o['text']}")
        self.card.setText("<br>".join(lines))


class OperationsPage(QWidget):
    def __init__(self, engine, run_command, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        title = QLabel(f"// {tr('operations')}")
        title.setObjectName("h1")
        lay.addWidget(title)
        self.tabs = QTabWidget()
        self.missions = MissionPanel(engine, run_command)
        self.daily = ChallengePage(engine, False)
        self.weekly = ChallengePage(engine, True)
        self.tabs.addTab(self.missions, tr("missions"))
        self.tabs.addTab(self.daily, tr("daily"))
        self.tabs.addTab(self.weekly, tr("weekly"))
        self.contracts = ContractPage(engine, run_command)
        self.tabs.addTab(self.contracts, "CONTRACTS")
        lay.addWidget(self.tabs, 1)
        self.engine = engine
        engine.state_changed.connect(self._badge)

    def _badge(self) -> None:
        pass

    def refresh(self) -> None:
        self.missions.refresh()
        self.daily.refresh()
        self.weekly.refresh()
        self.contracts.refresh()
        n = self.engine.progress.claimable_count()
        self.tabs.setTabText(1, f"{tr('daily')} ({n})" if n else tr("daily"))
