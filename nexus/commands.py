"""Terminal command processor.

Handlers are generators that yield ``outputs`` objects (see outputs.py); the
terminal UI (or the headless test driver) executes them step by step.
All commands only ever touch the simulated world.
"""
from __future__ import annotations

import base64
import binascii
import difflib
import inspect
import shlex
import traceback
import zlib
from typing import TYPE_CHECKING, Iterator

from .command_game import GameCommandsMixin
from .command_meta import MetaCommandsMixin
from . import reputation
from .config import ERROR_LOG
from .eggs import easter_egg
from .minigames import EncryptionPuzzle, FirewallPuzzle, RoutingPuzzle, TraceConfig, caesar
from .outputs import Banner, Fx, Minigame, Out, Progress, Prompt, Type, Wait, dim, err, info, kv, ok, out, warn
from .security import looks_like_real_address
from .simulation import ROLE_LEVELS, ROLE_NAMES

if TYPE_CHECKING:
    from .game_engine import GameEngine


def _fmt_size(n: int) -> str:
    return f"{n}B" if n < 1024 else f"{n / 1024:.1f}K"


class CommandProcessor(MetaCommandsMixin, GameCommandsMixin):
    def __init__(self, engine: "GameEngine"):
        self.e = engine
        self.registry: dict[str, str] = {}
        for cmd in engine.data.commands:
            for name in [cmd["name"], *cmd.get("aliases", [])]:
                self.registry[name] = f"cmd_{cmd['name']}"
        self.session_trains = 0

    # ------------------------------------------------------------- dispatch ---
    @staticmethod
    def split(line: str) -> list[str]:
        try:
            return shlex.split(line)
        except ValueError:
            return line.split()

    def execute(self, line: str) -> Iterator:
        """Generator: yields outputs for one command line."""
        line = line.strip()
        if not line:
            return
        e = self.e
        e.history.append(line)
        e.bump("commands_run")
        egg = easter_egg(self, line)
        if egg is not None:
            yield from egg
            return
        parts = self.split(line)
        cmd, args = parts[0].lower(), parts[1:]
        method_name = self.registry.get(cmd)
        if not method_name or not hasattr(self, method_name):
            yield err(f"command not found: {cmd}")
            close = difflib.get_close_matches(cmd, list(self.registry), n=2, cutoff=0.6)
            yield dim(f"did you mean: {', '.join(close)}?" if close else "type 'help' for a list of commands.")
            return
        try:
            result = getattr(self, method_name)(args)
            if inspect.isgenerator(result):
                yield from result
            elif result:
                yield from result
        except Exception:                                      # never crash the game loop
            trace = traceback.format_exc()
            try:
                ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
                with ERROR_LOG.open("a", encoding="utf-8") as fh:
                    fh.write(f"--- {line}\n{trace}\n")
            except OSError:
                pass
            yield err("SYSTEM FAULT: command aborted. Details written to saves/error.log")

    # --------------------------------------------------------------- helpers ---
    def _need_conn(self):
        if self.e.world.server is None:
            return err("NOT CONNECTED. Use: connect <server>")
        return None

    def _resolve_target(self, query: str):
        """Return (server, error_output). Rejects anything outside the simulation."""
        if looks_like_real_address(query):
            return None, [err("ADDRESS OUTSIDE SIMULATION SANDBOX — NO ROUTE."),
                          dim("NEXUS only simulates a fictional network (10.42.x.x). Nothing real is ever contacted.")]
        server = self.e.world.find(query)
        if server is None or not self.e.world.is_discovered(server.id):
            return None, [err(f"UNKNOWN HOST: {query}"), dim("Discover hosts with 'scan' and 'map'.")]
        return server, None

    def _effects(self, fx: dict | None, key: str) -> Iterator:
        """Apply one-shot story effects (flags, items, trust, messages...)."""
        if not fx:
            return
        e = self.e
        if fx.get("once", True) and not e.world.mark_once(key):
            return
        for line in fx.get("lines", []):
            yield Out(e.fmt(line), fx.get("style", "story"))
        for flag, value in fx.get("flags", {}).items():
            e.set_flag(flag, value)
        for item in fx.get("items", []):
            e.grant_item(item, 1)
        for contact, delta in fx.get("trust", {}).items():
            e.change_trust(contact, delta)
        for sid in fx.get("discover", []):
            if e.world.discover(sid):
                yield info(f"[+] NEW HOST DISCOVERED: {e.world.servers[sid].name}")
        if fx.get("xp"):
            e.grant_xp(fx["xp"])
        if fx.get("credits"):
            e.grant_credits(fx["credits"])
        if fx.get("heat"):
            e.reduce_heat(-fx["heat"]) if fx["heat"] < 0 else e.add_heat(fx["heat"], "story", scale=False)
        if "message" in fx:
            e.send_message(fx["message"]["from"], fx["message"]["text"])
        if "banner" in fx:
            yield Banner(fx["banner"].get("kind", "alert"), [e.fmt(x) for x in fx["banner"].get("lines", [])],
                         block=fx["banner"].get("block", False))

    def _triggers(self, triggers: list, prefix: str) -> Iterator:
        for i, trig in enumerate(triggers or []):
            if trig.get("requires") and not self.e.check_requirement(trig["requires"]):
                continue
            yield from self._effects(trig, f"{prefix}:{i}")

    # ---------------------------------------------------------- completion ---
    def complete(self, text: str) -> list[str]:
        """Candidates for the token being typed (used by TAB in the terminal)."""
        e, w = self.e, self.e.world
        parts = text.split(" ")
        prefix = parts[-1]
        if len(parts) == 1:
            return sorted(n for n in self.registry if n.startswith(prefix.lower()))
        cmd = self.registry.get(parts[0].lower(), "")[4:]
        candidates: list[str] = []
        if cmd in ("connect", "scan", "ping", "route"):
            candidates = [s for s in w.discovered()]
        elif cmd in ("cat", "open", "cd", "ls", "download", "decrypt", "rm", "upload"):
            dirpart, slash, base = prefix.rpartition("/")
            if w.server is None or cmd in ("rm", "upload"):
                folder = e.local.resolve(w.local_cwd, dirpart or "")
                if cmd == "upload" and not dirpart:
                    folder = "downloads"
                names = [n + ("/" if d else "") for n, d in e.local.list_dir(folder)]
            else:
                folder = w.resolve(dirpart or ".") if (dirpart or slash == "") else "/"
                if prefix.startswith("/") and not dirpart:
                    folder = "/"
                entries = w.list_dir(w.server, folder, show_hidden=base.startswith(".")) or []
                names = [n.name + ("/" if n.is_dir else "") for n in entries]
            head = dirpart + slash
            candidates = [head + n for n in names]
            prefix_cmp = prefix
            return sorted(c for c in candidates if c.lower().startswith(prefix_cmp.lower()))
        elif cmd == "use":
            candidates = list(e.player.inventory())
        elif cmd in ("msg",):
            candidates = [c for c in e.data.contacts if (e.db.get_contact(c) or {}).get("met")]
        elif cmd == "upgrade":
            candidates = list(e.data.upgrades)
        elif cmd == "mission":
            candidates = ["list", "start", "abort", "info"]
        elif cmd == "help":
            candidates = list(self.registry)
        elif cmd == "buy":
            candidates = [i for i, d in e.data.items.items() if d.get("price")]
        elif cmd == "train":
            candidates = ["firewall", "decrypt", "route", "access", "trace"]
        return sorted(c for c in candidates if c.lower().startswith(prefix.lower()))

    # ------------------------------------------------------- basic commands ---
    def cmd_help(self, args):
        cmds = self.e.data.commands
        if args:
            c = next((c for c in cmds if args[0].lower() in [c["name"], *c.get("aliases", [])]), None)
            if not c:
                return [err(f"no help for '{args[0]}'")]
            lines = [info(f"{c['name'].upper()} — {c['description']}"), kv("USAGE", c["usage"], 8, "normal")]
            if c.get("aliases"):
                lines.append(kv("ALIASES", ", ".join(c["aliases"]), 8, "normal"))
            return lines
        lines = [Out("== NEXUS COMMAND INDEX ==", "title"), dim("Type 'help <command>' for details. TAB completes. UP/DOWN browses history.")]
        cats: dict[str, list] = {}
        for c in cmds:
            cats.setdefault(c["category"], []).append(c)
        for cat, items in cats.items():
            lines.append(out())
            lines.append(Out(f"[{cat.upper()}]", "info"))
            for c in items:
                lines.append(Out(spans=[(f"  {c['name']:<12}", "ok"), (c["description"], "normal")]))
        return lines

    def cmd_clear(self, args):
        return [Fx("clear")]

    def cmd_status(self, args):
        e, p = self.e, self.e.player
        lines = [
            kv("OPERATOR:", p.username.upper(), 13), kv("RANK:", p.rank, 13), kv("LEVEL:", str(p.level), 13),
            kv("XP:", f"{p.xp} / {p.xp_needed}", 13), kv("CREDITS:", f"{p.credits:,}", 13),
            kv("REPUTATION:", f"{p.reputation}  ({reputation.status(p.reputation)})", 13), out(),
            Out("NETWORK STATUS:", "dim"),
        ]
        srv = e.world.server
        lines.append(Out("ONLINE" if srv is None or e.world.is_online(srv.id) else "LINK DEGRADED", "ok"))
        lines.append(kv("CONNECTION:", f"{srv.name} ({srv.ip}) as {ROLE_NAMES[e.world.role()]}" if srv else "none (local)", 13, "info"))
        heat_style = "ok" if e.heat < 40 else "warn" if e.heat < 70 else "err"
        lines.append(kv("TRACE ALERT:", f"{e.heat:.0f}%", 13, heat_style))
        m = e.missions.active()
        lines.append(kv("MISSION:", f"{m['number']:03d} {m['title']}" if m else "none", 13, "info"))
        return lines

    def cmd_whoami(self, args):
        e = self.e
        lines = [Out(e.player.username.upper(), "ok"), dim(f"{e.player.rank} // LEVEL {e.player.level}")]
        if e.world.server:
            lines.append(dim(f"remote identity: {ROLE_NAMES[e.world.role()]}@{e.world.server.name}"))
        return lines

    def cmd_pwd(self, args):
        w = self.e.world
        return [Out(w.cwd if w.server else "/home/" + self.e.player.username.lower() + ("/" + w.local_cwd if w.local_cwd else ""))]

    # ------------------------------------------------------- file system ---
    def cmd_ls(self, args):
        e, w = self.e, self.e.world
        show_hidden = any(a.startswith("-") and "a" in a for a in args)
        paths = [a for a in args if not a.startswith("-")]
        if w.server is None:
            return self._ls_local(paths[0] if paths else "", show_hidden)
        srv = w.server
        path = w.resolve(paths[0]) if paths else w.cwd
        entries = w.list_dir(srv, path, show_hidden)
        node = w.node_at(srv, path)
        if entries is None:
            if node and not node.is_dir:
                return [Out(node.name)]
            return [err(f"ls: cannot access '{path}': No such file or directory")]
        if node and not w.can_access(node):
            return [err("ls: PERMISSION DENIED — higher clearance required")]
        e.event("ls", server=srv.id, path=path)
        lines = [dim(f"{path}:")]
        if not entries:
            lines.append(dim("  (empty)"))
        for n in entries:
            tag = "" if w.can_access(n) else f"  [{n.access.upper()}]"
            if n.is_dir:
                lines.append(Out(spans=[("  d  ", "dim"), (n.name + "/", "info"), (tag, "warn")]))
            else:
                size = _fmt_size(len(n.content))
                enc = "  [ENCRYPTED]" if n.encrypted and not w.is_decrypted(srv.id, n.path) else ""
                lines.append(Out(spans=[(f"  -  {size:>6}  ", "dim"), (n.name, "normal"), (tag, "warn"), (enc, "err")]))
        return lines

    def _ls_local(self, path: str, show_hidden: bool):
        e = self.e
        resolved = e.local.resolve(e.world.local_cwd, path)
        if not e.local.is_dir(resolved):
            return [err(f"ls: cannot access '{path}': No such file or directory")]
        lines = [dim(f"~/{resolved}:" if resolved else "~:")]
        entries = e.local.list_dir(resolved)
        if not entries:
            lines.append(dim("  (empty)"))
        for name, is_dir in entries:
            if is_dir:
                lines.append(Out(spans=[("  d  ", "dim"), (name + "/", "info")]))
            else:
                content = e.local.read((resolved + "/" if resolved else "") + name) or ""
                lines.append(Out(spans=[(f"  -  {_fmt_size(len(content)):>6}  ", "dim"), (name, "normal")]))
        return lines

    def cmd_cd(self, args):
        e, w = self.e, self.e.world
        target = args[0] if args else ("/" if w.server else "~")
        if w.server is None:
            resolved = e.local.resolve(w.local_cwd, target)
            if not e.local.is_dir(resolved):
                return [err(f"cd: {target}: No such directory")]
            w.local_cwd = resolved
            return []
        path = w.resolve(target)
        node = w.node_at(w.server, path)
        if node is None or not node.is_dir:
            return [err(f"cd: {target}: No such directory")]
        if not w.can_access(node):
            return [err("cd: PERMISSION DENIED — higher clearance required")]
        w.set_cwd(path)
        return []

    def cmd_cat(self, args):
        if not args:
            return [err("usage: cat <file>")]
        return self._read_file(args[0])

    def _read_file(self, name: str) -> Iterator:
        e, w = self.e, self.e.world
        if w.server is None:
            resolved = e.local.resolve(w.local_cwd, name)
            content = e.local.read(resolved)
            if content is None:
                yield err(f"cat: {name}: No such file")
                return
            for line in e.fmt(content).splitlines():
                yield self._content_line(line)
            e.event("read_local", path=resolved, file=resolved.rsplit("/", 1)[-1])
            return
        srv = w.server
        path = w.resolve(name)
        node = w.node_at(srv, path)
        if node is None:
            yield err(f"cat: {name}: No such file or directory")
            return
        if node.is_dir:
            yield err(f"cat: {name}: Is a directory")
            return
        if not w.can_access(node):
            yield err("PERMISSION DENIED — login required" if w.role() == 0 else "PERMISSION DENIED — admin clearance required")
            e.add_heat(2, "denied read")
            return
        locked = node.encrypted and not w.is_decrypted(srv.id, node.path)
        if locked:
            enc = node.encrypted
            cipher = EncryptionPuzzle(self._plain(enc), enc["type"], enc.get("key"))
            yield warn("[ENCRYPTED PAYLOAD]")
            for line in cipher.ciphertext.splitlines():
                yield Out(line, "err")
            yield dim("Use 'decrypt " + node.name + "' to break the cipher.")
            e.event("read", server=srv.id, path=path, file=node.name, encrypted=True)
            return
        text = self._plain(node.encrypted) if node.encrypted else node.content
        for line in e.fmt(text).splitlines():
            yield self._content_line(line)
        e.bump("files_read")
        if node.secret and w.mark_once(f"secret:{srv.id}:{path}"):
            e.bump("secrets_found")
            yield Out("[✦] SECRET FOUND", "ok")
            e.notify_toast("achievement", "SECRET FOUND", node.name)
            e.sound.emit("achievement")
        yield from self._effects(node.on_read, f"read:{srv.id}:{path}")
        e.event("read", server=srv.id, path=path, file=node.name)

    @staticmethod
    def _plain(enc: dict) -> str:
        plain = enc["plain"]
        return "\n".join(plain) if isinstance(plain, list) else plain

    @staticmethod
    def _content_line(line: str) -> Out:
        s = line.strip()
        if s.startswith("!!") or "CRITICAL" in s or "ERROR" in s:
            return Out(line, "err")
        if s.startswith("##"):
            return Out(line, "title")
        if "WARN" in s or "ALERT" in s:
            return Out(line, "warn")
        if s.startswith(">") or s.startswith("ZERO>"):
            return Out(line, "info")
        return Out(line)

    def cmd_open(self, args):
        return self.cmd_cat(args)

    def cmd_rm(self, args):
        e = self.e
        if e.world.server:
            return [err("rm: permission denied on remote systems")]
        if not args:
            return [err("usage: rm <local file>")]
        resolved = e.local.resolve(e.world.local_cwd, args[0])
        if e.local.read(resolved) is None:
            return [err(f"rm: {args[0]}: No such file")]
        e.db.delete_local_file(resolved)
        e.inventory_changed.emit()
        return [ok(f"removed {resolved}")]

    # ----------------------------------------------------------- networking ---
    def cmd_ping(self, args):
        if not args:
            return [err("usage: ping <host>")]
        srv, problem = self._resolve_target(args[0])
        if problem:
            return problem
        e = self.e
        lines = [dim(f"PING {srv.name} ({srv.ip}) — simulated")]
        if not e.world.is_online(srv.id):
            return lines + [err("Request timed out. HOST OFFLINE.")]
        for i in range(3):
            lines.append(Out(f"reply from {srv.ip}: seq={i} time={e.rng.randint(8, 70)}ms", "normal"))
        return lines

    def cmd_connect(self, args):
        e, w = self.e, self.e.world
        if not args:
            return (yield err("usage: connect <server|ip>"))
        if args[0].lower() in ("local", "home", "~"):
            return (yield from self.cmd_disconnect([]))
        srv, problem = self._resolve_target(args[0])
        if problem:
            for o in problem:
                yield o
            return
        if w.current == srv.id:
            yield warn(f"Already connected to {srv.name}.")
            return
        if not w.is_online(srv.id):
            yield err(f"HOST UNREACHABLE: {srv.name} is offline.")
            e.event("connect_failed", server=srv.id)
            return
        if w.current:
            yield dim(f"Dropping connection to {w.server.name}...")
            w.disconnect()
        if srv.routing and (srv.routing.get("always") or not w.is_routed(srv.id)):
            yield warn(f"NO DIRECT ROUTE TO {srv.name}. Relay routing required.")
            ok_route = yield from self._run_routing(srv)
            if not ok_route:
                return
        yield Out(f"> CONNECTING TO {srv.name} ({srv.ip})...", "info")
        yield Progress("CONNECTING", 1300)
        w.connect(srv.id)
        e.bump("connections")
        e.add_heat(1.5 * srv.heat_mult, "connection", scale=False)
        yield ok("CONNECTION ESTABLISHED.")
        yield self._server_card(srv)
        for line in srv.motd:
            yield Out(e.fmt(line), "dim")
        if srv.auth.get("mode", "none") != "none":
            yield warn("AUTHENTICATION REQUIRED — use 'login <user>'.")
        if srv.firewall.get("enabled") and not w.is_breached(srv.id):
            yield warn("FIREWALL ACTIVE — use 'firewall' to breach it.")
        e.event("connect", server=srv.id)
        e.server_changed.emit()
        yield from self._triggers(srv.raw.get("on_connect"), f"conn:{srv.id}")

    def _server_card(self, srv) -> Out:
        return Out(spans=[(f"  {srv.name}  ", "ok"), (f"{srv.ip}  ", "info"), (f"SECURITY {srv.security}", "warn" if srv.security in ("HIGH", "CRITICAL") else "dim")])

    def _run_routing(self, srv) -> Iterator:
        e = self.e
        cfg = srv.routing
        seed = e.rng.randrange(1 << 30) if cfg.get("always") else zlib.crc32(srv.id.encode())
        puzzle = RoutingPuzzle(seed, cfg.get("difficulty", 1), e.player.route_budget_bonus,
                               reveal=e.player.network_level >= cfg.get("difficulty", 1), target_name=srv.name)
        res = yield Minigame("routing", puzzle)
        if res and res.get("aborted") and not res.get("success"):
            yield dim("Routing aborted. No relays were burned.")
            return False
        if res and res.get("success"):
            e.world.set_routed(srv.id)
            e.bump("routes_solved")
            e.bump("minigames_won")
            e.grant_xp(10 * cfg.get("difficulty", 1) + 10, announce=False)
            yield ok("ROUTE ESTABLISHED. Relay chain locked.")
            e.event("route", server=srv.id)
            return True
        e.add_heat(10 * srv.heat_mult, "routing failure")
        e.note_failure()
        e.bump("minigames_lost")
        yield err("ROUTING FAILED. Relay chain collapsed.")
        return False

    def cmd_route(self, args):
        if not args:
            return (yield err("usage: route <server>"))
        srv, problem = self._resolve_target(args[0])
        if problem:
            for o in problem:
                yield o
            return
        if not srv.routing:
            yield info(f"{srv.name} is directly reachable. No relay route needed.")
            return
        yield from self._run_routing(srv)

    def cmd_disconnect(self, args):
        e, w = self.e, self.e.world
        if not w.server:
            return (yield dim("Not connected."))
        name = w.server.name
        yield Out(f"> CLOSING TUNNEL TO {name}...", "info")
        yield Progress("DISCONNECTING", 700)
        w.disconnect()
        e.reduce_heat(8)
        yield ok("DISCONNECTED. Back on the local node.")
        e.event("disconnect", server=w.current)
        e.server_changed.emit()

    def cmd_logout(self, args):
        w = self.e.world
        if not w.server:
            return [dim("Not connected.")]
        if w.role() == 0:
            return [dim("No active session.")]
        w.logout()
        self.e.event("logout", server=w.server.id)
        self.e.server_changed.emit()
        return [ok("SESSION CLOSED.")]

    def cmd_exit(self, args):
        e = self.e
        if e.world.server:
            yield from self.cmd_disconnect([])
            return
        answer = yield Prompt("Return to main menu? Progress is autosaved. [y/N] ")
        if (answer or "").strip().lower() in ("y", "yes"):
            e.save()
            yield Fx("exit_menu")

    def cmd_scan(self, args):
        e, w = self.e, self.e.world
        if not args and w.server is None:
            yield Out("> SCANNING LOCAL NETWORK...", "info")
            yield Progress("SCANNING", 1100)
            yield Out("KNOWN HOSTS:", "title")
            for sid in w.discovered():
                s = w.servers[sid]
                state = "ONLINE" if w.is_online(sid) else "OFFLINE"
                yield Out(spans=[(f"  {s.name:<12}", "ok"), (f"{s.ip:<14}", "info"), (state, "ok" if state == "ONLINE" else "err")])
            e.bump("scans")
            e.event("scan", server="local")
            return
        if args:
            srv, problem = self._resolve_target(args[0])
            if problem:
                for o in problem:
                    yield o
                return
        else:
            srv = w.server
        if not w.is_online(srv.id):
            yield err(f"{srv.name}: HOST OFFLINE")
            return
        yield Out(f"> SCANNING {srv.name} ({srv.ip})...", "info")
        yield Progress("SCANNING", 1500)
        level = e.player.network_level
        yield out()
        yield kv("SERVER:", srv.name, 11)
        yield kv("IP:", srv.ip, 11, "info")
        yield kv("STATUS:", "ONLINE", 11)
        yield kv("SERVICES:", ", ".join(srv.services) or "-", 11, "normal")
        yield kv("SECURITY:", srv.security, 11, "warn" if srv.security in ("HIGH", "CRITICAL") else "normal")
        fw = srv.firewall
        fw_state = "NONE" if not fw.get("enabled") else ("BREACHED" if w.is_breached(srv.id) else f"ACTIVE ({fw.get('label', 'FW')})")
        yield kv("FIREWALL:", fw_state, 11, "err" if fw_state.startswith("ACTIVE") else "ok")
        yield kv("AUTH:", {"none": "OPEN", "password": "CREDENTIALS", "puzzle": "ACCESS CODE"}.get(srv.auth.get("mode"), "CREDENTIALS"), 11, "normal")
        yield Out("PORTS:", "dim")
        for port in srv.ports:
            if port.get("hidden") and level < 3:
                continue
            yield Out(f"  {port['port']:>5}/tcp  {port['service']:<10} open{'  (hidden)' if port.get('hidden') else ''}", "normal")
        if level >= 2 and srv.auth.get("users"):
            yield kv("USERS:", ", ".join(u["name"] for u in srv.auth["users"] if not u.get("hidden")), 11, "normal")
        if srv.links:
            yield Out("LINKED NODES:", "dim")
            for sid in srv.links:
                other = w.servers[sid]
                new = w.discover(sid)
                yield Out(spans=[(f"  -> {other.name:<12}", "info"), (other.ip, "dim"), ("   [NEW]" if new else "", "ok")])
        e.bump("scans")
        e.add_heat(2.5, "scan")
        e.event("scan", server=srv.id)
        e.server_changed.emit()
        yield from self._triggers(srv.raw.get("on_scan"), f"scan:{srv.id}")

    # -------------------------------------------------------------- hacking ---
    def cmd_firewall(self, args):
        e, w = self.e, self.e.world
        if (problem := self._need_conn()):
            return (yield problem)
        srv = w.server
        fw = srv.firewall
        if not fw.get("enabled"):
            return (yield ok("NO FIREWALL DETECTED. Perimeter is open."))
        if w.is_breached(srv.id):
            return (yield ok("Firewall already breached."))
        if args and args[0].lower() == "bypass":
            return (yield from self._use_item("firewall_bypass_chip", []))
        yield Out(f"> ANALYZING {fw.get('label', 'FIREWALL')}...", "info")
        yield Progress("ANALYZING", 900)
        p = e.player
        puzzle = FirewallPuzzle(fw.get("symbols", 6), fw.get("length", 4), fw.get("attempts", 6) + p.firewall_extra_attempts,
                                e.rng, reveal_one=p.firewall_reveals_one, name=fw.get("label", "FIREWALL"))
        res = yield Minigame("firewall", puzzle)
        wrong = (res or {}).get("failed_guesses", 0)
        if wrong:
            e.add_heat(3 * wrong, "firewall guesses")
        if (res or {}).get("aborted") and not res.get("success"):
            return (yield dim("Firewall attack aborted."))
        if res and res.get("success"):
            w.set_breached(srv.id)
            e.bump("firewalls_breached")
            e.bump("minigames_won")
            e.grant_xp(15 + 10 * fw.get("level", 1), announce=False)
            yield ok("FIREWALL BREACHED. Perimeter open.")
            e.event("firewall", server=srv.id)
            e.server_changed.emit()
        else:
            e.bump("minigames_lost")
            e.note_failure()
            e.add_heat(10, "firewall failure")
            yield err("FIREWALL HELD. Intrusion countermeasures triggered.")

    def cmd_login(self, args):
        e, w = self.e, self.e.world
        if (problem := self._need_conn()):
            return (yield problem)
        srv = w.server
        auth = srv.auth
        puzzle_cfg = auth.get("puzzle")
        if puzzle_cfg and puzzle_cfg.get("requires") and not e.check_requirement(puzzle_cfg["requires"]):
            puzzle_cfg = None
        if auth.get("mode", "none") == "none" and not puzzle_cfg:
            return (yield info("No authentication required on this host."))
        if srv.firewall.get("enabled") and not w.is_breached(srv.id):
            return (yield err("FIREWALL ACTIVE. Breach it first (firewall)."))
        if not args:
            return (yield err("usage: login <user> [password]"))
        user = args[0].lower()
        if srv.requires_item and not e.player.has(srv.requires_item):
            name = e.data.items[srv.requires_item]["name"]
            e.add_heat(4, "missing key")
            return (yield err(f"ACCESS KEY REQUIRED: {name} not found in inventory."))
        role = None
        if puzzle_cfg and user == puzzle_cfg["user"]:
            from .minigames import AccessPuzzle
            import random
            if puzzle_cfg.get("generate"):
                puzzle = AccessPuzzle.generate(random.Random(e.rng.random()), puzzle_cfg.get("length", 4), puzzle_cfg.get("attempts", 4))
            else:
                puzzle = AccessPuzzle(puzzle_cfg["code"], puzzle_cfg["clues"], puzzle_cfg.get("attempts", 4),
                                      puzzle_cfg.get("title", "ACCESS CODE REQUIRED"))
            yield Out("> ACCESS CODE CHALLENGE ISSUED", "info")
            res = yield Minigame("access", puzzle)
            if res and res.get("aborted") and not res.get("success"):
                return (yield dim("Login aborted."))
            if not (res and res.get("success")):
                e.bump("minigames_lost")
                e.note_failure()
                e.add_heat(12, "access failure")
                return (yield err("ACCESS DENIED. Challenge failed."))
            e.bump("access_solved")
            e.bump("minigames_won")
            role = puzzle_cfg.get("role", "admin")
        else:
            entry = next((u for u in auth.get("users", []) if u["name"].lower() == user), None)
            if entry is None:
                e.add_heat(4, "unknown user")
                return (yield err(f"login: unknown user '{user}'"))
            if entry.get("key_item"):
                if not e.player.has(entry["key_item"]):
                    e.add_heat(5, "missing key")
                    return (yield err(f"KEY REQUIRED: {e.data.items[entry['key_item']]['name']}"))
            else:
                password = args[1] if len(args) > 1 else (yield Prompt("password: ", secret=True))
                if (password or "") != entry["password"]:
                    e.add_heat(10, "bad password")
                    e.note_failure()
                    e.bump("failed_logins")
                    return (yield err("ACCESS DENIED. Invalid credentials."))
            role = entry.get("role", "user")
        yield Progress("AUTHENTICATING", 900)
        w.set_role(srv.id, ROLE_LEVELS[role])
        w.mark_compromised(srv.id)
        e.bump("logins")
        yield ok(f"ACCESS GRANTED — {user}@{srv.name} [{role.upper()}]")
        for line in auth.get("welcome", []):
            yield Out(e.fmt(line), "dim")
        e.event("login", server=srv.id, user=user, role=role)
        e.server_changed.emit()
        yield from self._triggers(srv.raw.get("on_login"), f"login:{srv.id}")

    def cmd_trace(self, args):
        e, w = self.e, self.e.world
        if args and w.server is None:
            return (yield err("Connect to the target first."))
        if (problem := self._need_conn()):
            return (yield problem)
        srv = w.server
        cfg = srv.trace
        if not cfg:
            return (yield dim("TRACE: no hostile signal detected on this node."))
        if w.role() < ROLE_LEVELS.get(cfg.get("min_role", "public"), 0):
            return (yield err("TRACE: log access required — login first."))
        yield Out("> ATTACHING TRACE PROBE...", "info")
        yield Progress("PROBING", 900)
        p = e.player
        tc = TraceConfig(cfg.get("hits", 5), cfg.get("misses", 3) + p.trace_extra_misses,
                         cfg.get("speed", 1.0) * p.trace_speed_factor, cfg.get("decoys", 6), cfg.get("title", "TRACE DATA STREAM"))
        res = yield Minigame("trace", tc)
        if res and res.get("aborted") and not res.get("success"):
            return (yield dim("Trace aborted."))
        if res and res.get("success"):
            e.bump("traces_done")
            e.bump("minigames_won")
            if w.mark_once(f"trace:{srv.id}"):
                e.grant_xp(30 + 10 * cfg.get("level", 1), announce=False)
            yield ok("TRACE COMPLETE. Signal origin resolved.")
            for line in cfg.get("output", []):
                yield Out(e.fmt(line), "info")
            for sid in cfg.get("reveals", []):
                if w.discover(sid):
                    yield info(f"[+] NEW HOST DISCOVERED: {w.servers[sid].name}")
            e.event("trace", server=srv.id)
            e.server_changed.emit()
            yield from self._effects(cfg.get("effects"), f"tracefx:{srv.id}")
        else:
            e.bump("minigames_lost")
            e.note_failure()
            e.add_heat(15, "trace failure")
            yield err("TRACE LOST. The signal slipped away.")

    def cmd_decrypt(self, args):
        e, w = self.e, self.e.world
        if (problem := self._need_conn()):
            return (yield problem)
        if not args:
            return (yield err("usage: decrypt <file>"))
        srv = w.server
        path = w.resolve(args[0])
        node = w.node_at(srv, path)
        if node is None or node.is_dir:
            return (yield err(f"decrypt: {args[0]}: No such file"))
        if not w.can_access(node):
            return (yield err("PERMISSION DENIED"))
        if not node.encrypted:
            return (yield info("File is not encrypted."))
        if w.is_decrypted(srv.id, path):
            return (yield ok("Already decrypted. Use 'cat'."))
        enc = node.encrypted
        puzzle = EncryptionPuzzle(self._plain(enc), enc["type"], enc.get("key"), enc.get("hints", []),
                                  e.player.decrypt_free_hints, title=node.name.upper())
        yield Out(f"> LOADING CIPHER ANALYSER FOR {node.name}...", "info")
        yield Progress("ANALYZING", 900)
        res = yield Minigame("encryption", puzzle)
        if (res or {}).get("aborted") and not res.get("success"):
            return (yield dim("Decryption aborted."))
        if (res or {}).get("extra_hints"):
            e.add_heat(4 * res["extra_hints"], "cipher hints")
        if res and res.get("success"):
            w.set_decrypted(srv.id, path)
            e.bump("decryptions")
            e.bump("minigames_won")
            e.grant_xp(20 + 10 * enc.get("level", 1), announce=False)
            yield ok("DECRYPTION COMPLETE.")
            e.event("decrypt", server=srv.id, path=path, file=node.name)
            yield dim(f"Use 'cat {node.name}' to read the plaintext.")
        else:
            e.bump("minigames_lost")
            e.note_failure()
            e.add_heat(6, "decryption failure")
            yield err("DECRYPTION ABORTED.")

    def cmd_decode(self, args):
        if not args:
            return (yield err("usage: decode <text> [-t b64|hex|rot13|bin|rev|caesar:N]"))
        mode = None
        if "-t" in args:
            i = args.index("-t")
            mode = args[i + 1].lower() if i + 1 < len(args) else None
            args = args[:i] + args[i + 2:]
        text = " ".join(args)
        results = decode_candidates(text, mode)
        if not results:
            return (yield err("DECODE: no plausible encoding found. Try -t <type>."))
        yield info(f"DECODE RESULTS for '{text[:40]}':")
        for name, value in results:
            yield Out(spans=[(f"  [{name}] ", "dim"), (value, "ok")])
            self.e.event("decode", input=text, result=value, method=name)
            trig = self.e.data.secrets["decode"].get(value.strip().lower())
            if trig and self.e.world.mark_once(f"secret:{trig['id']}"):
                from .eggs import apply_secret
                yield from apply_secret(self, trig, f"secretfx:{trig['id']}")
        self.e.bump("decodes")


