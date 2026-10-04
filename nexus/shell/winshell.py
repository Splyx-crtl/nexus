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


def run_ps(shell, src: str, record_history: bool = True) -> Result:
    shell.ps_pipeline_item = None
    stripped = src.strip()
    first_tok = stripped.split(None, 1)[0] if stripped else ""
    if first_tok.lower().endswith(".ps1"):
        return _run_ps1_file(shell, first_tok)
    res = Result()
    if record_history and stripped:
        shell.session.history.append(stripped)
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
    shell.emit("command", name=name, args=list(args), status=status or 0, family="ps")
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


# --------------------------------------------------------------------------------- .ps1 scripts (B8)
# A small block-structured layer on top of the single-line pipeline engine above: if/elseif/else, foreach, for, while,
# and variable assignment with a real expression on the right (the pipeline engine above only recognises `$x=literal`,
# one token, no spaces). Deliberately not a general PowerShell interpreter — no function definitions, no try/catch, no
# passing arguments into a script — just enough for mission-style automation scripts (B8 in docs/3.0-PROGRESS.md).
_MATCH_CLOSE = {"(": ")", "{": "}"}
_KEYWORD_RE = re.compile(r"[A-Za-z_]\w*")
_ASSIGN_RE = re.compile(r"^\$([A-Za-z_]\w*)\s*(\+\+|--|\+=|-=|=)\s*(.*)$", re.S)


def _scan_balanced(text: str, i: int) -> int:
    """text[i] is an opening '(' or '{'. Returns the index just after its matching closer, skipping quoted strings."""
    open_ch = text[i]
    close_ch = _MATCH_CLOSE[open_ch]
    depth, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in "\"'":
            q = c
            i += 1
            while i < n and text[i] != q:
                i += 1
            i += 1
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise PsEvalError(f"unbalanced {open_ch!r}")


def _skip_ws_comments(text: str, i: int) -> int:
    n = len(text)
    while True:
        while i < n and text[i] in " \t\r\n":
            i += 1
        if i < n and text[i] == "#":
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue
        return i


def _split_top(text: str, sep: str) -> list[str]:
    """Split on `sep` at depth 0, skipping quoted strings and anything inside () [] {}."""
    out, cur, depth = [], [], 0
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in "\"'":
            q = c
            cur.append(c)
            i += 1
            while i < n and text[i] != q:
                cur.append(text[i])
                i += 1
            if i < n:
                cur.append(text[i])
                i += 1
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        if c == sep and depth == 0:
            out.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    out.append("".join(cur))
    return out


def _truthy_ps(cond_text: str, shell) -> bool:
    try:
        return _PsExprEval._truthy(_PsExprEval(cond_text, shell, None).run())
    except (PsEvalError, IndexError, ZeroDivisionError):
        return False


def _eval_ps_rhs(text: str, shell):
    """An assignment's right-hand side: a range (1..5), an array literal (@(1,2,3) or a bare comma list), or a plain
    scalar expression — everything _PsExprEval already understands."""
    text = text.strip()
    m = re.fullmatch(r"(-?\d+)\.\.(-?\d+)", text)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return list(range(a, b + 1)) if b >= a else list(range(a, b - 1, -1))
    inner = text[2:-1] if text.startswith("@(") and text.endswith(")") else text
    items = _split_top(inner, ",")
    if len(items) > 1 or text.startswith("@("):
        return [_PsExprEval(item, shell, None).run() for item in items if item.strip() or len(items) == 1]
    return _PsExprEval(text, shell, None).run()


def _try_ps_assign(shell, stmt_text: str) -> bool:
    m = _ASSIGN_RE.match(stmt_text.strip())
    if not m:
        return False
    name, op, rest = m.groups()
    cur = shell.vars.get(name, 0)
    if op == "++":
        shell.vars[name] = _PsExprEval._num(cur) + 1
    elif op == "--":
        shell.vars[name] = _PsExprEval._num(cur) - 1
    elif op == "+=":
        value = _eval_ps_rhs(rest, shell)
        shell.vars[name] = (str(cur) + str(value)) if isinstance(cur, str) or isinstance(value, str) else _PsExprEval._num(cur) + _PsExprEval._num(value)
    elif op == "-=":
        shell.vars[name] = _PsExprEval._num(cur) - _PsExprEval._num(_eval_ps_rhs(rest, shell))
    else:
        shell.vars[name] = _eval_ps_rhs(rest, shell)
    return True


def _read_ps_line(text: str, i: int) -> tuple[int, str]:
    n = len(text)
    start = i
    while i < n:
        c = text[i]
        if c in "\"'":
            q = c
            i += 1
            while i < n and text[i] != q:
                i += 1
            i += 1
            continue
        if c == "\n":
            return i + 1, text[start:i]
        i += 1
    return i, text[start:i]


