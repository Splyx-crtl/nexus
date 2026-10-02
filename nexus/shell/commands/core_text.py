"""Text-processing commands: grep sort uniq cut tr tee rev nl diff seq xargs sed awk sleep yes column paste head-like helpers."""
from __future__ import annotations

import difflib
import re
import time

from .. import opts
from ..fs import FsError
from ..registry import command

POSIX_CLASSES = {"[:alpha:]": "a-zA-Z", "[:digit:]": "0-9", "[:alnum:]": "a-zA-Z0-9", "[:upper:]": "A-Z", "[:lower:]": "a-z", "[:space:]": r" \t\r\n\f\v",
                 "[:punct:]": r"!-/:-@\[-`{-~", "[:blank:]": r" \t", "[:xdigit:]": "0-9a-fA-F", "[:print:]": r" -~", "[:graph:]": r"!-~"}


def bre_to_python(pattern: str, extended: bool = False) -> str:
    """Convert a POSIX basic (or extended) regular expression to Python syntax."""
    for cls, rep in POSIX_CLASSES.items():
        pattern = pattern.replace(cls, rep)
    if extended:
        return pattern
    out, i = [], 0
    while i < len(pattern):
        c = pattern[i]
        if c == "\\" and i + 1 < len(pattern):
            n = pattern[i + 1]
            out.append(n if n in "+?|(){}" else "\\" + n)
            i += 2
            continue
        if c in "+?|(){}":
            out.append("\\" + c)
        elif c == "[":                                   # copy a bracket expression untouched
            j = i + 1
            if j < len(pattern) and pattern[j] in "^":
                j += 1
            if j < len(pattern) and pattern[j] == "]":
                j += 1
            while j < len(pattern) and pattern[j] != "]":
                j += 1
            out.append(pattern[i:j + 1])
            i = j + 1
            continue
        else:
            out.append(c)
        i += 1
    return "".join(out)


def compile_pattern(ctx, pattern: str, mode: str, ignore_case: bool, word: bool = False, line: bool = False):
    try:
        if mode == "F":
            body = re.escape(pattern)
        elif mode == "P":
            body = pattern
        else:
            body = bre_to_python(pattern, mode == "E")
        if word:
            body = rf"(?<!\w)(?:{body})(?!\w)"
        if line:
            body = rf"^(?:{body})$"
        return re.compile(body, re.I if ignore_case else 0)
    except re.error as exc:
        ctx.err(f"{ctx.name}: {exc}")
        return None


# ---------------------------------------------------------------------------------------------------- grep
@command("grep", level=8, summary="Print lines that match patterns.", usage="grep [OPTION]... PATTERNS [FILE]...",
         man="""NAME
       grep - print lines that match patterns

SYNOPSIS
       grep [OPTION]... PATTERNS [FILE]...

DESCRIPTION
       grep searches the named input FILEs for lines containing a match to the given PATTERN. With no FILE, it reads standard input
       (or the current directory with -r).

       -i, --ignore-case    ignore case distinctions
       -v, --invert-match   select non-matching lines
       -n, --line-number    prefix each line of output with its line number
       -c, --count          print only a count of selected lines per FILE
       -r, -R               read all files under each directory, recursively
       -E                   PATTERN is an extended regular expression
       -F                   PATTERN is a fixed string
       -w, --word-regexp    match only whole words
       -l                   print only names of FILEs with selected lines
       -o                   print only the matched parts of a line
       -A NUM / -B NUM / -C NUM   print NUM lines of trailing / leading / surrounding context
       -h / -H              suppress / print the file name prefix
""", lesson="grep searches text for a pattern: 'grep password config.txt' prints only the lines containing the word. Add -i to ignore case, -r to search a whole folder, -n to see line numbers.")
def grep(ctx, args):
    o = opts.parse(ctx, args, short="ivncrRElLFwoqshHPxa", with_arg="eABCm",
                   long={"ignore-case": "i", "invert-match": "v", "line-number": "n", "count": "c", "recursive": "r", "word-regexp": "w", "extended-regexp": "E",
                         "fixed-strings": "F", "files-with-matches": "l", "only-matching": "o", "quiet": "q", "no-messages": "s"},
                   long_arg={"regexp": "e", "after-context": "A", "before-context": "B", "context": "C", "max-count": "m"})
    if o is None:
        return 2
    patterns = list(o.all("e"))
    rest = list(o.rest)
    if not patterns:
        if not rest:
            ctx.err("Usage: grep [OPTION]... PATTERNS [FILE]...")
            ctx.err("Try 'grep --help' for more information.")
            return 2
        patterns = [rest.pop(0)]
    mode = "E" if o.has("E") else "F" if o.has("F") else "P" if o.has("P") else "G"
    regs = []
    for p in patterns:
        for part in p.split("\n"):
            rx = compile_pattern(ctx, part, mode, o.has("i"), o.has("w"), o.has("x"))
            if rx is None:
                return 2
            regs.append(rx)
    after = int(o.get("A") or o.get("C") or 0)
    before = int(o.get("B") or o.get("C") or 0)
    maxc = int(o.get("m")) if o.get("m") else None
    files = rest
    recursive = o.has("r", "R")
    sources: list[tuple[str, str]] = []
    status = 1
    errors = False
    if not files:
        if recursive:
            files = ["."]
        else:
            sources.append(("(standard input)", ctx.stdin or ""))
    for f in files:
        if f == "-":
            sources.append(("(standard input)", ctx.stdin or ""))
            continue
        try:
            node = ctx.fs.stat(ctx.user, f, ctx.cwd)
            if node.is_dir:
                if not recursive:
                    if not o.has("s"):
                        ctx.err(f"grep: {f}: Is a directory")
                    errors = True
                    continue
                base = ctx.path(f)
                for path, n in ctx.fs.walk(base):
                    if n.kind == "file":
                        shown = f.rstrip("/") + path[len(base):] if f != "." else "." + path[len(base):] if not files == ["."] or True else path
                        if f == "." and len(files) == 1 and not rest:
                            shown = path[len(base) + 1:] if path != base else path
                        try:
                            if not ctx.fs.can(ctx.user, n, "r", path):
                                raise FsError("EACCES", path)
                            sources.append((shown, ctx.read_text(path)))
                        except FsError as exc:
                            if not o.has("s"):
                                ctx.err(f"grep: {shown}: {exc.text}")
                            errors = True
                continue
            sources.append((f, ctx.read_text(f)))
        except FsError as exc:
            if not o.has("s"):
                ctx.err(f"grep: {f}: {exc.text}")
            errors = True
    show_name = (len(sources) > 1 or recursive) and not o.has("h") or o.has("H")
    for name, text in sources:
        lines = text.split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        matched_idx = []
        for idx, line in enumerate(lines):
            hit = any(r.search(line) for r in regs)
            if hit != o.has("v"):
                matched_idx.append(idx)
                if maxc is not None and len(matched_idx) >= maxc:
                    break
        if matched_idx:
            status = 0
        if o.has("q"):
            if matched_idx:
                return 0
            continue
        if o.has("c"):
            ctx.out((f"{name}:" if show_name else "") + str(len(matched_idx)))
            continue
        if o.has("l"):
            if matched_idx:
                ctx.out(name)
            continue
        if o.has("L"):
            if not matched_idx:
                ctx.out(name)
            continue
        shown = set()
        last_printed = -2
        for idx in matched_idx:
            lo, hi = max(0, idx - before), min(len(lines) - 1, idx + after)
            if (before or after) and lo > last_printed + 1 and last_printed >= 0:
                ctx.out("--")
            for j in range(max(lo, last_printed + 1), hi + 1):
                if j in shown:
                    continue
                shown.add(j)
                is_match = j in matched_idx
                sep = ":" if is_match else "-"
                prefix = (f"{name}{sep}" if show_name else "") + (f"{j + 1}{sep}" if o.has("n") else "")
                if o.has("o") and is_match and not o.has("v"):
                    for r in regs:
                        for m in r.finditer(lines[j]):
                            if m.group(0):
                                ctx.out(prefix + m.group(0))
                else:
                    ctx.out(prefix + lines[j])
            last_printed = max(last_printed, hi)
        if matched_idx:
            ctx.event("grep_match", file=name, machine=ctx.machine.id, count=len(matched_idx), pattern=patterns[0])
    return 2 if errors and status != 0 else status


