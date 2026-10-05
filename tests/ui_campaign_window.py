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

from PySide6.QtGui import QPixmap

from nexus import config
from nexus.campaign.content import ALL_MISSIONS
from nexus.config import SAVES_DIR
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

# ------------------------------------------------------------------- D3: showcase mode masks the callsign
config.set_showcase_mode(True)
win.panel.update_stats(win.profile)
check("Kestrel" not in win.panel.stats.text() and "OPERATOR" in win.panel.stats.text(), "showcase mode masks the callsign in the mission panel")
config.set_showcase_mode(False)
win.panel.update_stats(win.profile)
check("Kestrel" in win.panel.stats.text(), "turning showcase mode back off unmasks the callsign")

# ------------------------------------------------------------------- D1: profile card / share image
win._share_profile()
saved_name = win.toolbar_status.text().removeprefix("Saved: ")
check(saved_name.startswith("nexus_profile_") and saved_name.endswith(".png"), "share profile saves a PNG and reports its name")
saved_path = SAVES_DIR / "screenshots" / saved_name
check(saved_path.exists(), "the profile card PNG actually exists on disk")
loaded = QPixmap(str(saved_path))
check(loaded.width() == 1200 and loaded.height() == 675, "profile card is the expected 1200x675 share-image size")
saved_path.unlink()


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

# D1: the mission map as a graph (early playthrough state: exactly one done, exactly one up next)
win._open_mission_map()
pump()
early_nodes = [it for it in win.mission_map_dialog.scene.items() if it.data(0)]
early_statuses = {it.data(0): it.data(1) for it in early_nodes}
check(early_statuses["act1_m01"] == "complete", "mission map marks the finished mission as complete")
check(early_statuses["act1_m02"] == "up next", "mission map marks the actual next mission as up next")
check(early_statuses["act1_m03"] == "locked", "mission map marks a not-yet-reachable mission as locked")
win.mission_map_dialog.close()

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

# C6 guided mode: a command's lesson text appears the first time it's used (whoami: not run by anything earlier
# in this script, so it's a clean "never seen" probe — ls/cat/echo were all already run in Medium mode above,
# and Medium now marks a lesson seen too, same as Guided, just with shorter text)
win.profile.set_mode("guided")
check(not win.profile.has_seen_lesson("whoami"), "lesson unseen before first use")
win.terminal.run_command("whoami")
pump()
check(win.profile.has_seen_lesson("whoami"), "lesson marked seen after first use")
check("[LESSON]" in win.terminal.output.toPlainText(), "lesson text printed into the terminal")
win.terminal.output.clear()
win.terminal.run_command("whoami")
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

# F1: the daily op - same cached mission every time it's (re)started today
win._start_daily_mission()
pump()
daily_mission = win.current_mission
check(daily_mission is not None and daily_mission.id.startswith("daily_"), "daily op generated")
win._start_daily_mission()
pump()
check(win.current_mission.id == daily_mission.id, "starting the daily op again today reuses the same cached mission")

# German localization (nexus.campaign.i18n), if act1_m01 has a registered translation
from nexus import i18n as ui_i18n
from nexus.campaign.i18n import TRANSLATIONS
act1_m01 = next(m for m in ALL_MISSIONS if m.id == "act1_m01")
if "de" in TRANSLATIONS.get("act1_m01", {}):
    ui_i18n.set_language("de")
    win._play_mission(act1_m01, level=lambda: 1)
    pump()
    check(win.current_mission.title != act1_m01.title, "german translation changes the displayed title")
    win.grab().save(str(OUT / "campaign_german.png"))
    ui_i18n.set_language("en")

# C6: the lexicon — look up anything unlocked, any time, with search
win.profile.db.update_profile(level=50)
win._open_lexicon()
pump()
check(win.lexicon_dialog is not None, "lexicon opens")
check(win.lexicon_dialog.list.count() > 0, "lexicon lists unlocked commands")
all_count = win.lexicon_dialog.list.count()
win.lexicon_dialog.search.setText("grep")
pump()
check(0 < win.lexicon_dialog.list.count() < all_count, "search narrows the list")
win.lexicon_dialog.list.setCurrentRow(0)
pump()
check("grep" in win.lexicon_dialog.detail.text().lower(), "selecting an entry shows its lesson text")
win.lexicon_dialog.search.setText("")
pump()
check(win.lexicon_dialog.list.count() == all_count, "clearing the search restores the full list")
win.lexicon_dialog.grab().save(str(OUT / "campaign_lexicon.png"))

