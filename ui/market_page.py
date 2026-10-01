"""NEXUS MARKET: browse, filter and buy tools, upgrades, cosmetics, access and intel."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget)

from nexus import reputation
from nexus.config import COLORS
from nexus.i18n import tr
from nexus.market import CATEGORIES

from .widgets import Chip, ItemIcon, NeonButton, hline, play, rarity_color


class MarketRow(QWidget):
    def __init__(self, entry: dict):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.addWidget(ItemIcon(entry["category"], entry["rarity"], 38))
        mid = QVBoxLayout()
        mid.setSpacing(0)
        name = QLabel(entry["name"])
        name.setStyleSheet(f"color:{rarity_color(entry['rarity'])}; font-weight:bold;")
        sub = QLabel(f"{entry['rarity']}  ·  {entry.get('short', '')}")
        sub.setObjectName("dim")
        mid.addWidget(name)
        mid.addWidget(sub)
        lay.addLayout(mid, 1)
        owned = entry["owned"] and entry["kind"] != "upgrade"
        if entry.get("maxed"):
            status, color = "MAX", COLORS["green"]
        elif owned:
            status, color = tr("owned"), COLORS["green"]
        elif entry["locked_level"]:
            status, color = f"LV {entry['level']}", COLORS["red"]
        else:
            status, color = f"${entry['final_price']:,}", COLORS["amber"]
        right = QVBoxLayout()
        right.setSpacing(0)
        price = QLabel(status)
        price.setAlignment(Qt.AlignmentFlag.AlignRight)
        price.setStyleSheet(f"color:{color}; font-weight:bold;")
        right.addWidget(price)
        if entry["deal"] and not owned:
            deal = QLabel("-20% DEAL")
            deal.setAlignment(Qt.AlignmentFlag.AlignRight)
            deal.setStyleSheet(f"color:{COLORS['green']}; font-size: 10px;")
            right.addWidget(deal)
        lay.addLayout(right)


class MarketPage(QWidget):
    def __init__(self, engine, run_command=None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.category = "ALL"
        self.entries: list[dict] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        head = QHBoxLayout()
        title = QLabel("// NEXUS MARKET")
        title.setObjectName("h1")
        self.credits = QLabel("")
        self.credits.setStyleSheet(f"color:{COLORS['amber']}; font-weight:bold; font-size: 16px;")
        self.rep = QLabel("")
        self.rep.setObjectName("dim")
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self.rep)
        head.addSpacing(18)
        head.addWidget(self.credits)
        lay.addLayout(head)

        self.deal = QLabel("")
        self.deal.setStyleSheet(f"color:{COLORS['green']}; background:{COLORS['panel']}; border:1px solid {COLORS['green_dim']}; padding: 6px 10px;")
        lay.addWidget(self.deal)

        chips = QHBoxLayout()
        self.chips: dict[str, Chip] = {}
        for cat in ["ALL"] + CATEGORIES:
            chip = Chip(tr(cat.lower()))
            chip.clicked.connect(lambda _=False, c=cat: self.set_category(c))
            chips.addWidget(chip)
            self.chips[cat] = chip
        chips.addStretch(1)
        lay.addLayout(chips)

        body = QHBoxLayout()
        self.list = QListWidget()
        self.list.setMinimumWidth(380)
        self.list.currentRowChanged.connect(self._show)
        body.addWidget(self.list, 3)

        self.detail = QFrame()
        self.detail.setObjectName("panel")
        dl = QVBoxLayout(self.detail)
        dl.setContentsMargins(16, 14, 16, 14)
        top = QHBoxLayout()
        self.big_icon = ItemIcon("TOOLS", "COMMON", 72)
        top.addWidget(self.big_icon)
        tt = QVBoxLayout()
        self.d_name = QLabel("")
        self.d_name.setObjectName("h2")
        self.d_meta = QLabel("")
        self.d_meta.setObjectName("dim")
        tt.addWidget(self.d_name)
        tt.addWidget(self.d_meta)
        top.addLayout(tt, 1)
        dl.addLayout(top)
        dl.addWidget(hline())
        self.d_desc = QLabel("")
        self.d_desc.setWordWrap(True)
        self.d_stats = QLabel("")
        self.d_stats.setStyleSheet(f"color:{COLORS['cyan']}; font-weight:bold;")
        self.d_stats.setWordWrap(True)
        self.d_req = QLabel("")
        self.d_req.setObjectName("dim")
        self.d_price = QLabel("")
        self.d_price.setStyleSheet(f"color:{COLORS['amber']}; font-size: 20px; font-weight:bold;")
        for w in (self.d_desc, self.d_stats, self.d_req, self.d_price):
            dl.addWidget(w)
        dl.addStretch(1)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        dl.addWidget(self.status)
        row = QHBoxLayout()
        self.buy_btn = NeonButton(tr("buy"), "Purchase the selected item")
        self.equip_btn = NeonButton(tr("equip"), "Equip this gear in your loadout", "cyan")
        self.buy_btn.clicked.connect(self._buy)
        self.equip_btn.clicked.connect(self._equip)
        row.addWidget(self.buy_btn)
        row.addWidget(self.equip_btn)
        dl.addLayout(row)
        body.addWidget(self.detail, 2)
        lay.addLayout(body, 1)

        engine.inventory_changed.connect(self.refresh)
        engine.state_changed.connect(self._update_header)
        self.set_category("ALL")

    # ------------------------------------------------------------ helpers --
    def set_category(self, cat: str) -> None:
        self.category = cat
        for key, chip in self.chips.items():
            chip.setChecked(key == cat)
        self.refresh()

    def _update_header(self) -> None:
        p = self.engine.player
        self.credits.setText(f"${p.credits:,}")
        self.rep.setText(f"{tr('reputation')} {p.reputation} — {reputation.status(p.reputation)}  ·  {reputation.describe(p.reputation)}")

    def refresh(self) -> None:
        e = self.engine
        self._update_header()
        deal_id = e.market.daily_deal_id()
        if deal_id:
            d = e.market.find(deal_id)
            self.deal.setText(f"★ {tr('daily_deal')}: {d['name']}  —  20% OFF  →  ${d['final_price']:,}")
            self.deal.show()
        else:
            self.deal.hide()
        row = max(0, self.list.currentRow())
        self.entries = e.market.catalogue(None if self.category == "ALL" else self.category)
        self.list.blockSignals(True)
        self.list.clear()
        for entry in self.entries:
            item = QListWidgetItem()
            widget = MarketRow(entry)
            item.setSizeHint(widget.sizeHint())
            self.list.addItem(item)
            self.list.setItemWidget(item, widget)
        self.list.blockSignals(False)
        if self.entries:
            self.list.setCurrentRow(min(row, len(self.entries) - 1))
        self._show(self.list.currentRow())

    def _current(self) -> dict | None:
        row = self.list.currentRow()
        return self.entries[row] if 0 <= row < len(self.entries) else None

    def _show(self, row: int) -> None:
        entry = self._current()
        if not entry:
            return
        self.big_icon.set_item(entry["category"], entry["rarity"])
        self.d_name.setText(entry["name"])
        self.d_name.setStyleSheet(f"color:{rarity_color(entry['rarity'])}; font-weight:bold; font-size: 16px;")
        self.d_meta.setText(f"{entry['rarity']}  ·  {entry['category']}" + (f"  ·  SLOT {entry['slot']}" if entry.get("slot") else ""))
        self.d_desc.setText(entry["description"])
        self.d_stats.setText(entry.get("stats_text") or entry.get("short", ""))
        owned = entry["owned"] and entry["kind"] != "upgrade"
        self.d_req.setText(f"Required level {entry.get('level', 1)}" + ("   ·   ★ daily deal" if entry["deal"] else ""))
        if entry.get("maxed") or owned:
            self.d_price.setText("—")
        else:
            base = f"   (was ${entry['base_price']:,})" if entry["final_price"] != entry["base_price"] else ""
            self.d_price.setText(f"${entry['final_price']:,}{base}")
        p = self.engine.player
        reason = ""
        if entry.get("maxed"):
            reason = "Already at maximum level."
        elif owned:
            reason = "You already own this."
        elif entry["locked_level"]:
            reason = f"Reach level {entry['level']} to unlock."
        elif p.credits < entry["final_price"]:
            reason = f"You need ${entry['final_price'] - p.credits:,} more."
        self.buy_btn.setEnabled(not reason)
        self.buy_btn.setText(tr("buy") + (f"  ${entry['final_price']:,}" if not owned and not entry.get("maxed") else ""))
        self.status.setText(reason)
        self.status.setStyleSheet(f"color:{COLORS['dim']};")
        can_equip = entry.get("kind") == "gear" and entry["owned"] and not entry["equipped"]
        self.equip_btn.setVisible(entry.get("kind") == "gear")
        self.equip_btn.setEnabled(can_equip)
        self.equip_btn.setText(tr("equipped") if entry["equipped"] else tr("equip"))

    def _buy(self) -> None:
        entry = self._current()
        if not entry:
            return
        ok, msg = self.engine.market.purchase(entry["id"])
        play("notify" if ok else "error")
        self.refresh()
        self.status.setText(msg)
        self.status.setStyleSheet(f"color:{COLORS['green'] if ok else COLORS['red']}; font-weight:bold;")

    def _equip(self) -> None:
        entry = self._current()
        if not entry:
            return
        ok, msg = self.engine.market.equip(entry["id"])
        self.refresh()
        self.status.setText(msg)
        self.status.setStyleSheet(f"color:{COLORS['green'] if ok else COLORS['red']}; font-weight:bold;")