# ---------------------------------------------------------------------------------------------------- sort / uniq / cut / tr
def _sortkey_factory(o, field_sep: str | None):
    key_specs = o.all("k")

    def field(line: str, spec: str) -> str:
        m = re.fullmatch(r"(\d+)(?:,(\d+))?([nrfb]*)", spec)
        if not m:
            return line
        start, end = int(m.group(1)), int(m.group(2) or m.group(1))
        parts = line.split(field_sep) if field_sep else line.split()
        return (field_sep or " ").join(parts[start - 1:end])

    def keyfn(line: str):
        if key_specs:
            parts = []
            for spec in key_specs:
                text = field(line, spec)
                numeric = o.has("n") or "n" in spec.split(",")[-1]
                parts.append(_numeric_key(text) if numeric else (text.lower() if o.has("f") else text.lower()))
            return tuple(parts)
        if o.has("n"):
            return (_numeric_key(line), line)
        if o.has("h"):
            return (_human_key(line), line)
        return (line.lower(), line)
    return keyfn


def _numeric_key(text: str) -> float:
    m = re.match(r"\s*(-?\d+(?:\.\d+)?)", text)
    return float(m.group(1)) if m else 0.0


def _human_key(text: str) -> float:
    m = re.match(r"\s*(\d+(?:\.\d+)?)([KMGT]?)", text)
    return float(m.group(1)) * {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}[m.group(2)] if m else 0.0


@command("sort", level=8, summary="Sort lines of text files.", usage="sort [OPTION]... [FILE]...",
         man="""NAME
       sort - sort lines of text files

SYNOPSIS
       sort [OPTION]... [FILE]...

DESCRIPTION
       -n, --numeric-sort   compare according to string numerical value
       -r, --reverse        reverse the result of comparisons
       -u, --unique         output only the first of an equal run
       -k, --key=POS        sort via a key (field number); -t sets the field separator
       -t, --field-separator=SEP
       -f                   fold lower case to upper case characters
       -h                   compare human readable numbers (e.g., 2K 1G)
""", lesson="sort puts lines in order: 'sort names.txt'. -n sorts numbers properly, -r reverses. Combine with uniq: 'sort | uniq -c | sort -nr' counts and ranks things.")
def sort(ctx, args):
    o = opts.parse(ctx, args, short="nruhfbcM", with_arg="ktoT", long={"numeric-sort": "n", "reverse": "r", "unique": "u"}, long_arg={"key": "k", "field-separator": "t"})
    if o is None:
        return 2
    inputs, status = _lines_from(ctx, o.rest)
    lines = [l for _, text in inputs for l in text.split("\n")[:-1 if text.endswith("\n") else None]]
    keyfn = _sortkey_factory(o, o.get("t"))
    lines.sort(key=keyfn, reverse=o.has("r"))
    if o.has("u"):
        seen, uniq = set(), []
        for l in lines:
            k = keyfn(l) if o.get("k") or o.has("n") else l
            if k not in seen:
                seen.add(k)
                uniq.append(l)
        lines = uniq
    for l in lines:
        ctx.out(l)
    return status


def _lines_from(ctx, files):
    out, status = [], 0
    for f in files or ["-"]:
        if f == "-":
            out.append(("-", ctx.stdin or ""))
            continue
        try:
            node = ctx.fs.stat(ctx.user, f, ctx.cwd)
            if node.is_dir:
                ctx.err(f"{ctx.name}: read failed: {f}: Is a directory")
                status = 2
                continue
            out.append((f, ctx.read_text(f)))
        except FsError as exc:
            ctx.err(f"{ctx.name}: cannot read: {f}: {exc.text}")
            status = 2
    return out, status


@command("uniq", level=8, summary="Report or omit repeated lines.", usage="uniq [OPTION]... [INPUT [OUTPUT]]",
         lesson="uniq removes neighbouring duplicate lines; -c counts them. It only compares lines that follow each other, so sort first.")
def uniq(ctx, args):
    o = opts.parse(ctx, args, short="cduiD", with_arg="fsw")
    if o is None:
        return 2
    inputs, status = _lines_from(ctx, o.rest[:1])
    text = inputs[0][1] if inputs else ""
    lines = text.split("\n")[:-1 if text.endswith("\n") else None] if text else []
    groups: list[list[str]] = []
    for l in lines:
        same = groups and ((groups[-1][0].lower() == l.lower()) if o.has("i") else groups[-1][0] == l)
        if same:
            groups[-1].append(l)
        else:
            groups.append([l])
    for g in groups:
        if o.has("d") and len(g) < 2:
            continue
        if o.has("u") and len(g) > 1:
            continue
        ctx.out((f"{len(g):>7} " if o.has("c") else "") + g[0])
    return status


@command("cut", level=8, summary="Remove sections from each line of files.", usage="cut OPTION... [FILE]...",
         lesson="cut picks columns out of every line: 'cut -d: -f1 /etc/passwd' prints the first field of each line, using : as separator.")
