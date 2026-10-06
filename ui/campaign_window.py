"""The 3.0 campaign, playable for the first time from the real app: a standalone window pairing ``ShellTerminal``
(ui/shell_terminal.py, the real bash/PowerShell/cmd engine) with a live mission panel, backed by a v3 save profile
(nexus/campaign/profile.py).

Deliberately a separate top-level window rather than a graft into ``AppShell``/``GameEngine``: that pair is built
around 2.x-only mechanics (heat, trace, market, loadout, gear) that the 3.0 design replaces outright, not extends,
and MainWindow's state machine (music moods, banners, the tutorial overlay, F-key shortcuts) is tightly coupled to
those mechanics too. Opening a self-contained window is the lowest-risk way to make the finished 200-level campaign
(docs/3.0-PROGRESS.md: all nine acts complete) genuinely playable end to end while that larger integration — folding
this into AppShell properly, or retiring the 2.x UI per the project's "full replacement" decision — happens later,
ideally with the user able to click through it rather than it being GUI surgery done blind in one sitting.
"""
from __future__ import annotations

import random

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow, QPushButton, QScrollArea,
    QToolBar, QVBoxLayout, QWidget,
)

from nexus.campaign.content import ALL_MISSIONS
from nexus.campaign.endless import generate_endless_mission
from nexus.campaign.i18n import localize as localize_mission
from nexus.campaign import translations as _campaign_translations  # noqa: F401 (registers TRANSLATIONS on import)
from nexus.campaign.migrate import ensure_v3_profile
from nexus.campaign.mission import Mission
from nexus.campaign.profile import CampaignProfile
from nexus.campaign.runner import MissionRunner
from nexus.config import COLORS, mask_name
from nexus.i18n import language as ui_language
from nexus.save_system import SaveSystem

from .shell_terminal import ShellTerminal
from .widgets import NeonButton, hline, mono_font

HINT_LABELS = ["NUDGE", "TIP", "SOLUTION"]


