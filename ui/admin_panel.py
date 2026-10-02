"""ADMIN panel: player database, player editing, access-key management and an activity log.

Log in with the credentials set on the server (the game contains none). Every permission is checked by the server on every request;
this window only shows what the server returns. The admin session lives in memory only."""
from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QSpinBox, QStackedWidget, QTableWidget, QTableWidgetItem, QTabWidget, QTextBrowser, QTextEdit, QVBoxLayout, QWidget)

from nexus.config import COLORS

from .dialogs import ConfirmDialog, NeonDialog
from .online_page import Job
from .widgets import NeonButton, mono_font

KEY_LABEL = {"unused": "UNUSED", "in use": "ACTIVE", "revoked": "DEACTIVATED", "expired": "EXPIRED"}
KEY_COLOR = {"unused": "cyan", "in use": "green", "revoked": "red", "expired": "amber"}
ACCOUNT_LABEL = {"active": "ACTIVE", "disabled": "DEACTIVATED", "banned": "BANNED"}
ACCOUNT_COLOR = {"active": "green", "disabled": "amber", "banned": "red"}
RESET_LABEL = {"missions": "Mission progress", "inventory": "Inventory and upgrades", "heat": "Trace alert"}
PLAYER_SORTS = [("registered", "REGISTERED"), ("last login", "LAST LOGIN"), ("name", "NAME"), ("level", "LEVEL"), ("xp", "XP"),
                ("earned", "CREDITS EARNED"), ("playtime", "PLAYTIME")]
PLAYER_FILTERS = [("", "ALL PLAYERS"), ("active", "ACTIVE"), ("online", "ONLINE NOW"), ("disabled", "DEACTIVATED"), ("banned", "BANNED"), ("no key", "WITHOUT KEY")]
KEY_FILTERS = [("", "ALL KEYS"), ("unused", "UNUSED"), ("in use", "ACTIVE"), ("revoked", "DEACTIVATED"), ("expired", "EXPIRED")]
PER_PAGE = 20


def stamp(value, with_time: bool = False) -> str:
    if not value:
        return "—"
    return time.strftime("%Y-%m-%d %H:%M" if with_time else "%Y-%m-%d", time.localtime(value))


def ago(value) -> str:
    if not value:
        return "never"
    seconds = max(0, int(time.time() - value))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        return f"{seconds // 3600} h ago"
    return f"{seconds // 86400} d ago"


def money(value) -> str:
    return "—" if value is None else f"${int(value):,}"


# ------------------------------------------------------------------ helpers --
class Notice(QLabel):
    """One-line status area: green for success, red for errors, dim for information."""

    def __init__(self, parent=None):
        super().__init__("", parent)
        self.setWordWrap(True)
        self.setMinimumHeight(24)
        self._style("dim")

    def _style(self, kind: str) -> None:
        color = {"ok": COLORS["green"], "error": COLORS["red"], "dim": COLORS["dim"]}[kind]
        bar = f"border-left: 3px solid {color}; padding-left: 8px;" if kind != "dim" else "padding-left: 11px;"
        self.setStyleSheet(f"color:{color}; background:transparent; {bar}")

    def ok(self, text: str) -> None:
        self.setText("✔  " + text)
        self._style("ok")

    def error(self, text: str) -> None:
        self.setText("✖  " + text)
        self._style("error")

    def info(self, text: str) -> None:
        self.setText(text)
        self._style("dim")


class JobMixin:
    """Runs blocking network calls off the UI thread and routes failures to ``self.notice``."""

    def _init_jobs(self) -> None:
        self._jobs: list[Job] = []

    def _run(self, fn, on_done=None, on_fail=None) -> None:
        job = Job(fn, self)
        job.done.connect(lambda r: on_done(r) if on_done else None)
        failed = on_fail or self._failed
        job.failed.connect(failed)
        job.refused.connect(failed)
        job.finished.connect(lambda j=job: self._jobs.remove(j) if j in self._jobs else None)
        self._jobs.append(job)
        job.start()

    def _failed(self, message: str) -> None:
        self.notice.error(message)


def make_table(headers: list[str], stretch: int | None = None, height: int = 300) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    hh = table.horizontalHeader()
    hh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    if stretch is not None:
        hh.setSectionResizeMode(stretch, QHeaderView.ResizeMode.Stretch)
    table.verticalHeader().hide()
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setAlternatingRowColors(False)
    table.setMinimumHeight(height)
    return table


def set_row(table: QTableWidget, row: int, cells: list[str], colors: dict[int, str] | None = None) -> None:
    for col, text in enumerate(cells):
        item = QTableWidgetItem(text)
        if colors and col in colors:
            item.setForeground(QColor(COLORS[colors[col]]))
        table.setItem(row, col, item)