def cut(ctx, args):
    o = opts.parse(ctx, args, short="s", with_arg="dfcb", long_arg={"delimiter": "d", "fields": "f", "characters": "c"})
    if o is None:
        return 2
    spec = o.get("f") or o.get("c") or o.get("b")
    if spec is None:
        ctx.err("cut: you must specify a list of bytes, characters, or fields")
        ctx.err("Try 'cut --help' for more information.")
        return 1
    ranges = []
    for part in spec.split(","):
        m = re.fullmatch(r"(\d*)-?(\d*)", part)
        if not m or not part:
            ctx.err(f"cut: invalid field range")
            return 1
        if "-" in part:
            lo, hi = int(m.group(1) or 1), int(m.group(2)) if m.group(2) else 10**9
        else:
            lo = hi = int(m.group(1))
        ranges.append((lo, hi))
    delim = o.get("d", "\t")
    inputs, status = _lines_from(ctx, o.rest)
    for _, text in inputs:
        for line in text.split("\n")[:-1 if text.endswith("\n") else None]:
            if o.get("f"):
                if delim not in line:
                    if not o.has("s"):
                        ctx.out(line)
                    continue
                parts = line.split(delim)
                picked = [p for i, p in enumerate(parts, 1) if any(lo <= i <= hi for lo, hi in ranges)]
                ctx.out(delim.join(picked))
            else:
                picked = [c for i, c in enumerate(line, 1) if any(lo <= i <= hi for lo, hi in ranges)]
                ctx.out("".join(picked))
    return status


def _expand_set(s: str) -> str:
    s = re.sub(r"\[:(\w+):\]", lambda m: {"alpha": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz", "digit": "0123456789", "upper": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                                          "lower": "abcdefghijklmnopqrstuvwxyz", "space": " \t\n", "alnum": "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
                                          "punct": "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"}.get(m.group(1), ""), s)
    s = s.replace("\\n", "\n").replace("\\t", "\t")
    out, i = [], 0
    while i < len(s):
        if i + 2 < len(s) and s[i + 1] == "-":
            out.extend(chr(c) for c in range(ord(s[i]), ord(s[i + 2]) + 1))
            i += 3
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


@command("tr", level=8, summary="Translate or delete characters.", usage="tr [OPTION]... SET1 [SET2]",
         lesson="tr swaps characters: 'tr a-z A-Z' makes text upper case, 'tr -d 0-9' deletes digits. It reads from a pipe, not from a file.")
def tr(ctx, args):
    o = opts.parse(ctx, args, short="dcs")
    if o is None:
        return 2
    if not o.rest:
        ctx.err("tr: missing operand")
        ctx.err("Try 'tr --help' for more information.")
        return 1
    set1 = _expand_set(o.rest[0])
    set2 = _expand_set(o.rest[1]) if len(o.rest) > 1 else ""
    text = ctx.stdin or ""
    if o.has("c"):
        set1 = "".join(chr(c) for c in range(256) if chr(c) not in set1)
    if o.has("d"):
        text = "".join(ch for ch in text if ch not in set1)
    elif set2:
        set2 = set2 + set2[-1] * max(0, len(set1) - len(set2))
        table = {ord(a): b for a, b in zip(set1, set2)}
        text = text.translate(table)
    if o.has("s"):
        squeeze = set2 or set1
        text = re.sub("([" + re.escape(squeeze) + "])\\1+", r"\1", text)
    ctx.out(text, end="")
    return 0


@command("tee", level=8, summary="Read from standard input and write to standard output and files.", usage="tee [OPTION]... [FILE]...")
def tee(ctx, args):
    o = opts.parse(ctx, args, short="ai")
    if o is None:
        return 2
    text = ctx.stdin or ""
    status = 0
    for f in o.rest:
        try:
            ctx.fs.write(ctx.user, f, text, ctx.cwd, append=o.has("a"))
        except FsError as exc:
            ctx.err(f"tee: {f}: {exc.text}")
            status = 1
    ctx.out(text, end="")
    return status


@command("rev", level=9, summary="Reverse lines characterwise.", usage="rev [FILE]...")
def rev(ctx, args):
    inputs, status = _lines_from(ctx, args)
    for _, text in inputs:
        for line in text.split("\n")[:-1 if text.endswith("\n") else None]:
            ctx.out(line[::-1])
    return status


@command("nl", level=9, summary="Number lines of files.", usage="nl [OPTION]... [FILE]...")
def nl(ctx, args):
    inputs, status = _lines_from(ctx, [a for a in args if not a.startswith("-")])
    n = 0
    for _, text in inputs:
        for line in text.split("\n")[:-1 if text.endswith("\n") else None]:
            if line.strip():
                n += 1
                ctx.out(f"{n:>6}\t{line}")
            else:
                ctx.out("")
    return status


@command("seq", level=9, summary="Print a sequence of numbers.", usage="seq [OPTION]... LAST | FIRST LAST | FIRST INCREMENT LAST")
def seq(ctx, args):
    o = opts.parse(ctx, args, short="w", with_arg="s")
    if o is None:
        return 2
    try:
        nums = [float(a) if "." in a else int(a) for a in o.rest]
    except ValueError:
        ctx.err(f"seq: invalid floating point argument: '{o.rest[0]}'")
        return 1
    if not nums:
        ctx.err("seq: missing operand")
        return 1
    first, step, last = (1, 1, nums[0]) if len(nums) == 1 else (nums[0], 1, nums[1]) if len(nums) == 2 else (nums[0], nums[1], nums[2])
    if step == 0 or (last - first) * step < 0 and last != first:
        return 0
    sep = o.get("s", "\n")
    values, v = [], first
    while (v <= last if step > 0 else v >= last) and len(values) < 100000:
        values.append(str(v))
        v += step
    width = max((len(x) for x in values), default=0) if o.has("w") else 0
    ctx.out(sep.join(x.zfill(width) for x in values))
    return 0


@command("yes", level=9, summary="Output a string repeatedly until killed.", usage="yes [STRING]...")
def yes(ctx, args):
    for _ in range(2000):
        ctx.out(" ".join(args) or "y")
    return 0


@command("sleep", level=9, summary="Delay for a specified amount of time.", usage="sleep NUMBER[SUFFIX]...")
def sleep(ctx, args):
    total = 0.0
    for a in args:
        m = re.fullmatch(r"(\d+(?:\.\d+)?)([smhd]?)", a)
        if not m:
            ctx.err(f"sleep: invalid time interval '{a}'")
            ctx.err("Try 'sleep --help' for more information.")
            return 1
        total += float(m.group(1)) * {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}[m.group(2)]
    if not args:
        ctx.err("sleep: missing operand")
        return 1
    ctx.wait(int(min(total, 30) * 1000))
    return 0


@command("diff", level=10, summary="Compare files line by line.", usage="diff [OPTION]... FILES",
         lesson="diff shows what is different between two files. '-u' prints the familiar +/- format.")