# D1: the mission map as a graph
win._open_mission_map()
pump()
check(win.mission_map_dialog is not None, "mission map opens")
nodes = [it for it in win.mission_map_dialog.scene.items() if it.data(0)]
check(len(nodes) == len(ALL_MISSIONS), "mission map draws a node for every mission")
statuses = [it.data(1) for it in nodes]
# by this point in the script the whole 200-level campaign is already finished (see "C7 buttons appear" above)
check(statuses.count("complete") == len(ALL_MISSIONS), "every mission shown as complete once the campaign is finished")
check(statuses.count("up next") == 0, "nothing marked as up next once there's nothing left to play")
win.mission_map_dialog.grab().save(str(OUT / "campaign_mission_map.png"))
win.mission_map_dialog.close()

# C6: Medium mode shows a short one-liner instead of the full lesson
m2 = next(m for m in ALL_MISSIONS if m.id == "act1_m02")
win.profile.set_mode("medium")
win._play_mission(m2, level=lambda: 50)
pump()
win.terminal.run_command("cat welcome.txt")
pump()
out = win.terminal.output.toPlainText()
check("[cat]" in out, "medium mode shows a short [command] notice")
check("[LESSON]" not in out, "medium mode does not show the full guided-mode lesson")

# C6: a handful of commands with no objective progress gently offers a hint
m3 = next(m for m in ALL_MISSIONS if m.id == "act1_m03")
win.profile.set_mode("medium")
win._play_mission(m3, level=lambda: 50)
pump()
win.panel.hint_label.setText("")
for _ in range(5):
    win.terminal.run_command("pwd")
    pump()
check(bool(win.panel.hint_label.text()), "five unproductive commands auto-offer a hint")
check("[STUCK?]" in win.terminal.output.toPlainText(), "the auto-offered hint is also printed into the terminal")

win.db.close()

# --- the real finale flow: complete everything up to the last mission live, then play the finale for real ---
saves2 = SaveSystem(profiles_dir=root / "profiles2", slots_dir=root / "slots2")
win2 = CampaignWindow(saves2, default_username="finisher")
win2.resize(1220, 780)
win2.show()
pump()
win2.character_dialog.name_input.setText("Finisher")
win2.character_dialog.ok_btn.click()
pump()

finale = next(m for m in ALL_MISSIONS if "finale" in m.tags)
for m in ALL_MISSIONS:
    if m.id != finale.id:
        win2.profile.complete_mission(m, ALL_MISSIONS)
win2._load_mission()
pump()
check(win2.current_mission is not None and win2.current_mission.id == finale.id, "only the finale is left")

for line in finale.solution:
    win2.terminal.run_command(line)
    pump()
check(win2.runner.is_complete, "the finale's own solution completes it")
check(win2.ending_select_dialog is not None, "completing the finale opens the ending choice")
check(not win2.panel.continue_btn.isVisible(), "no plain CONTINUE past the finale — the ending dialog decides")
reachable_ids = {win2.ending_select_dialog.list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(win2.ending_select_dialog.list.count())}
# every mission except the finale was bulk-completed above, including the clue and secret-ending-track missions,
# so the secret ending is legitimately reachable here too.
check(reachable_ids == {"A", "B", "C", "D"}, "all four endings are offered when every requirement was actually met")
win2.grab().save(str(OUT / "campaign_ending_choice.png"))

first_ending_item = win2.ending_select_dialog.list.item(0)
chosen_id = first_ending_item.data(Qt.ItemDataRole.UserRole)
win2.ending_select_dialog._on_pick(first_ending_item)
pump()
check(win2.ending_select_dialog is None, "ending dialog closes after a choice")
check(win2.profile.db.get_profile()["ending"] == chosen_id, "the chosen ending is saved to the profile")
check(win2.terminal is None and win2.current_mission is None, "the epilogue replaces the terminal, not another mission")
from nexus.campaign.endings import ENDINGS
check(ENDINGS[chosen_id].title.upper() in win2.panel.header.text(), "the epilogue names the chosen ending")
win2.grab().save(str(OUT / "campaign_epilogue.png"))

win2.panel.replay_btn.click()
pump()
check(win2.mission_select_dialog is not None, "C7 still works after choosing an ending")
win2.mission_select_dialog.reject()
win2.db.close()

print("ALL OK — screenshots in", OUT)
