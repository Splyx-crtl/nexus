"""PowerShell and cmd.exe line runners for Windows targets.

Much smaller than the bash engine in interp.py: PowerShell and cmd lines in this game are single pipelines (``cmd1 | cmd2 | ...``)
chained with ``;``/``&``/``&&``/``||``, not full scripts (no PowerShell functions, no batch ``if``/``for`` — that can follow later).
Both share the same ``registry.Ctx``/``@command`` machinery as bash, just under the ``"ps"`` and ``"cmd"`` families, so a Windows
target reached over ``ssh`` (see net.py) gets its own prompt and command set automatically (``Machine.shell``/``Session.shell``).

PowerShell also gets a real (if small) object pipeline: a cmdlet that produces rows (``Get-ChildItem``, ``Get-Process`` ...) sets
``ctx.objects_out`` instead of printing; ``Where-Object``/``ForEach-Object``/``Select-Object``/``Sort-Object``/``Measure-Object`` read
``ctx.objects_in`` and re-set ``ctx.objects_out``; the last stage's objects are formatted as a table, exactly like a real PowerShell
console. Scriptblocks (``{ $_.Name -eq 'x' }``) are evaluated by the small expression engine below (``$_``, ``.Property``, the
``-eq``/``-gt``/... operators, ``-and``/``-or``/``-not``, arithmetic) — not a general PowerShell interpreter, just what missions need.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from . import registry
from .fs import FsError

MAX_STEPS = 5000


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


# ======================================================================================= PowerShell
_PS_TOKEN = re.compile(r"""
    \s+                                   # whitespace
  | \#[^\n]*                              # comment
  | "(?:[^"\\]|\\.)*"                     # double-quoted (supports $var/${var} interpolation, handled later)
  | '(?:[^'\\]|\\.)*'                     # single-quoted (literal)
  | \{(?:[^{}]|\{[^{}]*\})*\}             # a scriptblock, one level of nested braces
  | \$\{[^}]+\}|\$[A-Za-z_:][\w:]*        # $variable / ${variable with spaces} / $env:NAME
  | -[A-Za-z][\w]*                        # -ParamName or -eq/-gt/... (operators are a subset of these)
  | \|\||&&|[|;]                          # separators
  | [^\s|;]+                              # anything else (bare words, numbers, paths)
""", re.VERBOSE)


def _ps_tokens(line: str) -> list[str]:
    return [m.group(0) for m in _PS_TOKEN.finditer(line) if not m.group(0)[0] in " \t" and not m.group(0).startswith("#")]


def _ps_literal(tok: str, shell) -> str:
    """A bare token's value: strip quotes, expand $vars inside double quotes."""
    if tok.startswith("'") and tok.endswith("'") and len(tok) >= 2:
        return tok[1:-1].replace("\\'", "'")
    if tok.startswith('"') and tok.endswith('"') and len(tok) >= 2:
        inner = tok[1:-1].replace('\\"', '"')
        return re.sub(r"\$([A-Za-z_][A-Za-z0-9_]*|\{[^}]+\})", lambda m: str(_ps_var(shell, m.group(1).strip("{}"))), inner)
    if tok.startswith("$"):
        return str(_ps_var(shell, tok[1:].strip("{}")))
    return tok


def _ps_var(shell, name: str):
    if name.lower().startswith("env:"):
        return shell.session.env.get(name[4:], "")
    if name == "_":
        return shell.ps_pipeline_item
    return shell.vars.get(name, "")


def split_statements(tokens: list[str]) -> list[list[str]]:
    out, cur, depth = [], [], 0
    for t in tokens:
        if t in ("(",):
            depth += 1
        if t in (")",):
            depth -= 1
        if depth == 0 and t in (";", "&", "&&", "||"):
            if cur:
                out.append(cur + [t] if t in ("&&", "||") else cur)
            cur = []
            continue
        cur.append(t)
    if cur:
        out.append(cur)
    return out


