"""ACHIEVEMENTS: category filter, locked/unlocked state, date, description and reward."""
from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from nexus.config import COLORS
from nexus.i18n import tr

from .widgets import Chip, NeonBar

CATEGORIES = ["ALL", "STORY", "COMBAT", "PUZZLES", "EXPLORATION", "ECONOMY", "SECRETS", "MASTERY"]
CAT_COLOR = {"STORY": "cyan", "COMBAT": "red", "PUZZLES": "purple", "EXPLORATION": "green", "ECONOMY": "amber", "SECRETS": "white", "MASTERY": "green"}


def reward_text(reward: dict) -> str:
    parts = []
    if reward.get("credits"):
        parts.append(f"${reward['credits']:,}")
    if reward.get("xp"):
        parts.append(f"+{reward['xp']} XP")
    if reward.get("item"):
        parts.append(reward["item"])
    if reward.get("unlock"):
        parts.append("unlocks " + reward["unlock"].replace("theme:", "theme "))
    return "  ·  ".join(parts) or "—"


class AchievementCard(QFrame):
    def __init__(self, ach: dict, unlocked_at: float | None):
        super().__init__()
        self.setObjectName("card")
        have = unlocked_at is not None
        color = COLORS[CAT_COLOR.get(ach["category"], "green")] if have else COLORS["dim"]
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        star = QLabel("★" if have else "☆")
        star.setStyleSheet(f"color:{COLORS['amber'] if have else COLORS['dim']}; font-size: 24px;")
        lay.addWidget(star)
        col = QVBoxLayout()
        col.setSpacing(1)
        hidden = not have and ach.get("hidden")
        name = QLabel("??? — hidden achievement" if hidden else ach["name"])
        name.setStyleSheet(f"color:{color}; font-weight:bold; font-size: 13px;")
        desc = QLabel("Keep exploring to discover this one." if hidden else ach["description"])
        desc.setObjectName("dim")
        desc.setWordWrap(True)
        col.addWidget(name)
        col.addWidget(desc)
        lay.addLayout(col, 1)
        right = QVBoxLayout()
        right.setSpacing(1)
        state = QLabel(f"{tr('unlocked')}  {time.strftime('%Y-%m-%d', time.localtime(unlocked_at))}" if have else tr("locked"))
        state.setStyleSheet(f"color:{COLORS['green'] if have else COLORS['dim']}; font-weight:bold;")
        rew = QLabel("" if hidden else "REWARD  " + reward_text(ach.get("reward", {})))
        rew.setStyleSheet(f"color:{COLORS['amber']}; font-size: 10px;")
        cat = QLabel(ach["category"])
        cat.setStyleSheet(f"color:{color}; font-size: 10px;")
        for w in (state, rew, cat):
            w.setAlignment(Qt.AlignmentFlag.AlignRight)
            right.addWidget(w)
        lay.addLayout(right)


class AchievementsPage(QWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.cat = "ALL"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        head = QHBoxLayout()
        title = QLabel(f"// {tr('achievements')}")
        title.setObjectName("h1")
        self.summary = QLabel("")
        self.summary.setObjectName("dim")
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self.summary)
        lay.addLayout(head)
        self.bar = NeonBar(COLORS["amber"], 40, 10)
        lay.addWidget(self.bar)
        chips = QHBoxLayout()
        self.chips: dict[str, Chip] = {}
        for c in CATEGORIES:
            chip = Chip(c)
            chip.clicked.connect(lambda _=False, k=c: self.set_category(k))
            chips.addWidget(chip)
            self.chips[c] = chip
        chips.addStretch(1)
        lay.addLayout(chips)
        self.list = QListWidget()
        lay.addWidget(self.list, 1)
        engine.achievement_unlocked.connect(lambda _a: self.refresh())
        self.set_category("ALL")

    def set_category(self, cat: str) -> None:
        self.cat = cat
        for k, chip in self.chips.items():
            chip.setChecked(k == cat)
        self.refresh()

    def refresh(self) -> None:
        e = self.engine
        have = e.db.get_achievements()
        self.summary.setText(f"{len(have)} / {len(e.data.achievements)} {tr('unlocked')}")
        self.bar.set_value(len(have), len(e.data.achievements))
        self.list.clear()
        items = [a for a in e.data.achievements if self.cat == "ALL" or a["category"] == self.cat]
        items.sort(key=lambda a: (a["id"] not in have, a["category"]))
        for ach in items:
            li = QListWidgetItem()
            card = AchievementCard(ach, have.get(ach["id"]))
            li.setSizeHint(card.sizeHint())
            self.list.addItem(li)
            self.list.setItemWidget(li, card)
