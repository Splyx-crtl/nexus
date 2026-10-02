"""UI test: the ONLINE page against an invite-only server (Discord server + access key). Dev login stands in for Discord."""
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
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication

from nexus.audio import SoundManager
from nexus.save_system import SaveSystem, SettingsStore
from tests.test_keys import ADMIN, ADMIN_PASSWORD, ADMIN_USER, load_server
from ui.main_window import MainWindow
from ui.widgets import build_stylesheet

OUT = Path(os.environ.get("NEXUS_SHOTS", tempfile.mkdtemp(prefix="nexus_shots_")))
OUT.mkdir(exist_ok=True)
srv = load_server(Path(tempfile.mkdtemp()) / "online.db")
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

import json


def admin(method, path, payload=None):
    req = urllib.request.Request(url + path, data=json.dumps(payload).encode() if payload is not None else None, method=method,
                                 headers={**ADMIN, "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=5).read())


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
win.on_menu_action("online")
pump(1500)
page = win.shell.pages["online"]
check(page.gated is True and page.key_row.isVisible(), "the page learns that the server is invite-only and shows the key field")
win.grab().save(str(OUT / "online_key_login.png"))
page.consent.setChecked(True)

page.login_btn.click()
pump(500)
check("access key" in page.status.text().lower() and not page.client.logged_in, "login without a key is refused locally with a hint")

page.key_edit.setText("NX-AAAAA-BBBBB-CCCCC")
page.login_btn.click()
pump(1500)
check("not valid" in page.status.text() and not page.client.logged_in and page.login_btn.isEnabled(), "a wrong key shows the server's reason and the button comes back")
win.grab().save(str(OUT / "online_key_wrong.png"))

key = admin("POST", "/admin/keys", {"label": "ui test"})["keys"][0]
page.key_edit.setText(key["key"].lower())
page.login_btn.click()
pump(6000)
check(page.client.logged_in and page.in_view.isVisible(), "a valid key logs in")
check(settings.get("online_key") == key["key"].lower(), "the key is remembered for the next login")

# the admin revokes the key: the running game is logged out on its next request
admin("POST", f"/admin/keys/{key['id']}/revoke")
page._load_all()
pump(2500)
check(not page.client.logged_in and page.out_view.isVisible(), "revoking the key logs the player out of the running game")
check("log in again" in page.status.text(), "and asks them to log in again")
page.login_btn.click()
pump(1500)
check("revoked" in page.status.text(), "logging in again shows 'revoked'")
win.grab().save(str(OUT / "online_key_revoked.png"))

# ------------------------------------------------------------------ admin panel (inside the game)
from ui import admin_panel
from ui.admin_panel import AdminPanel

check(win.shell.admin_btn.isVisible(), "ADMIN button at the bottom of the sidebar")
admin_panel.ConfirmDialog.exec = lambda self: True                      # answer the confirmation dialogs with YES
panel = AdminPanel(win.shell.admin_client, win)
panel.show()
pump(300)
check(panel.stack.currentIndex() == 0, "the admin panel starts at the login form")
panel.login_btn.click()
pump(300)
check("Enter the admin user name" in panel.status.text(), "empty admin login is refused locally")
panel.user_edit.setText(ADMIN_USER)
panel.pass_edit.setText("wrong password!!")
panel.login_btn.click()
pump(1500)
check("Wrong user name or password" in panel.status.text() and panel.stack.currentIndex() == 0, "wrong admin credentials are refused by the server")
panel.pass_edit.setText(ADMIN_PASSWORD)
panel.login_btn.click()
pump(1500)
check(panel.stack.currentIndex() == 1 and panel.client.admin_logged_in, "right credentials open the key manager")
check(not panel.pass_edit.text(), "the password field is cleared after login")
check(panel.table.rowCount() >= 1, "existing keys are listed")
panel.label_edit.setText("Mira")
panel.count.setValue(2)
before = panel.table.rowCount()
panel.create_btn.click()
pump(2000)
check(panel.fresh_box.isVisible() and panel.fresh.toPlainText().count("NX-") == 2, "two new keys are shown once, ready to copy")
check(panel.table.rowCount() == before + 2, "the list shows the new keys")
panel.copy_btn.click()
from PySide6.QtGui import QGuiApplication
check(QGuiApplication.clipboard().text().count("NX-") == 2, "COPY puts the keys on the clipboard")
panel.table.selectRow(0)                                                  # newest key first
newest_id = panel._selected_id()
panel.revoke_btn.click()
pump(2000)
status = {k["id"]: k["status"] for k in admin("GET", "/admin/keys")["keys"]}
check(status[newest_id] == "revoked", "REVOKE blocks the selected key on the server")
panel.table.clearSelection()
panel.revoke_btn.click()
check("Select a key" in panel.status.text(), "revoking without a selection asks for one")
win.grab().save(str(OUT / "admin_panel.png"))
panel.grab().save(str(OUT / "admin_panel_dialog.png"))
panel.logout_btn.click()
pump(800)
check(panel.stack.currentIndex() == 0 and not panel.client.admin_logged_in, "LOG OUT returns to the login form and drops the session")
panel.close()
win._teardown()
server.should_exit = True
print("INVITE-ONLY UI OK")
sys.stdout.flush()
os._exit(0)
