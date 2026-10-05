"""UI integration test (v2): first launch, real terminal input with auto-solved mini-games, market purchase,
loadout, daily claim, save/load, settings/theme, network map, menu navigation and ending cinematic."""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ["NEXUS_NO_AUDIO"] = "1"
os.environ["NEXUS_LICENSE_PUBKEY"] = ""                      # these scripts test other things: no game key needed (tests/ui_license.py covers it)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from nexus import config
from nexus.audio import SoundManager
from nexus.save_system import SaveSystem, SettingsStore
from ui.dialogs import LoadDialog, PauseMenu, SlotDialog
from ui.main_window import MainWindow
from ui.minigames import AccessDialog, EncryptionDialog, FirewallDialog, RoutingDialog, TraceDialog
from ui.widgets import build_stylesheet, load_custom_fonts

OUT = Path(os.environ.get("NEXUS_SHOTS", tempfile.mkdtemp(prefix="nexus_shots_")))
OUT.mkdir(exist_ok=True)
app = QApplication([])
load_custom_fonts()
tmp = Path(tempfile.mkdtemp(prefix="nexus_flow_"))
settings = SettingsStore(tmp / "settings.json")
settings.values["text_speed"] = 5
app.setStyleSheet(build_stylesheet(12))
saves = SaveSystem(tmp / "profiles", tmp / "slots")
win = MainWindow(settings, saves, SoundManager(None))
win.resize(1366, 768)
win.show()
solved: list[str] = []


def pump(ms):
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def autosolve():
    dlg = app.activeModalWidget()
    if dlg is None or getattr(dlg, "_done", True):
        return
    if isinstance(dlg, FirewallDialog):
        for sym in dlg.p.secret:
            dlg._place(sym)
        dlg._submit()
    elif isinstance(dlg, EncryptionDialog):
        if dlg.p.type == "caesar":
            dlg.slider.setValue(dlg.p.key)
        elif dlg.p.type == "vigenere":
            dlg.key_input.setText(dlg.p.key)
        dlg._confirm()
    elif isinstance(dlg, RoutingDialog):
        dlg.canvas.path = list(dlg.p.optimal_path)
        dlg._go()
    elif isinstance(dlg, AccessDialog):
        for ch in dlg.p.code:
            dlg._key(ch)
        dlg._key("↵")
    elif isinstance(dlg, TraceDialog):
        for _ in range(dlg.cfg.required_hits):
            dlg._hit()
    else:
        return
    solved.append(type(dlg).__name__)


solver = QTimer()
solver.timeout.connect(autosolve)
solver.start(250)


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("ok:", msg)


# ---------------------------------------------------------------- first launch
win.startup()
check(win.stack.currentIndex() == win.PAGE_FIRST, "first launch screen shown on a fresh install")
pump(2600)
win.first.edit.setText("TESTER")
win.first._submit()
pump(3600)
win.story._end()
pump(2500)
check(win.engine is not None and win.engine.player.username == "TESTER", "profile created from first-launch form")
check(win.stack.currentIndex() == win.PAGE_SHELL, "shell visible after intro")
check(win.engine.missions.active()["id"] == "mission_000", "tutorial mission (boot camp) auto-started")
check(win.tutorial is not None and win.tutorial.isVisible(), "tutorial overlay shown")
win.tutorial.close_tutorial()
shell = win.shell
term = shell.terminal_page.terminal


def type_cmd(cmd, wait=2200, answer=None):
    term.input.setText(cmd)
    term.input.returnPressed.emit()
    pump(wait)
    if answer is not None:
        term.input.setText(answer)
        term.input.returnPressed.emit()
        pump(1200)
    while term.busy:
        pump(200)
    win.banner.queue.clear()
    win.banner.hide()


# ----------------------------------------------------------- tutorial via UI
for cmd in ["help", "connect echo", "scan", "ls", "cd training", "cat lesson.txt", "ls -a", "cat .keycard",
            "download field_notes.dat", "hint", "disconnect"]:
    type_cmd(cmd)
