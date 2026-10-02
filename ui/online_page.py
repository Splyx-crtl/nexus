"""ONLINE page: Discord login, leaderboards, friends with presence, privacy controls."""
from __future__ import annotations

import time

from PySide6.QtCore import QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QTabWidget,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from nexus import online
from nexus.config import COLORS
from nexus.i18n import tr
from nexus.version import DISCORD_URL

from .dialogs import ConfirmDialog
from .widgets import Chip, NeonButton, play

BOARDS = [("level", "LEVEL"), ("missions", "MISSIONS"), ("credits", "CREDITS"), ("weekly", "WEEKLY XP"), ("perfect", "PERFECT")]
SYNC_SECONDS = 300
PRESENCE_SECONDS = 60


class Job(QThread):
    """Runs one blocking network call off the UI thread."""

    done = Signal(object)
    failed = Signal(str)
    refused = Signal(str)          # the server said no (HTTP 403): a login refusal the player must be told about

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self.fn = fn

    def run(self) -> None:
        try:
            self.done.emit(self.fn())
        except online.OnlineError as exc:
            (self.refused if exc.status == 403 else self.failed).emit(str(exc))
        except Exception as exc:                                    # never let a network problem crash the game
            self.failed.emit(f"Unexpected error: {exc}")


def countdown(seconds: int) -> str:
    d, rest = divmod(max(0, int(seconds)), 86400)
    h, rest = divmod(rest, 3600)
    return f"{d}d {h}h" if d else f"{h}h {rest // 60}m"


