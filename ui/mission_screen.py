"""Mission board: operations grouped by chapter, filters, details, bonus goals and START."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QTextBrowser, QVBoxLayout, QWidget

from nexus.config import COLORS
from nexus.i18n import tr

from .widgets import Chip, NeonButton

STATUS_STYLE = {
    "completed": ("✔", "green"), "active": ("▶", "amber"), "available": ("●", "cyan"),
    "failed": ("✖", "red"), "locked": ("🔒", "dim"),
}
DIFF_NAMES = {1: "EASY", 2: "NORMAL", 3: "HARD", 4: "EXPERT", 5: "NEXUS"}
DIFF_COLORS = {1: "green", 2: "cyan", 3: "amber", 4: "red", 5: "purple"}
FILTERS = ["ALL", "AVAILABLE", "COMPLETED", "STORY", "SIDE"]


class MissionPanel(QWidget):
    def __init__(self, engine, run_command, parent=None):
        super().__init__(parent)
        self.engine, self.run_command = engine, run_command
        self.filter = "ALL"
        self.rows: list[dict | None] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        chips = QHBoxLayout()
        self.chips: dict[str, Chip] = {}
        for f in FILTERS:
            chip = Chip(f)
            chip.clicked.connect(lambda _=False, k=f: self.set_filter(k))
            chips.addWidget(chip)
            self.chips[f] = chip
        chips.addStretch(1)
        self.progress = QLabel("")
        self.progress.setObjectName("dim")
        chips.addWidget(self.progress)
        lay.addLayout(chips)
        body = QHBoxLayout()
        self.list = QListWidget()
        self.list.setMinimumWidth(300)
        self.list.setMaximumWidth(380)
        self.list.currentRowChanged.connect(self._show_detail)
        body.addWidget(self.list)
        right = QVBoxLayout()
        self.detail = QTextBrowser()
        self.detail.setStyleSheet(f"QTextBrowser {{ background:{COLORS['bg_alt']}; padding: 10px; border: 1px solid {COLORS['border']}; }}")
        right.addWidget(self.detail, 1)
        row = QHBoxLayout()
        self.start_btn = NeonButton(tr("start_mission"), "Begin this operation (mission start N)")
        self.abort_btn = NeonButton(tr("abort"), "Abandon the active mission", "danger")
        row.addWidget(self.start_btn)
        row.addWidget(self.abort_btn)
        right.addLayout(row)
        body.addLayout(right, 1)
        lay.addLayout(body, 1)
        self.start_btn.clicked.connect(self._start)
        self.abort_btn.clicked.connect(lambda: self.run_command("mission abort"))
        self.chips["ALL"].setChecked(True)
        engine.mission_changed.connect(self.refresh)
        self.refresh()

    def set_filter(self, key: str) -> None:
        self.filter = key
        for k, chip in self.chips.items():
            chip.setChecked(k == key)
        self.refresh()

    def _visible(self, m: dict, status: str) -> bool:
        ms = self.engine.missions
        if m.get("secret") and status == "locked" and not all(self.engine.player.has(i) for i in m.get("requires_items", [])):
            return False                                   # secret series stay hidden
        if self.filter == "AVAILABLE":
            return status in ("available", "active", "failed")
        if self.filter == "COMPLETED":
            return status == "completed"
        if self.filter == "STORY":
            return bool(m.get("main"))
        if self.filter == "SIDE":
            return not m.get("main")
        return True

    def refresh(self) -> None:
        e, ms = self.engine, self.engine.missions
        keep = self._selected()
        self.list.blockSignals(True)
        self.list.clear()
        self.rows = []
        chapters = {c["id"]: c["title"] for c in e.data.chapters}
        by_ch: dict[int, list[dict]] = {}
        for m in ms.defs:
            if not m.get("contract"):
                by_ch.setdefault(m.get("chapter", 0), []).append(m)
        for ch, items in sorted(by_ch.items()):
            entries = []
            for m in items:
                status = ms.status(m["id"])
                if self._visible(m, status):
                    entries.append((m, status))
            if not entries:
                continue
            head = QListWidgetItem(f"CHAPTER {ch} — {chapters.get(ch, '')}")
            head.setFlags(Qt.ItemFlag.NoItemFlags)
            head.setForeground(QColor(COLORS["cyan"]))
            self.list.addItem(head)
            self.rows.append(None)
            for m, status in entries:
                prereq_missing = any(not ms.is_complete(r) for r in m.get("requires", []))
                icon, color = STATUS_STYLE[status]
                title = "— — —" if (status == "locked" and prereq_missing) else m["title"]
                item = QListWidgetItem(f"{icon} {m['number']:03d}  {title}")
                item.setForeground(QColor(COLORS[color]))
                self.list.addItem(item)
                self.rows.append(m)
        done = sum(1 for m in ms.defs if ms.is_complete(m["id"]))
        self.progress.setText(f"{done} / {len(ms.defs)} {tr('missions')}")
        self.list.blockSignals(False)
        active = ms.active()
        target = active or keep or (ms.available()[0] if ms.available() else None)
        idx = next((i for i, r in enumerate(self.rows) if r and target and r["id"] == target["id"]), None)
        if idx is None:
            idx = next((i for i, r in enumerate(self.rows) if r), -1)
        self.list.setCurrentRow(idx)
        self._show_detail(idx)

    def _selected(self) -> dict | None:
        row = self.list.currentRow()
        return self.rows[row] if 0 <= row < len(self.rows) else None

    def _show_detail(self, _row: int) -> None:
        m = self._selected()
        if not m:
            self.detail.setHtml("")
            self.start_btn.setEnabled(False)
            self.abort_btn.setEnabled(False)
            return
        e, ms = self.engine, self.engine.missions
        status = ms.status(m["id"])
        self.start_btn.setEnabled(status in ("available", "failed") and not ms.active())
        self.abort_btn.setEnabled(status == "active")
        prereq_missing = any(not ms.is_complete(r) for r in m.get("requires", []))
        if status == "locked" and prereq_missing:
            self.detail.setHtml(f'<h2 style="color:{COLORS["dim"]}">MISSION {m["number"]:03d} — LOCKED</h2>'
                                f'<p style="color:{COLORS["dim"]}">{ms.lock_reason(m)}</p>')
            return
        reward = m.get("reward", {})
        d = m["difficulty"]
        icon, color = STATUS_STYLE[status]
        result = f" [{ms.result(m['id'])}]" if status == "completed" else ""
        html = [f'<h2 style="color:{COLORS["green"]}">MISSION {m["number"]:03d} — {m["title"]}</h2>',
                f'<p><span style="color:{COLORS[color]}">{icon} {status.upper()}{result}</span> &nbsp; '
                f'<span style="color:{COLORS[DIFF_COLORS[d]]}">{DIFF_NAMES[d]}</span> &nbsp; '
                f'<span style="color:{COLORS["cyan"]}">{m.get("type", "STORY")}</span> &nbsp; '
                f'<span style="color:{COLORS["dim"]}">chapter {m.get("chapter", "?")} · {"STORY" if m.get("main") else "SIDE"}</span></p>']
        if status == "locked":
            html.append(f'<p style="color:{COLORS["red"]}">🔒 {ms.lock_reason(m)}</p>')
        html += [f'<p>{e.fmt(m["description"])}</p>',
                 f'<p><span style="color:{COLORS["dim"]}">GOAL</span> {e.fmt(m.get("goal", ""))}<br>'
                 f'<span style="color:{COLORS["dim"]}">REWARD</span> <span style="color:{COLORS["green"]}">{reward.get("xp", 0)} XP · ${reward.get("credits", 0):,}'
                 f' · rep +{reward.get("reputation", 0)}</span>'
                 f'<br><span style="color:{COLORS["dim"]}">REQUIRES</span> level {m.get("required_level", 1)}'
                 + (f' · reputation {m["min_reputation"]}' if m.get("min_reputation") else "")
                 + (" · " + ", ".join(e.data.items[i]["name"] for i in m.get("requires_items", [])) if m.get("requires_items") else "")
                 + (f'<br><span style="color:{COLORS["amber"]}">TIME LIMIT {m["time_limit"] // 60} min</span>' if m.get("time_limit") else "") + "</p>",
                 f'<h3 style="color:{COLORS["cyan"]}">OBJECTIVES</h3>']
        for o in ms.objectives_view(m["id"]):
            mark = "✔" if o["done"] else ("▶" if o["current"] else "·")
            c = COLORS["green"] if o["done"] else (COLORS["amber"] if o["current"] else COLORS["text"])
            tag = " <i>(bonus goal)</i>" if o.get("bonus_goal") else (" <i>(bonus)</i>" if o["optional"] else "")
            html.append(f'<div style="color:{c}">{mark} {o["text"]}{tag}</div>')
        if status in ("active", "completed", "failed"):
            html.append(f'<h3 style="color:{COLORS["cyan"]}">BRIEFING</h3>')
            for line in m.get("story_start", []):
                html.append(f'<p style="color:#d6fff0">{e.fmt(line)}</p>')
        if status == "completed":
            for line in m.get("story_end", []):
                html.append(f'<p style="color:{COLORS["green"]}">{e.fmt(line)}</p>')
            decision = m.get("choice", {}).get("key")
            if decision:
                taken = e.db.get_decisions().get(decision)
                if taken:
                    html.append(f'<p style="color:{COLORS["amber"]}">DECISION: {taken.upper()}</p>')
        self.detail.setHtml("".join(html))

    def _start(self) -> None:
        m = self._selected()
        if m:
            self.run_command(f"mission start {m['number']}")
