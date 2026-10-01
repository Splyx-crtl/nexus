"""Messaging panel: talk to ZERO, MIRA, GHOST, VECTOR and ARCHER."""
from __future__ import annotations

import html
import time

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QTextBrowser, QVBoxLayout, QWidget

from nexus.config import COLORS

from .widgets import NeonBar, NeonButton


class ContactsPanel(QWidget):
    def __init__(self, engine, run_command, parent=None):
        super().__init__(parent)
        self.engine, self.run_command = engine, run_command
        self._ids: list[str] = []
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        left = QVBoxLayout()
        self.list = QListWidget()
        self.list.setMaximumWidth(210)
        self.list.currentRowChanged.connect(self._show)
        left.addWidget(self.list)
        lay.addLayout(left)
        right = QVBoxLayout()
        self.title = QLabel("")
        self.title.setObjectName("h2")
        self.sub = QLabel("")
        self.sub.setObjectName("dim")
        self.sub.setWordWrap(True)
        self.trust = NeonBar(COLORS["cyan"], 20, 10)
        self.chat = QTextBrowser()
        self.chat.setStyleSheet(f"QTextBrowser {{ background:{COLORS['bg_alt']}; padding: 8px; border: 1px solid {COLORS['border']}; }}")
        right.addWidget(self.title)
        right.addWidget(self.sub)
        right.addWidget(self.trust)
        right.addWidget(self.chat, 1)
        self.topics = QVBoxLayout()
        right.addLayout(self.topics)
        lay.addLayout(right, 1)
        engine.comms_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        e = self.engine
        row = max(0, self.list.currentRow())
        self.list.blockSignals(True)
        self.list.clear()
        self._ids = []
        for cid, c in e.data.contacts.items():
            rec = e.db.get_contact(cid)
            if not rec or not rec["met"]:
                continue
            unread = e.db.unread_count(cid)
            item = QListWidgetItem(f"{c['name']}" + (f"   ✉ {unread}" if unread else ""))
            item.setForeground(QColor(c["color"]))
            self.list.addItem(item)
            self._ids.append(cid)
        self.list.blockSignals(False)
        if self._ids:
            self.list.setCurrentRow(min(row, len(self._ids) - 1))
        self._show(self.list.currentRow())

    def _show(self, row: int) -> None:
        while self.topics.count():
            w = self.topics.takeAt(0).widget()
            if w:
                w.deleteLater()
        if not (0 <= row < len(self._ids)):
            self.title.setText("NO CONTACTS YET")
            self.chat.setHtml("")
            return
        e = self.engine
        cid = self._ids[row]
        c = e.data.contacts[cid]
        self.title.setText(f"{c['name']}  ·  {c['role']}")
        self.title.setStyleSheet(f"color:{c['color']};")
        self.sub.setText(c["bio"])
        trust = e.trust(cid)
        self.trust.set_color(c["color"])
        self.trust.set_value(trust, 100, f"TRUST {trust}")
        parts = []
        for m in e.db.get_messages(cid, 40):
            stamp = time.strftime("%H:%M", time.localtime(m["ts"]))
            text = html.escape(m["text"])
            if m["direction"] == "in":
                parts.append(f'<p><span style="color:{COLORS["dim"]}">{stamp}</span> <b style="color:{c["color"]}">{c["name"]}</b> {text}</p>')
            else:
                parts.append(f'<p><span style="color:{COLORS["dim"]}">{stamp}</span> <b style="color:{COLORS["green"]}">YOU</b> {text}</p>')
        self.chat.setHtml("".join(parts) or f'<p style="color:{COLORS["dim"]}">No messages yet.</p>')
        self.chat.verticalScrollBar().setValue(self.chat.verticalScrollBar().maximum())
        e.db.mark_read(cid)
        for i, (label, topic) in enumerate(e.commands._visible_topics(cid), 1):
            btn = NeonButton(label, "Ask this topic" if topic else "Raise trust to unlock", "" if topic else "danger")
            btn.setEnabled(topic is not None)
            btn.clicked.connect(lambda _=False, c_id=cid, n=i: self.run_command(f"msg {c_id} {n}"))
            self.topics.addWidget(btn)