class Pager(QWidget):
    changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.page, self.pages = 1, 1
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.prev = NeonButton("◀  PREV")
        self.next = NeonButton("NEXT  ▶")
        self.label = QLabel("")
        self.label.setObjectName("dim")
        self.prev.clicked.connect(lambda: self._go(self.page - 1))
        self.next.clicked.connect(lambda: self._go(self.page + 1))
        row.addWidget(self.prev)
        row.addWidget(self.label, 1, Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self.next)
        self.set(1, 1, 0)

    def _go(self, page: int) -> None:
        if 1 <= page <= self.pages and page != self.page:
            self.changed.emit(page)

    def set(self, page: int, pages: int, total: int) -> None:
        self.page, self.pages = page, pages
        self.label.setText(f"page {page} of {pages}  ·  {total:,} total")
        self.prev.setEnabled(page > 1)
        self.next.setEnabled(page < pages)


class TypeToConfirm(NeonDialog):
    """For the dangerous actions: the admin has to type the player's name before the button works."""

    def __init__(self, title: str, text: str, expected: str, parent=None, yes: str = "CONFIRM"):
        super().__init__(title, parent, 520)
        self.expected = expected.strip().lower()
        label = QLabel(text)
        label.setWordWrap(True)
        self.lay.addWidget(label)
        self.lay.addWidget(QLabel(f"Type  {expected}  to confirm:"))
        self.edit = QLineEdit()
        self.edit.textChanged.connect(self._check)
        self.lay.addWidget(self.edit)
        row = QHBoxLayout()
        cancel, self.yes = NeonButton("CANCEL"), NeonButton(yes, variant="danger")
        cancel.clicked.connect(self.reject)
        self.yes.clicked.connect(self.accept)
        self.yes.setEnabled(False)
        row.addWidget(cancel)
        row.addStretch(1)
        row.addWidget(self.yes)
        self.lay.addLayout(row)

    def _check(self, text: str) -> None:
        self.yes.setEnabled(text.strip().lower() == self.expected)


class NumberPrompt(NeonDialog):
    def __init__(self, title: str, text: str, parent=None, value: int = 30, high: int = 3650, yes: str = "SET"):
        super().__init__(title, parent, 420)
        label = QLabel(text)
        label.setWordWrap(True)
        self.lay.addWidget(label)
        self.spin = QSpinBox()
        self.spin.setRange(0, high)
        self.spin.setValue(value)
        self.spin.setSpecialValueText("never")
        self.lay.addWidget(self.spin)
        row = QHBoxLayout()
        cancel, ok = NeonButton("CANCEL"), NeonButton(yes, variant="cyan")
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addStretch(1)
        row.addWidget(ok)
        self.lay.addLayout(row)


def section(title: str) -> QLabel:
    label = QLabel(title)
    label.setStyleSheet(f"color:{COLORS['cyan']}; font-weight:bold; letter-spacing:3px; background:transparent; padding-top:6px;")
    return label


def fact(grid: QGridLayout, row: int, col: int, name: str, value: str, color: str = "text") -> QLabel:
    key = QLabel(name)
    key.setStyleSheet(f"color:{COLORS['dim']}; background:transparent; font-size:11px; letter-spacing:2px;")
    val = QLabel(value)
    val.setStyleSheet(f"color:{COLORS[color]}; background:transparent; font-weight:bold;")
    val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    grid.addWidget(key, row * 2, col)
    grid.addWidget(val, row * 2 + 1, col)
    return val


