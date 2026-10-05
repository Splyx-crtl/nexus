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

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMainWindow, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from nexus.campaign.content import ALL_MISSIONS
from nexus.campaign.migrate import ensure_v3_profile
from nexus.campaign.mission import Mission
from nexus.campaign.profile import CampaignProfile
from nexus.campaign.runner import MissionRunner
from nexus.config import COLORS
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

        for w in (self.header, self.stats, hline(), self.briefing_title, self.briefing, hline(),
                 self.objectives_title, obj_widget, self.hint_btn, self.hint_label,
                 self.debrief_title, self.debrief, self.continue_btn):
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
        self._hint_tier = 0
        self.hint_label.setText("")
        self.hint_btn.setVisible(profile.get_mode() != "hardcore")
        self._rebuild_objectives(mission)

    def update_stats(self, profile: CampaignProfile) -> None:
        name = profile.get_character().get("name") or profile.username
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
        endings = profile.reachable_endings(all_missions)
        lines = ["Endings reachable with what you found this run:", ""]
        lines += [f"  {e.title} ({e.subtitle})" for e in endings]
        self.debrief.setText("\n".join(lines))
        self.continue_btn.hide()

    def _rebuild_objectives_cleared(self) -> None:
        while self.objectives_box.count():
            item = self.objectives_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._obj_labels = []


class CampaignWindow(QMainWindow):
    def __init__(self, saves: SaveSystem, default_username: str = "operator", parent=None):
        super().__init__(parent)
        self.setWindowTitle("NEXUS // TERMINAL — Campaign 3.0 (beta)")
        self.resize(1220, 780)
        self.setMinimumSize(900, 600)

        self.saves = saves
        self.db = ensure_v3_profile(saves, default_username)
        self.profile = CampaignProfile(self.db)
        self.all_missions = ALL_MISSIONS
        self.current_mission: Mission | None = None
        self.runner: MissionRunner | None = None
        self.terminal: ShellTerminal | None = None

        central = QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet(f"background:{COLORS['bg']};")
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.panel = MissionPanel()
        self.panel.hint_btn.clicked.connect(self._on_hint)
        self.panel.continue_btn.clicked.connect(self._load_mission)
        lay.addWidget(self.panel)
        self.terminal_holder = QWidget()
        hold_lay = QVBoxLayout(self.terminal_holder)
        hold_lay.setContentsMargins(10, 10, 10, 10)
        lay.addWidget(self.terminal_holder, 1)

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

    def _on_character_created(self, name: str, look: str) -> None:
        self.profile.set_character(name, look)
        self.character_dialog = None
        self._load_mission()

    # ------------------------------------------------------------------ mission lifecycle
    def _load_mission(self) -> None:
        mission = self.profile.next_mission(self.all_missions)
        if mission is None:
            self._on_campaign_finished()
            return
        self.current_mission = mission
        self.runner = MissionRunner.start(mission, level=lambda: self.profile.level)
        self._swap_terminal()
        self.panel.set_mission(mission, self.profile)
        self.terminal.print_system(f"=== LEVEL {mission.number}: {mission.title} ===", COLORS["green"])
        for line in mission.briefing:
            self.terminal.print_system(line, COLORS["cyan"])

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
        self.panel.refresh_objectives(self.runner)
        self._maybe_record_decision(line)
        if self.runner.is_complete:
            self._on_mission_complete()

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
        for line in mission.debrief:
            self.terminal.print_system(line, COLORS["amber"])
        self.terminal.focus_input()

    def _on_hint(self) -> None:
        if self.runner is None:
            return
        hint = self.panel.next_hint(self.runner)
        self.panel.hint_label.setText(hint or "No hints left — you've got everything you need.")

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
        super().closeEvent(event)
