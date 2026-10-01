"""LOADOUT: five equipment slots, total bonuses and your gear inventory."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from nexus.config import COLORS
from nexus.i18n import tr
from nexus.market import SLOTS, STAT_LABELS

from .widgets import ItemIcon, NeonBar, NeonButton, hline, play, rarity_color

SLOT_HINT = {"TRACE": "Slows trace streams, more misses allowed", "DECRYPT": "Free cipher hints",
             "FIREWALL": "More firewall attempts, symbol reveal", "NETWORK": "Bigger routing budget, scan detail",
             "UTILITY": "Stealth, XP and credit bonuses"}


class SlotCard(QFrame):
    def __init__(self, slot: str, on_unequip, on_select):
        super().__init__()
        self.slot = slot
        self.setObjectName("card")
        self.setMinimumHeight(98)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        self.icon = ItemIcon("TOOLS", "COMMON", 56)
        lay.addWidget(self.icon)
        col = QVBoxLayout()
        self.title = QLabel(slot)
        self.title.setObjectName("h2")
        self.name = QLabel("")
        self.stats = QLabel("")
        self.stats.setObjectName("dim")
        self.stats.setWordWrap(True)
        col.addWidget(self.title)
        col.addWidget(self.name)
        col.addWidget(self.stats)
        lay.addLayout(col, 1)
        self.btn = NeonButton(tr("unequip"), "Remove this item", "danger")
        self.btn.clicked.connect(lambda: on_unequip(slot))
        lay.addWidget(self.btn)
        self.mousePressEvent = lambda ev: on_select(slot)

    def set_state(self, unlocked: bool, item: dict | None) -> None:
        self.btn.setVisible(bool(item))
        g = self.slot[0]
        if not unlocked:
            self.icon.set_item("SPECIAL", "COMMON", "×")
            self.name.setText(f"🔒 {tr('slot_locked')}")
            self.name.setStyleSheet(f"color:{COLORS['red']};")
            self.stats.setText("Progress the story to unlock this slot.")
        elif item:
            self.icon.set_item(item["category"], item["rarity"], g)
            self.name.setText(item["name"])
            self.name.setStyleSheet(f"color:{rarity_color(item['rarity'])}; font-weight:bold;")
            self.stats.setText(item.get("short", ""))
        else:
            self.icon.set_item("SPECIAL", "COMMON", g)
            self.name.setText(tr("empty"))
            self.name.setStyleSheet(f"color:{COLORS['dim']};")
            self.stats.setText(SLOT_HINT[self.slot])


class LoadoutPage(QWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.selected_slot = "TRACE"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        title = QLabel("// LOADOUT")
        title.setObjectName("h1")
        lay.addWidget(title)
        body = QHBoxLayout()

        left = QVBoxLayout()
        self.cards: dict[str, SlotCard] = {}
        for slot in SLOTS:
            card = SlotCard(slot, self._unequip, self._select)
            self.cards[slot] = card
            left.addWidget(card)
        body.addLayout(left, 3)

        right = QVBoxLayout()
        stat_panel = QFrame()
        stat_panel.setObjectName("panel")
        sl = QVBoxLayout(stat_panel)
        sl.setContentsMargins(14, 10, 14, 10)
        head = QLabel(f"// {tr('total_bonuses')}")
        head.setObjectName("h2")
        sl.addWidget(head)
        self.stat_bars: dict[str, tuple[QLabel, NeonBar]] = {}
        grid = QGridLayout()
        for i, (key, label) in enumerate(STAT_LABELS.items()):
            name = QLabel(label)
            bar = NeonBar(COLORS["cyan"], 20, 10)
            val = QLabel("+0%")
            val.setMinimumWidth(48)
            grid.addWidget(name, i, 0)
            grid.addWidget(bar, i, 1)
            grid.addWidget(val, i, 2)
            self.stat_bars[key] = (val, bar)
        sl.addLayout(grid)
        right.addWidget(stat_panel)

        inv = QFrame()
        inv.setObjectName("panel")
        il = QVBoxLayout(inv)
        il.setContentsMargins(14, 10, 14, 10)
        self.inv_title = QLabel("")
        self.inv_title.setObjectName("h2")
        il.addWidget(self.inv_title)
        self.gear_list = QListWidget()
        self.gear_list.itemDoubleClicked.connect(lambda _: self._equip())
        il.addWidget(self.gear_list, 1)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        il.addWidget(self.status)
        self.equip_btn = NeonButton(tr("equip"), "Equip the selected item (double-click works too)")
        self.equip_btn.clicked.connect(self._equip)
        il.addWidget(self.equip_btn)
        right.addWidget(inv, 1)
        body.addLayout(right, 2)
        lay.addLayout(body, 1)

        engine.inventory_changed.connect(self.refresh)
        self.refresh()

    def _select(self, slot: str) -> None:
        self.selected_slot = slot
        self.refresh()

    def refresh(self) -> None:
        e = self.engine
        eq = e.market.equipped()
        for slot, card in self.cards.items():
            item = e.data.items.get(eq.get(slot, ""))
            card.set_state(e.market.slot_unlocked(slot), item)
            card.setStyleSheet(f"QFrame#card {{ border: 1px solid {COLORS['green'] if slot == self.selected_slot else COLORS['border']}; }}")
        totals = e.market.total_stats()
        for key, (val, bar) in self.stat_bars.items():
            val.setText(f"+{totals[key]}%")
            bar.set_value(min(100, totals[key]), 100)
        self.inv_title.setText(f"// GEAR FOR {self.selected_slot}")
        self.gear_list.clear()
        self._gear: list[str] = []
        for item_id, qty in e.player.inventory().items():
            it = e.data.items[item_id]
            if it.get("kind") == "gear" and it.get("slot") == self.selected_slot:
                mark = "  [EQUIPPED]" if eq.get(self.selected_slot) == item_id else ""
                li = QListWidgetItem(f"{it['name']}  —  {it.get('short', '')}{mark}")
                from PySide6.QtGui import QColor
                li.setForeground(QColor(rarity_color(it["rarity"])))
                self.gear_list.addItem(li)
                self._gear.append(item_id)
        if not self._gear:
            self.status.setText("No gear for this slot yet — visit the MARKET.")
            self.status.setStyleSheet(f"color:{COLORS['dim']};")
        self.equip_btn.setEnabled(bool(self._gear))
        if self._gear:
            self.gear_list.setCurrentRow(0)

    def _equip(self) -> None:
        row = self.gear_list.currentRow()
        if 0 <= row < len(self._gear):
            ok, msg = self.engine.market.equip(self._gear[row])
            play("notify" if ok else "error")
            self.refresh()
            self.status.setText(msg)
            self.status.setStyleSheet(f"color:{COLORS['green'] if ok else COLORS['red']};")

    def _unequip(self, slot: str) -> None:
        ok, msg = self.engine.market.unequip(slot)
        self.refresh()
        self.status.setText(msg)