# ------------------------------------------------------------- player detail --
class PlayerDialog(JobMixin, NeonDialog):
    """Everything about one player, plus the edit and account controls. Every action is confirmed and answered with a clear message."""

    changed = Signal()

    def __init__(self, client, user_id: int, parent=None):
        super().__init__("PLAYER", parent, 960)
        self._init_jobs()
        self.client, self.user_id = client, user_id
        self.data: dict = {}
        self._tab_index = 0                          # the same tab stays open when the data is reloaded after a change
        self.setMinimumHeight(700)
        self.body = QVBoxLayout()
        self.lay.addLayout(self.body, 1)
        self.notice = Notice()
        self.lay.addWidget(self.notice)
        row = QHBoxLayout()
        self.refresh_btn = NeonButton("REFRESH")
        self.refresh_btn.clicked.connect(self.load)
        close = NeonButton("CLOSE")
        close.clicked.connect(self.accept)
        row.addWidget(self.refresh_btn)
        row.addStretch(1)
        row.addWidget(close)
        self.lay.addLayout(row)
        self.notice.info("Loading player...")
        self.load()

    # ------------------------------------------------------------- loading --
    def load(self) -> None:
        self._run(lambda: self.client.admin_player(self.user_id), self._fill)

    def _clear(self) -> None:
        while self.body.count():
            item = self.body.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._drop(item.layout())

    def _drop(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._drop(item.layout())

    def _fill(self, d: dict) -> None:
        self.data = d
        self._clear()
        status = d["account_status"]
        head = QHBoxLayout()
        name = QLabel(d["name"])
        name.setObjectName("h2")
        badge = QLabel(f"  {ACCOUNT_LABEL[status]}  ")
        badge.setStyleSheet(f"color:{COLORS['bg']}; background:{COLORS[ACCOUNT_COLOR[status]]}; font-weight:bold; letter-spacing:2px;")
        online = QLabel("● ONLINE" + (f"  ·  {d['presence']}" if d.get("presence") else "") if d["online"] else f"○ last seen {ago(d['last_seen'])}")
        online.setStyleSheet(f"color:{COLORS['green' if d['online'] else 'dim']}; background:transparent;")
        head.addWidget(name)
        head.addWidget(badge)
        head.addStretch(1)
        head.addWidget(online)
        self.body.addLayout(head)
        if d["status_reason"]:
            reason = QLabel(f"Reason: {d['status_reason']}")
            reason.setStyleSheet(f"color:{COLORS['amber']}; background:transparent;")
            self.body.addWidget(reason)

        tabs = QTabWidget()
        tabs.addTab(self._overview_tab(d), "OVERVIEW")
        tabs.addTab(self._edit_tab(d), "EDIT PLAYER")
        tabs.addTab(self._account_tab(d), "ACCOUNT")
        self.tabs = tabs
        tabs.setCurrentIndex(self._tab_index)
        tabs.currentChanged.connect(lambda i: setattr(self, "_tab_index", i))
        self.body.addWidget(tabs, 1)
        if self.notice.text().startswith("Loading"):
            self.notice.info("Loaded.")

    # ------------------------------------------------------------ overview --
    def _overview_tab(self, d: dict) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        grid = QGridLayout()
        grid.setHorizontalSpacing(28)
        key = d["key"]
        fact(grid, 0, 0, "ACCOUNT ID", str(d["id"]))
        fact(grid, 0, 1, "DISCORD ID", d["discord_id"])
        fact(grid, 0, 2, "GAME KEY", f"{key['key']}  ({KEY_LABEL[key['status']]})" if key else "none", "text" if key else "red")
        fact(grid, 0, 3, "KEY LABEL", (key or {}).get("label") or "—")
        fact(grid, 1, 0, "REGISTERED", stamp(d["registered"], True))
        fact(grid, 1, 1, "LAST LOGIN", stamp(d["last_login"], True))
        fact(grid, 1, 2, "LOGINS", str(d["login_count"]))
        fact(grid, 1, 3, "LAST SYNC", stamp(d["synced_at"], True))
        fact(grid, 2, 0, "LEVEL", f"{d['level']}  ·  {d['rank']}" if d["level"] else "no save synced yet", "green")
        fact(grid, 2, 1, "TOTAL XP", f"{d['xp_total']:,}" if d["xp_total"] is not None else "—", "green")
        fact(grid, 2, 2, "CREDITS", money(d["credits"]), "amber")
        fact(grid, 2, 3, "CREDITS EARNED", money(d["credits_earned"]))
        fact(grid, 3, 0, "MISSIONS", str(d["missions"]) if d["missions"] is not None else "—")
        fact(grid, 3, 1, "FLAWLESS", str(d["perfect"]) if d["perfect"] is not None else "—")
        fact(grid, 3, 2, "REPUTATION", str(d["reputation"]) if d["reputation"] is not None else "—")
        fact(grid, 3, 3, "NEW GAME+", str(d["ng_plus"]) if d["ng_plus"] is not None else "—")
        hours = f"{d['playtime'] / 3600:.1f} h" if d["playtime"] is not None else "—"
        fact(grid, 4, 0, "PLAYTIME", hours)
        fact(grid, 4, 1, "TRACE ALERT", f"{d['heat']}%" if d["heat"] is not None else "—")
        fact(grid, 4, 2, "FRIENDS", str(d["friends"]))
        fact(grid, 4, 3, "VISIBILITY", "public" if d["share"] else "hidden")
        lay.addLayout(grid)
        if d["pending_edits"]:
            pend = QLabel(f"⏳ {len(d['pending_edits'])} change(s) are waiting for the player's game to apply them at its next sync.")
            pend.setStyleSheet(f"color:{COLORS['amber']}; background:transparent;")
            lay.addWidget(pend)
        lay.addWidget(section("UNLOCKED CONTENT"))
        info = QTextBrowser()
        info.setMaximumHeight(170)
        ach, unl = d["achievements"], d["unlocks"]
        stats = d["stats"]
        parts = [f"<p><b style='color:{COLORS['green']}'>{len(ach)}</b> achievements: " + (", ".join(ach) or "none") + "</p>",
                 f"<p><b style='color:{COLORS['green']}'>{len(unl)}</b> unlocks: " + (", ".join(unl) or "none") + "</p>"]
        if stats:
            shown = sorted(stats.items(), key=lambda kv: -kv[1])[:24]
            parts.append("<p><b>Statistics:</b> " + " · ".join(f"{k.replace('_', ' ')} {v:,}" for k, v in shown) + "</p>")
        info.setHtml("".join(parts))
        lay.addWidget(info)
        lay.addWidget(section("RECENT ADMIN ACTIVITY"))
        log = QTextBrowser()
        log.setMaximumHeight(110)
        log.setHtml("".join(f"<div><span style='color:{COLORS['dim']}'>{stamp(a['ts'], True)}</span> <b>{a['action']}</b> {a['detail']}</div>"
                            for a in d["audit"]) or "<span style='color:#888'>Nothing yet.</span>")
        lay.addWidget(log)
        return w

    # ---------------------------------------------------------------- edit --
    def _edit_tab(self, d: dict) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        if d["level"] is None:
            note = QLabel("This player has not synced a save yet, so there is nothing to edit. They appear here with their numbers after their first sync.")
            note.setWordWrap(True)
            note.setStyleSheet(f"color:{COLORS['amber']}; background:transparent;")
            lay.addWidget(note)
            lay.addStretch(1)
            return w
        intro = QLabel("Changes are saved in the database right away and applied to the player's own save the next time their game syncs "
                       "(the player gets a notification). Fill in only what you want to change.")
        intro.setWordWrap(True)
        intro.setObjectName("dim")
        lay.addWidget(intro)
        grid = QGridLayout()
        self.level = QSpinBox()
        self.level.setRange(1, 100)
        self.level.setValue(d["level"])
        self.xp = QSpinBox()
        self.xp.setRange(0, 100 + 40 * d["level"] - 1)
        cumulative = sum(100 + 40 * lv for lv in range(1, d["level"]))
        self.xp.setValue(max(0, min(self.xp.maximum(), (d["xp_total"] or 0) - cumulative)))
        self.level.valueChanged.connect(lambda lv: (self.xp.setMaximum(100 + 40 * lv - 1), self.xp.setValue(0)) if lv != d["level"] else None)
        self.credits = QSpinBox()
        self.credits.setRange(0, 1_000_000_000)
        self.credits.setSingleStep(100)
        self.credits.setValue(d["credits"] or 0)
        self.credits.setEnabled(d["credits"] is not None)
        self.rep = QSpinBox()
        self.rep.setRange(0, 100)
        self.rep.setValue(d["reputation"] or 0)
        self.rep.setEnabled(d["reputation"] is not None)
        self._orig = {"level": d["level"], "xp": self.xp.value(), "credits": d["credits"], "reputation": d["reputation"]}
        for col, (name, widget) in enumerate((("LEVEL", self.level), ("XP IN THIS LEVEL", self.xp), ("CREDITS", self.credits), ("REPUTATION", self.rep))):
            label = QLabel(name)
            label.setStyleSheet(f"color:{COLORS['dim']}; background:transparent; font-size:11px; letter-spacing:2px;")
            grid.addWidget(label, 0, col)
            grid.addWidget(widget, 1, col)
        lay.addLayout(grid)
        lay.addWidget(section("RESET PROGRESS"))
        self.resets: dict[str, QCheckBox] = {}
        reset_row = QHBoxLayout()
        for key, label in RESET_LABEL.items():
            box = QCheckBox(label)
            self.resets[key] = box
            reset_row.addWidget(box)
        reset_row.addStretch(1)
        lay.addLayout(reset_row)
        self.reason = QLineEdit()
        self.reason.setPlaceholderText("reason (optional, written to the activity log)")
        self.reason.setMaxLength(200)
        lay.addWidget(self.reason)
        row = QHBoxLayout()
        revert = NeonButton("RESET FORM")
        revert.clicked.connect(lambda: self._fill(self.data))
        self.apply_btn = NeonButton("APPLY CHANGES", "Review and save the changes", "cyan")
        self.apply_btn.clicked.connect(self._apply)
        row.addWidget(revert)
        row.addStretch(1)
        row.addWidget(self.apply_btn)
        lay.addLayout(row)
        lay.addStretch(1)
        return w

    def _changes(self) -> tuple[dict, list[str]]:
        o = self._orig
        changes: dict = {}
        lines: list[str] = []
        if self.level.value() != o["level"]:
            changes["level"], changes["xp"] = self.level.value(), self.xp.value()
            lines.append(f"Level  {o['level']}  →  {self.level.value()}   (XP in that level: {self.xp.value():,})")
        elif self.xp.value() != o["xp"]:
            changes["xp"] = self.xp.value()
            lines.append(f"XP in level  {o['xp']:,}  →  {self.xp.value():,}")
        if self.credits.isEnabled() and self.credits.value() != o["credits"]:
            changes["credits"] = self.credits.value()
            lines.append(f"Credits  {money(o['credits'])}  →  {money(self.credits.value())}")
        if self.rep.isEnabled() and self.rep.value() != o["reputation"]:
            changes["reputation"] = self.rep.value()
            lines.append(f"Reputation  {o['reputation']}  →  {self.rep.value()}")
        resets = [k for k, box in self.resets.items() if box.isChecked()]
        if resets:
            changes["reset"] = resets
            lines += [f"RESET: {RESET_LABEL[k]}" for k in resets]
        return changes, lines

    def _apply(self) -> None:
        changes, lines = self._changes()
        if not changes:
            self.notice.error("Nothing to change: all values are the same as before.")
            return
        name = self.data["name"]
        text = f"Apply these changes to {name}?\n\n" + "\n".join("•  " + line for line in lines) + \
               "\n\nThey are saved now and applied to the player's save at their next sync."
        if "reset" in changes or changes.get("level", 99) < self.data["level"]:
            dialog = TypeToConfirm("CONFIRM CHANGE", text + "\n\nThis removes progress and cannot be undone.", name, self, "APPLY")
        else:
            dialog = ConfirmDialog("CONFIRM CHANGE", text, self, yes="APPLY")
        if not dialog.exec():
            self.notice.info("Cancelled. Nothing was changed.")
            return
        reason = self.reason.text().strip()
        self.apply_btn.setEnabled(False)
        self._run(lambda: self.client.admin_edit_player(self.user_id, changes, reason), self._saved, self._save_failed)

    def _saved(self, _result) -> None:
        self.notice.ok(f"Player {self.data['name']} updated successfully. The change is stored and reaches the player at their next sync.")
        self.changed.emit()
        self.load()

    def _save_failed(self, message: str) -> None:
        self.apply_btn.setEnabled(True)
        self.notice.error(f"The change could not be saved: {message}")

    # ------------------------------------------------------------- account --
    def _account_tab(self, d: dict) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        status = d["account_status"]
        text = {"active": "This account is active.", "disabled": "This account is deactivated: the player is logged out and cannot log in.",
                "banned": "This account is banned: the player is logged out and cannot log in."}[status]
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"color:{COLORS[ACCOUNT_COLOR[status]]}; background:transparent; font-weight:bold;")
        lay.addWidget(label)
        self.status_reason = QLineEdit()
        self.status_reason.setPlaceholderText("reason (shown to the player when they try to log in)")
        self.status_reason.setMaxLength(200)
        lay.addWidget(self.status_reason)
        row = QHBoxLayout()
        self.status_buttons: dict[str, NeonButton] = {}
        options = {"active": [("disabled", "DEACTIVATE", ""), ("banned", "BAN", "danger")],
                   "disabled": [("active", "ACTIVATE", "cyan"), ("banned", "BAN", "danger")],
                   "banned": [("active", "UNBAN", "cyan"), ("disabled", "DEACTIVATE", "")]}[status]
        for target, caption, variant in options:
            button = NeonButton(caption, variant=variant)
            button.clicked.connect(lambda _=False, t=target, c=caption: self._set_status(t, c))
            self.status_buttons[target] = button
            row.addWidget(button)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)
        return w

    def _set_status(self, target: str, caption: str) -> None:
        name = self.data["name"]
        reason = self.status_reason.text().strip() if target != "active" else ""
        what = {"disabled": "deactivate", "banned": "ban", "active": "reactivate"}[target]
        text = f"{caption} {name}?" + (" They are logged out at once and cannot log in again." if target != "active" else " They can log in again.")
        dialog = TypeToConfirm("CONFIRM", text, name, self, caption) if target == "banned" else ConfirmDialog("CONFIRM", text, self, yes=caption)
        if not dialog.exec():
            self.notice.info("Cancelled. The account was not changed.")
            return
        self._run(lambda: self.client.admin_set_status(self.user_id, target, reason),
                  lambda _r: (self.notice.ok(f"Account {name}: {what} done."), self.changed.emit(), self.load()),
                  lambda m: self.notice.error(f"The account could not be changed: {m}"))


