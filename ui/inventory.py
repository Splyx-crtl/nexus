"""Inventory: filterable item list with stats, equipped status, upgrades and local files."""
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QScrollArea, QTabWidget, QTextBrowser,
                               QVBoxLayout, QWidget)

from nexus.config import COLORS
from nexus.i18n import tr
from nexus.market import STAT_LABELS

from .widgets import Chip, Deferred, ItemIcon, NeonBar, NeonButton, Panel, hline, rarity_color

FILTERS = ["ALL", "TOOLS", "UPGRADES", "ACCESS", "COSMETICS", "SPECIAL"]


class InvRow(QWidget):
    def __init__(self, entry: dict):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 3, 6, 3)
        lay.addWidget(ItemIcon(entry["category"], entry["rarity"], 36))
        col = QVBoxLayout()
        col.setSpacing(0)
        name = QLabel(entry["name"])
        name.setStyleSheet(f"color:{rarity_color(entry['rarity'])}; font-weight:bold;")
        sub = QLabel(f"{entry['rarity']}  ·  {entry['category']}")
        sub.setObjectName("dim")
        col.addWidget(name)
        col.addWidget(sub)
        lay.addLayout(col, 1)
        if entry["equipped"]:
            tag = QLabel(f"● {tr('equipped')}")
            tag.setStyleSheet(f"color:{COLORS['green']}; font-size: 10px;")
            lay.addWidget(tag)
        if entry["qty"] > 1:
            qty = QLabel(f"x{entry['qty']}")
            qty.setStyleSheet(f"color:{COLORS['cyan']}; font-weight:bold;")
            lay.addWidget(qty)