def _ps_keyword_at(text: str, i: int) -> str:
    m = _KEYWORD_RE.match(text, i)
    if not m:
        return ""
    nxt = text[m.end():m.end() + 1]
    if nxt.isalnum() or nxt == "_":
        return ""
    return m.group(0).lower()


def _exec_ps_if(shell, text: str, i: int, res: "Result") -> tuple[int, int]:
    n = len(text)
    i += 2  # "if"
    status, executed = 0, False
    while True:
        i = _skip_ws_comments(text, i)
        if i >= n or text[i] != "(":
            raise PsEvalError("expected '(' after if/elseif")
        cond_end = _scan_balanced(text, i)
        cond_text = text[i + 1:cond_end - 1]
        i = _skip_ws_comments(text, cond_end)
        if i >= n or text[i] != "{":
            raise PsEvalError("expected '{' after if/elseif condition")
        block_end = _scan_balanced(text, i)
        block_text = text[i + 1:block_end - 1]
        i = block_end
        if not executed and _truthy_ps(cond_text, shell):
            status = _exec_ps_block(shell, block_text, res)
            executed = True
        save = i
        j = _skip_ws_comments(text, i)
        if _ps_keyword_at(text, j) == "elseif":
            i = j + 6
            continue
        if _ps_keyword_at(text, j) == "else":
            i = _skip_ws_comments(text, j + 4)
            if i < n and text[i] == "{":
                block_end = _scan_balanced(text, i)
                else_block = text[i + 1:block_end - 1]
                i = block_end
                if not executed:
                    status = _exec_ps_block(shell, else_block, res)
                    executed = True
            break
        i = save
        break
    return i, status


def _exec_ps_foreach(shell, text: str, i: int, res: "Result") -> tuple[int, int]:
    n = len(text)
    i = _skip_ws_comments(text, i + 7)  # "foreach"
    if i >= n or text[i] != "(":
        raise PsEvalError("expected '(' after foreach")
    header_end = _scan_balanced(text, i)
    header = text[i + 1:header_end - 1]
    i = _skip_ws_comments(text, header_end)
    if i >= n or text[i] != "{":
        raise PsEvalError("expected '{' after foreach header")
    block_end = _scan_balanced(text, i)
    block_text = text[i + 1:block_end - 1]
    i = block_end
    m = re.match(r"\$([A-Za-z_]\w*)\s+in\s+(.*)", header.strip(), re.S)
    if not m:
        raise PsEvalError("bad foreach header, expected $x in LIST")
    var, items = m.group(1), _eval_ps_rhs(m.group(2), shell)
    if not isinstance(items, list):
        items = [items]
    status = 0
    for item in items:
        shell.vars[var] = item
        status = _exec_ps_block(shell, block_text, res)
        if shell.ps_exit is not None:
            break
    return i, status


def _exec_ps_for(shell, text: str, i: int, res: "Result") -> tuple[int, int]:
    n = len(text)
    i = _skip_ws_comments(text, i + 3)  # "for"
    if i >= n or text[i] != "(":
        raise PsEvalError("expected '(' after for")
    header_end = _scan_balanced(text, i)
    header = text[i + 1:header_end - 1]
    i = _skip_ws_comments(text, header_end)
    if i >= n or text[i] != "{":
        raise PsEvalError("expected '{' after for header")
    block_end = _scan_balanced(text, i)
    block_text = text[i + 1:block_end - 1]
    i = block_end
    parts = _split_top(header, ";")
    if len(parts) != 3:
        raise PsEvalError("for needs (init; cond; incr)")
    init, cond, incr = parts
    if init.strip():
        _try_ps_assign(shell, init.strip())
    status, guard = 0, 0
    while (not cond.strip()) or _truthy_ps(cond, shell):
        guard += 1
        if guard > 100000:
            break
        status = _exec_ps_block(shell, block_text, res)
        if shell.ps_exit is not None:
            break
        if incr.strip():
            _try_ps_assign(shell, incr.strip())
    return i, status


def _exec_ps_while(shell, text: str, i: int, res: "Result") -> tuple[int, int]:
    n = len(text)
    i = _skip_ws_comments(text, i + 5)  # "while"
    if i >= n or text[i] != "(":
        raise PsEvalError("expected '(' after while")
    cond_end = _scan_balanced(text, i)
    cond_text = text[i + 1:cond_end - 1]
    i = _skip_ws_comments(text, cond_end)
    if i >= n or text[i] != "{":
        raise PsEvalError("expected '{' after while condition")
    block_end = _scan_balanced(text, i)
    block_text = text[i + 1:block_end - 1]
    i = block_end
    status, guard = 0, 0
    while _truthy_ps(cond_text, shell):
        guard += 1
        if guard > 100000:
            break
        status = _exec_ps_block(shell, block_text, res)
        if shell.ps_exit is not None:
            break
    return i, status