def diff(ctx, args):
    o = opts.parse(ctx, args, short="uqiyc")
    if o is None:
        return 2
    if len(o.rest) != 2:
        ctx.err("diff: missing operand after '" + (o.rest[-1] if o.rest else "diff") + "'")
        return 2
    try:
        a, b = ctx.read_text(o.rest[0]).splitlines(keepends=True), ctx.read_text(o.rest[1]).splitlines(keepends=True)
    except FsError as exc:
        ctx.err(f"diff: {exc.path or ''}: {exc.text}")
        return 2
    if a == b:
        return 0
    if o.has("q"):
        ctx.out(f"Files {o.rest[0]} and {o.rest[1]} differ")
        return 1
    if o.has("u"):
        for line in difflib.unified_diff(a, b, o.rest[0], o.rest[1], n=3):
            ctx.out(line.rstrip("\n"))
        return 1
    sm = difflib.SequenceMatcher(None, a, b)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        left = f"{i1 + 1}" if i2 - i1 <= 1 else f"{i1 + 1},{i2}"
        right = f"{j1 + 1}" if j2 - j1 <= 1 else f"{j1 + 1},{j2}"
        code = {"replace": "c", "delete": "d", "insert": "a"}[tag]
        ctx.out(f"{left if tag != 'insert' else i1}{code}{right if tag != 'delete' else j1}")
        for line in a[i1:i2]:
            ctx.out("< " + line.rstrip("\n"))
        if tag == "replace":
            ctx.out("---")
        for line in b[j1:j2]:
            ctx.out("> " + line.rstrip("\n"))
    return 1


@command("xargs", level=10, summary="Build and execute command lines from standard input.", usage="xargs [OPTION]... COMMAND [INITIAL-ARGS]...",
         lesson="xargs turns lines from a pipe into arguments: 'find . -name \"*.txt\" | xargs cat' reads every file that find lists.")
def xargs(ctx, args):
    o = opts.parse(ctx, args, short="0rt", with_arg="nIL", stop_at_positional=True)
    if o is None:
        return 2
    cmd = o.rest or ["echo"]
    items = [x for x in re.split(r"\0" if o.has("0") else r"\s+", (ctx.stdin or "").strip()) if x]
    if not items and o.has("r"):
        return 0
    quote = lambda s: "'" + s.replace("'", "'\\''") + "'"
    lines = []
    if o.get("I"):
        marker = o.get("I")
        for it in items:
            lines.append(" ".join(c.replace(marker, quote(it)) for c in cmd))
    else:
        size = int(o.get("n")) if o.get("n") else len(items) or 1
        for i in range(0, max(len(items), 1), size):
            lines.append(" ".join(cmd + [quote(x) for x in items[i:i + size]]))
    status = 0
    for line in lines:
        if o.has("t"):
            ctx.err(line)
        res = ctx.shell.run_inner(line)
        ctx.chunks.extend(res)
        if any(fd == 2 for fd, _ in res):
            status = 123
    return status


@command("paste", level=10, summary="Merge lines of files.", usage="paste [OPTION]... [FILE]...")
def paste(ctx, args):
    o = opts.parse(ctx, args, short="s", with_arg="d")
    if o is None:
        return 2
    inputs, status = _lines_from(ctx, o.rest)
    cols = [t.split("\n")[:-1 if t.endswith("\n") else None] for _, t in inputs]
    d = o.get("d", "\t")
    if o.has("s"):
        for c in cols:
            ctx.out(d.join(c))
    else:
        for row in zip(*cols) if cols else []:
            ctx.out(d.join(row))
    return status


@command("column", level=10, summary="Columnate lists.", usage="column [OPTION]... [FILE]...")
def column(ctx, args):
    o = opts.parse(ctx, args, short="t", with_arg="s")
    if o is None:
        return 2
    inputs, status = _lines_from(ctx, o.rest)
    rows = [re.split(re.escape(o.get("s")) if o.get("s") else r"\s+", l.strip()) for _, t in inputs for l in t.splitlines() if l.strip()]
    if o.has("t"):
        widths = [max(len(r[i]) for r in rows if i < len(r)) for i in range(max((len(r) for r in rows), default=0))]
        for r in rows:
            ctx.out("  ".join(c.ljust(widths[i]) for i, c in enumerate(r)).rstrip())
    else:
        for r in rows:
            ctx.out("  ".join(r))
    return status


# ---------------------------------------------------------------------------------------------------- sed
def _sed_parse(script: str, extended: bool):
    """Parse a small subset of sed: [addr[,addr]]cmd with cmd in s,d,p,y,q and ';' / newline separators."""
    cmds = []
    i = 0
    n = len(script)

    def read_addr():
        nonlocal i
        if i < n and script[i] == "$":
            i += 1
            return ("last",)
        m = re.match(r"\d+", script[i:])
        if m:
            i += m.end()
            return ("line", int(m.group(0)))
        if i < n and script[i] == "/":
            j = i + 1
            while j < n and script[j] != "/":
                j += 2 if script[j] == "\\" else 1
            rx = script[i + 1:j]
            i = j + 1
            return ("re", re.compile(bre_to_python(rx, extended)))
        return None

    while i < n:
        while i < n and script[i] in " \t;\n":
            i += 1
        if i >= n:
            break
        a1 = read_addr()
        a2 = None
        if a1 and i < n and script[i] == ",":
            i += 1
            a2 = read_addr()
        while i < n and script[i] == " ":
            i += 1
        negate = False
        if i < n and script[i] == "!":
            negate = True
            i += 1
        if i >= n:
            raise ValueError("missing command")
        c = script[i]
        i += 1
        if c == "s":
            delim = script[i]
            i += 1
            parts = []
            for _ in range(2):
                buf = []
                while i < n and script[i] != delim:
                    if script[i] == "\\" and i + 1 < n:
                        buf.append(script[i:i + 2])
                        i += 2
                    else:
                        buf.append(script[i])
                        i += 1
                if i >= n:
                    raise ValueError("unterminated `s' command")
                i += 1
                parts.append("".join(buf))
            flags = ""
            while i < n and script[i] not in ";\n }":
                flags += script[i]
                i += 1
            pattern = bre_to_python(parts[0].replace("\\" + delim, delim), extended)
            repl = re.sub(r"\\(\d)", r"\\g<\1>", parts[1].replace("\\" + delim, delim)).replace("&", r"\g<0>").replace(r"\&", "&").replace("\\n", "\n")
            rx = re.compile(pattern, re.I if "i" in flags.lower() else 0)
            cmds.append((a1, a2, negate, "s", (rx, repl, "g" in flags, "p" in flags)))
        elif c in "dpq":
            cmds.append((a1, a2, negate, c, None))
        elif c == "y":
            delim = script[i]
            i += 1
            src = script[i:script.index(delim, i)]
            i += len(src) + 1
            dst = script[i:script.index(delim, i)]
            i += len(dst) + 1
            cmds.append((a1, a2, negate, "y", {ord(a): b for a, b in zip(src, dst)}))
        else:
            raise ValueError(f"unknown command: `{c}'")
    return cmds


