"""UI test: the admin panel (player database, player editing, game keys, activity) against a real server, plus the player's own game
receiving an administrator's change through the ONLINE page. Run with QT_QPA_PLATFORM=windows (offscreen has no fonts)."""
import json
import os
import socket
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ["NEXUS_NO_AUDIO"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QApplication

from nexus.audio import SoundManager
from nexus.save_system import SaveSystem, SettingsStore
from server.validation import cumulative_xp
from tests.test_keys import ADMIN, ADMIN_PASSWORD, ADMIN_USER, load_server
from ui import admin_panel
from ui.admin_panel import AdminPanel, PlayerDialog
from ui.main_window import MainWindow
from ui.widgets import build_stylesheet

OUT = Path(os.environ.get("NEXUS_SHOTS", tempfile.mkdtemp(prefix="nexus_shots_")))
OUT.mkdir(exist_ok=True)
db_path = Path(tempfile.mkdtemp()) / "online.db"
srv = load_server(db_path)
s = socket.socket()
s.bind(("127.0.0.1", 0))
port = s.getsockname()[1]
s.close()
server = uvicorn.Server(uvicorn.Config(srv.app, host="127.0.0.1", port=port, log_level="error"))
threading.Thread(target=server.run, daemon=True).start()
url = f"http://127.0.0.1:{port}"
for _ in range(100):
    try:
        urllib.request.urlopen(url + "/health", timeout=1)
        break
    except OSError:
        time.sleep(0.1)
os.environ["NEXUS_SERVER_URL"] = url
os.environ["NEXUS_DEV_NAME"] = "Toto"
QDesktopServices.openUrl = staticmethod(lambda qurl: urllib.request.urlopen(qurl.toString(), timeout=5).read() and True)


def call(method, path, payload=None, headers=None):
    req = urllib.request.Request(url + path, data=json.dumps(payload).encode() if payload is not None else None, method=method,
                                 headers={**(headers or ADMIN), "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=5).read())


def seed_player(name, level, credits):
    key = call("POST", "/admin/keys", {"label": f"key for {name}"})["keys"][0]["key"]
    state = f"seed-{name}-" + "x" * 16
    call("POST", "/auth/begin", {"state": state, "key": key}, {})
    urllib.request.urlopen(f"{url}/auth/dev?name={name}&state={state}", timeout=5).read()
    token = call("POST", "/auth/poll", {"state": state}, {})["token"]
    score = {"level": level, "xp_total": cumulative_xp(level) + 20, "missions": level, "credits_earned": credits * 2, "perfect": 1, "playtime": 7200,
             "ng_plus": 0, "rank": "OPERATOR", "details": {"credits": credits, "reputation": 40, "heat": 5, "achievements": ["a1", "a2"], "unlocks": ["theme:x"],
                                                           "stats": {"commands_run": 10 * level}}}
    call("POST", "/scores", score, {"Authorization": f"Bearer {token}"})
    return key


for i, (name, level, credits) in enumerate([("Mira", 12, 5000), ("Zoe", 4, 300), ("Kai", 20, 99999), ("Lena", 7, 1200), ("Omar", 15, 800), ("Pia", 2, 50)]):
    seed_player(name, level, credits)
spare_key = call("POST", "/admin/keys", {"label": "spare", "count": 1})["keys"][0]["key"]       # a key nobody has used

app = QApplication([])
tmp = Path(tempfile.mkdtemp())
settings = SettingsStore(tmp / "s.json")
app.setStyleSheet(build_stylesheet(12))
saves = SaveSystem(tmp / "p", tmp / "s")
saves.create_profile("TOTO").close()
win = MainWindow(settings, saves, SoundManager(None))
win.resize(1366, 768)
win.show()
win.startup()


def pump(ms):
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("ok:", msg)


pump(600)
win.engine.db.set_flag("intro_pending", False)
win._first_run = False
admin_panel.ConfirmDialog.exec = lambda self: True                      # answer the confirmation dialogs with YES
admin_panel.TypeToConfirm.exec = lambda self: True
admin_panel.NumberPrompt.exec = lambda self: True

# ---------------------------------------------------------------- the player's game: registration with the key first
win.on_menu_action("online")
pump(1500)
page = win.shell.pages["online"]
page.consent.setChecked(True)
page.login_btn.click()
pump(500)
check(not page.client.logged_in and "access key" in page.status.text().lower(), "no key: the game refuses to start the registration")
page.key_edit.setText("NX-AAAAA-BBBBB-CCCCC")
page.login_btn.click()
pump(1500)
check(not page.client.logged_in and "not valid" in page.status.text(), "an invalid key is refused by the server")
page.key_edit.setText(spare_key)
page.login_btn.click()
pump(6000)
check(page.client.logged_in, "a valid key creates the account and logs in")
page._sync(manual=True)
pump(1500)

# ---------------------------------------------------------------- admin panel
panel = AdminPanel(win.shell.admin_client, win)
panel.show()
pump(300)
panel.user_edit.setText(ADMIN_USER)
panel.pass_edit.setText(ADMIN_PASSWORD)
panel.login_btn.click()
pump(2500)
check(panel.stack.currentIndex() == 1, "admin login opens the panel")
check(panel.p_table.rowCount() == 7, "all 7 registered players are listed (6 seeded + the one that just registered)")
check(panel.p_pager.pages == 1 and "7 total" in panel.p_pager.label.text(), "pagination shows the totals")
check("7 players" in panel.p_summary.text(), "summary counts")
panel.grab().save(str(OUT / "admin_players.png"))

panel.p_search.setText("mi")
pump(1500)
check([panel.p_table.item(r, 1).text().lstrip("● ") for r in range(panel.p_table.rowCount())] == ["Mira"], "search by name finds the player")
mira_id = int(panel.p_table.item(0, 0).text())
panel.p_search.setText(str(mira_id))
pump(1500)
check(panel.p_table.rowCount() == 1 and panel.p_table.item(0, 0).text() == str(mira_id), "search by account ID finds the player")
panel.p_search.setText("")
pump(1500)
panel.p_sort.setCurrentIndex([panel.p_sort.itemData(i) for i in range(panel.p_sort.count())].index("level"))
pump(1500)
levels = [panel.p_table.item(r, 3).text() for r in range(panel.p_table.rowCount())]
check(levels[:3] == ["20", "15", "12"], "sorting by level puts the highest first")
panel.p_filter.setCurrentIndex([panel.p_filter.itemData(i) for i in range(panel.p_filter.count())].index("banned"))
pump(1500)
check(panel.p_table.rowCount() == 0, "the BANNED filter is empty at first")
panel.p_filter.setCurrentIndex(0)
pump(1500)

# ---------------------------------------------------------------- player detail + edit
panel.p_table.selectRow(0)                                               # Kai (level 20)
kai_id = panel._selected_player_id()
dialog = PlayerDialog(panel.client, kai_id, panel)
dialog.show()
pump(1500)
check(dialog.data.get("name") == "Kai" and dialog.tabs.count() == 3, "the detail view opens with overview / edit / account")
check(dialog.data["credits"] == 99999 and len(dialog.data["achievements"]) == 2, "detail shows balance and unlocked content")
dialog.grab().save(str(OUT / "admin_player_overview.png"))
dialog.tabs.setCurrentIndex(1)
pump(300)
dialog.apply_btn.click()
pump(300)
check("Nothing to change" in dialog.notice.text(), "applying without a change is refused with a message")
dialog.credits.setValue(1234)
dialog.rep.setValue(75)
dialog.reason.setText("ui test")
dialog.grab().save(str(OUT / "admin_player_edit.png"))
dialog.apply_btn.click()
pump(2500)
check("updated successfully" in dialog.notice.text(), "a clear success message after saving")
d = call("GET", f"/admin/players/{kai_id}")
check((d["credits"], d["reputation"]) == (1234, 75) and len(d["pending_edits"]) == 1, "the change is stored in the database and queued for the player")
dialog.tabs.setCurrentIndex(1)
dialog.level.setValue(5)
dialog.resets["heat"].setChecked(True)
dialog.apply_btn.click()                                                 # level decrease + reset: needs the type-to-confirm dialog (auto-yes here)
pump(2500)
d = call("GET", f"/admin/players/{kai_id}")
check(d["level"] == 5 and d["heat"] == 0, "lowering the level and a reset are applied after the confirmation")
dialog.tabs.setCurrentIndex(2)
pump(200)
dialog.status_reason.setText("testing a ban")
dialog.status_buttons["banned"].click()
pump(2500)
d = call("GET", f"/admin/players/{kai_id}")
check(d["account_status"] == "banned" and d["status_reason"] == "testing a ban", "BAN is stored with its reason")
dialog.grab().save(str(OUT / "admin_player_account.png"))
dialog.tabs.setCurrentIndex(2)
dialog.status_buttons["active"].click()
pump(2500)
check(call("GET", f"/admin/players/{kai_id}")["account_status"] == "active", "UNBAN restores the account")
dialog.accept()
pump(1500)
check(panel.p_table.rowCount() == 7, "the list is still complete after editing")

# ---------------------------------------------------------------- game keys
panel.tabs.setCurrentIndex(1)
pump(300)
total_before = panel.k_pager.label.text()
panel.label_edit.setText("batch")
panel.count.setValue(3)
panel.expiry.setValue(14)
panel.create_btn.click()
pump(2000)
check(panel.fresh_box.isVisible() and panel.fresh.toPlainText().count("NX-") == 3, "three keys generated at once, shown once")
check(sum(1 for r in range(panel.table.rowCount()) if panel.table.item(r, 6).text() == "batch") == 3, "they are listed with label")
check(all(panel.table.item(r, 5).text() != "never" for r in range(panel.table.rowCount()) if panel.table.item(r, 6).text() == "batch"), "with an expiry date")
panel.k_filter.setCurrentIndex([panel.k_filter.itemData(i) for i in range(panel.k_filter.count())].index("in use"))
pump(1500)
check(panel.table.rowCount() == 7 and all(panel.table.item(r, 2).text() == "ACTIVE" for r in range(7)), "status filter ACTIVE shows the 7 keys in use")
check(all(panel.table.item(r, 3).text() != "—" for r in range(7)), "each active key shows its player")
panel.k_filter.setCurrentIndex([panel.k_filter.itemData(i) for i in range(panel.k_filter.count())].index("unused"))
pump(1500)
check(panel.table.rowCount() == 3, "status filter UNUSED shows the 3 new keys")
panel.table.selectRow(0)
key_id = panel._selected_id()
panel.revoke_btn.click()
pump(2000)
check(call("GET", "/admin/keys?status=revoked")["total"] == 1, "DEACTIVATE works")
panel.k_filter.setCurrentIndex([panel.k_filter.itemData(i) for i in range(panel.k_filter.count())].index("revoked"))
pump(1500)
panel.table.selectRow(0)
panel.activate_btn.click()
pump(2000)
check(call("GET", "/admin/keys?status=revoked")["total"] == 0, "ACTIVATE brings it back")
panel.k_filter.setCurrentIndex(0)
pump(1500)
panel.k_search.setText("batch")
pump(1500)
check(panel.table.rowCount() == 3, "search finds keys by label")
panel.table.selectRow(0)
panel.delete_btn.click()
pump(2000)
check(call("GET", "/admin/keys?search=batch")["total"] == 2, "DELETE removes the key for good")
panel.grab().save(str(OUT / "admin_keys.png"))
panel.tabs.setCurrentIndex(2)
pump(1500)
check(panel.a_table.rowCount() >= 5, "the activity log lists what was done")
panel.grab().save(str(OUT / "admin_activity.png"))

# ---------------------------------------------------------------- the player's game receives an administrator's change
me = call("GET", "/admin/players?search=toto")["players"]
toto_id = me[0]["id"]
call("POST", f"/admin/players/{toto_id}/edit", {"level": 6, "xp": 10, "credits": 4242, "reason": "welcome gift"})
page._sync(manual=True)
pump(3500)
check((win.engine.player.level, win.engine.player.xp, win.engine.player.credits) == (6, 10, 4242), "the player's game applied the change to the running save")
check(call("GET", f"/admin/players/{toto_id}")["pending_edits"] == [], "and confirmed it to the server")
check(any("ADMIN" in n["title"] for n in win.engine.db.get_notifications(10)), "the player was notified")
win.grab().save(str(OUT / "player_after_edit.png"))

panel.logout_btn.click()
pump(800)
check(panel.stack.currentIndex() == 0 and not panel.client.admin_logged_in, "LOG OUT drops the admin session")
panel.close()
win._teardown()
server.should_exit = True
print("ADMIN UI OK")
sys.stdout.flush()
os._exit(0)