check(win.engine.missions.is_complete("mission_000"), "tutorial completed via real terminal input")
check(win.engine.missions.active()["id"] == "mission_001", "mission 001 starts right after the tutorial")
check(win.engine.player.completed_missions == 0, "tutorial does not count as a completed mission")

# ----------------------------------------------------------- missions via UI
for cmd in ["connect echo", "scan", "ls", "cat readme.txt"]:
    type_cmd(cmd)
check(win.engine.missions.is_complete("mission_001"), "mission 1 via real terminal input")
type_cmd("mission start 2")
for cmd in ["connect echo", "ls -a", "cd .drop", "cat note.txt", "download package.dat"]:
    type_cmd(cmd)
check(win.engine.missions.is_complete("mission_002"), "mission 2 (hidden files, download)")
check(win.engine.db.get_flag("chapter_1_done"), "chapter 1 completed with story event")
type_cmd("mission start 3")
for cmd in ["connect blackvault", "scan", "firewall"]:
    type_cmd(cmd, wait=2600)
type_cmd("login svc_backup", answer="vault-7-Alpha")
for cmd in ["cd /srv/db", "cat manifest.txt", "download manifest.txt"]:
    type_cmd(cmd)
check(win.engine.missions.is_complete("mission_003"), "mission 3 (firewall mini-game dialog + password prompt)")
type_cmd("disconnect")

# ------------------------------------------------------------------- market / loadout
e = win.engine
e.player._set(level=12, credits=40000)
shell.show_page("market")
pump(500)
mk = shell.pages["market"]
ids = [x["id"] for x in mk.entries]
mk.list.setCurrentRow(ids.index("heat_sink"))
pump(200)
before = e.player.credits
mk.buy_btn.click()
pump(400)
check(e.player.qty("heat_sink") >= 1 and e.player.credits < before, "market purchase via BUY button")
mk.set_category("TOOLS")
ids = [x["id"] for x in mk.entries]
mk.list.setCurrentRow(ids.index("trace_booster"))
pump(200)
mk.buy_btn.click()
pump(300)
mk.equip_btn.click()
pump(300)
check(e.db.get_equipment().get("TRACE") == "trace_booster", "gear equipped from the market page")
shell.show_page("loadout")
pump(400)
check("Trace Booster" in shell.pages["loadout"].cards["TRACE"].name.text(), "loadout page shows the equipped item")
shell.pages["loadout"]._unequip("TRACE")
check("TRACE" not in e.db.get_equipment(), "unequip via loadout page")
shell.show_page("inventory")
pump(300)
shell.pages["inventory"].set_filter("TOOLS")
check(any(x["id"] == "heat_sink" for x in shell.pages["inventory"].entries), "inventory filter TOOLS lists Heat Sink")
win.grab().save(str(OUT / "flow_inventory.png"))

# ------------------------------------------------------------------- daily / weekly
shell.show_page("operations")
pump(400)
ops = shell.pages["operations"]
before = e.player.credits
ops.daily._claim()
check(e.player.credits > before, "daily streak reward claimed via CLAIM button")
ops.tabs.setCurrentIndex(2)
pump(200)
check(ops.weekly.body.count() >= 4, "weekly challenge cards rendered")

# ------------------------------------------------------------------- network page
shell.show_page("network")
pump(400)
net = shell.pages["network"]
net.map.selected = "echo"
net._select("echo")
net.connect_btn.click()
pump(2500)
while term.busy:
    pump(200)
check(e.world.current == "echo" and shell.current == "terminal", "network map CONNECT runs the command in the terminal")
type_cmd("disconnect")

# ------------------------------------------------------------------- profile / achievements / archives / settings
for page in ("profile", "achievements", "archives", "comms", "settings"):
    shell.show_page(page)
    pump(300)
