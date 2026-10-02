"""Random events that make the simulated world feel alive (data/events.json)."""
from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING

from .config import EVENT_CHANCE_PER_TICK, EVENT_MIN_INTERVAL

if TYPE_CHECKING:
    from .game_engine import GameEngine


class EventManager:
    def __init__(self, engine: "GameEngine", rng: random.Random | None = None):
        self.e = engine
        self.rng = rng or random.Random()
        self.defs = engine.data.events
        self.last_fired = time.time()
        self.recent: list[str] = []

    def update(self, dt: float) -> None:
        """Called every second by the engine tick; occasionally fires an event."""
        e = self.e
        if e.busy or not e.settings_value("random_events"):
            return
        active = e.missions.active()
        if active and active.get("tutorial"):            # nothing may interrupt the guided tutorial
            return
        if time.time() - self.last_fired < EVENT_MIN_INTERVAL:
            return
        if self.rng.random() < EVENT_CHANCE_PER_TICK:
            self.fire_random()

    def eligible(self) -> list[dict]:
        out = []
        for ev in self.defs:
            if ev.get("requires") and not self.e.check_requirement(ev["requires"]):
                continue
            if ev["kind"] == "firewall_update" and not self._rearm_candidates():
                continue
            if ev["kind"] in ("server_offline", "blackout", "server_migration") and not self._offline_candidates():
                continue
            out.append(ev)
        return out

    def fire_random(self) -> dict | None:
        pool = self.eligible()
        fresh = [x for x in pool if x["id"] not in self.recent]      # don't repeat the last few events
        pool = fresh or pool
        if not pool:
            return None
        ev = self.rng.choices(pool, weights=[x.get("weight", 1) for x in pool])[0]
        self.fire(ev["id"])
        return ev

    def _needed_servers(self) -> set:
        """Servers the open connection, the current mission or the upcoming story missions depend on.
        Random events must never take these away from the player."""
        ms = self.e.missions
        active = ms.active()
        needed = {self.e.world.current}
        completed = {m["id"] for m in ms.defs if ms.is_complete(m["id"])}
        reachable = completed | ({active["id"]} if active else set())
        for m in ms.defs:
            if m.get("contract") or not m.get("main") or m["id"] in completed:
                continue
            if all(r in reachable for r in m.get("requires", [])):      # active, startable, or unlocked by the active one
                needed.update(o.get("server") for o in m["objectives"])
        return needed

    def _rearm_candidates(self) -> list[str]:
        needed = self._needed_servers()
        return [s for s in self.e.world.db.get_world("breached", []) if s not in needed]

    def _offline_candidates(self) -> list[str]:
        w = self.e.world
        needed = self._needed_servers()
        return [s for s in w.discovered() if s not in needed and w.is_online(s)
                and s not in ("echo", "nexus_core")]

    def fire(self, event_id: str) -> None:
        ev = next(x for x in self.defs if x["id"] == event_id)
        e, rng = self.e, self.rng
        self.last_fired = time.time()
        self.recent = (self.recent + [event_id])[-3:]
        e.bump("events_seen")
        kind = ev["kind"]
        text = e.fmt(rng.choice(ev["texts"])) if ev.get("texts") else ""
        title = ev["title"]

        if kind == "message":
            contacts = [c for c in e.data.contacts if e.db.get_contact(c) and e.db.get_contact(c)["met"]
                        and e.data.contacts[c].get("idle_messages")]
            if not contacts:
                return
            cid = rng.choice(contacts)
            e.send_message(cid, rng.choice(e.data.contacts[cid]["idle_messages"]))
            e.alert("INCOMING MESSAGE", f"New transmission from {e.data.contacts[cid]['name']}.", "info", sound="notify")
            return
        if kind == "unknown_connection":
            ip = f"10.42.{rng.randint(100, 250)}.{rng.randint(2, 250)}"
            e.alert(title, f"{text} Source: {ip}", "warn", sound="warning")
            e.add_heat(rng.randint(6, 12), "unknown connection")
        elif kind == "system_alert":
            e.alert(title, text, "warn", sound="warning")
            e.add_heat(rng.randint(2, 5), "system alert")
        elif kind == "firewall_update":
            candidates = self._rearm_candidates()
            if not candidates:
                return
            sid = rng.choice(candidates)
            e.world.rearm_firewall(sid)
            name = e.world.servers[sid].name
            e.alert(title, f"{name} firewall re-armed. Breach required again.", "warn", sound="warning")
        elif kind == "server_offline":
            cands = self._offline_candidates()
            if not cands:
                return
            sid = rng.choice(cands)
            e.world.set_offline(sid, rng.randint(60, 120))
            e.alert(title, f"{e.world.servers[sid].name} dropped off the grid. ETA ~2 min.", "warn", sound="error")
            e.server_changed.emit()
        elif kind == "unknown_user":
            e.alert(title, text, "info", sound="notify")
            if e.db.get_flag("zero_met") and rng.random() < 0.5:
                e.send_message("zero", rng.choice(e.data.contacts["zero"]["idle_messages"]))
        elif kind == "data_fragment":
            if e.player.qty("data_fragment") < 6 and not e.db.get_flag("quantum_key_built"):
                e.grant_item("data_fragment", 1)
                e.bump("fragments_found")
                e.alert(title, "A stray DATA FRAGMENT was recovered from the noise.", "ok", sound="notify")
            else:
                amount = rng.randint(150, 450)
                e.grant_credits(amount)
                e.alert(title, f"Recovered a dormant credit cache: +${amount}.", "ok", sound="notify")
        elif kind == "credits":
            amount = rng.randint(100, 400) + 20 * e.player.level
            e.grant_credits(amount)
            e.alert(title, f"{text} +${amount}", "ok", sound="notify")
        elif kind == "xp":
            amount = rng.randint(30, 90) + 5 * e.player.level
            e.grant_xp(amount)
            e.alert(title, f"{text} +{amount} XP", "ok", sound="notify")

        elif kind == "system_instability":
            e.instability_until = time.time() + 25
            e.alert(title, text + " Trace alert rising for ~25s — disconnect or cool down.", "warn", sound="warning")
            e.add_heat(rng.randint(3, 6), "instability")
        elif kind == "data_leak":
            hidden = {s for s, d in e.data.servers.items() if d.get("hidden")}
            unseen = [s for s in e.world.servers if not e.world.is_discovered(s) and s not in hidden]
            if unseen and rng.random() < 0.45:
                sid = rng.choice(unseen)
                e.world.discover(sid)
                e.server_changed.emit()
                e.alert(title, f"{text} Coordinates for {e.world.servers[sid].name} are now on your map.", "ok", sound="notify")
            else:
                amount = rng.randint(200, 700) + 25 * e.player.level
                e.grant_credits(amount)
                e.alert(title, f"{text} Resold for ${amount:,}.", "ok", sound="notify")
        elif kind == "blackout":
            victims = self._offline_candidates()
            rng.shuffle(victims)
            victims = victims[:3]
            for sid in victims:
                e.world.set_offline(sid, rng.randint(40, 70))
            e.banner.emit("blackout", ["BLACKOUT", "GRID FAILURE", f"{len(victims)} NODES OFFLINE"], {})
            e.alert(title, f"{text} {len(victims)} nodes dark for ~1 min.", "warn", sound="error")
            e.server_changed.emit()
        elif kind == "server_migration":
            cands = self._offline_candidates()
            if not cands:
                return
            sid = rng.choice(cands)
            e.world.rearm_firewall(sid)
            e.world.set_offline(sid, 30)
            e.alert(title, f"{e.world.servers[sid].name}: {text}", "warn", sound="warning")
            e.server_changed.emit()
        elif kind == "zero_event":
            stage = None
            for st in e.data.zero_stages:
                if e.check_requirement(st["requires"]):
                    stage = st
            if stage:
                last = e.db.get_world("zero_last", "")
                options = [m for m in stage["messages"] if m != last] or stage["messages"]
                msg = rng.choice(options)
                e.db.set_world("zero_last", msg)
                if rng.random() < 0.3:
                    e.banner.emit("zero", ["UNKNOWN USER DETECTED", "> ZERO is watching the network."], {})
                e.send_message("zero", msg)
                e.bump("zero_events")
        elif kind == "secret_data":
            amount = rng.randint(300, 900) + 30 * e.player.level
            e.grant_credits(amount)
            e.grant_xp(rng.randint(50, 150) + 10 * e.player.level)
            e.bump("secret_data")
            e.alert(title, f"{text} +${amount:,}", "ok", sound="achievement")