def _exec_ps_block(shell, text: str, res: "Result") -> int:
    i, n = 0, len(text)
    status, steps = 0, 0
    while i < n:
        i = _skip_ws_comments(text, i)
        if i >= n:
            break
        steps += 1
        if steps > MAX_STEPS:
            break
        kw = _ps_keyword_at(text, i)
        if kw == "if":
            i, status = _exec_ps_if(shell, text, i, res)
        elif kw == "foreach":
            i, status = _exec_ps_foreach(shell, text, i, res)
        elif kw == "for":
            i, status = _exec_ps_for(shell, text, i, res)
        elif kw == "while":
            i, status = _exec_ps_while(shell, text, i, res)
        else:
            j, line = _read_ps_line(text, i)
            i = j
            for seg in _split_top(line, ";"):          # a ';'-joined line can mix assignments and cmdlets, e.g. "Write-Output $i; $i++"
                stripped = seg.strip()
                if not stripped:
                    continue
                if _try_ps_assign(shell, stripped):
                    continue
                sub = run_ps(shell, seg, record_history=False)
                res.chunks.extend(sub.chunks)
                res.delay_ms += sub.delay_ms
                res.interactive.extend(sub.interactive)
                status = sub.status
                if shell.ps_exit is not None:
                    break
        if shell.ps_exit is not None:
            break
    return status


def run_ps_script(shell, text: str) -> Result:
    """Run a .ps1 script's full text: a sequence of statements and the control flow above."""
    res = Result()
    shell.ps_exit = None
    status = _exec_ps_block(shell, text, res)
    shell.session.last_status = res.status = status
    return res


def _run_ps1_file(shell, path: str) -> Result:
    res = Result()
    sess = shell.session
    shell.session.history.append(path.strip())
    try:
        text = sess.machine.fs.read(sess.user, path, sess.cwd)
        if isinstance(text, bytes):
            text = text.decode("latin-1")
        shell.emit("file_read", path=sess.machine.fs.norm(path, sess.cwd), machine=sess.machine.id)
    except FsError as exc:
        res.chunks.append((2, f"{path} : {exc.text}\n"))
        shell.session.last_status = res.status = 1
        return res
    shell.ps_exit = None
    status = _exec_ps_block(shell, text, res)
    shell.session.last_status = res.status = status
    return res


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


def run_cmd(shell, src: str, record_history: bool = True) -> Result:
    stripped = src.strip()
    first_tok = stripped.split(None, 1)[0] if stripped else ""
    if first_tok.lower().endswith((".bat", ".cmd")):
        return _run_batch_file(shell, first_tok)
    res = Result()
    if record_history and stripped:
        shell.session.history.append(stripped)
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
            shell.emit("command", name=name, args=list(args), status=status, family="cmd")
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


# --------------------------------------------------------------------------------- .bat/.cmd scripts (B8)
# Same idea as the .ps1 layer above, much smaller: cmd.exe's own batch language. Supports @echo off / rem comments,
# `if A==B (...) [else (...)]`, `if [not] exist PATH (...) [else (...)]`, `for %%v in (a b c) do command`, and plain
# sequential lines (each run through run_cmd). Deliberately no goto/labels/call :sub — the gnarliest, most quirk-ridden
# part of real batch syntax and not needed for mission-style automation scripts.
def _read_cmd_line(text: str, i: int) -> tuple[int, str]:
    n = len(text)
    start = i
    while i < n and text[i] != "\n":
        i += 1
    return (i + 1 if i < n else i), text[start:i]


def _cmd_keyword_at(line: str) -> tuple[str, str]:
    """(keyword, rest) if line starts with a recognised batch keyword, else ("", line)."""
    m = re.match(r"\s*(if|for)\b", line, re.I)
    if not m:
        return "", line
    return m.group(1).lower(), line[m.end():]