check(shell.pages["profile"].tiles["MISSIONS COMPLETED"].value.text() == "3", "profile statistics tile")
shell.show_page("achievements")
shell.pages["achievements"].set_category("STORY")
check(shell.pages["achievements"].list.count() > 5, "achievements page lists the STORY category")

# theme purchase + switch through the settings page
e.player._set(credits=50000, level=12)
check(e.market.purchase("theme_cyan")[0], "theme purchased")
shell.show_page("settings")
sp = shell.pages["settings"]
sp._fill_themes()
idx = sp.theme.findData("cyan")
check(idx >= 0, "unlocked theme offered in settings")
sp.theme.setCurrentIndex(idx)
pump(1200)
check(settings.get("theme") == "cyan" and config.COLORS["green"] == "#2de2ff", "theme applied to the whole UI")
settings.set("theme", "default")
win.reload_ui()
shell = win.shell
term = shell.terminal_page.terminal
check(config.COLORS["green"] == "#00ff9c", "theme reset to default")

# ------------------------------------------------------------------- accessibility (D3)
sp = shell.pages["settings"]            # earlier theme reloads replaced the settings page; grab the live one
sp._fill_themes()
check(sp.theme.findData("colorblind") >= 0 and sp.theme.findData("mono") >= 0, "colorblind-safe and mono themes offered in settings")
sp._controls["reduced_motion"].setChecked(True)
pump(200)
check(win.scan.reduce_motion, "reduced motion freezes the scanline overlay")
check(not win.menu.bg.animated and not win.menu.title.enabled and not win.banner.glitch_enabled,
      "reduced motion overrides animations/glitch toggles even if they're individually on")
sp._controls["reduced_motion"].setChecked(False)
pump(200)
check(not win.scan.reduce_motion, "reduced motion off restores normal motion")
check(win.menu.card.name.text() == "TESTER", "callsign shown normally with showcase mode off")
sp._controls["showcase_mode"].setChecked(True)
pump(300)
check(win.menu.card.name.text() == "OPERATOR", "showcase mode masks the callsign in the sidebar")
sp = win.shell.pages["settings"]        # reload_ui() rebuilt the menu/settings page
sp._controls["showcase_mode"].setChecked(False)
pump(300)
check(win.menu.card.name.text() == "TESTER", "turning showcase mode back off unmasks the callsign")

# ------------------------------------------------------------------- save / load slots
win.saves.save_slot(win.engine.db, 1)
slot_info = saves.list_slots()[0]
check(slot_info.slot == 1, "manual save slot written")
for name, dlg in (("pause", PauseMenu(win)), ("slots", SlotDialog(saves, win.engine.db.path, win)), ("load", LoadDialog(saves, win))):
    dlg.show()
    pump(300)
    dlg.grab().save(str(OUT / f"flow_dlg_{name}.png"))
    dlg.close()

# ------------------------------------------------------------------- menu navigation
win.to_menu()
pump(900)
check(win.stack.currentIndex() == win.PAGE_MENU, "back to main menu")
win.on_menu_action("market")
pump(1800)
check(win.stack.currentIndex() == win.PAGE_SHELL and win.shell.current == "market", "menu button MARKET opens the page")
win.to_menu()
pump(900)

# ------------------------------------------------------------------- reload from slot, ending cinematic
win.open_save(slot_info)
pump(3600)
if win.stack.currentIndex() != win.PAGE_SHELL:
    win.on_menu_action("continue")
    pump(1500)
check(win.engine.missions.is_complete("mission_003"), "slot reload keeps progress")
win.engine.trigger_ending("liberation")
pump(1800)
check(win.stack.currentIndex() == win.PAGE_STORY, "ending cinematic started")
win.story._end()
pump(1500)
check(win.stack.currentIndex() == win.PAGE_SHELL, "returned to the game after the ending")
print("mini-games solved:", solved)
win.close()
print("ALL UI FLOW CHECKS PASSED")