@command("sed", level=11, summary="Stream editor for filtering and transforming text.", usage="sed [OPTION]... {script-only-if-no-other-script} [input-file]...",
         man="""NAME
       sed - stream editor for filtering and transforming text

SYNOPSIS
       sed [OPTION]... {script-only-if-no-other-script} [input-file]...

DESCRIPTION
       -n          suppress automatic printing of pattern space
       -e SCRIPT   add the script to the commands to be executed
       -E, -r      use extended regular expressions
       -i          edit files in place

       Commands:  s/regexp/replacement/[g]   substitute      d   delete the line      p   print the line      y/abc/xyz/  transliterate
       Addresses: N (line number), $ (last line), /regexp/ ; ranges N,M
""", lesson="sed edits text as it flows past: 'sed s/old/new/g file' replaces every 'old' with 'new'. 'sed -n 5,10p file' prints only lines 5 to 10.")
def sed(ctx, args):
    o = opts.parse(ctx, args, short="nEriz", with_arg="e", long={"quiet": "n", "silent": "n", "in-place": "i"}, long_arg={"expression": "e"})
    if o is None:
        return 2
    rest = list(o.rest)
    scripts = list(o.all("e"))
    if not scripts:
        if not rest:
            ctx.err("Usage: sed [OPTION]... {script-only-if-no-other-script} [input-file]...")
            return 1
        scripts = [rest.pop(0)]
    try:
        cmds = _sed_parse("\n".join(scripts), o.has("E", "r"))
    except (ValueError, re.error, IndexError) as exc:
        ctx.err(f"sed: -e expression #1, char 0: {exc}")
        return 1
    inputs, status = _lines_from(ctx, rest)
    for name, text in inputs:
        lines = text.split("\n")
        had_nl = text.endswith("\n")
        if had_nl:
            lines.pop()
        out_lines, active = [], {}
        total = len(lines)
        quit_now = False
        for idx, line in enumerate(lines, 1):
            deleted = False
            printed_extra = []
            for ci, (a1, a2, neg, c, arg) in enumerate(cmds):
                def hit(addr, ln=line, i=idx):
                    return addr is not None and ((addr[0] == "line" and addr[1] == i) or (addr[0] == "last" and i == total) or (addr[0] == "re" and addr[1].search(ln)))
                if a1 is None:
                    selected = True
                elif a2 is None:
                    selected = hit(a1)
                else:
                    if active.get(ci):
                        selected = True
                        if hit(a2) or (a2[0] == "line" and idx >= a2[1]):
                            active[ci] = False
                    elif hit(a1):
                        selected = True
                        active[ci] = not (a2[0] == "line" and a2[1] <= idx) and not hit(a2) if a2[0] != "re" else True
                    else:
                        selected = False
                if neg:
                    selected = not selected
                if not selected:
                    continue
                if c == "s":
                    rx, repl, glob, pr = arg
                    new, count = rx.subn(repl, line, 0 if glob else 1)
                    if count:
                        line = new
                        if pr:
                            printed_extra.append(line)
                elif c == "d":
                    deleted = True
                    break
                elif c == "p":
                    printed_extra.append(line)
                elif c == "y":
                    line = line.translate(arg)
                elif c == "q":
                    quit_now = True
            out_lines.extend(printed_extra)
            if not deleted and not o.has("n"):
                out_lines.append(line)
            if quit_now:
                break
        result = "\n".join(out_lines) + ("\n" if out_lines and (had_nl or True) else "")
        if o.has("i") and name != "-":
            try:
                ctx.fs.write(ctx.user, name, result, ctx.cwd)
            except FsError as exc:
                ctx.err(f"sed: couldn't open temporary file {name}: {exc.text}")
                status = 4
        else:
            ctx.out(result, end="")
    return status


# ---------------------------------------------------------------------------------------------------- awk
class _AwkError(Exception):
    pass


def _awk_tokens(src: str):
    tokens, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c in " \t\r":
            i += 1
        elif c == "\n":
            tokens.append(("nl", "\n"))
            i += 1
        elif c == "#":
            while i < n and src[i] != "\n":
                i += 1
        elif c == '"':
            j, buf = i + 1, []
            while j < n and src[j] != '"':
                if src[j] == "\\" and j + 1 < n:
                    buf.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(src[j + 1], src[j + 1]))
                    j += 2
                else:
                    buf.append(src[j])
                    j += 1
            tokens.append(("str", "".join(buf)))
            i = j + 1
        elif c == "/" and (not tokens or tokens[-1][0] in ("op", "nl", "punct") and tokens[-1][1] not in (")", "]")):
            j = i + 1
            while j < n and src[j] != "/":
                j += 2 if src[j] == "\\" else 1
            tokens.append(("re", src[i + 1:j]))
            i = j + 1
        elif c.isdigit() or (c == "." and i + 1 < n and src[i + 1].isdigit()):
            m = re.match(r"\d*\.?\d+(?:[eE][-+]?\d+)?|\d+\.", src[i:])
            tokens.append(("num", float(m.group(0))))
            i += m.end()
        elif c.isalpha() or c == "_":
            m = re.match(r"[A-Za-z_]\w*", src[i:])
            tokens.append(("id", m.group(0)))
            i += m.end()
        elif c == "$":
            tokens.append(("op", "$"))
            i += 1
        else:
            two = src[i:i + 2]
            if two in ("==", "!=", "<=", ">=", "&&", "||", "++", "--", "+=", "-=", "*=", "/=", "%=", "!~"):
                tokens.append(("op", two))
                i += 2
            else:
                tokens.append(("op" if c in "+-*/%<>=!~?:" else "punct", c))
                i += 1
    return tokens


