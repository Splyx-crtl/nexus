"""ADMIN panel: log in with the credentials set on the server, then create and manage the access keys of the online service.

The credentials are checked by the server; the game contains none. The admin session only lives in memory."""
from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QSpinBox, QStackedWidget, QTableWidget,
                               QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget)

from nexus.config import COLORS

from .dialogs import ConfirmDialog, NeonDialog
from .online_page import Job
from .widgets import NeonButton, mono_font

STATUS_COLOR = {"unused": "cyan", "in use": "green", "revoked": "red"}


class AdminPanel(NeonDialog):
    def __init__(self, client, parent=None):
        super().__init__("ADMIN PANEL", parent, 820)
        self.client = client
        self._jobs: list[Job] = []
        self.keys: list[dict] = []
        self.stack = QStackedWidget()
        self.lay.addWidget(self.stack, 1)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setObjectName("dim")
        self.lay.addWidget(self.status)
        self._build_login()
        self._build_manage()
        row = QHBoxLayout()
        close = NeonButton("CLOSE")
        close.clicked.connect(self.accept)
        row.addStretch(1)
        row.addWidget(close)
        self.lay.addLayout(row)
        self._show_state()

    # ------------------------------------------------------------ builders --
    def _build_login(self) -> None:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 8)
        intro = QLabel("Log in with the admin user name and password you set on the server (NEXUS_ADMIN_USER / NEXUS_ADMIN_PASSWORD). "
                       "They are checked by the server and are not stored in the game.")
        intro.setWordWrap(True)
        intro.setObjectName("dim")
        lay.addWidget(intro)
        self.user_edit = QLineEdit()
        self.user_edit.setPlaceholderText("admin user name")
        self.pass_edit = QLineEdit()
        self.pass_edit.setPlaceholderText("password")
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.user_edit.returnPressed.connect(self.pass_edit.setFocus)
        self.pass_edit.returnPressed.connect(self._login)
        lay.addWidget(self.user_edit)
        lay.addWidget(self.pass_edit)
        self.login_btn = NeonButton("▶  ADMIN LOGIN", variant="cyan")
        self.login_btn.clicked.connect(self._login)
        lay.addWidget(self.login_btn)
        lay.addStretch(1)
        self.stack.addWidget(w)

    def _build_manage(self) -> None:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 4, 0, 4)
        make = QHBoxLayout()
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("who is this key for? (label)")
        self.label_edit.setMaxLength(60)
        self.count = QSpinBox()
        self.count.setRange(1, 50)
        self.count.setToolTip("How many keys to create")
        self.create_btn = NeonButton("CREATE KEY", "Create new access keys", "cyan")
        self.create_btn.clicked.connect(self._create)
        make.addWidget(self.label_edit, 1)
        make.addWidget(self.count)
        make.addWidget(self.create_btn)
        lay.addLayout(make)

        self.fresh = QTextEdit()                        # newly created keys: shown once, copy them now
        self.fresh.setReadOnly(True)
        self.fresh.setFont(mono_font(13, True))
        self.fresh.setMaximumHeight(92)
        self.fresh.setStyleSheet(f"QTextEdit {{ background:{COLORS['bg_alt']}; color:{COLORS['green']}; border:1px solid {COLORS['green']}; padding:6px; }}")
        self.fresh_note = QLabel("NEW KEYS — shown only once. Copy them now and send them to the players privately.")
        self.fresh_note.setStyleSheet(f"color:{COLORS['amber']}; background:transparent; font-weight:bold;")
        self.copy_btn = NeonButton("COPY")
        self.copy_btn.clicked.connect(self._copy)
        self.fresh_box = QWidget()
        fl = QVBoxLayout(self.fresh_box)
        fl.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        top.addWidget(self.fresh_note, 1)
        top.addWidget(self.copy_btn)
        fl.addLayout(top)
        fl.addWidget(self.fresh)
        self.fresh_box.hide()
        lay.addWidget(self.fresh_box)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "KEY", "STATUS", "PLAYER", "CREATED", "LABEL"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setMinimumHeight(230)
        lay.addWidget(self.table, 1)

        row = QHBoxLayout()
        self.revoke_btn = NeonButton("REVOKE KEY", "Block the selected key for good and log its owner out", "danger")
        self.unbind_btn = NeonButton("FREE KEY", "Detach the selected key from its Discord account (player switched accounts)")
        self.refresh_btn = NeonButton("REFRESH")
        self.logout_btn = NeonButton("LOG OUT")
        self.revoke_btn.clicked.connect(self._revoke)
        self.unbind_btn.clicked.connect(self._unbind)
        self.refresh_btn.clicked.connect(self._load)
        self.logout_btn.clicked.connect(self._logout)
        for b in (self.revoke_btn, self.unbind_btn):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(self.refresh_btn)
        row.addWidget(self.logout_btn)
        lay.addLayout(row)
        self.summary = QLabel("")
        self.summary.setObjectName("dim")
        lay.addWidget(self.summary)
        self.stack.addWidget(w)

    # ------------------------------------------------------------ plumbing --
    def _run(self, fn, on_done=None) -> None:
        job = Job(fn, self)
        job.done.connect(lambda r: on_done(r) if on_done else None)
        job.failed.connect(self._error)
        job.refused.connect(self._error)
        job.finished.connect(lambda j=job: self._jobs.remove(j) if j in self._jobs else None)
        self._jobs.append(job)
        job.start()

    def _error(self, msg: str) -> None:
        self.status.setText(f"⚠ {msg}")
        self.status.setStyleSheet(f"color:{COLORS['amber']};")
        self.login_btn.setEnabled(True)
        if not self.client.admin_logged_in:                # an expired session sends the admin back to the login form
            self._show_state()

    def _info(self, msg: str) -> None:
        self.status.setText(msg)
        self.status.setStyleSheet(f"color:{COLORS['dim']};")

    def _show_state(self) -> None:
        logged = self.client.admin_logged_in
        self.stack.setCurrentIndex(1 if logged else 0)
        if logged:
            self._load()
        else:
            self.user_edit.setFocus()

    # --------------------------------------------------------------- login --
    def _login(self) -> None:
        user, password = self.user_edit.text().strip(), self.pass_edit.text()
        if not user or not password:
            self._error("Enter the admin user name and password.")
            return
        self.login_btn.setEnabled(False)
        self._info("Checking...")
        self._run(lambda: self.client.admin_login(user, password), self._logged_in)

    def _logged_in(self, _result) -> None:
        self.pass_edit.clear()
        self.login_btn.setEnabled(True)
        self._info("Logged in as admin. The session ends after 60 minutes or when you log out.")
        self._show_state()

    def _logout(self) -> None:
        self._run(self.client.admin_logout, lambda _r: self._after_logout())
        self.client._admin_token = ""
        self._after_logout()

    def _after_logout(self) -> None:
        self.fresh_box.hide()
        self.fresh.clear()
        self._info("Logged out.")
        self._show_state()

    # ---------------------------------------------------------------- keys --
    def _load(self) -> None:
        self._run(self.client.admin_keys, self._fill)

    def _fill(self, keys: list[dict]) -> None:
        self.keys = keys
        keep = self._selected_id()
        self.table.setRowCount(len(keys))
        for r, k in enumerate(reversed(keys)):                       # newest first
            created = time.strftime("%Y-%m-%d", time.localtime(k["created_at"])) if k.get("created_at") else "-"
            cells = [str(k["id"]), k["key"], k["status"].upper(), k.get("user") or "-", created, k.get("label") or ""]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if c == 2:
                    from PySide6.QtGui import QColor
                    item.setForeground(QColor(COLORS[STATUS_COLOR.get(k["status"], "dim")]))
                self.table.setItem(r, c, item)
            if keep == k["id"]:
                self.table.selectRow(r)
        by = {s: sum(1 for k in keys if k["status"] == s) for s in ("unused", "in use", "revoked")}
        self.summary.setText(f"{len(keys)} keys  ·  {by['unused']} unused  ·  {by['in use']} in use  ·  {by['revoked']} revoked")

    def _selected_id(self) -> int | None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        return int(self.table.item(rows[0].row(), 0).text()) if rows else None

    def _create(self) -> None:
        label, count = self.label_edit.text().strip(), self.count.value()
        self._info("Creating...")
        self._run(lambda: self.client.admin_create_keys(label, count), self._created)

    def _created(self, made: list[dict]) -> None:
        self.fresh.setPlainText("\n".join(f"{k['key']}   {k['label']}".rstrip() for k in made))
        self.fresh_box.show()
        self.label_edit.clear()
        self._info(f"{len(made)} key(s) created. Copy them now: the full keys cannot be shown again.")
        self._load()

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText("\n".join(line.split()[0] for line in self.fresh.toPlainText().splitlines() if line.strip()))
        self._info("Copied to the clipboard.")

    def _need_selection(self) -> dict | None:
        key_id = self._selected_id()
        key = next((k for k in self.keys if k["id"] == key_id), None)
        if key is None:
            self._error("Select a key in the list first.")
        return key

    def _revoke(self) -> None:
        key = self._need_selection()
        if key is None:
            return
        who = f" It belongs to {key['user']}, who will be logged out at once." if key.get("user") else ""
        if ConfirmDialog("REVOKE KEY", f"Revoke key #{key['id']} ({key['key']})?{who} This cannot be undone.", self, yes="REVOKE").exec():
            self._run(lambda: self.client.admin_revoke(key["id"]), lambda _r: self._done(f"Key #{key['id']} revoked."))

    def _unbind(self) -> None:
        key = self._need_selection()
        if key is None:
            return
        if key["status"] != "in use":
            self._error("Only keys that are in use can be freed.")
            return
        if ConfirmDialog("FREE KEY", f"Detach key #{key['id']} from {key.get('user') or 'its player'}? They are logged out, and anyone can claim the key next.", self, yes="FREE KEY").exec():
            self._run(lambda: self.client.admin_unbind(key["id"]), lambda _r: self._done(f"Key #{key['id']} is free again."))

    def _done(self, message: str) -> None:
        self._info(message)
        self._load()