def split_pipeline(tokens: list[str]) -> list[list[str]]:
    stages, cur = [], []
    for t in tokens:
        if t == "|":
            stages.append(cur)
            cur = []
        else:
            cur.append(t)
    stages.append(cur)
    return stages


def run_ps(shell, src: str) -> Result:
    shell.ps_pipeline_item = None
    res = Result()
    if src.strip():
        shell.session.history.append(src.strip())
    status = 0
    for stmt in split_statements(_ps_tokens(src)):
        if stmt and stmt[0] in ("&&", "||"):               # conditional continuation after the previous stage
            if (stmt[0] == "&&" and status != 0) or (stmt[0] == "||" and status == 0):
                continue
            stmt = stmt[1:]
        if not stmt:
            continue
        status = _run_ps_pipeline(shell, stmt, res)
        if shell.ps_exit is not None:
            res.events.append(("exit", {"status": shell.ps_exit}))
            status = shell.ps_exit
            break
    shell.session.last_status = res.status = status
    return res


def _run_ps_pipeline(shell, tokens: list[str], res: Result) -> int:
    stages = split_pipeline(tokens)
    objects = None
    text_in: str | None = None
    status = 0
    for i, stage in enumerate(stages):
        if not stage:
            continue
        last = i == len(stages) - 1
        name_tok, arg_toks = stage[0], stage[1:]
        if "=" in name_tok and re.match(r"^\$[A-Za-z_][\w]*=", name_tok) and not arg_toks:
            shell.vars[name_tok[1:].split("=", 1)[0]] = _ps_literal(name_tok.split("=", 1)[1], shell)
            continue
        args = [_ps_literal(t, shell) if not t.startswith("{") else t for t in arg_toks]
        chunks: list[tuple[int, str]] = []
        ctx = registry.Ctx(shell, name_tok, text_in)
        ctx.objects_in, ctx.objects_out = objects, None
        status = _dispatch_ps(shell, name_tok, args, ctx, chunks)
        res.delay_ms += ctx.delay_ms
        res.interactive.extend(ctx.interactive)
        objects = ctx.objects_out
        text_in = "".join(t for fd, t in chunks if fd == 1) or None
        if not last:
            res.chunks.extend(c for c in chunks if c[0] == 2)
        else:
            res.chunks.extend(chunks)
            if objects is not None:
                res.chunks.append((1, render_table(objects)))
    return status


def _dispatch_ps(shell, name: str, args: list[str], ctx, chunks: list) -> int:
    spec = registry.lookup("ps", name) or registry.lookup("cmd", name)        # PowerShell can also run legacy console tools
    if spec is None:
        chunks.append((2, f"{name} : The term '{name}' is not recognized as the name of a cmdlet, function, script file, or operable program.\n"))
        return 1
    if spec.level > shell.level():
        hint = shell.locked_hint(spec) if shell.locked_hint else ""
        chunks.append((2, f"{name} : The term '{name}' is not recognized as the name of a cmdlet, function, script file, or operable program.\n"))
        if hint:
            chunks.append((1, hint + "\n"))
        return 1
    try:
        status = spec.fn(ctx, args)
    except FsError as exc:
        ctx.err(f"{name} : {exc.text}")
        status = 1
    except Exception as exc:
        ctx.err(f"{name} : internal error ({type(exc).__name__})")
        status = 1
    chunks.extend(ctx.chunks)
    return status or 0


def render_table(objects: list) -> str:
    """The default PowerShell console rendering of a list of objects (or a single one)."""
    if not objects:
        return ""
    if all(isinstance(o, (str, int, float)) for o in objects):
        return "".join(f"{o}\n" for o in objects)
    rows = [o if isinstance(o, dict) else {"Value": o} for o in objects]
    cols = list(rows[0].keys())
    widths = [max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in cols]
    lines = ["".join(c.ljust(w + 2) for c, w in zip(cols, widths)).rstrip()]
    lines.append("".join(("-" * len(c)).ljust(w + 2) for c, w in zip(cols, widths)).rstrip())
    for r in rows:
        lines.append("".join(str(r.get(c, "")).ljust(w + 2) for c, w in zip(cols, widths)).rstrip())
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------------- scriptblock evaluator
class PsEvalError(Exception):
    pass