def _printable(s: str) -> bool:
    return bool(s) and sum(c.isprintable() for c in s) / len(s) > 0.95 and any(c.isalnum() for c in s)


def decode_candidates(text: str, mode: str | None = None) -> list[tuple[str, str]]:
    """Pure string decoders (base64, hex, binary, rot13, reverse, caesar:N)."""
    found: list[tuple[str, str]] = []

    def b64():
        try:
            return base64.b64decode(text + "=" * (-len(text) % 4), validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            return None

    def hexd():
        try:
            return bytes.fromhex(text.replace(" ", "")).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None

    def binary():
        bits = text.replace(" ", "")
        if not bits or set(bits) - {"0", "1"} or len(bits) % 8:
            return None
        try:
            return bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8)).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None

    decoders = {"b64": b64, "hex": hexd, "bin": binary, "rot13": lambda: caesar(text, 13), "rev": lambda: text[::-1]}
    if mode and mode.startswith("caesar:"):
        try:
            return [(mode, caesar(text, -int(mode.split(":")[1])))]
        except ValueError:
            return []
    for name, fn in decoders.items():
        if mode and mode != name:
            continue
        value = fn()
        if value and value != text and (mode or _printable(value)):
            found.append((name, value))
    if not mode:                      # rot13/rev are always "printable"; keep them only as last resorts
        strong = [f for f in found if f[0] in ("b64", "hex", "bin")]
        found = strong + [f for f in found if f[0] in ("rot13", "rev")]
    return found
