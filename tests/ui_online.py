"""UI test for the ONLINE page against a real local server (dev login). Saves screenshots."""
import importlib
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
os.environ["NEXUS_DB"] = str(Path(tempfile.mkdtemp()) / "online.db")
os.environ["NEXUS_DEV_LOGIN"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication

import server.app as srv
from nexus.audio import SoundManager
from nexus.online import OnlineClient
from nexus.save_system import SaveSystem, SettingsStore
from server.validation import cumulative_xp
from ui.main_window import MainWindow
from ui.widgets import build_stylesheet

OUT = Path(os.environ.get("NEXUS_SHOTS", tempfile.mkdtemp(prefix="nexus_shots_")))
OUT.mkdir(exist_ok=True)
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

# the "browser": completes the login URL the game would open
QDesktopServices.openUrl = staticmethod(lambda qurl: urllib.request.urlopen(qurl.toString(), timeout=5).read() and True)


class Plain:
    def __init__(self):
        self.v = {"online_enabled": True, "online_token": ""}

    def get(self, k):
        return self.v.get(k)

    def set(self, k, val):
        self.v[k] = val


# a second player already on the server
friend_settings = Plain()
friend = OnlineClient(friend_settings, url)
st, link = friend.new_login(dev_name="Mira_Fan")
urllib.request.urlopen(link, timeout=5).read()
friend.poll_login(st)
friend.submit_scores({"level": 12, "xp_total": cumulative_xp(12) + 5, "missions": 9, "credits_earned": 20000, "perfect": 3, "playtime": 3000, "ng_plus": 0, "rank": "OPERATOR"})
friend.presence("Mission 004 · THE GHOST")

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
check(page.out_view.isVisible(), "logged-out view with consent shown")
check(not page.key_row.isVisible(), "no key field on an open server")
page._on_info({"gated": True})
check(page.key_row.isVisible(), "key field appears for an invite-only server")
page._on_info({"gated": False})
check(not page.key_row.isVisible(), "key field hidden again for an open server")
page.login_btn.click()
pump(500)
check(not page.client.logged_in, "login refuses without consent")
page.consent.setChecked(True)
page.login_btn.click()
pump(6000)
check(page.client.logged_in and page.in_view.isVisible(), "logged in through the (simulated) browser flow")
page._sync(manual=True)
page.add_edit.setText("mira_fan")
page._add_friend()
pump(2500)
# the friend accepts
friend.friend_respond("Toto", True)
page._load_friends()
pump(2000)
check(page.table.rowCount() >= 1, "leaderboard filled")
texts = [page.friend_list.item(i).text() for i in range(page.friend_list.count())]
print(texts)
check(any("Mira_Fan" in t and "THE GHOST" in t for t in texts), "friend shown with live status")
check(win.shell.friends_bar.isVisible() and "ONLINE" in win.shell.friends_bar.text(), "friends bar in the sidebar shows who is online")
check("Mira_Fan" in win.shell.friends_bar.toolTip(), "friends bar tooltip names the online friend")
page._load_challenge()
pump(2000)
check(page.ch_title.text() != "" and page.ch_table.rowCount() >= 1, "weekly challenge tab filled")
check("Ends in" in page.ch_meta.text(), "weekly challenge shows the time left")
page.tabs.setCurrentIndex(0)
pump(300)
win.grab().save(str(OUT / "online_challenge.png"))
page.tabs.setCurrentIndex(1)
pump(300)
win.grab().save(str(OUT / "online_page.png"))
page.tabs.setCurrentIndex(2)
pump(300)
win.grab().save(str(OUT / "online_friends.png"))
page.refresh()
page.client.logout()
page.refresh()
pump(300)
check(not win.shell.friends_bar.isVisible(), "friends bar hides again after logging out")
win._teardown()
server.should_exit = True
print("ONLINE UI OK")
sys.stdout.flush()
os._exit(0)