_PS_OPS = ("-notlike", "-notmatch", "-notcontains", "-like", "-match", "-contains", "-eq", "-ne", "-gt", "-ge", "-lt", "-le",
           "-and", "-or", "-not", "-xor")
_TOKEN_RE = re.compile(r"""
    \s+ | "(?:[^"\\]|\\.)*" | '(?:[^'\\]|\\.)*' | \$_|\$[A-Za-z_][\w]* | -[A-Za-z]+ | \d+\.\d+|\d+
  | \.[A-Za-z_][\w]* | [(){}\[\],;+*/%!]|==|-eq|<=|>=|[<>]|&&|\|\| | [A-Za-z_][\w]*
""", re.VERBOSE)


def _tokenize_expr(src: str) -> list[str]:
    return [m.group(0) for m in _TOKEN_RE.finditer(src) if not m.group(0)[0] in " \t\n"]


class _PsExprEval:
    """Recursive-descent evaluator for one PowerShell scriptblock's statements (``;``-separated), with ``$_`` bound to ``item``."""

    def __init__(self, text: str, shell, item):
        body = text.strip()
        if body.startswith("{") and body.endswith("}"):
            body = body[1:-1]
        self.shell, self.item = shell, item
        self.statements = self._split(_tokenize_expr(body))

    @staticmethod
    def _split(tokens: list[str]) -> list[list[str]]:
        out, cur, depth = [], [], 0
        for t in tokens:
            if t == "(":
                depth += 1
            if t == ")":
                depth -= 1
            if depth == 0 and t == ";":
                if cur:
                    out.append(cur)
                cur = []
                continue
            cur.append(t)
        if cur:
            out.append(cur)
        return out

    def run(self):
        value = None
        for stmt in self.statements:
            self.t, self.p = stmt, 0
            value = self._or()
        return value

    def _peek(self):
        return self.t[self.p] if self.p < len(self.t) else None

    def _next(self):
        tok = self._peek()
        self.p += 1
        return tok

    def _or(self):
        v = self._and()
        while self._peek() in ("-or", "||", "-xor"):
            op = self._next()
            r = self._and()
            v = (self._truthy(v) != self._truthy(r)) if op == "-xor" else (self._truthy(v) or self._truthy(r))
        return v

    def _and(self):
        v = self._not()
        while self._peek() in ("-and", "&&"):
            self._next()
            r = self._not()
            v = self._truthy(v) and self._truthy(r)
        return v

    def _not(self):
        if self._peek() in ("-not", "!"):
            self._next()
            return not self._truthy(self._not())
        return self._cmp()

    def _cmp(self):
        v = self._add()
        while self._peek() in _PS_OPS or self._peek() in ("==", "<", ">", "<=", ">="):
            op = self._next()
            r = self._add()
            v = self._compare(op, v, r)
        return v

    def _compare(self, op, a, b):
        sa, sb = str(a).lower(), str(b).lower()
        if op in ("-eq", "=="):
            return self._num_or(a) == self._num_or(b) if self._both_num(a, b) else sa == sb
        if op == "-ne":
            return not self._compare("-eq", a, b)
        if op in ("-gt", ">"):
            return self._num(a) > self._num(b)
        if op in ("-ge", ">="):
            return self._num(a) >= self._num(b)
        if op in ("-lt", "<"):
            return self._num(a) < self._num(b)
        if op in ("-le", "<="):
            return self._num(a) <= self._num(b)
        if op == "-like":
            import fnmatch
            return fnmatch.fnmatchcase(sa, sb)
        if op == "-notlike":
            import fnmatch
            return not fnmatch.fnmatchcase(sa, sb)
        if op == "-match":
            return re.search(sb, sa) is not None
        if op == "-notmatch":
            return re.search(sb, sa) is None
        if op == "-contains":
            return b in (a if isinstance(a, (list, tuple)) else [a])
        if op == "-notcontains":
            return b not in (a if isinstance(a, (list, tuple)) else [a])
        raise PsEvalError(f"unknown operator {op}")

    def _add(self):
        v = self._mul()
        while self._peek() in ("+", "-"):
            op = self._next()
            r = self._mul()
            v = (str(v) + str(r)) if op == "+" and (isinstance(v, str) or isinstance(r, str)) else (self._num(v) + self._num(r) if op == "+" else self._num(v) - self._num(r))
        return v

    def _mul(self):
        v = self._unary()
        while self._peek() in ("*", "/", "%"):
            op = self._next()
            r = self._unary()
            v = self._num(v) * self._num(r) if op == "*" else (self._num(v) / self._num(r) if op == "/" else self._num(v) % self._num(r))
        return v

    def _unary(self):
        if self._peek() == "-":
            self._next()
            return -self._num(self._unary())
        return self._postfix()

    def _postfix(self):
        v = self._primary()
        while self._peek() is not None and self._peek().startswith("."):
            prop = self._next()[1:]
            v = self._property(v, prop)
        return v

    def _property(self, v, prop: str):
        if isinstance(v, dict):
            for k in v:
                if k.lower() == prop.lower():
                    return v[k]
            return ""
        if prop.lower() == "length":
            return len(v) if isinstance(v, (str, list)) else 0
        if isinstance(v, str) and prop.lower() in ("toupper", "tolower", "trim"):
            return (v.upper() if prop.lower() == "toupper" else v.lower() if prop.lower() == "tolower" else v.strip())
        return ""

    def _primary(self):
        tok = self._next()
        if tok is None:
            raise PsEvalError("unexpected end of expression")
        if tok == "(":
            v = self._or()
            if self._peek() == ")":
                self._next()
            return v
        if tok == "$_":
            return self.item
        if tok.startswith("$"):
            return _ps_var(self.shell, tok[1:])
        if tok.startswith('"'):
            inner = tok[1:-1]
            return re.sub(r"\$([A-Za-z_]\w*)", lambda m: str(_ps_var(self.shell, m.group(1))) if m.group(1) != "_" else str(self.item), inner)
        if tok.startswith("'"):
            return tok[1:-1]
        if re.fullmatch(r"\d+\.\d+", tok):
            return float(tok)
        if tok.isdigit():
            return int(tok)
        if tok in ("$true", "true"):
            return True
        if tok in ("$false", "false"):
            return False
        return tok               # a bare word (e.g. a property name used without quotes)

    @staticmethod
    def _truthy(v) -> bool:
        if isinstance(v, (int, float)):
            return v != 0
        if isinstance(v, str):
            return v != ""
        return bool(v)

    @staticmethod
    def _num(v) -> float:
        if isinstance(v, (int, float)):
            return v
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _both_num(cls, a, b) -> bool:
        return isinstance(a, (int, float)) or isinstance(b, (int, float))

    @classmethod
    def _num_or(cls, v):
        return cls._num(v) if isinstance(v, (int, float)) or (isinstance(v, str) and re.fullmatch(r"-?\d+\.?\d*", v)) else v