class _Awk:
    def __init__(self, src: str, fs: str | None, assigns: dict[str, str]):
        self.fs = fs
        self.vars: dict[str, object] = dict(assigns)
        self.out: list[str] = []
        self.tokens = _awk_tokens(src)
        self.pos = 0
        self.rules: list[tuple[str, object, list]] = []        # (kind, pattern, action-tokens)
        self.fields: list[str] = []
        self.line = ""
        self.steps = 0
        self._parse_program()

    # -- parsing into rules ---------------------------------------------------------------------------
    def _parse_program(self):
        t = self.tokens
        while self.pos < len(t):
            while self.pos < len(t) and t[self.pos][0] == "nl" or (self.pos < len(t) and t[self.pos] == ("punct", ";")):
                self.pos += 1
            if self.pos >= len(t):
                break
            kind, pattern = "main", None
            tok = t[self.pos]
            if tok == ("id", "BEGIN"):
                kind = "begin"
                self.pos += 1
            elif tok == ("id", "END"):
                kind = "end"
                self.pos += 1
            elif tok != ("punct", "{"):
                start = self.pos
                depth = 0
                while self.pos < len(t) and not (t[self.pos] == ("punct", "{") and depth == 0) and not (t[self.pos][0] == "nl" and depth == 0):
                    if t[self.pos] in (("punct", "("), ("punct", "[")):
                        depth += 1
                    if t[self.pos] in (("punct", ")"), ("punct", "]")):
                        depth -= 1
                    self.pos += 1
                pattern = t[start:self.pos]
            action = None
            if self.pos < len(t) and t[self.pos] == ("punct", "{"):
                depth, start = 0, self.pos + 1
                while self.pos < len(t):
                    if t[self.pos] == ("punct", "{"):
                        depth += 1
                    elif t[self.pos] == ("punct", "}"):
                        depth -= 1
                        if depth == 0:
                            break
                    self.pos += 1
                action = t[start:self.pos]
                self.pos += 1
            self.rules.append((kind, pattern, action))

    # -- expression evaluation (recursive descent over a token slice) --------------------------------------
    def _eval_tokens(self, toks: list):
        self._t, self._p = toks, 0
        return self._expr()

    def _peek(self):
        return self._t[self._p] if self._p < len(self._t) else (None, None)

    def _next(self):
        tok = self._peek()
        self._p += 1
        return tok

    def _expr(self):
        return self._assign()

    def _assign(self):
        start = self._p
        tok = self._peek()
        if tok[0] == "id" or tok == ("op", "$"):
            target = self._lvalue_peek()
            if target is not None:
                kind, nxt = target
                if nxt in ("=", "+=", "-=", "*=", "/=", "%="):
                    self._p = nxt_pos = self._lv_end
                    self._next()
                    value = self._assign()
                    cur = self._get(kind)
                    if nxt != "=":
                        value = self._arith(nxt[0], self._num(cur), self._num(value))
                    self._set(kind, value)
                    return value
        self._p = start
        return self._ternary()

    def _lvalue_peek(self):
        save = self._p
        tok = self._next()
        if tok == ("op", "$"):
            idx = self._primary()
            kind = ("field", self._num(idx))
        elif tok[0] == "id":
            kind = ("var", tok[1])
            if self._peek() == ("punct", "["):
                self._next()
                key = self._expr()
                self._next()
                kind = ("arr", tok[1], str(key))
        else:
            self._p = save
            return None
        nxt = self._peek()
        self._lv_end = self._p
        self._p = save
        return (kind, nxt[1]) if nxt[0] == "op" else None

    def _get(self, kind):
        if kind[0] == "field":
            i = int(kind[1])
            return self.line if i == 0 else (self.fields[i - 1] if 0 < i <= len(self.fields) else "")
        if kind[0] == "arr":
            return self.vars.get(kind[1], {}).get(kind[2], "") if isinstance(self.vars.get(kind[1]), dict) else ""
        return self.vars.get(kind[1], "")

    def _set(self, kind, value):
        if kind[0] == "field":
            i = int(kind[1])
            if i == 0:
                self.line = str(value)
                self.fields = self._split(self.line)
            else:
                while len(self.fields) < i:
                    self.fields.append("")
                self.fields[i - 1] = self._str(value)
                self.line = " ".join(self.fields)
            self.vars["NF"] = len(self.fields)
        elif kind[0] == "arr":
            self.vars.setdefault(kind[1], {})
            self.vars[kind[1]][kind[2]] = value
        else:
            self.vars[kind[1]] = value

    def _ternary(self):
        cond = self._or()
        if self._peek() == ("op", "?"):
            self._next()
            a = self._ternary()
            self._next()
            b = self._ternary()
            return a if self._truthy(cond) else b
        return cond

    def _or(self):
        v = self._and()
        while self._peek() == ("op", "||"):
            self._next()
            r = self._and()
            v = 1 if (self._truthy(v) or self._truthy(r)) else 0
        return v

    def _and(self):
        v = self._match()
        while self._peek() == ("op", "&&"):
            self._next()
            r = self._match()
            v = 1 if (self._truthy(v) and self._truthy(r)) else 0
        return v

    def _match(self):
        v = self._cmp()
        while self._peek() in (("op", "~"), ("op", "!~")):
            op = self._next()[1]
            tok = self._peek()
            if tok[0] == "re":
                self._next()
                rx = tok[1]
            else:
                rx = self._str(self._cmp())
            hit = re.search(bre_to_python(rx, True), self._str(v)) is not None
            v = 1 if hit == (op == "~") else 0
        return v

    def _cmp(self):
        v = self._concat()
        while self._peek()[0] == "op" and self._peek()[1] in ("<", ">", "<=", ">=", "==", "!="):
            op = self._next()[1]
            r = self._concat()
            both_num = self._isnum(v) and self._isnum(r)
            a, b = (self._num(v), self._num(r)) if both_num else (self._str(v), self._str(r))
            v = 1 if {"<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b, "==": a == b, "!=": a != b}[op] else 0
        return v

    def _concat(self):
        v = self._add()
        while self._peek()[0] in ("num", "str", "id") or self._peek() in (("op", "$"), ("punct", "(")) or self._peek() == ("op", "!") and False:
            if self._peek()[0] == "id" and self._peek()[1] in ("in",):
                break
            r = self._add()
            v = self._str(v) + self._str(r)
        return v

    def _add(self):
        v = self._mul()
        while self._peek() in (("op", "+"), ("op", "-")):
            op = self._next()[1]
            r = self._mul()
            v = self._arith(op, self._num(v), self._num(r))
        return v

    def _mul(self):
        v = self._unary()
        while self._peek() in (("op", "*"), ("op", "/"), ("op", "%")):
            op = self._next()[1]
            r = self._unary()
            v = self._arith(op, self._num(v), self._num(r))
        return v

    def _unary(self):
        tok = self._peek()
        if tok == ("op", "!"):
            self._next()
            return 0 if self._truthy(self._unary()) else 1
        if tok == ("op", "-"):
            self._next()
            return -self._num(self._unary())
        if tok == ("op", "+"):
            self._next()
            return self._num(self._unary())
        if tok in (("op", "++"), ("op", "--")):
            self._next()
            kind = self._lv_kind()
            val = self._num(self._get(kind)) + (1 if tok[1] == "++" else -1)
            self._set(kind, val)
            return val
        return self._postfix()

    def _lv_kind(self):
        tok = self._next()
        if tok == ("op", "$"):
            return ("field", self._num(self._primary()))
        if self._peek() == ("punct", "["):
            self._next()
            key = self._expr()
            self._next()
            return ("arr", tok[1], str(key))
        return ("var", tok[1])

    def _postfix(self):
        v = self._primary()
        if self._peek() in (("op", "++"), ("op", "--")) and self._last_kind:
            op = self._next()[1]
            self._set(self._last_kind, self._num(v) + (1 if op == "++" else -1))
        return v

    _last_kind = None

    def _primary(self):
        tok = self._next()
        self._last_kind = None
        if tok[0] == "num":
            return tok[1]
        if tok[0] == "str":
            return tok[1]
        if tok[0] == "re":
            return 1 if re.search(bre_to_python(tok[1], True), self.line) else 0
        if tok == ("punct", "("):
            v = self._expr()
            if self._peek() == ("punct", ")"):
                self._next()
            return v
        if tok == ("op", "$"):
            idx = int(self._num(self._primary()))
            self._last_kind = ("field", idx)
            return self._get(("field", idx))
        if tok[0] == "id":
            name = tok[1]
            if self._peek() == ("punct", "("):
                self._next()
                args = []
                while self._peek() != ("punct", ")") and self._peek()[0] is not None:
                    args.append(self._expr())
                    if self._peek() == ("punct", ","):
                        self._next()
                self._next()
                return self._call(name, args)
            if self._peek() == ("punct", "["):
                self._next()
                key = self._expr()
                self._next()
                self._last_kind = ("arr", name, str(key))
                return self._get(("arr", name, str(key)))
            self._last_kind = ("var", name)
            if name == "NF":
                return len(self.fields)
            return self.vars.get(name, "")
        raise _AwkError("syntax error")

    def _call(self, name, a):
        if name == "length":
            return len(self._str(a[0])) if a else len(self.line)
        if name == "toupper":
            return self._str(a[0]).upper()
        if name == "tolower":
            return self._str(a[0]).lower()
        if name == "substr":
            s, start = self._str(a[0]), int(self._num(a[1]))
            length = int(self._num(a[2])) if len(a) > 2 else len(s)
            return s[max(start - 1, 0):max(start - 1, 0) + length]
        if name == "index":
            return self._str(a[0]).find(self._str(a[1])) + 1
        if name == "int":
            return int(self._num(a[0]))
        if name == "sqrt":
            return self._num(a[0]) ** 0.5
        if name == "sprintf":
            return self._format(a)
        if name == "split":
            parts = self._split(self._str(a[0]), self._str(a[2]) if len(a) > 2 else None)
            return len(parts)
        if name == "sub" or name == "gsub":
            return 0
        raise _AwkError(f"function {name} never defined")

    # -- helpers -----------------------------------------------------------------------------------------
    def _split(self, s, fs=None):
        fs = fs if fs is not None else self.fs
        if fs is None or fs == " ":
            return s.split()
        if len(fs) == 1 and fs != "\\":
            return s.split(fs)
        return re.split(bre_to_python(fs, True), s)

    @staticmethod
    def _isnum(v):
        if isinstance(v, (int, float)):
            return True
        return bool(re.fullmatch(r"\s*[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?\s*", str(v)))

    @staticmethod
    def _num(v):
        if isinstance(v, (int, float)):
            return v
        m = re.match(r"\s*[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?", str(v))
        return float(m.group(0)) if m else 0

    @staticmethod
    def _str(v):
        if isinstance(v, float):
            return str(int(v)) if v == int(v) else f"{v:.6g}"
        return str(v)

    @staticmethod
    def _truthy(v):
        if isinstance(v, (int, float)):
            return v != 0
        return v != "" and not (re.fullmatch(r"\s*[-+]?\d+\.?\d*\s*", v) and float(v) == 0 and False)

    @staticmethod
    def _arith(op, a, b):
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            if b == 0:
                raise _AwkError("division by zero")
            return a / b
        return a % b if b else 0

    def _format(self, a):
        fmt = self._str(a[0])
        vals = list(a[1:])
        idx = 0

        def repl(m):
            nonlocal idx
            conv = m.group(2)
            if conv == "%":
                return "%"
            v = vals[idx] if idx < len(vals) else ""
            idx += 1
            if conv in "di":
                return f"%{m.group(1)}d" % int(self._num(v))
            if conv in "fFeEgG":
                return f"%{m.group(1)}{conv}" % self._num(v)
            if conv in "xXo":
                return f"%{m.group(1)}{conv}" % int(self._num(v))
            if conv == "c":
                return chr(int(v)) if isinstance(v, (int, float)) else str(v)[:1]
            return f"%{m.group(1)}s" % self._str(v)
        return re.sub(r"%([-+ 0#]?\d*(?:\.\d+)?)([diouxXeEfFgGcs%])", repl, fmt)

    # -- statements ------------------------------------------------------------------------------------------
    def _run_block(self, toks: list):
        """Run a statement list: print, printf, assignments, if/else, for, while, next, exit and expressions separated by ; or newlines."""
        stmts = self._split_statements(toks)
        for st in stmts:
            self._run_statement(st)

    def _split_statements(self, toks: list) -> list[list]:
        out, cur, depth = [], [], 0
        for t in toks:
            if t in (("punct", "{"), ("punct", "(")):
                depth += 1
            elif t in (("punct", "}"), ("punct", ")")):
                depth -= 1
            if depth == 0 and (t == ("punct", ";") or t[0] == "nl"):
                if cur:
                    out.append(cur)
                cur = []
                continue
            cur.append(t)
            if depth == 0 and t == ("punct", "}"):
                nxt_else = False
                out.append(cur)
                cur = []
        if cur:
            out.append(cur)
        merged = []
        for st in out:                      # glue "else" blocks onto the previous if
            if st and st[0] == ("id", "else") and merged:
                merged[-1] = merged[-1] + [("nl", "\n")] + st
            else:
                merged.append(st)
        return merged

    def _run_statement(self, st: list):
        self.steps += 1
        if self.steps > 200000:
            raise _AwkError("too many operations")
        if not st:
            return
        head = st[0]
        if head == ("id", "print") or head == ("id", "printf"):
            args_toks = st[1:]
            redirect = None
            for k, t in enumerate(args_toks):
                if t == ("op", ">") and False:
                    redirect = args_toks[k + 1:]
            parts, cur, depth = [], [], 0
            for t in args_toks:
                if t in (("punct", "("),):
                    depth += 1
                if t in (("punct", ")"),):
                    depth -= 1
                if t == ("punct", ",") and depth == 0:
                    parts.append(cur)
                    cur = []
                else:
                    cur.append(t)
            if cur:
                parts.append(cur)
            if len(parts) == 1 and parts[0] and parts[0][0] == ("punct", "(") and parts[0][-1] == ("punct", ")"):
                inner, depth = parts[0][1:-1], 0
                split_inner, cur2 = [], []
                for t in inner:
                    if t == ("punct", "("):
                        depth += 1
                    if t == ("punct", ")"):
                        depth -= 1
                    if t == ("punct", ",") and depth == 0:
                        split_inner.append(cur2)
                        cur2 = []
                    else:
                        cur2.append(t)
                split_inner.append(cur2)
                if len(split_inner) > 1:
                    parts = split_inner
            vals = [self._eval_tokens(p) for p in parts] if parts else [self.line]
            if head[1] == "printf":
                self.out.append(self._format(vals))
            else:
                self.out.append(self.vars.get("OFS", " ").join(self._str(v) for v in vals) + self.vars.get("ORS", "\n"))
            return
        if head == ("id", "next"):
            raise _Next()
        if head == ("id", "exit"):
            raise _Exit()
        if head == ("id", "if") or head == ("id", "while") or head == ("id", "for"):
            self._run_control(st)
            return
        if head == ("id", "delete"):
            name = st[1][1]
            self.vars[name] = {}
            return
        if head == ("punct", "{"):
            self._run_block(st[1:-1])
            return
        self._eval_tokens(st)

    def _run_control(self, st: list):
        kind = st[0][1]
        # condition between the first ( ... )
        depth, end = 0, 0
        for k in range(1, len(st)):
            if st[k] == ("punct", "("):
                depth += 1
            elif st[k] == ("punct", ")"):
                depth -= 1
                if depth == 0:
                    end = k
                    break
        cond_toks = st[2:end]
        body = st[end + 1:]
        while body and body[0][0] == "nl":
            body = body[1:]
        else_body = None
        if kind == "if":
            for k in range(len(body)):
                if body[k] == ("id", "else"):
                    body, else_body = body[:k], body[k + 1:]
                    break
            while body and body[-1][0] == "nl":
                body = body[:-1]
        def run(b):
            while b and b[0][0] == "nl":
                b = b[1:]
            if b and b[0] == ("punct", "{") and b[-1] == ("punct", "}"):
                self._run_block(b[1:-1])
            elif b:
                self._run_statement(b)
        if kind == "if":
            if self._truthy(self._eval_tokens(cond_toks)):
                run(body)
            elif else_body is not None:
                run(else_body)
        elif kind == "while":
            guard = 0
            while self._truthy(self._eval_tokens(cond_toks)) and guard < 100000:
                guard += 1
                run(body)
        else:                                                    # for (init; cond; step)  or  for (k in arr)
            if any(t == ("id", "in") for t in cond_toks):
                var, arr = cond_toks[0][1], cond_toks[-1][1]
                for key in list(self.vars.get(arr, {})):
                    self.vars[var] = key
                    run(body)
            else:
                parts, cur = [], []
                for t in cond_toks:
                    if t == ("punct", ";"):
                        parts.append(cur)
                        cur = []
                    else:
                        cur.append(t)
                parts.append(cur)
                if len(parts) == 3:
                    self._eval_tokens(parts[0])
                    guard = 0
                    while self._truthy(self._eval_tokens(parts[1])) and guard < 100000:
                        guard += 1
                        run(body)
                        self._eval_tokens(parts[2])

    # -- driver -------------------------------------------------------------------------------------------------
    def run(self, text_inputs: list[str]) -> str:
        self.vars.setdefault("NR", 0)
        self.vars.setdefault("OFS", " ")
        self.vars.setdefault("ORS", "\n")
        try:
            for kind, pattern, action in self.rules:
                if kind == "begin" and action is not None:
                    self._run_block(action)
            has_main = any(k == "main" for k, _, _ in self.rules)
            ended = False
            if has_main or any(k == "end" for k, _, _ in self.rules):
                try:
                    for text in text_inputs:
                        for line in text.split("\n")[:-1 if text.endswith("\n") else None]:
                            self.vars["NR"] = self.vars["NR"] + 1
                            self.line = line
                            self.fields = self._split(line)
                            self.vars["NF"] = len(self.fields)
                            try:
                                for kind, pattern, action in self.rules:
                                    if kind != "main":
                                        continue
                                    if pattern is not None and not self._truthy(self._eval_tokens(pattern)):
                                        continue
                                    if action is None:
                                        self.out.append(line + "\n")
                                    else:
                                        self._run_block(action)
                            except _Next:
                                continue
                except _Exit:
                    ended = True
            for kind, pattern, action in self.rules:
                if kind == "end" and action is not None:
                    self.vars["NF"] = len(self.fields)
                    try:
                        self._run_block(action)
                    except _Exit:
                        break
        except _Exit:
            pass
        return "".join(self.out)


class _Next(Exception):
    pass


class _Exit(Exception):
    pass


@command("awk", level=12, summary="Pattern scanning and processing language.", usage="awk [-F fs] [-v var=value] 'program' [file ...]",
         man="""NAME
       awk - pattern scanning and processing language

SYNOPSIS
       awk [-F fs] [-v var=value] 'program' [file ...]

DESCRIPTION
       awk reads each line, splits it into fields ($1, $2, ... $NF; $0 is the whole line) and runs the program on it.

       program:   pattern { action }  ...      BEGIN { ... }  runs before the first line,  END { ... }  after the last
       -F fs      field separator (default: whitespace)
       -v v=val   assign a variable before the program starts

       Examples:  awk '{print $1}' file      awk -F: '{print $1, $7}' /etc/passwd      awk '/error/ {n++} END {print n}' log      awk 'NR==2' file
""", lesson="awk works on columns: 'awk {print $1} file' prints the first word of each line; 'awk -F: {print $1} /etc/passwd' uses : as the separator.")
def awk(ctx, args):
    o = opts.parse(ctx, args, short="", with_arg="Fvf", long_arg={"field-separator": "F"})
    if o is None:
        return 2
    rest = list(o.rest)
    if not rest:
        ctx.err("usage: awk [-F fs][-v var=value][prog | -f progfile][file ...]")
        return 2
    program = rest.pop(0)
    assigns = {}
    for a in o.all("v"):
        k, _, v = a.partition("=")
        assigns[k] = v
    fs = o.get("F")
    if fs is not None and fs.startswith("\\t"):
        fs = "\t"
    inputs, status = _lines_from(ctx, rest)
    try:
        engine = _Awk(program, fs, assigns)
        ctx.out(engine.run([t for _, t in inputs]), end="")
    except _AwkError as exc:
        ctx.err(f"awk: {exc}")
        return 2
    except (IndexError, ValueError, KeyError, TypeError):
        ctx.err("awk: syntax error")
        return 2
    return status
