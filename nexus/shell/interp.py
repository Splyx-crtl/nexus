"""bash interpreter: runs parsed command lines against a simulated machine.

Everything is synchronous and deterministic: pipelines run one command after the other with the previous stdout as stdin, `sleep` and
long-running tools only add to a delay the UI plays back, and a step limit stops runaway scripts. Output is kept as ordered chunks of
(stream, text) so the terminal can colour stderr differently and redirections like `2>&1` behave correctly.
"""
from __future__ import annotations

import ast
import fnmatch
import operator
import re
from dataclasses import dataclass, field
from typing import Callable

from . import registry
from .fs import FsError
from .machine import Job, Session, World
from .parser import (AndOr, Case, For, FuncDef, Group, If, ParseError, Part, Pipeline, Redirect, Seq, Simple, While, Word, parse)

MAX_STEPS = 20000
MAX_OUTPUT = 400_000
MAX_DEPTH = 40


@dataclass
class Result:
    chunks: list[tuple[int, str]] = field(default_factory=list)
    status: int = 0
    delay_ms: int = 0
    interactive: list[dict] = field(default_factory=list)
    events: list[tuple[str, dict]] = field(default_factory=list)

    @property
    def out(self) -> str:
        return "".join(t for fd, t in self.chunks if fd == 1)

    @property
    def err(self) -> str:
        return "".join(t for fd, t in self.chunks if fd == 2)

    @property
    def text(self) -> str:
        return "".join(t for _, t in self.chunks)


class _Flow(Exception):
    pass


class _Break(_Flow):
    def __init__(self, n: int = 1):
        self.n = n


class _Continue(_Flow):
    def __init__(self, n: int = 1):
        self.n = n


class _Return(_Flow):
    def __init__(self, status: int):
        self.status = status


class _Exit(_Flow):
    def __init__(self, status: int):
        self.status = status


class _Abort(_Flow):
    pass


_ARITH_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Mod: operator.mod, ast.Pow: operator.pow,
              ast.BitAnd: operator.and_, ast.BitOr: operator.or_, ast.BitXor: operator.xor, ast.LShift: operator.lshift, ast.RShift: operator.rshift}


def arith(expr: str, lookup: Callable[[str], str]) -> int:
    """Evaluate a $(( )) expression safely (integers only)."""
    text = re.sub(r"\$?\b([A-Za-z_][A-Za-z0-9_]*)\b", lambda m: str(int(lookup(m.group(1)) or 0) if re.fullmatch(r"-?\d+", lookup(m.group(1)) or "0") else 0), expr)
    text = text.replace("&&", " and ").replace("||", " or ").replace("/", "//")
    try:
        tree = ast.parse(text.strip() or "0", mode="eval")
    except SyntaxError:
        raise ValueError(f"syntax error in expression (error token is \"{expr.strip()}\")")

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return int(node.value)
        if isinstance(node, ast.UnaryOp):
            v = ev(node.operand)
            return {ast.USub: -v, ast.UAdd: v, ast.Not: int(not v), ast.Invert: ~v}[type(node.op)] if type(node.op) in (ast.USub, ast.UAdd, ast.Not, ast.Invert) else 0
        if isinstance(node, ast.BinOp) and type(node.op) in _ARITH_OPS or isinstance(node, ast.BinOp) and isinstance(node.op, ast.FloorDiv):
            a, b = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.FloorDiv):
                if b == 0:
                    raise ZeroDivisionError("division by 0")
                return int(a / b) if (a < 0) != (b < 0) and a % b else a // b
            if isinstance(node.op, ast.Pow) and (b > 64 or abs(a) > 10**6):
                raise ValueError("exponent too large")
            if isinstance(node.op, ast.Mod) and b == 0:
                raise ZeroDivisionError("division by 0")
            return _ARITH_OPS[type(node.op)](a, b)
        if isinstance(node, ast.Compare):
            left, result = ev(node.left), True
            for op, right in zip(node.ops, node.comparators):
                r = ev(right)
                result = result and {ast.Eq: left == r, ast.NotEq: left != r, ast.Lt: left < r, ast.LtE: left <= r, ast.Gt: left > r, ast.GtE: left >= r}[type(op)]
                left = r
            return int(result)
        if isinstance(node, ast.BoolOp):
            vals = [ev(v) for v in node.values]
            return int(all(vals)) if isinstance(node.op, ast.And) else int(any(vals))
        raise ValueError(f"syntax error in expression (error token is \"{expr.strip()}\")")
    return ev(tree)