class MissionPanel(QWidget):
    """Briefing / objectives / hints / debrief sidebar for the mission currently in the terminal."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(320)
        self.setMaximumWidth(380)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 10, 12)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setSpacing(8)

        self.header = QLabel("")
        self.header.setWordWrap(True)
        self.header.setStyleSheet(f"color:{COLORS['green']}; font-size:16px; font-weight:bold;")
        self.stats = QLabel("")
        self.stats.setWordWrap(True)
        self.stats.setStyleSheet(f"color:{COLORS['cyan']}; font-weight:bold;")
        self.briefing_title = QLabel("BRIEFING")
        self.briefing_title.setObjectName("h2")
        self.briefing = QLabel("")
        self.briefing.setWordWrap(True)
        self.objectives_title = QLabel("OBJECTIVES")
        self.objectives_title.setObjectName("h2")
        self.objectives_box = QVBoxLayout()
        self.objectives_box.setSpacing(4)
        obj_widget = QWidget()
        obj_widget.setLayout(self.objectives_box)
        self.hint_btn = NeonButton("[ HINT ]", "Show the next hint tier for your current objective")
        self.hint_label = QLabel("")
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet(f"color:{COLORS['amber']};")
        self.debrief_title = QLabel("DEBRIEF")
        self.debrief_title.setObjectName("h2")
        self.debrief_title.hide()
        self.debrief = QLabel("")
        self.debrief.setWordWrap(True)
        self.continue_btn = NeonButton("[ CONTINUE ]", "Move on to the next mission")
        self.continue_btn.hide()
        self.replay_btn = NeonButton("[ REPLAY A MISSION ]", "Pick any of the 200 missions to run again (C7)")
        self.replay_btn.hide()
        self.endless_btn = NeonButton("[ KEEP GOING (ENDLESS) ]", "One more procedurally-generated op, for as long as you want")
        self.endless_btn.hide()
        self.daily_btn = NeonButton("[ DAILY OP ]", "Today's op - the same seed for every player, every day")
        self.daily_btn.hide()

        for w in (self.header, self.stats, hline(), self.briefing_title, self.briefing, hline(),
                 self.objectives_title, obj_widget, self.hint_btn, self.hint_label,
                 self.debrief_title, self.debrief, self.continue_btn, self.replay_btn, self.endless_btn, self.daily_btn):
            lay.addWidget(w)
        lay.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        self._obj_labels: list[QLabel] = []
        self._hint_tier = 0

    def set_mission(self, mission: Mission, profile: CampaignProfile) -> None:
        self.header.setText(f"LEVEL {mission.number} — {mission.title}")
        self.update_stats(profile)
        self.briefing.setText("\n".join(mission.briefing) or "—")
        self.debrief.setText("")
        self.debrief_title.hide()
        self.continue_btn.hide()
        self.replay_btn.hide()
        self.endless_btn.hide()
        self.daily_btn.hide()
        self._hint_tier = 0
        self.hint_label.setText("")
        self.hint_btn.setVisible(profile.get_mode() != "hardcore")
        self._rebuild_objectives(mission)

    def update_stats(self, profile: CampaignProfile) -> None:
        name = mask_name(profile.get_character().get("name") or profile.username)
        self.stats.setText(f"{name}   ·   RANK {profile.rank}   ·   LEVEL {profile.level}   ·   XP {profile.xp}")

    def _rebuild_objectives(self, mission: Mission) -> None:
        while self.objectives_box.count():
            item = self.objectives_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._obj_labels = []
        for o in mission.objectives:
            lbl = QLabel(f"[ ] {o.text}" + ("  (bonus)" if o.optional else ""))
            lbl.setWordWrap(True)
            self.objectives_box.addWidget(lbl)
            self._obj_labels.append(lbl)

    def refresh_objectives(self, runner: MissionRunner) -> None:
        for lbl, state in zip(self._obj_labels, runner.states):
            mark = "[x]" if state.done else "[ ]"
            suffix = "  (bonus)" if state.objective.optional else ""
            lbl.setText(f"{mark} {state.objective.text}{suffix}")
            lbl.setStyleSheet(f"color:{COLORS['green'] if state.done else COLORS['text']};")

    def next_hint(self, runner: MissionRunner) -> str | None:
        target = next((s for s in runner.required_states if not s.done and s.objective.hints), None)
        if target is None:
            return None
        tier = min(self._hint_tier, len(target.objective.hints) - 1)
        text = target.objective.hints[tier]
        label = HINT_LABELS[min(tier, len(HINT_LABELS) - 1)]
        if self._hint_tier < len(target.objective.hints) - 1:
            self._hint_tier += 1
        return f"[{label}] {text}"

    def show_debrief(self, mission: Mission) -> None:
        self.debrief_title.show()
        self.debrief.setText("\n".join(mission.debrief) or "—")
        self.continue_btn.show()

    def show_finished(self, profile: CampaignProfile, all_missions: list[Mission]) -> None:
        self.header.setText("CAMPAIGN COMPLETE")
        self.update_stats(profile)
        self.briefing.setText("")
        self._rebuild_objectives_cleared()
        self.hint_btn.hide()
        self.hint_label.setText("")
        self.debrief_title.show()
        chosen_id = profile.db.get_profile().get("ending")
        if chosen_id:
            from nexus.campaign.endings import ENDINGS
            ending = ENDINGS[chosen_id]
            self.debrief.setText(f"Your ending: {ending.title} ({ending.subtitle})\n\n{ending.summary}")
        else:
            endings = profile.reachable_endings(all_missions)
            lines = ["Endings reachable with what you found this run:", ""]
            lines += [f"  {e.title} ({e.subtitle})" for e in endings]
            self.debrief.setText("\n".join(lines))
        self.continue_btn.hide()
        self.replay_btn.show()
        self.endless_btn.show()
        self.daily_btn.show()

    def show_epilogue(self, ending, profile: CampaignProfile) -> None:
        self.header.setText(f"ENDING: {ending.title.upper()}")
        self.update_stats(profile)
        self.briefing.setText("")
        self._rebuild_objectives_cleared()
        self.hint_btn.hide()
        self.hint_label.setText("")
        self.debrief_title.show()
        self.debrief.setText(f"{ending.title} — {ending.subtitle}\n\n{ending.summary}")
        self.continue_btn.hide()
        self.replay_btn.show()
        self.endless_btn.show()
        self.daily_btn.show()

    def _rebuild_objectives_cleared(self) -> None:
        while self.objectives_box.count():
            item = self.objectives_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._obj_labels = []


class MissionSelectDialog(QDialog):
    """C7: after level 200, every mission is freely selectable and repeatable. Non-blocking by the same convention
    as CharacterDialog — connect ``picked`` and call ``show()``, not ``exec()``."""

    picked = Signal(str)       # mission id

    def __init__(self, all_missions: list[Mission], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Replay a Mission")
        self.resize(520, 640)
        self.setStyleSheet(f"QDialog {{ background:{COLORS['bg']}; }}")
        lay = QVBoxLayout(self)
        title = QLabel("PICK A MISSION TO REPLAY")
        title.setStyleSheet(f"color:{COLORS['green']}; font-size:14px; font-weight:bold;")
        lay.addWidget(title)
        self.list = QListWidget()
        self.list.setFont(mono_font(11))
        for m in sorted(all_missions, key=lambda m: m.number):
            item = QListWidgetItem(f"LEVEL {m.number:>3}  —  {m.title}  [{m.size}]")
            item.setData(Qt.ItemDataRole.UserRole, m.id)
            self.list.addItem(item)
        self.list.itemDoubleClicked.connect(self._on_pick)
        lay.addWidget(self.list, 1)
        go_btn = NeonButton("[ PLAY ]", "Run the selected mission again")
        go_btn.clicked.connect(lambda: self.list.currentItem() and self._on_pick(self.list.currentItem()))
        lay.addWidget(go_btn)

    def _on_pick(self, item: QListWidgetItem) -> None:
        self.picked.emit(item.data(Qt.ItemDataRole.UserRole))
        self.accept()


class EndingSelectDialog(QDialog):
    """C5/decision:8: the finale itself (act9_m200, tagged "finale"). Lists only the endings
    nexus/campaign/endings.py's reachable_endings() actually returns for this save — the secret ending only
    appears here if its real requirements (clues 2/5/8 + the Act IX side-mission) were met. Non-blocking, same
    convention as the other dialogs."""

    chosen = Signal(str)       # ending id

    def __init__(self, endings: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("The Choice")
        self.resize(560, 420)
        self.setStyleSheet(f"QDialog {{ background:{COLORS['bg']}; }}")
        lay = QVBoxLayout(self)
        title = QLabel("WHAT HAPPENS TO NEXUS AND ZERO?")
        title.setStyleSheet(f"color:{COLORS['green']}; font-size:14px; font-weight:bold;")
        lay.addWidget(title)
        self.list = QListWidget()
        self.list.setFont(mono_font(11))
        self.list.setWordWrap(True)
        for e in endings:
            item = QListWidgetItem(f"{e.title} ({e.subtitle})\n{e.summary}")
            item.setData(Qt.ItemDataRole.UserRole, e.id)
            self.list.addItem(item)
        self.list.itemDoubleClicked.connect(self._on_pick)
        lay.addWidget(self.list, 1)
        go_btn = NeonButton("[ DECIDE ]", "This is final for this save")
        go_btn.clicked.connect(lambda: self.list.currentItem() and self._on_pick(self.list.currentItem()))
        lay.addWidget(go_btn)

    def _on_pick(self, item: QListWidgetItem) -> None:
        self.chosen.emit(item.data(Qt.ItemDataRole.UserRole))
        self.accept()


class CampaignWindow(QMainWindow):
    def __init__(self, saves: SaveSystem, default_username: str = "operator", parent=None, sound=None):
        super().__init__(parent)
        self.setWindowTitle("NEXUS // TERMINAL — Campaign 3.0 (beta)")
        self.resize(1220, 780)
        self.setMinimumSize(900, 600)

        if sound is None:
            from nexus.audio import SoundManager
            sound = SoundManager(None)
        self.sound = sound
        self.sound.set_music("terminal")

        self.saves = saves
        self.db = ensure_v3_profile(saves, default_username)
        self.profile = CampaignProfile(self.db)
        self.all_missions = ALL_MISSIONS
        self.current_mission: Mission | None = None
        self.runner: MissionRunner | None = None
        self.terminal: ShellTerminal | None = None
        self.lexicon_dialog = None

        toolbar = QToolBar("Reference")
        toolbar.setMovable(False)
        toolbar.setStyleSheet(f"QToolBar {{ background:{COLORS['bg_alt']}; border-bottom:1px solid {COLORS['border']}; spacing:8px; padding:4px; }}")
        lexicon_btn = NeonButton("[ LEXICON ]", "Look up anything you've unlocked, any time (not just the first time)")
        lexicon_btn.clicked.connect(self._open_lexicon)
        toolbar.addWidget(lexicon_btn)
        share_btn = NeonButton("[ SHARE PROFILE ]", "Save a PNG summary of your profile (callsign, rank, progress) to saves/screenshots")
        share_btn.clicked.connect(self._share_profile)
        toolbar.addWidget(share_btn)
        map_btn = NeonButton("[ MISSION MAP ]", "See your progress across all 9 acts at a glance")
        map_btn.clicked.connect(self._open_mission_map)
        toolbar.addWidget(map_btn)
        self.mission_map_dialog = None
        self.toolbar_status = QLabel("")
        self.toolbar_status.setStyleSheet(f"color:{COLORS['dim']}; padding-left:8px;")
        toolbar.addWidget(self.toolbar_status)
        self.addToolBar(toolbar)

        central = QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet(f"background:{COLORS['bg']};")
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.panel = MissionPanel()
        self.panel.hint_btn.clicked.connect(self._on_hint)
        self.panel.continue_btn.clicked.connect(self._load_mission)
        self.panel.replay_btn.clicked.connect(self._open_mission_select)
        self.panel.endless_btn.clicked.connect(self._start_endless_mission)
        self.panel.daily_btn.clicked.connect(self._start_daily_mission)
        lay.addWidget(self.panel)
        self.terminal_holder = QWidget()
        hold_lay = QVBoxLayout(self.terminal_holder)
        hold_lay.setContentsMargins(10, 10, 10, 10)
        lay.addWidget(self.terminal_holder, 1)

        self.mission_select_dialog = None
        self.ending_select_dialog = None
        self._endless_counter = 0
        self._stuck_counter = 0
        self._daily_missions: dict[str, Mission] = {}      # cache: same id can't be registered with generate_endless_mission twice
        self.character_dialog = None
        if self.profile.completed_count == 0 and not self.profile.get_character()["name"]:
            self._show_character_dialog()
        else:
            self._load_mission()

    def _show_character_dialog(self) -> None:
        from .character_dialog import CharacterDialog
        self.character_dialog = CharacterDialog(self)
        self.character_dialog.created.connect(self._on_character_created)
        self.character_dialog.show()

    def _on_character_created(self, name: str, look: str, mode: str) -> None:
        self.profile.set_character(name, look)
        self.profile.set_mode(mode)
        self.character_dialog = None
        self._load_mission()

    # ------------------------------------------------------------------ mission lifecycle
    def _load_mission(self) -> None:
        mission = self.profile.next_mission(self.all_missions)
        if mission is None:
            self._on_campaign_finished()
            return
        self._play_mission(mission, level=lambda: self.profile.level)

    def _play_mission(self, mission: Mission, level) -> None:
        mission = localize_mission(mission, ui_language())
        self.current_mission = mission
        self._stuck_counter = 0
        self.runner = MissionRunner.start(mission, level=level)
        self._swap_terminal()
        self.panel.set_mission(mission, self.profile)
        self.terminal.print_system(f"=== LEVEL {mission.number}: {mission.title} ===", COLORS["green"])
        for line in mission.briefing:
            self.terminal.print_system(line, COLORS["cyan"])

    # -- C7: post-200 free mission select / endless ops --------------------------------------------------------------
    def _open_mission_select(self) -> None:
        self.mission_select_dialog = MissionSelectDialog(self.all_missions, self)
        self.mission_select_dialog.picked.connect(self._on_mission_picked)
        self.mission_select_dialog.show()

    def _on_mission_picked(self, mission_id: str) -> None:
        self.mission_select_dialog = None
        mission = next(m for m in self.all_missions if m.id == mission_id)
        from nexus.campaign.progression import MAX_LEVEL
        self._play_mission(mission, level=lambda: MAX_LEVEL)

    def _start_endless_mission(self) -> None:
        from nexus.campaign.progression import MAX_LEVEL
        self._endless_counter += 1
        seed = random.randint(0, 10**9)
        mission = generate_endless_mission(f"endless_replay_{self._endless_counter}_{seed}", MAX_LEVEL, 9, seed)
        self._play_mission(mission, level=lambda: MAX_LEVEL)

    def _start_daily_mission(self) -> None:
        """F1: the same op for every player, every day (nexus/campaign/daily.py) - cached per id, since
        generate_endless_mission refuses to register the same mission_id twice in one process."""
        from nexus.campaign.daily import daily_mission_id, daily_seed
        from nexus.campaign.progression import MAX_LEVEL
        mid = daily_mission_id()
        mission = self._daily_missions.get(mid)
        if mission is None:
            mission = generate_endless_mission(mid, MAX_LEVEL, 9, daily_seed())
            self._daily_missions[mid] = mission
        self._play_mission(mission, level=lambda: MAX_LEVEL)

    def _swap_terminal(self) -> None:
        if self.terminal is not None:
            self.terminal_holder.layout().removeWidget(self.terminal)
            self.terminal.deleteLater()
        self.terminal = ShellTerminal(self.runner.shell)
        self.terminal.setFont(mono_font(12))
        self.terminal.command_run.connect(self._on_command)
        self.terminal_holder.layout().addWidget(self.terminal)
        self.terminal.focus_input()

    def _on_command(self, line: str) -> None:
        hits_before = sum(s.hits for s in self.runner.states)
        self.panel.refresh_objectives(self.runner)
        self._maybe_record_decision(line)
        self._maybe_show_lesson(line)
        if sum(s.hits for s in self.runner.states) > hits_before:
            self._stuck_counter = 0           # real progress — the player isn't stuck
            if not self.runner.is_complete:
                self.sound.play("notify")
        else:
            self._maybe_offer_hint()
        if self.runner.is_complete:
            self._on_mission_complete()

    def _maybe_show_lesson(self, line: str) -> None:
        """C6: explain a command the first time it's used, not just on unlock — the full lesson in Guided mode,
        a short one-liner in Medium mode ("kurze Freischalt-Meldung"), nothing in Hardcore."""
        mode = self.profile.get_mode()
        if mode == "hardcore":
            return
        name = line.strip().split(None, 1)[0] if line.strip() else ""
        if not name or self.profile.has_seen_lesson(name):
            return
        from nexus.shell.registry import lookup
        from .shell_terminal import _family_of
        family = _family_of(self.runner.shell.session.shell)
        spec = lookup(family, name)
        if spec is None or not spec.lesson:
            return
        self.profile.mark_lesson_seen(name)
        if mode == "guided":
            self.terminal.print_system(f"[LESSON] {spec.lesson}", COLORS["purple"])
        else:
            self.terminal.print_system(f"[{name}] {spec.summary}", COLORS["purple"])

    def _maybe_offer_hint(self) -> None:
        """C6 "Angebot nach Fehlversuchen": a handful of commands in a row with no objective progress gently
        offers the hint button's next tier, instead of waiting for the player to find it themselves. Not shown in
        Hardcore mode, which deliberately offers no help at all."""
        if self.profile.get_mode() == "hardcore" or self.runner is None or self.runner.is_complete:
            return
        self._stuck_counter += 1
        if self._stuck_counter < 5:
            return
        self._stuck_counter = 0
        hint = self.panel.next_hint(self.runner)
        if hint:
            self.panel.hint_label.setText(hint)
            self.terminal.print_system(f"[STUCK?] {hint}", COLORS["amber"])

    def _maybe_record_decision(self, line: str) -> None:
        mission = self.current_mission
        tag = next((t for t in mission.tags if t.startswith("decision:")), None)
        if tag is None:
            return
        stripped = line.strip()
        if not stripped.lower().startswith("echo "):
            return
        text = stripped[5:].strip()
        if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
            text = text[1:-1]
        self.profile.record_decision(tag, text, mission.id)

    def _on_mission_complete(self) -> None:
        mission = self.current_mission
        self.profile.complete_mission(mission, self.all_missions)
        self.panel.update_stats(self.profile)
        self.panel.show_debrief(mission)
        self.sound.play("achievement" if mission.size == "milestone" else "complete")
        for line in mission.debrief:
            self.terminal.print_system(line, COLORS["amber"])
        self.terminal.focus_input()
        if "finale" in mission.tags and not self.profile.db.get_profile().get("ending"):
            self.panel.continue_btn.hide()        # the ending dialog decides what happens next, not CONTINUE
            self._show_ending_select()

    def _show_ending_select(self) -> None:
        reachable = self.profile.reachable_endings(self.all_missions)
        self.ending_select_dialog = EndingSelectDialog(reachable, self)
        self.ending_select_dialog.chosen.connect(self._on_ending_chosen)
        self.ending_select_dialog.show()

    def _on_ending_chosen(self, ending_id: str) -> None:
        from nexus.campaign.endings import ENDINGS
        self.profile.set_ending(ending_id)
        self.sound.play("levelup")
        self.ending_select_dialog = None
        self.current_mission = None
        self.runner = None
        if self.terminal is not None:
            self.terminal_holder.layout().removeWidget(self.terminal)
            self.terminal.deleteLater()
            self.terminal = None
        self.panel.show_epilogue(ENDINGS[ending_id], self.profile)

    def _on_hint(self) -> None:
        if self.runner is None:
            return
        hint = self.panel.next_hint(self.runner)
        self.panel.hint_label.setText(hint or "No hints left — you've got everything you need.")

    def _open_lexicon(self) -> None:
        from .lexicon_dialog import LexiconDialog
        self.lexicon_dialog = LexiconDialog(self.profile.level, self)
        self.lexicon_dialog.show()

    def _share_profile(self) -> None:
        import time

        from nexus.config import SAVES_DIR

        from .profile_card import render_profile_card
        folder = SAVES_DIR / "screenshots"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"nexus_profile_{time.strftime('%Y%m%d_%H%M%S')}.png"
        render_profile_card(self.profile, total_missions=len(self.all_missions)).save(str(path))
        self.toolbar_status.setText(f"Saved: {path.name}")

    def _open_mission_map(self) -> None:
        from .mission_map_dialog import MissionMapDialog
        self.mission_map_dialog = MissionMapDialog(self.all_missions, self.profile, self)
        self.mission_map_dialog.show()

    def _on_campaign_finished(self) -> None:
        self.current_mission = None
        self.runner = None
        if self.terminal is not None:
            self.terminal_holder.layout().removeWidget(self.terminal)
            self.terminal.deleteLater()
            self.terminal = None
        self.panel.show_finished(self.profile, self.all_missions)

    # ------------------------------------------------------------------ lifecycle
    def closeEvent(self, event: QCloseEvent) -> None:
        self.db.flush()
        self.sound.set_music("menu")       # this window doesn't live in MainWindow's own page stack, so nothing
        super().closeEvent(event)          # else would revert the mood once it closes