def _exec_cmd_if(shell, text: str, i: int, res: Result) -> tuple[int, int]:
    """`text[i]` is the start of an 'if' line. The condition and the opening '(' of its block must be on that same
    physical line (real cmd.exe syntax); the block itself (and any 'else (...)') can span further lines."""
    n = len(text)
    line_end = text.find("\n", i)
    if line_end == -1:
        line_end = n
    header = text[i:line_end]
    m = re.match(r"if\s+", header, re.I)
    rest = header[m.end():]
    paren_idx = rest.find("(")
    if paren_idx == -1:
        raise PsEvalError("expected '(' on if line")
    cond_part = rest[:paren_idx]
    block_start = i + m.end() + paren_idx
    neg = False
    mm = re.match(r"\s*not\s+", cond_part, re.I)
    if mm:
        neg = True
        cond_part = cond_part[mm.end():]
    mm = re.match(r"\s*exist\s+(\S+)", cond_part, re.I)
    if mm:
        path = _cmd_expand(mm.group(1), shell)
        cond_true = shell.session.machine.fs.exists(shell.session.machine.fs.norm(path, shell.session.cwd))
    else:
        mm = re.match(r"\s*(.+?)==(.+)", cond_part)
        if mm:
            cond_true = _cmd_expand(mm.group(1).strip(), shell) == _cmd_expand(mm.group(2).strip(), shell)
        else:
            cond_true = bool(_cmd_expand(cond_part.strip(), shell))
    if neg:
        cond_true = not cond_true
    block_end = _scan_balanced(text, block_start)
    block_text = text[block_start + 1:block_end - 1]
    i = block_end
    status = 0
    executed = False
    if cond_true:
        status = _exec_cmd_block(shell, block_text, res)
        executed = True
    save = i
    j = _skip_ws_comments(text, i)
    if re.match(r"else\b", text[j:j + 5], re.I):
        j2 = _skip_ws_comments(text, j + 4)
        if j2 < n and text[j2] == "(":
            block_end2 = _scan_balanced(text, j2)
            else_block = text[j2 + 1:block_end2 - 1]
            i = block_end2
            if not executed:
                status = _exec_cmd_block(shell, else_block, res)
            return i, status
        i = save
        return i, status
    i = save
    return i, status


def _exec_cmd_for(shell, rest: str, res: Result) -> int:
    """`for %%v in (a b c) do command` — the whole thing is on one line, already captured in `rest` (everything after
    'for')."""
    m = re.match(r"\s*%%(\w+)\s+in\s*\(([^)]*)\)\s*do\s+(.*)", rest, re.I | re.S)
    if not m:
        raise PsEvalError("bad for header, expected %%v in (...) do command")
    var, items_text, cmd_template = m.group(1), m.group(2), m.group(3)
    items = [it for it in re.split(r"[\s,]+", items_text.strip()) if it]
    status = 0
    for item in items:
        shell.session.env[var] = item
        line = cmd_template.replace(f"%%{var}", item)
        sub = run_cmd(shell, line, record_history=False)
        res.chunks.extend(sub.chunks)
        res.delay_ms += sub.delay_ms
        res.interactive.extend(sub.interactive)
        status = sub.status
    return status


def _exec_cmd_block(shell, text: str, res: Result) -> int:
    i, n = 0, len(text)
    status, steps = 0, 0
    while i < n:
        while i < n and text[i] in " \t\r\n":
            i += 1
        if i >= n:
            break
        steps += 1
        if steps > MAX_STEPS:
            break
        line_end = text.find("\n", i)
        preview = text[i:line_end if line_end != -1 else n].strip()
        if re.match(r"rem\b", preview, re.I) or preview.startswith("::") or not preview:
            i = (line_end + 1) if line_end != -1 else n
            continue
        if re.match(r"@?echo\s+(off|on)\s*$", preview, re.I):
            i = (line_end + 1) if line_end != -1 else n
            continue
        if re.match(r"if\b", preview, re.I):
            i, status = _exec_cmd_if(shell, text, i, res)
            continue
        if re.match(r"for\b", preview, re.I):
            j, line = _read_cmd_line(text, i)
            i = j
            _, rest = _cmd_keyword_at(line.strip())
            status = _exec_cmd_for(shell, rest, res)
            continue
        j, line = _read_cmd_line(text, i)
        i = j
        sub = run_cmd(shell, line, record_history=False)
        res.chunks.extend(sub.chunks)
        res.delay_ms += sub.delay_ms
        res.interactive.extend(sub.interactive)
        status = sub.status
    return status


def _run_batch_file(shell, path: str) -> Result:
    res = Result()
    sess = shell.session
    shell.session.history.append(path.strip())
    try:
        text = sess.machine.fs.read(sess.user, path, sess.cwd)
        if isinstance(text, bytes):
            text = text.decode("latin-1")
        shell.emit("file_read", path=sess.machine.fs.norm(path, sess.cwd), machine=sess.machine.id)
    except FsError as exc:
        res.chunks.append((2, f"'{path}' is not recognized as an internal or external command,\noperable program or batch file.\n"))
        shell.session.last_status = res.status = 1
        return res
    status = _exec_cmd_block(shell, text, res)
    shell.session.last_status = res.status = status
    return res