class Shell:
    def __init__(self, world: World, session: Session, level: Callable[[], int] = lambda: 10**6, listener: Callable[[str, dict], None] | None = None,
                 locked_hint: Callable[[registry.CommandSpec], str] | None = None):
        self.world = world
        self.session = session
        self.level = level
        self.listener = listener
        self.locked_hint = locked_hint
        self.vars: dict[str, str] = {}
        self.funcs: dict[str, FuncDef] = {}
        self.positional: list[str] = []
        self.script_name = "bash"
        self.steps = 0
        self.depth = 0
        self.delay_ms = 0
        self.interactive: list[dict] = []
        self.events: list[tuple[str, dict]] = []
        self._bg = 0
        self._extra_err: list[str] = []
        self.tty = True               # is the command being run writing to the terminal (not a pipe or substitution)?
        self._cmd_tty = True

    # ----------------------------------------------------------------------------- public
    def run(self, src: str) -> Result:
        """Run a command line or script and collect everything it printed."""
        self.steps = 0
        self.delay_ms, self.interactive, self.events = 0, [], []
        res = Result()
        if src.strip():
            self.session.history.append(src.strip())
        try:
            tree = parse(src)
        except ParseError as exc:
            res.chunks.append((2, f"bash: {exc}\n"))
            res.status = self.session.last_status = 2
            return res
        try:
            res.status = self.exec_seq(tree, None, res.chunks)
        except _Exit as exc:
            res.status = exc.status
            self.events.append(("exit", {"status": exc.status}))
        except (_Break, _Continue):
            res.status = 0
        except _Return as exc:
            res.status = exc.status
        except _Abort as exc:
            res.chunks.append((2, f"bash: {exc}\n"))
            res.status = 1
        self.session.last_status = res.status
        res.delay_ms, res.interactive, res.events = self.delay_ms, self.interactive, self.events
        return res

    def run_inner(self, src: str) -> list[tuple[int, str]]:
        """Run a command line for another command (find -exec, xargs, sudo): returns its output chunks, keeps history and counters untouched."""
        sink: list[tuple[int, str]] = []
        try:
            self.exec_seq(parse(src), None, sink)
        except ParseError as exc:
            sink.append((2, f"bash: {exc}\n"))
        return sink

    def emit(self, event: str, /, **data) -> None:
        self.events.append((event, data))
        if self.listener:
            self.listener(event, data)

    # ----------------------------------------------------------------------------- variables
    def get_var(self, name: str) -> str:
        s = self.session
        if name == "?":
            return str(s.last_status)
        if name == "$":
            return str(s.pid)
        if name == "#":
            return str(len(self.positional))
        if name in ("@", "*"):
            return " ".join(self.positional)
        if name == "0":
            return self.script_name
        if name.isdigit():
            i = int(name)
            return self.positional[i - 1] if 0 < i <= len(self.positional) else ""
        if name == "!":
            return str(s.pid + self._bg)
        if name == "PWD":
            return s.cwd
        if name == "RANDOM":
            return str((s.pid * 1103515245 + len(s.history) * 12345 + self.steps) % 32768)
        if name in self.vars:
            return self.vars[name]
        return s.env.get(name, "")

    def has_var(self, name: str) -> bool:
        return name in self.vars or name in self.session.env or name in ("?", "$", "#", "@", "*", "0", "PWD") or (name.isdigit() and 0 < int(name) <= len(self.positional))

    def set_var(self, name: str, value: str) -> None:
        self.vars[name] = value
        if name in self.session.env:
            self.session.env[name] = value

    def _param(self, text: str) -> str:
        """Expand the inside of $... : `HOME`, `?`, `{name:-default}`, `{#name}`, `{name%pat}`, ..."""
        if not text.startswith("{"):
            return self.get_var(text)
        inner = text[1:-1]
        if inner.startswith("#") and len(inner) > 1:
            return str(len(self.get_var(inner[1:])))
        m = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*|[0-9?$#@*!]+)(.*)", inner, re.S)
        if not m:
            return ""
        name, rest = m.group(1), m.group(2)
        value, is_set = self.get_var(name), self.has_var(name)
        if not rest:
            return value
        op = re.match(r":?[-=+?]|%%|%|##|#|//|/", rest)
        if not op:
            return value
        o, arg = op.group(0), rest[op.end():]
        arg = self.expand_str(parse_word(arg)) if arg else ""
        if o in (":-", "-"):
            return value if (value if o == ":-" else is_set) else arg
        if o in (":=", "="):
            if not (value if o == ":=" else is_set):
                self.set_var(name, arg)
                return arg
            return value
        if o in (":+", "+"):
            return arg if (value if o == ":+" else is_set) else ""
        if o in (":?", "?"):
            if not (value if o == ":?" else is_set):
                raise _Abort(f"{name}: {arg or 'parameter null or not set'}")
            return value
        if o in ("%", "%%"):
            for i in range(len(value), -1, -1) if o == "%" else range(0, len(value) + 1):
                if fnmatch.fnmatchcase(value[i:], arg):
                    return value[:i]
            return value
        if o in ("#", "##"):
            for i in range(0, len(value) + 1) if o == "#" else range(len(value), -1, -1):
                if fnmatch.fnmatchcase(value[:i], arg):
                    return value[i:]
            return value
        if o in ("/", "//"):
            old, _, new = arg.partition("/")
            return value.replace(old, new) if o == "//" else value.replace(old, new, 1)
        return value

    # ----------------------------------------------------------------------------- expansion
    def _tilde(self, text: str) -> str:
        if text == "~" or text.startswith("~/"):
            return self.session.env.get("HOME", "/") + text[1:]
        if text.startswith("~") and re.match(r"~[A-Za-z_][\w-]*(/|$)", text):
            name = re.match(r"~([\w-]+)", text).group(1)
            u = self.session.machine.user(name)
            if u:
                return (u.home or "/") + text[1 + len(name):]
        return text

    def _part_value(self, part: Part) -> str:
        if part.kind == "var":
            return self._param(part.text)
        if part.kind == "cmd":
            return self.capture(part.text)
        if part.kind == "arith":
            try:
                return str(arith(self._expand_inner(part.text), self.get_var))
            except (ValueError, ZeroDivisionError) as exc:
                raise _Abort(str(exc))
        return part.text

    def _expand_inner(self, text: str) -> str:
        """Expand $vars inside an arithmetic expression."""
        return re.sub(r"\$\{?([A-Za-z_][A-Za-z0-9_]*|[0-9?#])\}?", lambda m: self.get_var(m.group(1)) or "0", text)

    def expand(self, word: Word) -> list[str]:
        """Word -> list of arguments (parameter/command expansion, word splitting, globbing)."""
        fields: list[list[tuple[str, bool]]] = [[]]      # each field: list of (text, quoted)
        ifs = self.get_var("IFS") or " \t\n"
        splitter = re.compile("([" + re.escape(ifs) + "]+)")
        first = True
        for part in word.parts:
            if part.kind == "lit":
                text = self._tilde(part.text) if part.quote == "none" and first else part.text
                fields[-1].append((text, part.quote != "none"))
            elif part.kind == "var" and part.text in ("@", "*") and part.quote == "double":
                for k, item in enumerate(self.positional):
                    if k:
                        fields.append([])
                    fields[-1].append((item, True))
            else:
                value = self._part_value(part)
                if part.quote == "double":
                    fields[-1].append((value, True))
                else:
                    for idx, piece in enumerate(splitter.split(value)):
                        if idx % 2:                              # a separator: end the current field
                            if fields[-1]:
                                fields.append([])
                        elif piece:
                            fields[-1].append((piece, False))
            first = False
        results: list[str] = []
        for f in fields:
            if not f:
                continue
            text = "".join(t for t, _ in f)
            pattern = "".join(t if not q else re.sub(r"([*?\[\]])", r"[\1]", t) for t, q in f)
            if self.session.machine.os == "linux" and any(not q and any(ch in t for ch in "*?[") for t, q in f):
                results.extend(self.session.machine.fs.glob(pattern, self.session.cwd, self.session.user))
            else:
                results.append(text)
        return results

    def expand_str(self, word: Word) -> str:
        """Single string expansion (assignments, redirect targets, case words): no splitting, no globbing."""
        out = []
        for i, part in enumerate(word.parts):
            if part.kind == "lit":
                out.append(self._tilde(part.text) if i == 0 and part.quote == "none" else part.text)
            else:
                out.append(self._part_value(part))
        return "".join(out)

    def capture(self, src: str) -> str:
        """Run $(...) and return its stdout without trailing newlines. Variable changes inside do not leak out."""
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise _Abort("command substitution nested too deeply")
        saved = (dict(self.vars), dict(self.funcs), list(self.positional), self.session.cwd, dict(self.session.env))
        sink: list[tuple[int, str]] = []
        outer_tty, self.tty = self.tty, False
        try:
            status = self.exec_seq(parse(src), None, sink)
            self.session.last_status = status
        except ParseError as exc:
            sink.append((2, f"bash: {exc}\n"))
        finally:
            self.vars, self.funcs, self.positional, self.session.cwd, self.session.env = saved
            self.depth -= 1
            self.tty = outer_tty
        self._extra_err.extend(t for fd, t in sink if fd == 2)
        return "".join(t for fd, t in sink if fd == 1).rstrip("\n")

    # ----------------------------------------------------------------------------- execution
    def tick(self) -> None:
        self.steps += 1
        if self.steps > MAX_STEPS:
            raise _Abort("script aborted: too many operations (infinite loop?)")

    def exec_seq(self, seq: Seq, stdin: str | None, sink: list) -> int:
        status = 0
        for item, background in seq.items:
            status = self.exec_andor(item, stdin, sink, background)
            self.session.last_status = status
            if self._extra_err:
                sink.extend((2, t) for t in self._extra_err)
                self._extra_err.clear()
        return status

    def exec_andor(self, node: AndOr, stdin, sink, background: bool = False) -> int:
        if background:
            self._bg += 1
            job = Job(len(self.session.jobs) + 1, self.session.pid + self._bg, "", True)
            self.session.jobs.append(job)
            sink.append((1, f"[{job.number}] {job.pid}\n"))
        status = self.exec_pipeline(node.first, stdin, sink)
        for op, pipeline in node.rest:
            if (op == "&&" and status == 0) or (op == "||" and status != 0):
                status = self.exec_pipeline(pipeline, stdin, sink)
        return status

    def exec_pipeline(self, pl: Pipeline, stdin, sink) -> int:
        data, status = stdin, 0
        for i, cmd in enumerate(pl.commands):
            last = i == len(pl.commands) - 1
            local: list = sink if last else []
            outer = self.tty
            self.tty = outer and last
            try:
                status = self.exec_command(cmd, data, local)
            finally:
                self.tty = outer
            if not last:
                data = "".join(t for fd, t in local if fd == 1)
                sink.extend(c for c in local if c[0] == 2)
        if pl.negate:
            status = 0 if status else 1
        return status

    def exec_command(self, cmd, stdin, sink) -> int:
        self.tick()
        if isinstance(cmd, Simple):
            return self.exec_simple(cmd, stdin, sink)
        if isinstance(cmd, If):
            for cond, body in cmd.branches:
                if self.exec_seq(cond, stdin, sink) == 0:
                    return self.exec_seq(body, stdin, sink)
            return self.exec_seq(cmd.otherwise, stdin, sink) if cmd.otherwise else 0
        if isinstance(cmd, For):
            items = [x for w in cmd.words for x in self.expand(w)] if cmd.words is not None else list(self.positional)
            status = 0
            for item in items:
                self.set_var(cmd.var, item)
                try:
                    status = self.exec_seq(cmd.body, stdin, sink)
                except _Break as b:
                    if b.n > 1:
                        raise _Break(b.n - 1)
                    break
                except _Continue as c:
                    if c.n > 1:
                        raise _Continue(c.n - 1)
            return status
        if isinstance(cmd, While):
            status = 0
            while True:
                self.tick()
                cond = self.exec_seq(cmd.cond, stdin, sink)
                if (cond == 0) == cmd.until:
                    break
                try:
                    status = self.exec_seq(cmd.body, stdin, sink)
                except _Break as b:
                    if b.n > 1:
                        raise _Break(b.n - 1)
                    break
                except _Continue as c:
                    if c.n > 1:
                        raise _Continue(c.n - 1)
            return status
        if isinstance(cmd, Case):
            value = self.expand_str(cmd.word)
            for patterns, body in cmd.clauses:
                for p in patterns:
                    if fnmatch.fnmatchcase(value, self.expand_str(p)):
                        return self.exec_seq(body, stdin, sink)
            return 0
        if isinstance(cmd, Group):
            if cmd.subshell:
                saved = (dict(self.vars), dict(self.funcs), list(self.positional), self.session.cwd, dict(self.session.env))
                try:
                    return self.exec_seq(cmd.body, stdin, sink)
                finally:
                    self.vars, self.funcs, self.positional, self.session.cwd, self.session.env = saved
            return self.exec_seq(cmd.body, stdin, sink)
        if isinstance(cmd, FuncDef):
            self.funcs[cmd.name] = cmd
            return 0
        return 0

    # -- simple commands --------------------------------------------------------------------------
    def exec_simple(self, cmd: Simple, stdin: str | None, sink: list) -> int:
        words: list[str] = []
        for w in cmd.words:
            words.extend(self.expand(w))
        assigns = [(n, self.expand_str(w)) for n, w in cmd.assigns]
        if not words:
            for name, value in assigns:
                self.set_var(name, value)
            fd_map, stdin2, status = self.apply_redirect_setup(cmd.redirects, stdin, sink)
            return status
        saved = {n: self.vars.get(n) for n, _ in assigns}
        saved_env = {n: self.session.env.get(n) for n, _ in assigns}
        for name, value in assigns:
            self.vars[name] = value
            self.session.env[name] = value
        try:
            fd_map, stdin2, status = self.apply_redirect_setup(cmd.redirects, stdin, sink)
            if status:
                return status
            chunks: list[tuple[int, str]] = []
            self._cmd_tty = self.tty and fd_map.get(1) == ("term", 1)
            status = self.dispatch(words[0], words[1:], stdin2, chunks)
            self.route(chunks, fd_map, sink)
            return status
        finally:
            for name, old in saved.items():
                if old is None:
                    self.vars.pop(name, None)
                else:
                    self.vars[name] = old
            for name, old in saved_env.items():
                if old is None:
                    self.session.env.pop(name, None)
                else:
                    self.session.env[name] = old

    def apply_redirect_setup(self, redirects: list[Redirect], stdin: str | None, sink: list):
        """Resolve redirections left to right into a destination map {fd: ('term', n) | ('file', path, append)}."""
        fd_map: dict[int, tuple] = {1: ("term", 1), 2: ("term", 2)}
        fs, user, cwd = self.session.machine.fs, self.session.user, self.session.cwd
        for r in redirects:
            target = self.expand_str(r.target)
            if r.op == "<":
                try:
                    stdin = fs.read(user, target, cwd)
                    if isinstance(stdin, bytes):
                        stdin = stdin.decode("latin-1")
                except FsError as exc:
                    sink.append((2, f"bash: {target}: {exc.text}\n"))
                    return fd_map, stdin, 1
                continue
            if r.op == ">&":
                if target in ("1", "2"):
                    fd_map[r.fd] = fd_map[int(target)]
                elif target == "-":
                    fd_map[r.fd] = ("null",)
                continue
            fds = [1, 2] if r.fd == -1 else [r.fd]
            if target == "/dev/null":
                dest = ("null",)
            else:
                append = r.op == ">>"
                path = fs.norm(target, cwd)
                try:
                    if not append:
                        fs.write(user, target, "", cwd)
                    elif not fs.exists(path):
                        fs.write(user, target, "", cwd)
                    elif not fs.can(user, fs.lookup(path), "w", path):
                        raise FsError("EACCES", target)
                except FsError as exc:
                    sink.append((2, f"bash: {target}: {exc.text}\n"))
                    return fd_map, stdin, 1
                dest = ("file", target, True)
            for fd in fds:
                fd_map[fd] = dest
        return fd_map, stdin, 0

    def route(self, chunks: list[tuple[int, str]], fd_map: dict, sink: list) -> None:
        fs, user, cwd = self.session.machine.fs, self.session.user, self.session.cwd
        for fd, text in chunks:
            dest = fd_map.get(fd, ("term", fd))
            if dest[0] == "term":
                sink.append((dest[1], text))
            elif dest[0] == "file":
                try:
                    fs.write(user, dest[1], text, cwd, append=True)
                except FsError as exc:
                    sink.append((2, f"bash: {dest[1]}: {exc.text}\n"))

    # -- dispatch ---------------------------------------------------------------------------------
    def dispatch(self, name: str, args: list[str], stdin: str | None, chunks: list) -> int:
        if name in self.session.aliases and self.depth < 5:
            alias = self.session.aliases[name].split()
            if alias:
                name, args = alias[0], alias[1:] + args
        if name in self.funcs:
            return self.call_function(name, args, stdin, chunks)
        method = BUILTINS.get(name)
        if method is not None:
            return getattr(self, method)(args, stdin, chunks)
        if "/" in name:
            return self.run_path(name, args, stdin, chunks)
        return self.run_command(name, args, stdin, chunks)

    def call_function(self, name: str, args: list[str], stdin, chunks) -> int:
        self.depth += 1
        if self.depth > MAX_DEPTH:
            self.depth -= 1
            chunks.append((2, f"bash: {name}: maximum function nesting level exceeded\n"))
            return 1
        saved = self.positional
        self.positional = list(args)
        try:
            return self.exec_command(self.funcs[name].body, stdin, chunks)
        except _Return as r:
            return r.status
        finally:
            self.positional = saved
            self.depth -= 1

    def installed(self, spec: registry.CommandSpec) -> bool:
        m = self.session.machine
        if m.installed is None:
            return True
        return spec.remote and (spec.category == "core" or spec.name in m.installed) or spec.name in m.installed

    def run_command(self, name: str, args: list[str], stdin: str | None, chunks: list) -> int:
        spec = registry.lookup("bash", name)
        if spec is None or not self.installed(spec):
            chunks.append((2, f"bash: {name}: command not found\n"))
            self.emit("command_not_found", name=name)
            return 127
        if spec.level > self.level():
            hint = self.locked_hint(spec) if self.locked_hint else ""
            chunks.append((2, f"bash: {name}: command not found\n"))
            if hint:
                chunks.append((1, hint + "\n"))
            self.emit("command_locked", name=name, level=spec.level)
            return 127
        ctx = registry.Ctx(self, name, stdin)
        if "--help" in args and spec.usage:
            chunks.append((1, f"Usage: {spec.usage}\n{spec.summary}\n"))
            return 0
        try:
            status = spec.fn(ctx, args)
        except _Flow:
            raise
        except FsError as exc:
            ctx.fs_error(exc)
            status = 1
        except Exception as exc:                                 # a bug in a command must never crash the game
            ctx.err(f"{name}: internal error ({type(exc).__name__})")
            status = 1
        self.delay_ms += ctx.delay_ms
        self.interactive.extend(ctx.interactive)
        chunks.extend(ctx.chunks)
        self.emit("command", name=name, args=list(args), status=status or 0)
        return status or 0

    def run_path(self, name: str, args: list[str], stdin, chunks) -> int:
        fs, user, cwd = self.session.machine.fs, self.session.user, self.session.cwd
        base = name.rsplit("/", 1)[-1]
        if name.startswith(("/bin/", "/usr/bin/", "/usr/sbin/", "/sbin/", "/usr/local/bin/")) and registry.lookup("bash", base) and not fs.exists(name, cwd):
            return self.run_command(base, args, stdin, chunks)
        try:
            node = fs.stat(user, name, cwd)
        except FsError as exc:
            chunks.append((2, f"bash: {name}: {exc.text}\n"))
            return 127 if exc.code == "ENOENT" else 126
        if node.is_dir:
            chunks.append((2, f"bash: {name}: Is a directory\n"))
            return 126
        if not fs.can(user, node, "x", fs.norm(name, cwd)):
            chunks.append((2, f"bash: {name}: Permission denied\n"))
            return 126
        text = node.content if isinstance(node.content, str) else node.content.decode("latin-1")
        return self.run_script_text(text, args, name, stdin, chunks)

    def run_script_text(self, text: str, args: list[str], name: str, stdin, chunks) -> int:
        lines = text.splitlines()
        if lines and lines[0].startswith("#!"):
            interp = lines[0][2:].strip().split()
            if interp and not re.search(r"(ba|da|z|k)?sh$|env", interp[0]):
                chunks.append((2, f"bash: {name}: {interp[0]}: bad interpreter: No such file or directory\n"))
                return 126
        saved = (self.positional, self.script_name, dict(self.vars))
        self.positional, self.script_name = list(args), name
        self.depth += 1
        try:
            if self.depth > MAX_DEPTH:
                chunks.append((2, f"bash: {name}: scripts nested too deeply\n"))
                return 1
            try:
                return self.exec_seq(parse(text), stdin, chunks)
            except ParseError as exc:
                chunks.append((2, f"{name}: line {1}: {exc}\n"))
                return 2
            except _Exit as e:
                return e.status
            except _Return as e:
                return e.status
        finally:
            self.positional, self.script_name = saved[0], saved[1]
            self.depth -= 1

    # ----------------------------------------------------------------------------- builtins
    def b_true(self, args, stdin, chunks) -> int:
        return 0

    def b_false(self, args, stdin, chunks) -> int:
        return 1

    def b_echo(self, args, stdin, chunks) -> int:
        newline, interpret = True, False
        while args and re.fullmatch(r"-[neE]+", args[0]):
            newline = newline and "n" not in args[0]
            interpret = interpret or "e" in args[0] and "E" not in args[0]
            args = args[1:]
        text = " ".join(args)
        if interpret:
            text = re.sub(r"\\(n|t|r|\\|a|0[0-7]{0,3}|x[0-9a-fA-F]{1,2}|e)", _unescape, text)
        chunks.append((1, text + ("\n" if newline else "")))
        return 0

    def b_printf(self, args, stdin, chunks) -> int:
        if not args:
            chunks.append((2, "printf: usage: printf [-v var] format [arguments]\n"))
            return 2
        fmt, values = args[0], list(args[1:])
        fmt = re.sub(r"\\(n|t|r|\\|a|e)", _unescape, fmt)
        out, idx = [], 0

        def repl(m):
            nonlocal idx
            conv = m.group(2)
            if conv == "%":
                return "%"
            val = values[idx] if idx < len(values) else ""
            idx += 1
            try:
                if conv in "di":
                    return f"%{m.group(1)}d" % int(val or 0)
                if conv in "xXo":
                    return f"%{m.group(1)}{conv}" % int(val or 0)
                if conv in "fFeEgG":
                    return f"%{m.group(1)}{conv}" % float(val or 0)
                if conv == "c":
                    return val[:1]
            except ValueError:
                return "0"
            return f"%{m.group(1)}s" % val
        text = re.sub(r"%([-+ 0#]?\d*(?:\.\d+)?)([diouxXeEfFgGcs%])", repl, fmt)
        while values[idx:] and "%" in fmt and idx > 0:                # printf reuses the format for extra arguments
            text += re.sub(r"%([-+ 0#]?\d*(?:\.\d+)?)([diouxXeEfFgGcs%])", repl, fmt)
        chunks.append((1, text))
        return 0

    def b_pwd(self, args, stdin, chunks) -> int:
        chunks.append((1, self.session.cwd + "\n"))
        return 0

    def b_cd(self, args, stdin, chunks) -> int:
        s = self.session
        fs = s.machine.fs
        args = [a for a in args if a not in ("-L", "-P")]
        target = args[0] if args else s.env.get("HOME", "/")
        if target == "-":
            target = s.env.get("OLDPWD") or s.cwd
            chunks.append((1, target + "\n"))
        try:
            node = fs.stat(s.user, target, s.cwd)
        except FsError as exc:
            chunks.append((2, f"bash: cd: {target}: {exc.text}\n"))
            return 1
        if not node.is_dir:
            chunks.append((2, f"bash: cd: {target}: Not a directory\n"))
            return 1
        path = fs.norm(target, s.cwd)
        if not fs.can(s.user, node, "x", path):
            chunks.append((2, f"bash: cd: {target}: Permission denied\n"))
            return 1
        s.env["OLDPWD"] = s.cwd
        s.cwd = path
        s.env["PWD"] = path
        self.emit("cd", path=path)
        return 0

    def b_export(self, args, stdin, chunks) -> int:
        if not args:
            for k in sorted(self.session.env):
                chunks.append((1, f"declare -x {k}=\"{self.session.env[k]}\"\n"))
            return 0
        for a in args:
            if a.startswith("-"):
                continue
            name, eq, value = a.partition("=")
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                chunks.append((2, f"bash: export: `{a}': not a valid identifier\n"))
                return 1
            if eq:
                self.vars[name] = value
            self.session.env[name] = self.vars.get(name, self.session.env.get(name, ""))
        return 0

    def b_unset(self, args, stdin, chunks) -> int:
        for a in args:
            if a.startswith("-"):
                continue
            self.vars.pop(a, None)
            self.session.env.pop(a, None)
            self.funcs.pop(a, None)
        return 0

    def b_set(self, args, stdin, chunks) -> int:
        if not args:
            merged = {**self.session.env, **self.vars}
            for k in sorted(merged):
                chunks.append((1, f"{k}={merged[k]}\n"))
            return 0
        if args[0] == "--":
            self.positional = list(args[1:])
        return 0

    def _declare(self, args, stdin, chunks) -> int:
        for a in args:
            if a.startswith("-"):
                continue
            name, eq, value = a.partition("=")
            if eq:
                self.vars[name] = value
            elif name not in self.vars:
                self.vars[name] = ""
        return 0

    b_local = b_declare = b_readonly = b_typeset = _declare

    def b_exit(self, args, stdin, chunks) -> int:
        status = int(args[0]) if args and args[0].lstrip("-").isdigit() else self.session.last_status
        if self.session.parent is not None:                      # leaving an ssh session: back to the machine we came from
            host = self.session.machine.ip
            self.pop_session()
            chunks.append((1, f"logout\nConnection to {host} closed.\n"))
            return status
        raise _Exit(status)

    def push_session(self, machine, user, shell_name: str = "", origin: str = "") -> Session:
        """Open a new login on another machine (ssh): own variables, own cwd, own prompt. exit goes back."""
        new = Session(machine, user, shell_name or machine.shell, parent=self.session, origin=origin or self.session.machine.ip)
        new.saved_state = {"vars": self.vars, "funcs": self.funcs, "positional": self.positional}
        self.vars, self.funcs, self.positional = {}, {}, []
        self.session = new
        self.emit("session_start", machine=machine.id, user=user.name, shell=new.shell)
        return new

    def pop_session(self) -> Session:
        old = self.session
        parent = old.parent
        if parent is None:
            return old
        state = old.saved_state
        self.vars, self.funcs, self.positional = state.get("vars", {}), state.get("funcs", {}), state.get("positional", [])
        self.session = parent
        self.emit("session_end", machine=old.machine.id, user=old.user.name)
        return parent

    def b_return(self, args, stdin, chunks) -> int:
        raise _Return(int(args[0]) if args and args[0].isdigit() else self.session.last_status)

    def b_break(self, args, stdin, chunks) -> int:
        raise _Break(int(args[0]) if args and args[0].isdigit() else 1)

    def b_continue(self, args, stdin, chunks) -> int:
        raise _Continue(int(args[0]) if args and args[0].isdigit() else 1)

    def b_shift(self, args, stdin, chunks) -> int:
        n = int(args[0]) if args and args[0].isdigit() else 1
        if n > len(self.positional):
            return 1
        self.positional = self.positional[n:]
        return 0

    def b_source(self, args, stdin, chunks) -> int:
        if not args:
            chunks.append((2, "bash: source: filename argument required\n"))
            return 2
        s = self.session
        try:
            text = s.machine.fs.read(s.user, args[0], s.cwd)
        except FsError as exc:
            chunks.append((2, f"bash: {args[0]}: {exc.text}\n"))
            return 1
        saved = self.positional
        self.positional = list(args[1:])
        try:
            return self.exec_seq(parse(text if isinstance(text, str) else text.decode("latin-1")), stdin, chunks)
        except ParseError as exc:
            chunks.append((2, f"bash: {args[0]}: {exc}\n"))
            return 2
        finally:
            self.positional = saved

    def b_eval(self, args, stdin, chunks) -> int:
        try:
            return self.exec_seq(parse(" ".join(args)), stdin, chunks)
        except ParseError as exc:
            chunks.append((2, f"bash: eval: {exc}\n"))
            return 2

    def b_read(self, args, stdin, chunks) -> int:
        names, prompt = [], ""
        it = iter(args)
        for a in it:
            if a == "-p":
                prompt = next(it, "")
            elif a.startswith("-"):
                continue
            else:
                names.append(a)
        if prompt:
            chunks.append((1, prompt))
        if stdin is None or stdin == "":
            for n in names or ["REPLY"]:
                self.set_var(n, "")
            return 1
        line, _, rest = stdin.partition("\n")
        parts = line.split(None, len(names) - 1) if len(names) > 1 else [line]
        for i, n in enumerate(names or ["REPLY"]):
            self.set_var(n, parts[i] if i < len(parts) else "")
        return 0

    def b_test(self, args, stdin, chunks) -> int:
        if args and args[-1] == "]":
            args = args[:-1]
        elif args and args[-1] == "]]":
            args = args[:-1]
        try:
            return 0 if self._test(list(args)) else 1
        except ValueError as exc:
            chunks.append((2, f"bash: [: {exc}\n"))
            return 2

    b_test_ = b_test

    def _test(self, a: list[str]) -> bool:
        s = self.session
        fs = s.machine.fs
        if not a:
            return False
        if a[0] == "!":
            return not self._test(a[1:])
        for op in ("-o", "||"):
            if op in a:
                i = a.index(op)
                return self._test(a[:i]) or self._test(a[i + 1:])
        for op in ("-a", "&&"):
            if op in a:
                i = a.index(op)
                return self._test(a[:i]) and self._test(a[i + 1:])
        if a[0] == "(" and a[-1] == ")":
            return self._test(a[1:-1])
        if len(a) == 1:
            return a[0] != ""
        if len(a) == 2:
            op, x = a
            if op == "-z":
                return x == ""
            if op == "-n":
                return x != ""
            if op in ("-e", "-f", "-d", "-r", "-w", "-x", "-s", "-L", "-h"):
                try:
                    node = fs.stat(s.user, x, s.cwd, follow=op not in ("-L", "-h"))
                except FsError:
                    return False
                path = fs.norm(x, s.cwd)
                return {"-e": True, "-f": node.kind == "file", "-d": node.is_dir, "-s": node.size > 0, "-L": node.kind == "link", "-h": node.kind == "link",
                        "-r": fs.can(s.user, node, "r", path), "-w": fs.can(s.user, node, "w", path), "-x": fs.can(s.user, node, "x", path)}[op]
            raise ValueError(f"{op}: unary operator expected")
        if len(a) == 3:
            x, op, y = a
            if op in ("=", "==", "!="):
                match = fnmatch.fnmatchcase(x, y) if any(c in y for c in "*?[") else x == y
                return match if op != "!=" else not match
            if op == "=~":
                return re.search(y, x) is not None
            if op in ("-eq", "-ne", "-lt", "-le", "-gt", "-ge"):
                try:
                    xi, yi = int(x), int(y)
                except ValueError:
                    raise ValueError("integer expression expected")
                return {"-eq": xi == yi, "-ne": xi != yi, "-lt": xi < yi, "-le": xi <= yi, "-gt": xi > yi, "-ge": xi >= yi}[op]
            if op == "<":
                return x < y
            if op == ">":
                return x > y
            raise ValueError(f"{op}: binary operator expected")
        raise ValueError("too many arguments")

    def b_type(self, args, stdin, chunks) -> int:
        status = 0
        for a in args:
            if a in self.funcs:
                chunks.append((1, f"{a} is a function\n"))
            elif a in BUILTINS:
                chunks.append((1, f"{a} is a shell builtin\n"))
            elif registry.lookup("bash", a) and self.installed(registry.lookup("bash", a)):
                chunks.append((1, f"{a} is /usr/bin/{a}\n"))
            else:
                chunks.append((2, f"bash: type: {a}: not found\n"))
                status = 1
        return status

    def b_command(self, args, stdin, chunks) -> int:
        if args and args[0] in ("-v", "-V"):
            status = 0
            for a in args[1:]:
                if a in self.funcs or a in BUILTINS:
                    chunks.append((1, a + "\n"))
                elif registry.lookup("bash", a) and self.installed(registry.lookup("bash", a)):
                    chunks.append((1, f"/usr/bin/{a}\n"))
                else:
                    status = 1
            return status
        return self.dispatch(args[0], args[1:], stdin, chunks) if args else 0

    def b_alias(self, args, stdin, chunks) -> int:
        if not args:
            for k, v in sorted(self.session.aliases.items()):
                chunks.append((1, f"alias {k}='{v}'\n"))
            return 0
        for a in args:
            name, eq, value = a.partition("=")
            if eq:
                self.session.aliases[name] = value
            elif name in self.session.aliases:
                chunks.append((1, f"alias {name}='{self.session.aliases[name]}'\n"))
            else:
                chunks.append((2, f"bash: alias: {name}: not found\n"))
                return 1
        return 0

    def b_unalias(self, args, stdin, chunks) -> int:
        for a in args:
            self.session.aliases.pop(a, None)
        return 0

    def b_history(self, args, stdin, chunks) -> int:
        hist = self.session.history
        if args and args[0] == "-c":
            hist.clear()
            return 0
        shown = hist[-int(args[0]):] if args and args[0].isdigit() else hist
        start = len(hist) - len(shown) + 1
        for i, line in enumerate(shown, start):
            chunks.append((1, f"{i:>5}  {line}\n"))
        return 0

    def b_jobs(self, args, stdin, chunks) -> int:
        for job in self.session.jobs:
            chunks.append((1, f"[{job.number}]+  Done                    {job.command or 'command'}\n"))
        return 0

    def b_wait(self, args, stdin, chunks) -> int:
        return 0

    def b_trap(self, args, stdin, chunks) -> int:
        return 0

    def b_umask(self, args, stdin, chunks) -> int:
        if not args:
            chunks.append((1, "0022\n"))
        return 0

    def b_let(self, args, stdin, chunks) -> int:
        last = 0
        for a in args:
            name, eq, expr = a.partition("=")
            try:
                last = arith(self._expand_inner(expr if eq else a), self.get_var)
            except (ValueError, ZeroDivisionError) as exc:
                chunks.append((2, f"bash: let: {exc}\n"))
                return 1
            if eq:
                self.set_var(name, str(last))
        return 0 if last else 1


BUILTINS = {"true": "b_true", "false": "b_false", ":": "b_true", "echo": "b_echo", "printf": "b_printf", "pwd": "b_pwd", "cd": "b_cd", "export": "b_export",
            "unset": "b_unset", "set": "b_set", "local": "b_local", "declare": "b_declare", "readonly": "b_readonly", "typeset": "b_typeset", "exit": "b_exit",
            "return": "b_return", "break": "b_break", "continue": "b_continue", "shift": "b_shift", "source": "b_source", ".": "b_source", "eval": "b_eval",
            "read": "b_read", "test": "b_test", "[": "b_test", "[[": "b_test", "type": "b_type", "command": "b_command", "alias": "b_alias",
            "unalias": "b_unalias", "history": "b_history", "jobs": "b_jobs", "wait": "b_wait", "trap": "b_trap", "umask": "b_umask", "let": "b_let"}


def _unescape(m: re.Match) -> str:
    code = m.group(1)
    if code == "n":
        return "\n"
    if code == "t":
        return "\t"
    if code == "r":
        return "\r"
    if code == "\\":
        return "\\"
    if code == "a":
        return "\a"
    if code == "e":
        return "\x1b"
    if code.startswith("x"):
        return chr(int(code[1:], 16))
    if code.startswith("0"):
        return chr(int(code[1:] or "0", 8))
    return m.group(0)


def parse_word(text: str) -> Word:
    """Parse a fragment (the default in ${x:-fragment}) into a Word; spaces are kept, $ expansions still work."""
    from .parser import _read_word
    if not text:
        return Word([])
    word, _ = _read_word('"' + text.replace('"', '\\"') + '"', 0)
    return word