def eval_scriptblock(text: str, shell, item):
    try:
        return _PsExprEval(text, shell, item).run()
    except (PsEvalError, IndexError, ZeroDivisionError):
        return None


# ======================================================================================= cmd.exe
def _cmd_tokens(line: str) -> list[str]:
    out, i, n = [], 0, len(line)
    while i < n:
        c = line[i]
        if c in " \t":
            i += 1
            continue
        if line[i:i + 2] == "&&" or line[i:i + 2] == "||":
            out.append(line[i:i + 2])
            i += 2
            continue
        if c in "&|;><":
            if line[i:i + 2] == ">>":
                out.append(">>")
                i += 2
            else:
                out.append(c)
                i += 1
            continue
        if c == '"':
            j = line.find('"', i + 1)
            j = j if j >= 0 else n - 1
            out.append(line[i:j + 1])
            i = j + 1
            continue
        j = i
        while j < n and line[j] not in " \t&|;><":
            j += 1
        out.append(line[i:j])
        i = j
    return out


def _cmd_expand(tok: str, shell) -> str:
    if tok.startswith('"') and tok.endswith('"'):
        tok = tok[1:-1]
    return re.sub(r"%([A-Za-z_][\w]*)%", lambda m: shell.session.env.get(m.group(1), ""), tok)


