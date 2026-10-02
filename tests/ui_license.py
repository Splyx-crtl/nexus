"""UI test: the game key comes first. Activation, offline play, tampering, expiry, renewal, revocation, another computer.
Run with QT_QPA_PLATFORM=windows. Uses a real server (licence signing on) and the real MainWindow."""
import base64
import json
import os
import secrets
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

from nexus import ed25519
from nexus.audio import SoundManager
from nexus.save_system import SaveSystem, SettingsStore
from tests.test_keys import ADMIN, load_server
from ui.main_window import MainWindow
from ui.widgets import build_stylesheet

OUT = Path(os.environ.get("NEXUS_SHOTS", tempfile.mkdtemp(prefix="nexus_shots_")))
OUT.mkdir(exist_ok=True)
SEED = secrets.token_bytes(32)
os.environ["NEXUS_LICENSE_PUBKEY"] = ed25519.public_key(SEED).hex()          # this build "ships" with that public key
srv = load_server(Path(tempfile.mkdtemp()) / "online.db", NEXUS_LICENSE_SEED=SEED.hex())
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
QDesktopServices.openUrl = staticmethod(lambda qurl: True)


def admin(method, path, payload=None):
    req = urllib.request.Request(url + path, data=json.dumps(payload).encode() if payload is not None else None, method=method,
                                 headers={**ADMIN, "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=5).read())


app = QApplication([])
app.setStyleSheet(build_stylesheet(12))


def pump(ms):
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("ok:", msg)


def launch(settings, saves):
    win = MainWindow(settings, saves, SoundManager(None))
    win.resize(1100, 720)
    win.show()
    win.startup()
    pump(500)
    return win


def close(win):
    try:
        win._teardown()
    except Exception:
        pass
    win.close()
    pump(100)


tmp = Path(tempfile.mkdtemp())
settings = SettingsStore(tmp / "s.json")
saves = SaveSystem(tmp / "p", tmp / "slots")
key = admin("POST", "/admin/keys", {"label": "ui"})["keys"][0]

# ------------------------------------------------------------ first start: nothing works without a key
win = launch(settings, saves)
check(win.stack.currentIndex() == win.PAGE_LICENSE, "a new installation asks for the game key before anything else")
screen = win.license_screen
win.grab().save(str(OUT / "license_screen.png"))
screen.button.click()
pump(200)
check("Enter your game key" in screen.notice.text(), "an empty key is refused with a message")
screen.edit.setText("NX-AAAAA-BBBBB-CCCCC")
screen.button.click()
pump(2000)
check("not valid" in screen.notice.text() and win.stack.currentIndex() == win.PAGE_LICENSE, "an invalid key is refused by the server and the game stays locked")
check(not settings.get("license_token"), "no licence was stored")
win.grab().save(str(OUT / "license_wrong_key.png"))
screen.edit.setText(key["key"].lower())
screen.button.click()
pump(3000)
check(win.stack.currentIndex() == win.PAGE_FIRST, "a valid key activates the game and the first-launch (profile creation) follows")
check(bool(settings.get("license_token")) and settings.get("license_key") == key["key"].lower(), "the licence is stored for offline play")
check(admin("GET", "/admin/keys")["keys"][0]["status"] == "in use", "the server shows the key as in use")
saves.create_profile("TOTO").close()                                      # the player creates a profile
close(win)

# ------------------------------------------------------------ the next start works without a connection
os.environ["NEXUS_SERVER_URL"] = "http://127.0.0.1:9"                    # nothing listens there: offline
win = launch(SettingsStore(tmp / "s.json"), saves)
check(win.stack.currentIndex() == win.PAGE_MENU, "OFFLINE: the activated game starts straight into the menu")
close(win)

# ------------------------------------------------------------ editing the settings file does not bypass anything
raw = json.loads((tmp / "s.json").read_text())
good_token = raw["license_token"]
raw["license_token"] = "forged.token"
(tmp / "s.json").write_text(json.dumps(raw))
win = launch(SettingsStore(tmp / "s.json"), saves)
check(win.stack.currentIndex() == win.PAGE_LICENSE and "not valid" in win.license_screen.notice.text(), "a forged licence in the settings file is rejected")
close(win)
payload, sig = good_token.split(".")
fake_payload = base64.urlsafe_b64encode(json.dumps({"v": 1, "kid": 1, "dev": raw["device_id"], "iat": 0, "exp": 4102444800}).encode()).rstrip(b"=").decode()
raw["license_token"] = fake_payload + "." + sig                           # real signature, edited payload (expiry in 2100)
(tmp / "s.json").write_text(json.dumps(raw))
win = launch(SettingsStore(tmp / "s.json"), saves)
check(win.stack.currentIndex() == win.PAGE_LICENSE, "a licence with an edited expiry date is rejected")
close(win)
raw["license_token"] = good_token
raw["device_id"] = "0" * 32                                              # the settings copied to another computer
(tmp / "s.json").write_text(json.dumps(raw))
win = launch(SettingsStore(tmp / "s.json"), saves)
check(win.stack.currentIndex() == win.PAGE_LICENSE and "another computer" in win.license_screen.notice.text(), "a licence copied to another computer is rejected")
close(win)
raw["device_id"] = json.loads((tmp / "s.json").read_text())["device_id"] if False else raw["device_id"]

# ------------------------------------------------------------ an expired licence offline asks for a connection; online it renews itself
real_device = None
settings = SettingsStore(tmp / "s2.json")
saves2 = SaveSystem(tmp / "p2", tmp / "slots2")
saves2.create_profile("TOTO").close()
os.environ["NEXUS_SERVER_URL"] = url
key2 = admin("POST", "/admin/keys", {"label": "ui2"})["keys"][0]
win = launch(settings, saves2)
screen = win.license_screen
screen.edit.setText(key2["key"])
screen.button.click()
pump(3000)
check(win.stack.currentIndex() == win.PAGE_MENU, "second installation: key accepted, straight to the menu")
close(win)
device = settings.get("device_id")
now = int(time.time())
old = json.dumps({"v": 1, "kid": 2, "dev": device, "iat": now - 40 * 86400, "exp": now - 10 * 86400}, separators=(",", ":")).encode()
b64 = lambda raw_bytes: base64.urlsafe_b64encode(raw_bytes).rstrip(b"=").decode()
settings.set("license_token", f"{b64(old)}.{b64(ed25519.sign(SEED, old))}")
os.environ["NEXUS_SERVER_URL"] = "http://127.0.0.1:9"
win = launch(SettingsStore(tmp / "s2.json"), saves2)
pump(6000)
check(win.stack.currentIndex() == win.PAGE_LICENSE and "run out" in win.license_screen.notice.text(),
      "offline with an expired licence: the game asks to connect once")
win.grab().save(str(OUT / "license_expired.png"))
close(win)
os.environ["NEXUS_SERVER_URL"] = url
win = launch(SettingsStore(tmp / "s2.json"), saves2)
pump(3500)
check(win.stack.currentIndex() == win.PAGE_MENU, "online with an expired licence: it renews itself with the stored key")
check(SettingsStore(tmp / "s2.json").get("license_token") != "", "the renewed licence is stored")

# ------------------------------------------------------------ revoking the key stops the game at its next renewal
admin("POST", f"/admin/keys/{key2['id']}/revoke")
win._renew_license()
pump(2500)
check(win.stack.currentIndex() == win.PAGE_LICENSE and "revoked" in win.license_screen.notice.text(), "a deactivated key locks the game again (shown in the menu)")
check(not win.settings.get("license_token"), "and the licence is removed")
admin("POST", f"/admin/keys/{key2['id']}/activate")
win.license_screen.edit.setText(key2["key"])
win.license_screen.button.click()
pump(3000)
check(win.stack.currentIndex() == win.PAGE_MENU, "activating the key again lets the player back in")
close(win)

# ------------------------------------------------------------ one key, one computer
tmp3 = Path(tempfile.mkdtemp())
other = SettingsStore(tmp3 / "s.json")
saves3 = SaveSystem(tmp3 / "p", tmp3 / "slots")
win = launch(other, saves3)
win.license_screen.edit.setText(key2["key"])
win.license_screen.button.click()
pump(2500)
check(win.stack.currentIndex() == win.PAGE_LICENSE and "another computer" in win.license_screen.notice.text(), "the same key on a second computer is refused")
close(win)
server.should_exit = True
print("LICENSE UI OK")
sys.stdout.flush()
os._exit(0)