class OnlinePage(QWidget):
    friends_summary = Signal(int, str)      # (friends online, tooltip text); -1 = not logged in (hide the bar)

    def __init__(self, engine, settings, parent=None):
        super().__init__(parent)
        self.engine, self.settings = engine, settings
        self.client = online.OnlineClient(settings)
        self.board = "level"
        self._jobs: list[Job] = []
        self._poll_state = ""
        self._poll_left = 0
        self.gated: bool | None = None          # None = not asked yet; the key field is shown unless the server says it is open
        self._last_sync = 0.0
        self._friends_seen: set[str] | None = None
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(14, 10, 14, 10)
        title = QLabel(f"// {tr('online')}")
        title.setObjectName("h1")
        self.lay.addWidget(title)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setObjectName("dim")

        # ---- logged-out view
        self.out_view = QFrame()
        self.out_view.setObjectName("panel")
        ol = QVBoxLayout(self.out_view)
        ol.setContentsMargins(20, 18, 20, 18)
        self.intro = QLabel("")
        self.intro.setWordWrap(True)
        ol.addWidget(self.intro)
        self.key_row = QWidget()
        kl = QVBoxLayout(self.key_row)
        kl.setContentsMargins(0, 0, 0, 0)
        key_title = QLabel("ACCESS KEY")
        key_title.setStyleSheet(f"color:{COLORS['green']}; font-weight:bold; letter-spacing:3px; background:transparent;")
        kl.addWidget(key_title)
        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("NX-XXXXX-XXXXX-XXXXX")
        self.key_edit.setMaxLength(40)
        self.key_edit.setText(self.client.key)
        self.key_edit.returnPressed.connect(self._login)
        kl.addWidget(self.key_edit)
        key_hint = QLabel("This server is invite-only. Join our Discord server, get your access key from the staff and paste it here. "
                          "You have to stay on the Discord server to keep playing online.")
        key_hint.setWordWrap(True)
        key_hint.setObjectName("dim")
        kl.addWidget(key_hint)
        if DISCORD_URL:
            join = NeonButton("OPEN DISCORD SERVER", "Opens our Discord invite in your browser", "cyan")
            join.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(DISCORD_URL)))
            kl.addWidget(join)
        ol.addWidget(self.key_row)
        self.consent = QCheckBox("I agree to share my display name, level, rank, mission count and credits earned with other players (leaderboards, friends).")
        ol.addWidget(self.consent)
        self.login_btn = NeonButton("LOGIN WITH DISCORD", "Opens your browser for a Discord login. NEXUS never sees your password.", "cyan")
        self.login_btn.clicked.connect(self._login)
        ol.addWidget(self.login_btn)
        ol.addStretch(1)
        self.lay.addWidget(self.out_view)

        # ---- logged-in view
        self.in_view = QWidget()
        il = QVBoxLayout(self.in_view)
        il.setContentsMargins(0, 0, 0, 0)
        self.who = QLabel("")
        self.who.setObjectName("h2")
        il.addWidget(self.who)
        self.tabs = QTabWidget()
        il.addWidget(self.tabs, 1)
        self._build_challenge_tab()
        self._build_board_tab()
        self._build_friends_tab()
        self._build_account_tab()
        self.lay.addWidget(self.in_view, 1)
        self.lay.addWidget(self.status)

        self.timer = QTimer(self, interval=PRESENCE_SECONDS * 1000)
        self.timer.timeout.connect(self._heartbeat)
        self.poll_timer = QTimer(self, interval=2000)
        self.poll_timer.timeout.connect(self._poll)
        engine.mission_changed.connect(self._maybe_sync)
        engine.level_up.connect(lambda *_: self._maybe_sync())
        self.refresh()

    # ------------------------------------------------------------ builders --
    def _build_challenge_tab(self) -> None:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.ch_title = QLabel("")
        self.ch_title.setObjectName("h2")
        self.ch_text = QLabel("")
        self.ch_text.setWordWrap(True)
        self.ch_meta = QLabel("")
        self.ch_meta.setObjectName("dim")
        lay.addWidget(self.ch_title)
        lay.addWidget(self.ch_text)
        lay.addWidget(self.ch_meta)
        self.ch_table = QTableWidget(0, 3)
        self.ch_table.setHorizontalHeaderLabels(["#", "OPERATOR", "THIS WEEK"])
        from PySide6.QtWidgets import QHeaderView
        hh = self.ch_table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.ch_table.verticalHeader().hide()
        self.ch_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self.ch_table, 1)
        self.ch_mine = QLabel("")
        self.ch_mine.setObjectName("dim")
        lay.addWidget(self.ch_mine)
        self.tabs.addTab(w, "WEEKLY CHALLENGE")

    def _build_board_tab(self) -> None:
        w = QWidget()
        lay = QVBoxLayout(w)
        chips = QHBoxLayout()
        self.chips: dict[str, Chip] = {}
        for key, label in BOARDS:
            chip = Chip(label)
            chip.clicked.connect(lambda _=False, k=key: self._set_board(k))
            chips.addWidget(chip)
            self.chips[key] = chip
        chips.addStretch(1)
        self.sync_btn = NeonButton("SYNC MY SCORE", "Send your current numbers to the leaderboard", "cyan")
        self.sync_btn.clicked.connect(lambda: self._sync(manual=True))
        chips.addWidget(self.sync_btn)
        lay.addLayout(chips)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["#", "OPERATOR", "RANK", "LEVEL", "VALUE"])
        from PySide6.QtWidgets import QHeaderView
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self.table, 1)
        self.mine = QLabel("")
        self.mine.setObjectName("dim")
        lay.addWidget(self.mine)
        self.tabs.addTab(w, "LEADERBOARD")

    def _build_friends_tab(self) -> None:
        w = QWidget()
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        self.add_edit = QLineEdit()
        self.add_edit.setPlaceholderText("Add a friend by their NEXUS name...")
        self.add_edit.returnPressed.connect(self._add_friend)
        add = NeonButton("ADD FRIEND")
        add.clicked.connect(self._add_friend)
        row.addWidget(self.add_edit, 1)
        row.addWidget(add)
        lay.addLayout(row)
        self.requests = QVBoxLayout()
        lay.addLayout(self.requests)
        self.friend_list = QListWidget()
        lay.addWidget(self.friend_list, 1)
        remove = NeonButton("REMOVE SELECTED", "Remove the selected friend", "danger")
        remove.clicked.connect(self._remove_friend)
        lay.addWidget(remove)
        self.tabs.addTab(w, "FRIENDS")

    def _build_account_tab(self) -> None:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.share_box = QCheckBox("Show me on leaderboards and to friends")
        self.share_box.toggled.connect(self._set_share)
        lay.addWidget(self.share_box)
        note = QLabel("Only these numbers leave your PC: display name, level, rank, XP, missions, credits earned, playtime and a short status line "
                      "(like 'Mission 007'). Never your saves or files. You can delete everything the server stored about you below.")
        note.setWordWrap(True)
        note.setObjectName("dim")
        lay.addWidget(note)
        out = NeonButton("LOG OUT")
        out.clicked.connect(self._logout)
        delete = NeonButton("DELETE MY ONLINE ACCOUNT", "Erases your account, scores and friend links on the server", "danger")
        delete.clicked.connect(self._delete)
        lay.addWidget(out)
        lay.addWidget(delete)
        lay.addStretch(1)
        self.tabs.addTab(w, "ACCOUNT")

    # ----------------------------------------------------------- plumbing --
    def _run(self, fn, on_done=None, on_fail=None, on_refused=None) -> None:
        job = Job(fn, self)
        job.done.connect(lambda r: on_done(r) if on_done else None)
        job.failed.connect(on_fail or self._error)
        job.refused.connect(on_refused or on_fail or self._error)
        job.finished.connect(lambda j=job: self._jobs.remove(j) if j in self._jobs else None)
        self._jobs.append(job)
        job.start()

    def _error(self, msg: str) -> None:
        if msg == "Not logged in." and not self.client.token:
            return                                    # follow-up of a call that already told the player why they were logged out
        self.status.setText(f"⚠ {msg}")
        self.status.setStyleSheet(f"color:{COLORS['amber']};")
        if not self.client.token:
            self.refresh()

    def _info(self, msg: str) -> None:
        self.status.setText(msg)
        self.status.setStyleSheet(f"color:{COLORS['dim']};")

    # ------------------------------------------------------------- refresh --
    def refresh(self) -> None:
        c = self.client
        logged = c.logged_in
        self.out_view.setVisible(not logged)
        self.in_view.setVisible(logged)
        if not logged:
            self.friends_summary.emit(-1, "")
        if not c.configured:
            self.intro.setText("Online services are not available in this build.\n\n"
                               "They add Discord login, leaderboards and a friends list with live status. Everything stays optional — "
                               "the game works fully offline.")
            self.login_btn.setEnabled(False)
            self.consent.setEnabled(False)
        elif not logged:
            self.intro.setText("Log in with Discord to join the leaderboards and add friends. It is optional and uses your Discord display name only.")
            self.login_btn.setEnabled(True)
            self.consent.setEnabled(True)
            self.timer.stop()
            self.key_row.setVisible(self.gated is not False)
            if self.gated is None:
                self._run(self.client.server_info, self._on_info, lambda _m: None)
        else:
            self.timer.start()
            self._load_all()

    def _on_info(self, info: dict) -> None:
        self.gated = bool(info.get("gated"))
        self.key_row.setVisible(not self.client.logged_in and self.gated)

    def _load_all(self) -> None:
        self._run(self.client.me, self._on_me)
        self._load_board()
        self._load_challenge()
        self._load_friends()
        self._heartbeat()

    def _on_me(self, data: dict) -> None:
        self.who.setText(f"● {data['name']}  —  online")
        self.share_box.blockSignals(True)
        self.share_box.setChecked(bool(data["share"]))
        self.share_box.blockSignals(False)
        if not data.get("score"):
            self._sync()

    # --------------------------------------------------------------- login --
    def _login(self, dev_name: str = "") -> None:
        if not self.consent.isChecked():
            self._error("Please tick the consent box first.")
            return
        key = self.key_edit.text().strip()
        if self.gated is not False and not key:
            self._error("Please enter your access key. You get it from the staff on our Discord server.")
            return
        self.settings.set("online_enabled", True)
        import os
        state, url = self.client.new_login(os.environ.get("NEXUS_DEV_NAME", ""))
        self.login_btn.setEnabled(False)
        self._info("Checking your access key...")
        self._run(lambda: self.client.begin_login(state, key), lambda _r: self._begun(state, url), self._login_failed, self._login_failed)

    def _begun(self, state: str, url: str) -> None:
        self._poll_state, self._poll_left = state, 90
        QDesktopServices.openUrl(QUrl(url))
        self._info("Waiting for the Discord login in your browser...")
        self.poll_timer.start()

    def _login_failed(self, msg: str) -> None:
        self.poll_timer.stop()
        self.login_btn.setEnabled(True)
        self._error(msg)

    def _poll(self) -> None:
        self._poll_left -= 1
        if self._poll_left <= 0:
            self.poll_timer.stop()
            self.login_btn.setEnabled(True)
            self._error("Login timed out.")
            return
        self._run(lambda: self.client.poll_login(self._poll_state), self._poll_done, lambda m: None, self._login_failed)

    def _poll_done(self, ok: bool) -> None:
        if ok:
            self.poll_timer.stop()
            self.login_btn.setEnabled(True)
            self._info("Logged in.")
            self.refresh()

    def _logout(self) -> None:
        self._run(self.client.logout, lambda _r: self.refresh())
        self.settings.set("online_token", "")
        self.settings.set("online_enabled", False)
        self.refresh()

    def _delete(self) -> None:
        if ConfirmDialog("DELETE ACCOUNT", "Delete your online account, scores and friend links from the server? This cannot be undone.", self).exec():
            def done(_r):
                self.settings.set("online_enabled", False)
                self.refresh()
            self._run(self.client.delete_account, done)

    def _set_share(self, value: bool) -> None:
        self._run(lambda: self.client.set_share(value), lambda _r: self._info("Privacy setting saved."))

    # ----------------------------------------------------------------- sync --
    def _maybe_sync(self) -> None:
        if self.client.logged_in and time.time() - self._last_sync > 20:
            self._sync()

    def _sync(self, manual: bool = False) -> None:
        if not self.client.logged_in:
            return
        self._last_sync = time.time()
        snap = online.snapshot(self.engine)
        self._run(lambda: self.client.submit_scores(snap), lambda _r: (self._info("Score synced."), self._load_board()) if manual else None,
                  self._error if manual else (lambda m: None))

    def _heartbeat(self) -> None:
        if self.client.logged_in:
            text = online.presence_text(self.engine)
            self._run(lambda: self.client.presence(text), None, lambda m: None)
            self._load_friends()
            if time.time() - self._last_sync > SYNC_SECONDS:
                self._sync()

    # ---------------------------------------------------------- leaderboard --
    def _set_board(self, key: str) -> None:
        self.board = key
        self._load_board()

    def _load_board(self) -> None:
        for k, chip in self.chips.items():
            chip.setChecked(k == self.board)
        self._run(lambda: self.client.leaderboard(self.board), self._fill_board)

    def _fill_board(self, data: dict) -> None:
        rows = data["entries"]
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            value = f"${r['value']:,}" if self.board == "credits" else f"{r['value']:,}"
            for col, text in enumerate([str(r["position"]), r["name"], r["rank"], str(r["level"]), value]):
                item = QTableWidgetItem(text)
                if r["me"]:
                    item.setForeground(QColor(COLORS["green"]))
                self.table.setItem(i, col, item)
        me = data.get("me")
        self.mine.setText(f"You are #{me['position']} of {data['total']}." if me else f"{data['total']} operators ranked. Sync your score to appear.")

    # ------------------------------------------------------------ challenge --
    def _load_challenge(self) -> None:
        self._run(self.client.challenge, self._fill_challenge, lambda m: None)

    def _fill_challenge(self, data: dict) -> None:
        self.ch_title.setText(f"{data['title']}  ·  {data['week']}")
        self.ch_text.setText(data["text"])
        self.ch_meta.setText(f"Ends in {countdown(data['ends_in'])}  ·  {data['players']} operators competing  ·  "
                             f"community total this week: {data['community_total']:,}")
        rows = data["entries"]
        self.ch_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for col, text in enumerate([str(r["position"]), r["name"], f"{r['value']:,}"]):
                item = QTableWidgetItem(text)
                if r["me"]:
                    item.setForeground(QColor(COLORS["green"]))
                self.ch_table.setItem(i, col, item)
        me = data.get("me")
        self.ch_mine.setText(f"You are #{me['position']} with {me['value']:,}." if me else
                             "Sync your score (LEADERBOARD tab) to join this week's challenge. The winners are announced on our Discord.")

    # -------------------------------------------------------------- friends --
    def _load_friends(self) -> None:
        self._run(self.client.friends, self._fill_friends, lambda m: None)

    def _fill_friends(self, data: dict) -> None:
        if not self.client.logged_in:                        # an answer that arrives after logging out
            return
        while self.requests.count():
            w = self.requests.takeAt(0).widget()
            if w:
                w.deleteLater()
        for req in data["incoming"]:
            row = QFrame()
            row.setObjectName("card")
            hl = QHBoxLayout(row)
            hl.addWidget(QLabel(f"{req['name']} wants to be your friend"), 1)
            yes, no = NeonButton("ACCEPT"), NeonButton("DECLINE", variant="danger")
            yes.clicked.connect(lambda _=False, n=req["name"]: self._respond(n, True))
            no.clicked.connect(lambda _=False, n=req["name"]: self._respond(n, False))
            hl.addWidget(yes)
            hl.addWidget(no)
            self.requests.addWidget(row)
        self.friend_list.clear()
        for f in data["friends"]:
            dot = "●" if f["online"] else "○"
            text = f"{dot}  {f['name']}   LV {f['level'] or '?'}  {f['rank']}" + (f"   —   {f['status']}" if f["status"] else "")
            item = QListWidgetItem(text)
            item.setData(256, f["name"])
            item.setForeground(QColor(COLORS["green"] if f["online"] else COLORS["dim"]))
            self.friend_list.addItem(item)
        if data["outgoing"]:
            self.friend_list.addItem(QListWidgetItem("pending: " + ", ".join(o["name"] for o in data["outgoing"])))
        if not data["friends"] and not data["outgoing"]:
            self.friend_list.addItem(QListWidgetItem("No friends yet. Ask them for their NEXUS name!"))
        online_now = [f for f in data["friends"] if f["online"]]
        names = {f["name"] for f in online_now}
        if self._friends_seen is not None and names - self._friends_seen:
            play("friend")                                   # somebody just came online
        self._friends_seen = names
        tip = "\n".join(f"● {f['name']}  LV {f['level'] or '?'}" + (f"  —  {f['status']}" if f["status"] else "") for f in online_now)
        self.friends_summary.emit(len(online_now), tip or "None of your friends is online right now.")

    def _add_friend(self) -> None:
        name = self.add_edit.text().strip()
        if name:
            self.add_edit.clear()
            self._run(lambda: self.client.friend_request(name), lambda r: (self._info(f"Request {r['status']}."), self._load_friends()))

    def _respond(self, name: str, accept: bool) -> None:
        self._run(lambda: self.client.friend_respond(name, accept), lambda _r: self._load_friends())

    def _remove_friend(self) -> None:
        item = self.friend_list.currentItem()
        name = item.data(256) if item else None
        if name:
            self._run(lambda: self.client.friend_remove(name), lambda _r: self._load_friends())

    def stop(self) -> None:
        self.timer.stop()
        self.poll_timer.stop()