# -------------------------------------------------------------------- panel --
class AdminPanel(JobMixin, NeonDialog):
    def __init__(self, client, parent=None):
        super().__init__("ADMIN PANEL", parent, 1100)
        self._init_jobs()
        self.client = client
        self.keys: list[dict] = []
        self.players: list[dict] = []
        self.setMinimumHeight(720)
        self.stack = QStackedWidget()
        self.lay.addWidget(self.stack, 1)
        self.notice = Notice()
        self.lay.addWidget(self.notice)
        self._build_login()
        self._build_manage()
        row = QHBoxLayout()
        self.logout_btn = NeonButton("LOG OUT")
        self.logout_btn.clicked.connect(self._logout)
        close = NeonButton("CLOSE")
        close.clicked.connect(self.accept)
        row.addWidget(self.logout_btn)
        row.addStretch(1)
        row.addWidget(close)
        self.lay.addLayout(row)
        self._search_timer = QTimer(self, singleShot=True, interval=350)
        self._search_timer.timeout.connect(lambda: self._load_players(1))
        self._key_timer = QTimer(self, singleShot=True, interval=350)
        self._key_timer.timeout.connect(lambda: self._load_keys(1))
        self._show_state()

    def _failed(self, message: str) -> None:
        self.notice.error(message)
        self.login_btn.setEnabled(True)
        if not self.client.admin_logged_in:                 # an expired session sends the admin back to the login form
            self._show_state()

    # -------------------------------------------------------------- login --
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

    def _show_state(self) -> None:
        logged = self.client.admin_logged_in
        self.stack.setCurrentIndex(1 if logged else 0)
        self.logout_btn.setVisible(logged)
        if logged:
            self._load_players(1)
            self._load_keys(1)
        else:
            self.user_edit.setFocus()

    def _login(self) -> None:
        user, password = self.user_edit.text().strip(), self.pass_edit.text()
        if not user or not password:
            self.notice.error("Enter the admin user name and password.")
            return
        self.login_btn.setEnabled(False)
        self.notice.info("Checking...")
        self._run(lambda: self.client.admin_login(user, password), self._logged_in)

    def _logged_in(self, _result) -> None:
        self.pass_edit.clear()
        self.login_btn.setEnabled(True)
        self.notice.ok("Logged in as administrator. The session ends after 60 minutes or when you log out.")
        self._show_state()

    def _logout(self) -> None:
        self._run(self.client.admin_logout)
        self.client._admin_token = ""
        self.fresh_box.hide()
        self.fresh.clear()
        self.notice.info("Logged out.")
        self._show_state()

    # ------------------------------------------------------------- manage --
    def _build_manage(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.addTab(self._players_tab(), "PLAYERS")
        self.tabs.addTab(self._keys_tab(), "GAME KEYS")
        self.tabs.addTab(self._activity_tab(), "ACTIVITY")
        self.tabs.currentChanged.connect(lambda i: self._load_activity() if i == 2 else None)
        self.stack.addWidget(self.tabs)

    # ------------------------------------------------------------ players --
    def _players_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        bar = QHBoxLayout()
        self.p_search = QLineEdit()
        self.p_search.setPlaceholderText("search by player name or account ID...")
        self.p_search.textChanged.connect(lambda _t: self._search_timer.start())
        self.p_filter = QComboBox()
        for value, caption in PLAYER_FILTERS:
            self.p_filter.addItem(caption, value)
        self.p_sort = QComboBox()
        for value, caption in PLAYER_SORTS:
            self.p_sort.addItem("SORT: " + caption, value)
        self.p_dir = QComboBox()
        self.p_dir.addItem("NEWEST / HIGHEST FIRST", "desc")
        self.p_dir.addItem("OLDEST / LOWEST FIRST", "asc")
        for combo in (self.p_filter, self.p_sort, self.p_dir):
            combo.currentIndexChanged.connect(lambda _i: self._load_players(1))
        bar.addWidget(self.p_search, 1)
        bar.addWidget(self.p_filter)
        bar.addWidget(self.p_sort)
        bar.addWidget(self.p_dir)
        lay.addLayout(bar)
        self.p_summary = QLabel("")
        self.p_summary.setObjectName("dim")
        lay.addWidget(self.p_summary)
        self.p_table = make_table(["ID", "PLAYER", "STATUS", "LEVEL", "XP", "CREDITS", "KEY", "REGISTERED", "LAST LOGIN"], 1, 330)
        self.p_table.doubleClicked.connect(lambda _i: self._open_player())
        lay.addWidget(self.p_table, 1)
        self.p_pager = Pager()
        self.p_pager.changed.connect(self._load_players)
        lay.addWidget(self.p_pager)
        row = QHBoxLayout()
        self.p_view = NeonButton("VIEW / EDIT PLAYER", "Open the detail view of the selected player", "cyan")
        self.p_view.clicked.connect(self._open_player)
        refresh = NeonButton("REFRESH")
        refresh.clicked.connect(lambda: self._load_players(self.p_pager.page))
        row.addWidget(self.p_view)
        row.addStretch(1)
        row.addWidget(refresh)
        lay.addLayout(row)
        return w

    def _load_players(self, page: int = 1) -> None:
        if not self.client.admin_logged_in:
            return
        search, status = self.p_search.text().strip(), self.p_filter.currentData()
        sort, direction = self.p_sort.currentData(), self.p_dir.currentData()
        self._run(lambda: self.client.admin_players(search, status, sort, direction, page, PER_PAGE), self._fill_players)

    def _fill_players(self, data: dict) -> None:
        self.players = data["players"]
        keep = self._selected_player_id()
        self.p_table.setRowCount(len(self.players))
        for r, p in enumerate(self.players):
            key = p["key"]
            cells = [str(p["id"]), ("● " if p["online"] else "") + p["name"], ACCOUNT_LABEL[p["account_status"]],
                     str(p["level"]) if p["level"] else "—", f"{p['xp_total']:,}" if p["xp_total"] is not None else "—", money(p["credits"]),
                     key["key"][-9:] if key else "no key", stamp(p["registered"]), ago(p["last_login"])]
            set_row(self.p_table, r, cells, {2: ACCOUNT_COLOR[p["account_status"]], 1: "green" if p["online"] else "text"})
            if keep == p["id"]:
                self.p_table.selectRow(r)
        c = data["counts"]
        self.p_summary.setText(f"{c['all']:,} players  ·  {c['online']} online  ·  {c['disabled']} deactivated  ·  {c['banned']} banned  ·  "
                               f"{c['no key']} without a key")
        self.p_pager.set(data["page"], data["pages"], data["total"])
        if not self.players:
            self.notice.info("No players match this search.")

    def _selected_player_id(self) -> int | None:
        rows = self.p_table.selectionModel().selectedRows() if self.p_table.selectionModel() else []
        return int(self.p_table.item(rows[0].row(), 0).text()) if rows else None

    def _open_player(self) -> None:
        user_id = self._selected_player_id()
        if user_id is None:
            self.notice.error("Select a player in the list first.")
            return
        dialog = PlayerDialog(self.client, user_id, self)
        dialog.changed.connect(lambda: self._load_players(self.p_pager.page))
        dialog.exec()
        self._load_players(self.p_pager.page)

    # --------------------------------------------------------------- keys --
    def _keys_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        make = QHBoxLayout()
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("who is this key for? (label)")
        self.label_edit.setMaxLength(60)
        self.count = QSpinBox()
        self.count.setRange(1, 50)
        self.count.setToolTip("How many keys to create")
        self.expiry = QSpinBox()
        self.expiry.setRange(0, 3650)
        self.expiry.setSpecialValueText("no expiry")
        self.expiry.setSuffix(" days")
        self.expiry.setToolTip("Days until an unused key can no longer be redeemed")
        self.create_btn = NeonButton("CREATE KEYS", "Create new game keys", "cyan")
        self.create_btn.clicked.connect(self._create)
        make.addWidget(self.label_edit, 1)
        make.addWidget(self.count)
        make.addWidget(self.expiry)
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

        bar = QHBoxLayout()
        self.k_search = QLineEdit()
        self.k_search.setPlaceholderText("search by label, player, ID or the last characters of a key...")
        self.k_search.textChanged.connect(lambda _t: self._key_timer.start())
        self.k_filter = QComboBox()
        for value, caption in KEY_FILTERS:
            self.k_filter.addItem(caption, value)
        self.k_filter.currentIndexChanged.connect(lambda _i: self._load_keys(1))
        bar.addWidget(self.k_search, 1)
        bar.addWidget(self.k_filter)
        lay.addLayout(bar)
        self.summary = QLabel("")
        self.summary.setObjectName("dim")
        lay.addWidget(self.summary)

        self.table = make_table(["ID", "KEY", "STATUS", "PLAYER", "CREATED", "EXPIRES", "LABEL"], 6, 220)
        lay.addWidget(self.table, 1)
        self.k_pager = Pager()
        self.k_pager.changed.connect(self._load_keys)
        lay.addWidget(self.k_pager)

        row = QHBoxLayout()
        self.revoke_btn = NeonButton("DEACTIVATE", "Block the selected key and log its owner out (can be activated again)", "danger")
        self.activate_btn = NeonButton("ACTIVATE", "Switch a deactivated key back on")
        self.unbind_btn = NeonButton("FREE KEY", "Detach the selected key from its player (they switched accounts)")
        self.expiry_btn = NeonButton("SET EXPIRY", "Change when the selected key expires")
        self.delete_btn = NeonButton("DELETE", "Delete the selected key for good", "danger")
        self.refresh_btn = NeonButton("REFRESH")
        self.revoke_btn.clicked.connect(self._revoke)
        self.activate_btn.clicked.connect(self._activate)
        self.unbind_btn.clicked.connect(self._unbind)
        self.expiry_btn.clicked.connect(self._set_expiry)
        self.delete_btn.clicked.connect(self._delete_key)
        self.refresh_btn.clicked.connect(lambda: self._load_keys(self.k_pager.page))
        for b in (self.revoke_btn, self.activate_btn, self.unbind_btn, self.expiry_btn, self.delete_btn):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(self.refresh_btn)
        lay.addLayout(row)
        return w

    def _load_keys(self, page: int = 1) -> None:
        if not self.client.admin_logged_in:
            return
        search, status = self.k_search.text().strip(), self.k_filter.currentData()
        self._run(lambda: self.client.admin_keys_page(search, status, page, PER_PAGE, True), self._fill)

    def _fill(self, data: dict) -> None:
        keys = data["keys"]
        self.keys = keys
        keep = self._selected_id()
        self.table.setRowCount(len(keys))
        for r, k in enumerate(keys):
            cells = [str(k["id"]), k["key"], KEY_LABEL[k["status"]], k.get("user") or "—", stamp(k.get("created_at")),
                     stamp(k["expires_at"]) if k.get("expires_at") else "never", k.get("label") or ""]
            set_row(self.table, r, cells, {2: KEY_COLOR.get(k["status"], "dim")})
            if keep == k["id"]:
                self.table.selectRow(r)
        c = data["counts"]
        self.summary.setText(f"{sum(c.values())} keys  ·  {c['unused']} unused  ·  {c['in use']} active  ·  {c['revoked']} deactivated  ·  {c['expired']} expired")
        self.k_pager.set(data["page"], data["pages"], data["total"])

    def _selected_id(self) -> int | None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        return int(self.table.item(rows[0].row(), 0).text()) if rows else None

    def _create(self) -> None:
        label, count, days = self.label_edit.text().strip(), self.count.value(), self.expiry.value()
        self.notice.info("Creating...")
        self._run(lambda: self.client.admin_create_keys(label, count, days), self._created)

    def _created(self, made: list[dict]) -> None:
        self.fresh.setPlainText("\n".join(f"{k['key']}   {k['label']}".rstrip() for k in made))
        self.fresh_box.show()
        self.label_edit.clear()
        self.notice.ok(f"{len(made)} key(s) created. Copy them now: the full keys cannot be shown again.")
        self._load_keys(1)

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText("\n".join(line.split()[0] for line in self.fresh.toPlainText().splitlines() if line.strip()))
        self.notice.ok("Copied to the clipboard.")

    def _need_selection(self) -> dict | None:
        key_id = self._selected_id()
        key = next((k for k in self.keys if k["id"] == key_id), None)
        if key is None:
            self.notice.error("Select a key in the list first.")
        return key

    def _key_done(self, message: str) -> None:
        self.notice.ok(message)
        self._load_keys(self.k_pager.page)

    def _revoke(self) -> None:
        key = self._need_selection()
        if key is None:
            return
        if key["status"] == "revoked":
            self.notice.error("This key is already deactivated.")
            return
        who = f" It belongs to {key['user']}, who will be logged out at once." if key.get("user") else ""
        if ConfirmDialog("DEACTIVATE KEY", f"Deactivate key #{key['id']} ({key['key']})?{who} You can activate it again later.", self, yes="DEACTIVATE").exec():
            self._run(lambda: self.client.admin_revoke(key["id"]), lambda _r: self._key_done(f"Key #{key['id']} deactivated."))

    def _activate(self) -> None:
        key = self._need_selection()
        if key is None:
            return
        if key["status"] != "revoked":
            self.notice.error("Only deactivated keys can be activated.")
            return
        self._run(lambda: self.client.admin_activate(key["id"]), lambda _r: self._key_done(f"Key #{key['id']} activated again."))

    def _unbind(self) -> None:
        key = self._need_selection()
        if key is None:
            return
        if key["status"] != "in use":
            self.notice.error("Only keys that are in use can be freed.")
            return
        if ConfirmDialog("FREE KEY", f"Detach key #{key['id']} from {key.get('user') or 'its player'}? They are logged out, and anyone can claim the key next.",
                         self, yes="FREE KEY").exec():
            self._run(lambda: self.client.admin_unbind(key["id"]), lambda _r: self._key_done(f"Key #{key['id']} is free again."))

    def _set_expiry(self) -> None:
        key = self._need_selection()
        if key is None:
            return
        dialog = NumberPrompt("KEY EXPIRY", f"Days from now until key #{key['id']} can no longer be redeemed (0 = never). "
                                           "Players who already use the key are not affected.", self)
        if dialog.exec():
            days = dialog.spin.value()
            self._run(lambda: self.client.admin_key_expiry(key["id"], days), lambda _r: self._key_done(f"Expiry of key #{key['id']} updated."))

    def _delete_key(self) -> None:
        key = self._need_selection()
        if key is None:
            return
        who = f" {key['user']} is logged out and cannot play until they get a new key." if key.get("user") else ""
        if ConfirmDialog("DELETE KEY", f"Delete key #{key['id']} ({key['key']}) for good?{who} This cannot be undone.", self, yes="DELETE").exec():
            self._run(lambda: self.client.admin_delete_key(key["id"]), lambda _r: self._key_done(f"Key #{key['id']} deleted."))

    # ----------------------------------------------------------- activity --
    def _activity_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        info = QLabel("Everything an administrator did, newest first.")
        info.setObjectName("dim")
        lay.addWidget(info)
        self.a_table = make_table(["TIME", "ACTION", "PLAYER", "KEY", "DETAIL"], 4, 400)
        lay.addWidget(self.a_table, 1)
        return w

    def _load_activity(self) -> None:
        if self.client.admin_logged_in:
            self._run(lambda: self.client.admin_audit(100), self._fill_activity)

    def _fill_activity(self, entries: list[dict]) -> None:
        self.a_table.setRowCount(len(entries))
        for r, e in enumerate(entries):
            set_row(self.a_table, r, [stamp(e["ts"], True), e["action"], e.get("user") or "—", f"#{e['key_id']}" if e.get("key_id") else "—", e.get("detail") or ""])
