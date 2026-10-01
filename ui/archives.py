"""ARCHIVES: lore, endings, raw statistics and the activity log for the current operator."""
from __future__ import annotations

import time

from PySide6.QtWidgets import (QLabel, QTableWidget, QTableWidgetItem, QTabWidget, QTextBrowser, QVBoxLayout, QWidget)

from nexus.config import COLORS
from nexus.i18n import tr
from nexus.save_system import SaveSystem

STAT_LABELS = [
    ("missions_completed", "Missions completed"), ("missions_failed", "Missions failed"), ("perfect_missions", "Perfect operations"),
    ("clean_missions", "Mistake-free missions"), ("hard_missions", "Hard missions"), ("bonus_goals_done", "Bonus goals"),
    ("connections", "Connections"), ("scans", "Scans"), ("logins", "Logins"), ("firewalls_breached", "Firewalls breached"),
    ("decryptions", "Decryptions"), ("routes_solved", "Routes solved"), ("access_solved", "Access codes cracked"),
    ("traces_done", "Traces completed"), ("minigames_won", "Mini-games won"), ("minigames_lost", "Mini-games lost"),
    ("files_read", "Files read"), ("downloads", "Downloads"), ("secrets_found", "Secret files found"), ("secret_commands", "Secret commands"),
    ("hidden_found", "Hidden servers"), ("events_seen", "Random events"), ("commands_run", "Commands run"),
    ("credits_earned", "Credits earned"), ("credits_spent", "Credits spent"), ("market_spent", "Spent at the market"),
    ("purchases", "Market purchases"), ("xp_earned", "XP earned"), ("upgrades_bought", "Upgrades bought"),
    ("daily_claims", "Daily rewards claimed"), ("weekly_claims", "Weekly rewards claimed"), ("chapters_completed", "Chapters completed"),
    ("easter_eggs", "Easter eggs"),
]


class ArchivesWidget(QWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        title = QLabel(f"// {tr('archives')}")
        title.setObjectName("h1")
        lay.addWidget(title)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)
        self.lore = QTextBrowser()
        self.endings = QTextBrowser()
        self.stats = QTableWidget(0, 2)
        self.stats.setHorizontalHeaderLabels(["STATISTIC", "VALUE"])
        self.stats.horizontalHeader().setStretchLastSection(True)
        self.stats.verticalHeader().hide()
        self.stats.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.log = QTextBrowser()
        for w, name in ((self.lore, "LORE"), (self.endings, "ENDINGS"), (self.stats, tr("statistics")), (self.log, tr("notifications"))):
            self.tabs.addTab(w, name)
        self.refresh()

    def refresh(self) -> None:
        e = self.engine
        db, data = e.db, e.data
        profile = db.get_profile()

        done = db.all_missions()
        html = [f'<h2 style="color:{COLORS["cyan"]}">OPERATOR ROSTER</h2>']
        known = "mission_011" in done and done["mission_011"]["status"] == "completed"
        for op in data.operators:
            html.append(f'<div style="color:{COLORS["text"]}">{op["id"]} &nbsp; {op["callsign"] if known else "████████"} &nbsp; '
                        f'<span style="color:{COLORS["amber"]}">{op["status"] if known else "CLASSIFIED"}</span></div>')
        html.append(f'<h2 style="color:{COLORS["cyan"]}">STORY SO FAR</h2>')
        for ch in data.chapters:
            chapter_done = db.get_flag(f"chapter_{ch['id']}_done")
            html.append(f'<h3 style="color:{COLORS["green"] if chapter_done else COLORS["dim"]}">CHAPTER {ch["id"]} — {ch["title"]}'
                        f'{"  ✔" if chapter_done else ""}</h3><p style="color:{COLORS["dim"]}">{ch["summary"]}</p>')
            for m in data.missions:
                rec = done.get(m["id"])
                if m.get("main") and m.get("chapter") == ch["id"] and rec and rec["status"] == "completed":
                    html.append(f'<h4 style="color:{COLORS["green"]}">{m["number"]:03d} {m["title"]}</h4>')
                    for line in m.get("story_start", []) + m.get("story_end", []):
                        html.append(f'<p style="color:#d6fff0">{line.replace("{player}", profile["username"])}</p>')
        self.lore.setHtml("".join(html))

        seen = db.get_world("endings", [])
        parts = []
        for end in data.endings.values():
            if end["id"] in seen:
                body = "".join(f"<p>{line.replace('{player}', profile['username'])}</p>" for line in end["lines"])
                parts.append(f'<h2 style="color:{COLORS["green"]}">{end["title"]}</h2><p style="color:{COLORS["cyan"]}">{end["subtitle"]}</p>{body}<hr>')
            else:
                parts.append(f'<h2 style="color:{COLORS["dim"]}">??? — undiscovered ending</h2><hr>')
        self.endings.setHtml("".join(parts))

        stats = db.all_stats()
        rows = [("Operator", profile["username"]), ("Level", profile["level"]), ("Credits", f"${profile['credits']:,}"),
                ("Reputation", profile["reputation"]), ("Playtime", SaveSystem.format_time(profile["playtime"]))]
        rows += [(label, f"{int(stats[key]):,}") for key, label in STAT_LABELS if key in stats]
        self.stats.setRowCount(len(rows))
        for r, (label, value) in enumerate(rows):
            self.stats.setItem(r, 0, QTableWidgetItem(str(label)))
            self.stats.setItem(r, 1, QTableWidgetItem(str(value)))

        log = []
        for n in db.get_notifications(80):
            stamp = time.strftime("%m-%d %H:%M", time.localtime(n["ts"]))
            log.append(f'<div><span style="color:{COLORS["dim"]}">{stamp}</span> <b style="color:{COLORS["cyan"]}">{n["title"]}</b> {n["text"]}</div>')
        self.log.setHtml("".join(log) or f'<p style="color:{COLORS["dim"]}">{tr("no_notifications")}</p>')
