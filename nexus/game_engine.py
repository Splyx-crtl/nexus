"""Central game engine: owns all subsystems and exposes signals to the UI.

The engine has no widgets and no timers of its own. The UI calls ``tick()``
once per second, which makes the whole game logic testable headlessly.
"""
from __future__ import annotations

import random
import time

from PySide6.QtCore import QObject, Signal

from .achievements import AchievementManager
from .commands import CommandProcessor
from .config import AUTOSAVE_INTERVAL, HEAT_DECAY_CONNECTED, HEAT_DECAY_IDLE, HEAT_MAX, rank_for_level
from .data import GameData, get_data
from .database import Database
from .contracts import ContractManager
from .events import EventManager
from .market import Market
from .progress import ProgressManager
from . import reputation
from .mission_engine import MissionEngine
from .player import Player
from .save_system import SettingsStore
from .simulation import LocalFS, World


class GameEngine(QObject):
    # --- signals consumed by the UI -----------------------------------
    async_line = Signal(str, str)          # text, style  (printed in the terminal)
    banner = Signal(str, list, dict)       # kind, lines, options
    toast = Signal(str, str, str)          # kind, title, text
    sound = Signal(str)
    state_changed = Signal()
    mission_changed = Signal()
    inventory_changed = Signal()
    server_changed = Signal()
    comms_changed = Signal()
    heat_changed = Signal(float)
    achievement_unlocked = Signal(dict)
    level_up = Signal(int, str)
    ending_reached = Signal(str)
    saved = Signal()

    def __init__(self, db: Database, settings: SettingsStore | None = None,
                 data: GameData | None = None, rng: random.Random | None = None):
        super().__init__()
        self.db = db
        self.data = data or get_data()
        self.settings = settings
        self.rng = rng or random.Random()
        self.player = Player(db, self.data)
        self.world = World(self.data, db)
        self.world.condition = self.check_requirement
        self.local = LocalFS(db)
        self.heat: float = float(db.get_world("heat", 0.0))
        self.busy = False                  # True while a mini-game / modal is open
        self.cloak_until = 0.0
        self._burning = False
        self._last_save = time.time()
        self._warned = False
        self._tick_n = 0
        self.instability_until = 0.0
        self.history: list[str] = db.get_world("history", [])
        self.missions = MissionEngine(self)
        self.achievements = AchievementManager(self)
        self.events = EventManager(self, self.rng)
        self.commands = CommandProcessor(self)
        self.market = Market(self)
        self.progress = ProgressManager(self)
        self.contracts = ContractManager(self)
        self._last_snapshot = time.time()
        if not db.get_flag("initialized"):
            self._new_game_setup()
        self.check_chapters(silent=True)             # saves from older versions: derive chapter unlocks
        if db.migrated_from:
            db.set_flag("migrated_from_v1", True)

    # ------------------------------------------------------------ helpers ---
    def settings_value(self, key: str):
        return self.settings.get(key) if self.settings else True

    def fmt(self, text: str) -> str:
        return (text.replace("{player}", self.player.username).replace("{rank}", self.player.rank)
                .replace("{level}", str(self.player.level)))

    def say(self, text: str, style: str = "normal") -> None:
        self.async_line.emit(text, style)

    def notify_toast(self, kind: str, title: str, text: str) -> None:
        """Show a toast and keep it in the notification centre log."""
        self.db.add_notification(kind, title, text)
        self.toast.emit(kind, title, text)

    def notify(self, kind: str, title: str, text: str, sound: str | None = "notify", log_only: bool = False) -> None:
        if log_only:
            self.db.add_notification(kind, title, text)
        else:
            self.notify_toast(kind, title, text)
        if sound:
            self.sound.emit(sound)

    def unlock(self, key: str) -> bool:
        """Persistently unlock a theme / secret; notifies the player the first time."""
        if not self.db.unlock(key):
            return False
        kind, _, name = key.partition(":")
        if kind == "theme":
            theme = next((t for t in self.data.themes if t["id"] == name), None)
            self.notify("ok", "NEW THEME UNLOCKED", theme["name"] if theme else name, sound="achievement")
            self.say(f"[✦] NEW THEME UNLOCKED: {theme['name'] if theme else name}  (command: theme {name})", "ok")
        self.bump("unlocks_total")
        self.state_changed.emit()
        return True

    def check_chapters(self, silent: bool = False) -> None:
        """Apply the end-of-chapter story event + unlocks once all its missions are done."""
        for ch in self.data.chapters:
            flag = f"chapter_{ch['id']}_done"
            if self.db.get_flag(flag) or not all(self.missions.is_complete(m) for m in ch["missions"]):
                continue
            fx = ch["complete"]
            self.db.set_flag(flag, True)
            for k, v in fx.get("flags", {}).items():
                self.db.set_flag(k, v)
            for sid in fx.get("discover", []):
                self.world.discover(sid)
            for key in fx.get("unlock", []):
                self.db.unlock(key)
            if silent:
                continue
            self.say("", "normal")
            for line in fx.get("lines", []):
                self.say(line, "ok" if line.startswith("CHAPTER") else "story")
            for item in fx.get("items", []):
                self.grant_item(item, 1)
            self.grant_credits(fx.get("credits", 0), bonus=False)
            self.grant_xp(fx.get("xp", 0), bonus=False)
            if "message" in fx:
                self.send_message(fx["message"]["from"], fx["message"]["text"])
            b = fx.get("banner")
            if b:
                self.banner.emit(b.get("kind", "complete"), b["lines"], b)
            self.bump("chapters_completed")
            self.notify("ok", f"CHAPTER {ch['id']} COMPLETE", ch["title"], sound="achievement")

    def snapshot_history(self) -> None:
        """Record a data point for the statistics charts."""
        s = self.db.all_stats()
        p = self.player
        total_xp = s.get("xp_earned", 0)
        self.db.add_history(p.level, total_xp, s.get("credits_earned", 0), p.completed_missions, p.playtime,
                            len(self.db.get_achievements()))
        self._last_snapshot = time.time()

    # ----------------------------------------------------------- difficulty ---
    DIFFICULTY = {"easy": {"heat": 0.6, "reward": 0.85, "decay": 1.5}, "normal": {"heat": 1.0, "reward": 1.0, "decay": 1.0},
                  "hard": {"heat": 1.35, "reward": 1.2, "decay": 0.8}}

    @property
    def difficulty(self) -> str:
        value = self.db.get_flag("difficulty", "normal")
        return value if value in self.DIFFICULTY else "normal"

    def set_difficulty(self, name: str) -> bool:
        if name not in self.DIFFICULTY:
            return False
        self.db.set_flag("difficulty", name)
        self.state_changed.emit()
        return True

    @property
    def ng_plus(self) -> int:
        return int(self.db.get_stat("ng_plus"))

    @property
    def reward_mult(self) -> float:
        return self.DIFFICULTY[self.difficulty]["reward"] * (1 + 0.25 * self.ng_plus)

    def start_new_game_plus(self) -> tuple[bool, str]:
        """Prestige: restart the story with level, credits, items, upgrades and achievements kept."""
        if not self.db.get_flag("campaign_complete"):
            return False, "Finish the campaign (mission 016) first."
        keep_flags = {"initialized", "difficulty", "shop_open", "slot_decrypt", "slot_network", "slot_utility",
                      "ghost_token_owned", "black_key_owned", "operator_license_owned"}
        for key in list(self.db.all_flags()):
            if key not in keep_flags and not key.startswith(("ending_", "ghost_")):
                self.db.conn.execute("DELETE FROM flags WHERE key=?", (key,))
        self.db.conn.execute("DELETE FROM missions")
        self.db.conn.execute("DELETE FROM decisions")
        self.db.conn.commit()
        for key in ("discovered", "breached", "routed", "decrypted", "compromised", "offline", "contract", "roles", "current", "cwd"):
            self.db.set_world(key, None if key in ("current", "contract") else ({} if key in ("offline", "roles") else ([] if key != "cwd" else "/")))
        once = [k for k in self.db.get_world("once", []) if k.startswith(("secret:", "egg:", "secretfx:", "topic:"))]
        self.db.set_world("once", once)
        self.db.set_world("zero_last", "")
        self.world.current, self.world.roles, self.world.cwd = None, {}, "/"
        self.world.discover("echo")
        self.missions._cache = None
        self.missions.unregister_prefix("contract_")
        self.heat = 0.0
        self.bump("ng_plus")
        self.send_message("mira", "A new cycle begins, {player}. I remember everything. Do you? 'mission start 1' whenever you're ready.")
        self.check_chapters(silent=True)
        for sig in (self.mission_changed, self.server_changed, self.inventory_changed, self.state_changed, self.comms_changed):
            sig.emit()
        return True, f"NEW GAME+ {self.ng_plus} started. Rewards x{self.reward_mult:.2f}, harder trace alert."

    def alert(self, title: str, text: str, kind: str = "info", sound: str = "notify") -> None:
        style = {"info": "info", "warn": "warn", "ok": "ok", "err": "err"}.get(kind, "info")
        self.say(f"[!] {title}: {text}", style)
        self.notify_toast(kind, title, text)
        self.sound.emit(sound)

    @property
    def prompt(self) -> str:
        user = self.player.username.lower()
        server = self.world.server
        if server is None:
            path = "~" + ("/" + self.world.local_cwd if self.world.local_cwd else "")
            return f"nexus@{user}:{path}$ "
        role = self.world.role()
        who = {0: "guest", 1: "user", 2: "root"}[role] if role else "guest"
        return f"{who}@{server.id}:{self.world.cwd}$ "

    # ------------------------------------------------------------- flags ---
    def flag(self, key: str, default=None):
        return self.db.get_flag(key, default)

    def set_flag(self, key: str, value=True) -> None:
        self.db.set_flag(key, value)
        self.missions.sync_states()
        self.achievements.check()

    def check_requirement(self, req: dict) -> bool:
        if "flag" in req and not self.db.get_flag(req["flag"]):
            return False
        if "not_flag" in req and self.db.get_flag(req["not_flag"]):
            return False
        if "mission" in req and not self.missions.is_complete(req["mission"]):
            return False
        if "not_mission" in req and self.missions.is_complete(req["not_mission"]):
            return False
        if "mission_active" in req:
            active = self.missions.active()
            if not active or active["id"] != req["mission_active"]:
                return False
        if "level" in req and self.player.level < req["level"]:
            return False
        if "item" in req and not self.player.has(req["item"]):
            return False
        if "stat_gte" in req and self.db.get_stat(req["stat_gte"]["stat"]) < req["stat_gte"]["value"]:
            return False
        if "reputation" in req and self.player.reputation < req["reputation"]:
            return False
        if "owned" in req and not self.player.has(req["owned"]):
            return False
        if "unlocked" in req and not self.db.is_unlocked(req["unlocked"]):
            return False
        if "chapter" in req and not self.db.get_flag(f"chapter_{req['chapter']}_done"):
            return False
        if "choice" in req:
            key, value = req["choice"]["key"], req["choice"]["value"]
            if self.db.get_flag(f"choice:{key}") != value:
                return False
        return True

    def bump(self, stat: str, amount: float = 1) -> None:
        self.db.add_stat(stat, amount)
        self.achievements.check()

    # ----------------------------------------------------------- rewards ---
    def grant_xp(self, amount: int, announce: bool = True, bonus: bool = True) -> None:
        if amount <= 0:
            return
        if bonus:
            amount = int(round(amount * self.player.xp_multiplier * self.reward_mult))
        old_level = self.player.level
        levels = self.player.add_xp(amount)
        self.db.add_stat("xp_earned", amount)
        if announce:
            self.say(f"+{amount} XP", "ok")
        for lvl in levels:
            rank = rank_for_level(lvl)
            self.say(f"*** LEVEL UP — LEVEL {lvl} [{rank}] ***", "ok")
            self.sound.emit("achievement")
        if levels:
            self._announce_level_up(old_level, levels[-1])
        self.achievements.check()
        self.state_changed.emit()

    def _announce_level_up(self, old: int, new: int) -> None:
        """Big level-up banner listing rank / item / mission unlocks."""
        lines = ["LEVEL UP", f"+{new - old} LEVEL  ->  {new}"]
        if rank_for_level(new) != rank_for_level(old):
            lines.append(f"NEW RANK UNLOCKED: {rank_for_level(new)}")
        items = [i["name"] for i in self.data.items.values()
                 if i.get("price") and old < i.get("level", 1) <= new and i.get("category") != "COSMETICS"]
        if items:
            lines.append("NEW ITEM UNLOCKED: " + items[0] + (f" (+{len(items) - 1} more)" if len(items) > 1 else ""))
        missions = [m for m in self.data.missions if old < m.get("required_level", 1) <= new and not self.missions.lock_reason(m)
                    and self.missions.status(m["id"]) in ("available", "failed")]
        if missions:
            lines.append("NEW MISSION UNLOCKED: " + missions[0]["title"] + (f" (+{len(missions) - 1} more)" if len(missions) > 1 else ""))
        self.level_up.emit(new, rank_for_level(new))
        self.banner.emit("levelup", lines, {})
        self.notify("ok", f"LEVEL UP — {new}", f"Rank: {rank_for_level(new)}", sound=None, log_only=True)
        self.snapshot_history()

    def grant_credits(self, amount: int, announce: bool = True, bonus: bool = True) -> None:
        if amount <= 0:
            return
        if bonus:
            amount = int(round(amount * self.player.income_multiplier * self.reward_mult))
        self.player.add_credits(amount)
        self.db.add_stat("credits_earned", amount)
        if announce:
            self.say(f"+${amount:,}", "ok")
        self.achievements.check()
        self.state_changed.emit()

    def spend_credits(self, amount: int) -> bool:
        if not self.player.spend_credits(amount):
            return False
        self.db.add_stat("credits_spent", amount)
        self.state_changed.emit()
        return True

    def grant_item(self, item_id: str, qty: int = 1, announce: bool = True) -> int:
        granted = self.player.add_item(item_id, qty)
        item = self.data.items.get(item_id, {"name": item_id})
        if granted:
            if announce:
                self.say(f"[+] ITEM ACQUIRED: {item['name']} x{granted}", "ok")
                self.sound.emit("notify")
            self.inventory_changed.emit()
            self.missions.sync_states()
        elif announce:
            self.say(f"[=] {item['name']}: already at maximum capacity.", "dim")
        return granted

    def change_trust(self, contact: str, delta: int) -> None:
        row = self.db.get_contact(contact) or {"trust": self.data.contacts[contact].get("trust_start", 20), "met": 0}
        self.db.set_contact(contact, max(0, min(100, row["trust"] + delta)), row["met"])
        self.achievements.check()
        self.comms_changed.emit()

    def trust(self, contact: str) -> int:
        row = self.db.get_contact(contact)
        return row["trust"] if row else self.data.contacts[contact].get("trust_start", 20)

    def send_message(self, contact: str, text: str) -> None:
        if contact not in self.data.contacts:
            return
        row = self.db.get_contact(contact)
        self.db.set_contact(contact, row["trust"] if row else self.data.contacts[contact].get("trust_start", 20), 1)
        self.db.set_flag(f"{contact}_met", True)
        self.db.add_message(contact, "in", self.fmt(text))
        name = self.data.contacts[contact]["name"]
        self.say(f"[✉] INCOMING MESSAGE — {name}   (type: msg {contact})", "info")
        self.notify_toast("info", f"MESSAGE // {name}", self.fmt(text)[:90])
        self.sound.emit("notify")
        self.bump("messages_received")
        self.comms_changed.emit()

    # --------------------------------------------------------------- heat ---
    def add_heat(self, base: float, reason: str = "", scale: bool = True) -> None:
        amount = base
        if scale:
            server = self.world.server
            amount = base * (server.heat_mult if server else 1.0) * self.player.heat_factor \
                * self.DIFFICULTY[self.difficulty]["heat"] * (1 + 0.1 * self.ng_plus)
            if time.time() < self.cloak_until:
                amount *= 0.4
        self.heat = max(0.0, min(HEAT_MAX, self.heat + amount))
        self.missions.note_heat(self.heat)
        self.heat_changed.emit(self.heat)
        if self.heat >= 70 and not self._warned:
            self._warned = True
            self.say("[!] WARNING: TRACE ALERT CRITICAL — disconnect or cool down!", "err")
            self.sound.emit("warning")
        if self.heat >= HEAT_MAX:
            self.burn()

    def reduce_heat(self, amount: float) -> None:
        self.heat = max(0.0, self.heat - amount)
        if self.heat < 60:
            self._warned = False
        self.heat_changed.emit(self.heat)

    def note_failure(self) -> None:
        """A failed mini-game / bad login: counts against PERFECT ratings."""
        self.missions.note_loss()

    def burn(self) -> None:
        if self._burning:
            return
        self._burning = True
        try:
            self.say("!! TRACE COMPLETE — CONNECTION BURNED !!", "err")
            self.sound.emit("error")
            self.heat = 35.0
            self._warned = False
            self.world.disconnect()
            self.banner.emit("failure", ["TRACE COMPLETE", "CONNECTION BURNED"], {})
            if self.missions.active():
                self.missions.fail("TRACED BY NEXUS SECURITY")
            else:
                fee = int(self.player.credits * 0.03)
                self.player.add_credits(-fee)
                self.say(f"Containment fee: -${fee:,}", "warn")
            self.heat_changed.emit(self.heat)
            self.server_changed.emit()
            self.state_changed.emit()
        finally:
            self._burning = False

    # ------------------------------------------------------------- events ---
    def event(self, etype: str, **kw) -> None:
        """Report a gameplay event to the mission system."""
        self.missions.on_event(etype, kw)

    def on_achievement(self, ach: dict) -> None:
        self.say(f"[★] ACHIEVEMENT UNLOCKED: {ach['name']} — {ach['description']}", "ok")
        reward = ach.get("reward", {})
        if reward.get("credits"):
            self.player.add_credits(reward["credits"])
            self.db.add_stat("credits_earned", reward["credits"])
        if reward.get("xp"):
            self.grant_xp(reward["xp"], announce=False, bonus=False)
        if reward.get("item"):
            self.grant_item(reward["item"], 1, announce=False)
        if reward.get("unlock"):
            self.unlock(reward["unlock"])
        self.notify_toast("achievement", ach["name"], ach["description"])
        self.sound.emit("achievement")
        self.achievement_unlocked.emit(ach)
        self.state_changed.emit()

    def trigger_ending(self, ending_id: str) -> None:
        endings = self.db.get_world("endings", [])
        if ending_id not in endings:
            endings.append(ending_id)
            self.db.set_world("endings", endings)
        self.player.set_ending(ending_id)
        self.set_flag(f"ending_{ending_id}", True)
        self.achievements.check()
        self.ending_reached.emit(ending_id)

    # --------------------------------------------------------------- tick ---
    def tick(self, dt: float = 1.0) -> None:
        """Advance simulated time. Called ~once per second by the UI."""
        self.player.add_playtime(dt)
        self.db.flush()
        self._tick_n += 1
        if self._tick_n % 5 == 0:
            self.db.set_stat("playtime_seconds", self.player.playtime)
        if not self.busy:
            active = self.missions.active()
            decay = (HEAT_DECAY_CONNECTED if self.world.current else HEAT_DECAY_IDLE) * self.DIFFICULTY[self.difficulty]["decay"]
            rate = (active or {}).get("heat_rate", 0.0) if self.world.current else 0.0
            if rate:
                self.add_heat(rate * dt, scale=False)
            elif self.heat > 0:
                self.reduce_heat(decay * dt)
            self.missions.tick(dt)
            if active and any(o.get("event") == "heat_below" for o in active["objectives"]):
                self.missions.sync_states()              # "cool the alert" objectives watch the live value
            if time.time() < self.instability_until:
                self.add_heat(0.4 * dt, scale=False)
            self.events.update(dt)
            self.state_changed.emit()
        if time.time() - self._last_snapshot >= 600:
            self.snapshot_history()
        if time.time() - self._last_save >= (self.settings_value("autosave_seconds") or AUTOSAVE_INTERVAL):
            self.maybe_autosave(force=True)

    def maybe_autosave(self, force: bool = False) -> None:
        if not force and time.time() - self._last_save < AUTOSAVE_INTERVAL:
            return
        self.save()

    def save(self) -> None:
        self.player.flush()
        self.missions.save()
        self.db.flush()
        self.db.set_world("heat", self.heat)
        self.db.set_world("history", self.history[-200:])
        self._last_save = time.time()
        self.saved.emit()

    def shutdown(self) -> None:
        self.save()
        self.db.close()

    # -------------------------------------------------------------- setup ---
    def _new_game_setup(self) -> None:
        for cid, c in self.data.contacts.items():
            self.db.set_contact(cid, c.get("trust_start", 20), 0)
        self.world.discover("echo")
        self.db.set_flag("initialized", True)
        self.db.set_flag("intro_pending", True)
        self.send_message("mira", "Welcome to NEXUS, {player}. I'm MIRA, your handler. "
                                  "Open your terminal and type 'mission start 1' whenever you're ready.")
        self.db.conn.execute("UPDATE messages SET read=0")
        self.db.conn.commit()