class InventoryPanel(QWidget):
    def __init__(self, engine, run_command, parent=None):
        super().__init__(parent)
        self.engine, self.run_command = engine, run_command
        self.filter = "ALL"
        self.entries: list[dict] = []
        self._files: list[str] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        title = QLabel(f"// {tr('inventory')}")
        title.setObjectName("h1")
        lay.addWidget(title)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)

        # ----- items
        items = QWidget()
        il = QVBoxLayout(items)
        chips = QHBoxLayout()
        self.chips: dict[str, Chip] = {}
        for f in FILTERS:
            chip = Chip(tr(f.lower()))
            chip.clicked.connect(lambda _=False, k=f: self.set_filter(k))
            chips.addWidget(chip)
            self.chips[f] = chip
        chips.addStretch(1)
        il.addLayout(chips)
        body = QHBoxLayout()
        self.item_list = QListWidget()
        self.item_list.setMinimumWidth(320)
        self.item_list.currentRowChanged.connect(self._show_item)
        body.addWidget(self.item_list, 3)
        right = QVBoxLayout()
        top = QHBoxLayout()
        self.big_icon = ItemIcon("TOOLS", "COMMON", 64)
        top.addWidget(self.big_icon)
        self.d_name = QLabel("")
        self.d_name.setObjectName("h2")
        top.addWidget(self.d_name, 1)
        right.addLayout(top)
        right.addWidget(hline())
        self.d_text = QTextBrowser()
        right.addWidget(self.d_text, 1)
        row = QHBoxLayout()
        self.act_btn = NeonButton(tr("use"), "Use / equip the selected item")
        self.act_btn.clicked.connect(self._act)
        self.act2_btn = NeonButton(tr("unequip"), "Remove from loadout", "cyan")
        self.act2_btn.clicked.connect(self._act2)
        row.addWidget(self.act_btn)
        row.addWidget(self.act2_btn)
        right.addLayout(row)
        body.addLayout(right, 2)
        il.addLayout(body, 1)
        self.tabs.addTab(items, tr("inventory"))

        # ----- upgrades
        up = QScrollArea()
        up.setWidgetResizable(True)
        self.up_body = QWidget()
        self.up_lay = QVBoxLayout(self.up_body)
        self.up_lay.setSpacing(8)
        up.setWidget(self.up_body)
        self.tabs.addTab(up, tr("upgrades"))

        # ----- files
        files = QWidget()
        fl = QHBoxLayout(files)
        self.file_list = QListWidget()
        self.file_list.setMaximumWidth(260)
        self.file_list.currentRowChanged.connect(self._show_file)
        fl.addWidget(self.file_list)
        fr = QVBoxLayout()
        self.file_view = QTextBrowser()
        fr.addWidget(self.file_view, 1)
        self.storage_label = QLabel("")
        self.storage_label.setObjectName("dim")
        fr.addWidget(self.storage_label)
        fl.addLayout(fr, 1)
        self.tabs.addTab(files, "LOCAL FILES")

        engine.inventory_changed.connect(Deferred(self, self.refresh))
        self.set_filter("ALL")

    # ------------------------------------------------------------ entries --
    def _collect(self) -> list[dict]:
        e = self.engine
        eq = set(e.db.get_equipment().values())
        out: list[dict] = []
        for item_id, qty in e.player.inventory().items():
            it = e.data.items[item_id]
            stats = ", ".join(f"{STAT_LABELS[k]} +{v}%" for k, v in it.get("stats", {}).items())
            out.append({"id": item_id, "kind": it.get("kind", "item"), "name": it["name"], "category": it.get("category", "SPECIAL"),
                        "rarity": it.get("rarity", "COMMON").upper(), "qty": qty, "equipped": item_id in eq, "desc": it["description"],
                        "stats": stats, "slot": it.get("slot"), "item": it})
        for uid, up in e.data.upgrades.items():
            lvl = e.player.upgrade_level(uid)
            if lvl:
                out.append({"id": f"upgrade:{uid}", "kind": "upgrade", "name": f"{up['name']}  LV {lvl}/{up['max_level']}", "category": "UPGRADES",
                            "rarity": ["COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY", "NEXUS"][min(lvl, 5)], "qty": 1, "equipped": False,
                            "desc": up["description"], "stats": f"Level {lvl} of {up['max_level']}", "slot": None, "item": up})
        current_theme = e.settings_value("theme") if e.settings else "default"
        for t in e.data.themes:
            if t.get("free") or e.db.is_unlocked(f"theme:{t['id']}"):
                out.append({"id": f"theme:{t['id']}", "kind": "theme", "name": f"Theme: {t['name']}", "category": "COSMETICS", "rarity": "COMMON" if t.get("free") else "RARE",
                            "qty": 1, "equipped": t["id"] == current_theme, "desc": "Terminal colour theme. Applies to the whole interface.",
                            "stats": "", "slot": None, "item": t})
        return out

    def set_filter(self, key: str) -> None:
        self.filter = key
        for k, chip in self.chips.items():
            chip.setChecked(k == key)
        self.refresh()

    def refresh(self) -> None:
        row = max(0, self.item_list.currentRow())
        entries = self._collect()
        self.entries = [x for x in entries if self.filter == "ALL" or x["category"] == self.filter]
        self.item_list.blockSignals(True)
        self.item_list.clear()
        for entry in self.entries:
            li = QListWidgetItem()
            w = InvRow(entry)
            li.setSizeHint(w.sizeHint())
            self.item_list.addItem(li)
            self.item_list.setItemWidget(li, w)
        self.item_list.blockSignals(False)
        if self.entries:
            self.item_list.setCurrentRow(min(row, len(self.entries) - 1))
        self._show_item(self.item_list.currentRow())
        self._build_upgrades()
        self._refresh_files()

    def _current(self) -> dict | None:
        row = self.item_list.currentRow()
        return self.entries[row] if 0 <= row < len(self.entries) else None

    def _show_item(self, _row: int) -> None:
        e = self._current()
        if not e:
            self.d_name.setText("")
            self.d_text.setHtml(f'<p style="color:{COLORS["dim"]}">Nothing here yet. Complete missions or visit the market.</p>')
            self.act_btn.setEnabled(False)
            self.act2_btn.hide()
            return
        self.big_icon.set_item(e["category"], e["rarity"])
        self.d_name.setText(e["name"])
        self.d_name.setStyleSheet(f"color:{rarity_color(e['rarity'])}; font-weight:bold; font-size: 16px;")
        html = [f'<p style="color:{COLORS["dim"]}">{e["rarity"]} · {e["category"]}' + (f" · owned x{e['qty']}" if e["kind"] not in ("theme", "upgrade") else "") + "</p>",
                f"<p>{e['desc']}</p>"]
        if e["stats"]:
            html.append(f'<p style="color:{COLORS["cyan"]}"><b>{e["stats"]}</b></p>')
        if e["slot"]:
            html.append(f'<p style="color:{COLORS["dim"]}">SLOT: {e["slot"]}   ·   {"EQUIPPED" if e["equipped"] else "not equipped"}</p>')
        self.d_text.setHtml("".join(html))
        kind = e["kind"]
        self.act2_btn.hide()
        if kind == "gear":
            self.act_btn.setText(tr("equipped") if e["equipped"] else tr("equip"))
            self.act_btn.setEnabled(not e["equipped"])
            self.act2_btn.setVisible(e["equipped"])
        elif kind == "theme":
            self.act_btn.setText("APPLY THEME")
            self.act_btn.setEnabled(not e["equipped"])
        elif kind in ("consumable", "special") and e["item"].get("effect") not in (None, "passive"):
            self.act_btn.setText(tr("use"))
            self.act_btn.setEnabled(True)
        else:
            self.act_btn.setText("PASSIVE")
            self.act_btn.setEnabled(False)

    def _act(self) -> None:
        e = self._current()
        if not e:
            return
        if e["kind"] == "gear":
            self.engine.market.equip(e["id"])
        elif e["kind"] == "theme":
            self.run_command(f"theme {e['id'].split(':')[1]}")
        else:
            self.run_command(f"use {e['id']}")

    def _act2(self) -> None:
        e = self._current()
        if e and e["slot"]:
            self.engine.market.unequip(e["slot"])

    # ------------------------------------------------------------ upgrades --
    def _build_upgrades(self) -> None:
        while self.up_lay.count():
            w = self.up_lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        self._up_buttons: dict[str, NeonButton] = {}
        e, p = self.engine, self.engine.player
        for i, (uid, up) in enumerate(e.data.upgrades.items(), 1):
            panel = Panel()
            head = QHBoxLayout()
            name = QLabel(up["name"])
            name.setObjectName("h2")
            lvl = p.upgrade_level(uid)
            level = QLabel(f"LV {lvl}/{up['max_level']}")
            level.setObjectName("dim")
            head.addWidget(name)
            head.addStretch(1)
            head.addWidget(level)
            panel.body.addLayout(head)
            bar = NeonBar(COLORS["cyan"], up["max_level"], 8)
            bar.set_value(lvl, up["max_level"])
            panel.body.addWidget(bar)
            desc = QLabel(up["description"])
            desc.setWordWrap(True)
            desc.setObjectName("dim")
            panel.body.addWidget(desc)
            cost = p.upgrade_cost(uid)
            btn = NeonButton("MAXED" if cost is None else f"BUY  ${cost:,}", f"Spend credits to raise {up['name']}")
            btn.setEnabled(cost is not None and p.credits >= cost)
            btn.clicked.connect(lambda _=False, n=i: self.run_command(f"upgrade {n}"))
            panel.body.addWidget(btn)
            self._up_buttons[uid] = btn
            self.up_lay.addWidget(panel)
        self.up_lay.addStretch(1)

    def refresh_buttons(self) -> None:
        p = self.engine.player
        for uid, btn in getattr(self, "_up_buttons", {}).items():
            cost = p.upgrade_cost(uid)
            btn.setEnabled(cost is not None and p.credits >= cost)

    # --------------------------------------------------------------- files --
    def _refresh_files(self) -> None:
        e = self.engine
        self._files = list(e.local.files())
        self.file_list.blockSignals(True)
        self.file_list.clear()
        for path in self._files:
            self.file_list.addItem(f"~/{path}")
        self.file_list.blockSignals(False)
        self.storage_label.setText(f"downloads: {e.local.download_count()} / {e.player.storage_capacity} slots  ·  'rm <file>' frees space")
        if self._files:
            self.file_list.setCurrentRow(0)
        else:
            self.file_view.setHtml(f'<p style="color:{COLORS["dim"]}">No local files. Use "download" on a server.</p>')

    def _show_file(self, row: int) -> None:
        if 0 <= row < len(self._files):
            content = self.engine.local.files()[self._files[row]]["content"]
            esc = content.replace("&", "&amp;").replace("<", "&lt;")
            self.file_view.setHtml(f'<pre style="color:{COLORS["text"]}">{esc}</pre>')
