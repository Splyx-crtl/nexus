"""UI test: the 3.0 campaign window (ui/campaign_window.py) — mission loading, live objective tracking, XP/level
progression, hint tiers, decision capture, and the campaign-finished/endings screen. Run with QT_QPA_PLATFORM=windows
(offscreen has no fonts, see ui_shell_terminal.py)."""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ["NEXUS_NO_AUDIO"] = "1"
os.environ["NEXUS_LICENSE_PUBKEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from nexus.campaign.content import ALL_MISSIONS
from nexus.campaign.runner import MissionRunner
from nexus.save_system import SaveSystem
from ui.campaign_window import CampaignWindow
from ui.widgets import build_stylesheet, load_custom_fonts

OUT = Path(os.environ.get("NEXUS_SHOTS", tempfile.mkdtemp(prefix="nexus_shots_")))
OUT.mkdir(exist_ok=True)
app = QApplication([])
load_custom_fonts()
app.setStyleSheet(build_stylesheet(12))

tmp = tempfile.TemporaryDirectory()
root = Path(tmp.name)
saves = SaveSystem(profiles_dir=root / "profiles", slots_dir=root / "slots")
win = CampaignWindow(saves, default_username="operator")
win.resize(1220, 780)
win.show()


def pump(ms=120):
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("ok:", msg)


pump()
check(win.character_dialog is not None, "a brand-new profile is asked for a callsign first")
check(win.current_mission is None, "no mission loads until the character dialog is answered")
win.character_dialog.name_input.setText("Kestrel")
win.character_dialog.look_input.setPlainText("quiet, methodical")
win.character_dialog.mode_buttons["medium"].setChecked(True)
win.character_dialog.ok_btn.click()
pump()
check(win.character_dialog is None, "dialog closes itself after submission")
check(win.profile.get_character() == {"name": "Kestrel", "look": "quiet, methodical"}, "character saved to the profile")
check(win.profile.get_mode() == "medium", "chosen help mode saved to the profile")
check("Kestrel" in win.panel.stats.text(), "callsign shown in the mission panel")
win.grab().save(str(OUT / "campaign_character.png"))


pump()
check(win.current_mission is not None and win.current_mission.id == "act1_m01", "opens on level 1")
check(win.profile.level == 1 and win.profile.xp == 0, "fresh profile starts at level 1, 0 xp")

m1 = win.current_mission
for line in m1.solution:
    win.terminal.run_command(line)
    pump()
check(win.profile.is_completed("act1_m01"), "solution completes the mission")
check(win.profile.level == 2, "completing level 1 advances to level 2")
check(win.profile.xp == m1.reward_xp, "xp equals the mission's reward")
check(win.panel.continue_btn.isVisible(), "continue button appears after completion")
check("[x]" in win.panel._obj_labels[0].text(), "objective marked done in the panel")
win.grab().save(str(OUT / "campaign_m1_done.png"))

win.panel.continue_btn.click()
pump()
check(win.current_mission.id == "act1_m02", "continue advances to the next mission")

# decision capture, driven directly against a decision-tagged mission
decision_mission = next(m for m in ALL_MISSIONS if any(t.startswith("decision:") for t in m.tags))
win.current_mission = decision_mission
win.runner = MissionRunner.start(decision_mission, level=lambda: 200)
win._swap_terminal()
win.panel.set_mission(decision_mission, win.profile)
pump()
win.terminal.run_command("echo 'the player picks a side'")
pump()
tag = next(t for t in decision_mission.tags if t.startswith("decision:"))
check(win.profile.get_decision(tag) == "the player picks a side", "decision text captured from the echo command")
win.grab().save(str(OUT / "campaign_decision.png"))

# hint tiers
win.current_mission = win.profile.next_mission(ALL_MISSIONS) or ALL_MISSIONS[1]
win.runner = MissionRunner.start(win.current_mission, level=lambda: win.current_mission.number)
win._swap_terminal()
win.panel.set_mission(win.current_mission, win.profile)
win._on_hint()
first_hint = win.panel.hint_label.text()
win._on_hint()
second_hint = win.panel.hint_label.text()
check(bool(first_hint) and first_hint != second_hint, "hint button advances through tiers")

# C6 guided mode: a command's lesson text appears the first time it's used
win.profile.set_mode("guided")
check(not win.profile.has_seen_lesson("ls"), "lesson unseen before first use")
win.terminal.run_command("ls")
pump()
check(win.profile.has_seen_lesson("ls"), "lesson marked seen after first use")
check("[LESSON]" in win.terminal.output.toPlainText(), "lesson text printed into the terminal")
win.terminal.output.clear()
win.terminal.run_command("ls")
pump()
check("[LESSON]" not in win.terminal.output.toPlainText(), "lesson not repeated on later uses")
win.profile.set_mode("medium")

# campaign-finished path
for m in ALL_MISSIONS:
    win.profile.complete_mission(m, ALL_MISSIONS)
win._load_mission()
pump()
check(win.current_mission is None and win.terminal is None, "finished state clears the active mission/terminal")
check("CAMPAIGN COMPLETE" in win.panel.header.text(), "finished screen shown")
check("Full Truth" in win.panel.debrief.text(), "secret ending listed once every clue/track mission is done")
check(win.panel.replay_btn.isVisible() and win.panel.endless_btn.isVisible(), "C7 buttons appear once the campaign is done")
win.grab().save(str(OUT / "campaign_finished.png"))

# C7: replay any of the 200 missions freely
win.panel.replay_btn.click()
pump()
check(win.mission_select_dialog is not None, "replay opens the mission-select dialog")
check(win.mission_select_dialog.list.count() == len(ALL_MISSIONS), "every mission listed")
first_item = win.mission_select_dialog.list.item(0)
win.mission_select_dialog._on_pick(first_item)
pump()
check(win.mission_select_dialog is None, "dialog closes after picking")
check(win.current_mission is not None and win.current_mission.id == first_item.data(Qt.ItemDataRole.UserRole), "picked mission loads")
for line in win.current_mission.solution:
    win.terminal.run_command(line)
    pump()
check(win.runner.is_complete, "a replayed mission can be solved again")
win.panel.continue_btn.click()
pump()
check(win.current_mission is None, "finishing a replay returns to the C7 hub (nothing left to require)")
win.grab().save(str(OUT / "campaign_replay.png"))

# C7: endless ops keep generating fresh missions
win.panel.endless_btn.click()
pump()
check(win.current_mission is not None and win.current_mission.id.startswith("endless_replay_1_"), "endless op generated")
endless_mission = win.current_mission
for line in endless_mission.solution:
    win.terminal.run_command(line)
    pump()
check(win.runner.is_complete, "a generated endless op is itself solvable")
win.panel.continue_btn.click()
pump()
win.panel.endless_btn.click()
pump()
check(win.current_mission.id != endless_mission.id, "a second endless op is a different generated mission")
win.grab().save(str(OUT / "campaign_endless.png"))

win.db.close()
print("ALL OK — screenshots in", OUT)