def run_cmd(shell, src: str) -> Result:
    res = Result()
    if src.strip():
        shell.session.history.append(src.strip())
    tokens = _cmd_tokens(src)
    segments: list[tuple[str, list[str]]] = []          # (connector-before, tokens)
    cur, connector = [], ""
    for t in tokens:
        if t in ("&", "&&", "||"):
            segments.append((connector, cur))
            cur, connector = [], t
            continue
        cur.append(t)
    segments.append((connector, cur))
    status = 0
    for connector, seg in segments:
        if connector == "&&" and status != 0:
            continue
        if connector == "||" and status == 0:
            continue
        if not seg:
            continue
        status = _run_cmd_pipeline(shell, seg, res)
    shell.session.last_status = res.status = status
    return res


def _run_cmd_pipeline(shell, tokens: list[str], res: Result) -> int:
    stages, cur = [], []
    for t in tokens:
        if t == "|":
            stages.append(cur)
            cur = []
        else:
            cur.append(t)
    stages.append(cur)
    text_in = None
    status = 0
    for i, stage in enumerate(stages):
        if not stage:
            continue
        last = i == len(stages) - 1
        words, redirects = [], []
        it = iter(range(len(stage)))
        k = 0
        while k < len(stage):
            tok = stage[k]
            if tok in (">", ">>"):
                k += 1
                if k < len(stage):
                    redirects.append((tok, _cmd_expand(stage[k], shell)))
            else:
                if "=" in tok and k == 0 and re.match(r"^set\b", tok, re.I):
                    words.append(tok)
                else:
                    words.append(_cmd_expand(tok, shell))
            k += 1
        if not words:
            continue
        name, args = words[0], words[1:]
        if name.lower() == "set" and args and "=" in args[0] and args[0][0] != "/":
            k2, v2 = args[0].split("=", 1)
            shell.session.env[k2] = v2
            continue
        chunks: list[tuple[int, str]] = []
        ctx = registry.Ctx(shell, name, text_in)
        spec = registry.lookup("cmd", name)
        if spec is None:
            chunks.append((1, f"'{name}' is not recognized as an internal or external command,\noperable program or batch file.\n"))
            status = 1
        elif spec.level > shell.level():
            hint = shell.locked_hint(spec) if shell.locked_hint else ""
            chunks.append((1, f"'{name}' is not recognized as an internal or external command,\noperable program or batch file.\n" + (hint + "\n" if hint else "")))
            status = 1
        else:
            try:
                status = spec.fn(ctx, args) or 0
            except FsError as exc:
                ctx.err(exc.text)
                status = 1
            except Exception:
                ctx.err("internal error")
                status = 1
            chunks.extend(ctx.chunks)
            res.delay_ms += ctx.delay_ms
            res.interactive.extend(ctx.interactive)
        text_in = "".join(t for fd, t in chunks if fd == 1) or None
        if redirects:
            fs, user, cwd = shell.session.machine.fs, shell.session.user, shell.session.cwd
            out_text = "".join(t for fd, t in chunks if fd == 1)
            for op, path in redirects:
                try:
                    fs.write(user, path, out_text, cwd, append=(op == ">>"))
                except FsError as exc:
                    res.chunks.append((2, f"The system cannot find the path specified.\n" if exc.code == "ENOENT" else f"Access is denied.\n"))
            res.chunks.extend(c for c in chunks if c[0] == 2)
        elif not last:
            res.chunks.extend(c for c in chunks if c[0] == 2)
        else:
            res.chunks.extend(chunks)
    return status
