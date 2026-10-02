"""Linux file commands: ls cat head tail wc mkdir rmdir touch cp mv rm ln chmod chown stat du df tree find file basename dirname realpath readlink."""
from __future__ import annotations

import fnmatch
import re
import time

from .. import opts
from ..fs import FsError, Node, mode_string
from ..registry import command


def _time(ts: float) -> str:
    return time.strftime("%b %e %H:%M", time.gmtime(ts))


def _human(n: int) -> str:
    if n < 1024:
        return str(n)
    for unit in "KMGT":
        n /= 1024
        if n < 10 and unit != "T":
            return f"{n:.1f}{unit}"
        if n < 1024 or unit == "T":
            return f"{round(n)}{unit}"
    return str(n)


def _blocks(n: Node) -> int:
    return 0 if n.kind == "link" else max(0, -(-n.size // 4096)) * 4


def _sortkey(name: str):
    return (name.lower().lstrip("."), name)


# ------------------------------------------------------------------------------------------------ ls
@command("ls", level=1, summary="List directory contents.", usage="ls [OPTION]... [FILE]...",
         man="""NAME
       ls - list directory contents

SYNOPSIS
       ls [OPTION]... [FILE]...

DESCRIPTION
       List information about the FILEs (the current directory by default).

       -a, --all          do not ignore entries starting with .
       -A, --almost-all   do not list implied . and ..
       -l                 use a long listing format (permissions, owner, size, date)
       -h                 with -l, print sizes like 1K 234M 2G
       -R, --recursive    list subdirectories recursively
       -r, --reverse      reverse order while sorting
       -t                 sort by modification time, newest first
       -S                 sort by file size, largest first
       -d                 list directories themselves, not their contents
       -F                 append indicator (one of */@) to entries
       -1                 list one file per line
""", lesson="ls shows what is inside a folder. Try 'ls -la': -l adds permissions, owner and size, -a also shows hidden files that start with a dot.")
def ls(ctx, args):
    o = opts.parse(ctx, args, short="lLaAhRrtS1dFinG", long={"all": "a", "almost-all": "A", "human-readable": "h", "recursive": "R", "reverse": "r",
                                                              "directory": "d", "classify": "F"})
    if o is None:
        return 2
    fs, user, cwd = ctx.fs, ctx.user, ctx.cwd
    status = 0
    targets = o.rest or ["."]
    files: list[tuple[str, Node]] = []
    dirs: list[tuple[str, Node]] = []
    for t in targets:
        try:
            node = fs.stat(user, t, cwd, follow=not o.has("l") or t.endswith("/"))
        except FsError as exc:
            ctx.err(f"ls: cannot access '{t}': {exc.text}")
            status = 2
            continue
        if node.is_dir and not o.has("d"):
            dirs.append((t, node))
        else:
            files.append((t, node))

    def entry_name(name: str, node: Node) -> str:
        shown = name
        if o.has("F"):
            shown += "/" if node.is_dir else ("@" if node.kind == "link" else ("*" if node.mode & 0o111 else ""))
        if o.has("i"):
            shown = f"{abs(hash(name)) % 900000 + 100000} " + shown
        return shown

    def sort(items: list[tuple[str, Node]]) -> list[tuple[str, Node]]:
        if o.has("S"):
            items = sorted(items, key=lambda it: (-it[1].size, _sortkey(it[0])))
        elif o.has("t"):
            items = sorted(items, key=lambda it: (-it[1].mtime, _sortkey(it[0])))
        else:
            items = sorted(items, key=lambda it: _sortkey(it[0]))
        return list(reversed(items)) if o.has("r") else items

    def render(items: list[tuple[str, Node]], base_total: bool) -> None:
        if o.has("l", "n"):
            rows = []
            for name, node in items:
                size = _human(node.size) if o.has("h") else str(node.size)
                owner, group = (str(0 if node.owner == "root" else 1000), str(0 if node.group == "root" else 1000)) if o.has("n") else (node.owner, node.group)
                label = entry_name(name, node)
                if node.kind == "link":
                    label += f" -> {node.target}"
                links = 2 + sum(1 for c in node.children.values() if c.is_dir) if node.is_dir else 1
                rows.append((mode_string(node), str(links), owner, group, size, _time(node.mtime), label))
            if base_total:
                ctx.out(f"total {sum(_blocks(n) for _, n in items) // 1}")
            widths = [max(len(r[i]) for r in rows) if rows else 0 for i in range(6)]
            for r in rows:
                ctx.out(f"{r[0]} {r[1]:>{widths[1]}} {r[2]:<{widths[2]}} {r[3]:<{widths[3]}} {r[4]:>{widths[4]}} {r[5]} {r[6]}")
            return
        names = [entry_name(n, nd) for n, nd in items]
        if not names:
            return
        if o.has("1") or not ctx.tty:
            for n in names:
                ctx.out(n)
            return
        width = ctx.width
        for ncols in range(len(names), 0, -1):
            rows_n = -(-len(names) // ncols)
            cols = [names[i * rows_n:(i + 1) * rows_n] for i in range(ncols)]
            widths = [max(len(x) for x in c) for c in cols if c]
            if sum(widths) + 2 * (len(widths) - 1) <= width or ncols == 1:
                break
        for r in range(rows_n):
            line = ""
            for ci, c in enumerate(cols):
                if r < len(c):
                    line += c[r].ljust(widths[ci] + 2) if ci < len(cols) - 1 and cols[ci + 1:] and r < len(cols[ci + 1]) else c[r] + ("  " if ci < len(cols) - 1 and r < len(cols[ci + 1]) else "")
            ctx.out(line.rstrip())

    def list_dir(display: str, node: Node, header: bool) -> None:
        nonlocal status
        path = fs.norm(display, cwd)
        try:
            kids = fs.listdir(user, display, cwd)
        except FsError as exc:
            ctx.err(f"ls: cannot open directory '{display}': {exc.text}")
            status = 2
            return
        if header:
            ctx.out(f"{display}:")
        items = [(k.name, k) for k in kids if o.has("a", "A") or not k.name.startswith(".")]
        if o.has("a") and not o.has("A"):
            parent = fs.lookup(fs.dirname(path)) or node
            items = [(".", node), ("..", parent)] + items
        render(sort(items), True)
        ctx.event("ls", path=path, machine=ctx.machine.id)
        if o.has("R"):
            for k in sort([(k.name, k) for k in kids if k.is_dir and (o.has("a", "A") or not k.name.startswith("."))]):
                sub = display.rstrip("/") + "/" + k[0] if display != "." else "./" + k[0]
                ctx.out("")
                list_dir(sub, k[1], True)

    if files:
        render(sort(files), False)
    for i, (display, node) in enumerate(sort(dirs) if len(dirs) > 1 else dirs):
        if files or i:
            ctx.out("")
        list_dir(display, node, len(dirs) + len(files) > 1 or o.has("R"))
    return status


# ------------------------------------------------------------------------------------------------ cat / head / tail / wc / tac
def _inputs(ctx, files: list[str], verb: str = ""):
    """Yield (display name, text) for each input: stdin when there are no files or the name is '-'. Prints errors, returns exit status via .status."""
    status = 0
    out = []
    for f in files or ["-"]:
        if f == "-":
            out.append(("standard input", ctx.stdin or ""))
            continue
        try:
            node = ctx.fs.stat(ctx.user, f, ctx.cwd)
            if node.is_dir:
                ctx.err(f"{ctx.name}: {f}: Is a directory")
                status = 1
                continue
            out.append((f, ctx.read_text(f)))
        except FsError as exc:
            ctx.err(f"{ctx.name}: {f}: {exc.text}")
            status = 1
    return out, status


@command("cat", level=1, summary="Concatenate files and print on the standard output.", usage="cat [OPTION]... [FILE]...",
         man="""NAME
       cat - concatenate files and print on the standard output

SYNOPSIS
       cat [OPTION]... [FILE]...

DESCRIPTION
       Concatenate FILE(s) to standard output. With no FILE, or when FILE is -, read standard input.

       -n, --number     number all output lines
       -b               number nonempty output lines
       -E               display $ at end of each line
       -s               suppress repeated empty output lines
""", lesson="cat prints the content of a file. 'cat notes.txt' shows the file; with no file it copies what you pipe into it.")
def cat(ctx, args):
    o = opts.parse(ctx, args, short="nbEsAvTe", long={"number": "n", "show-ends": "E", "squeeze-blank": "s"})
    if o is None:
        return 2
    inputs, status = _inputs(ctx, o.rest)
    n = 0
    blank_prev = False
    for _, text in inputs:
        for line in text.split("\n")[:-1] if text.endswith("\n") else text.split("\n"):
            if o.has("s") and line == "" and blank_prev:
                continue
            blank_prev = line == ""
            prefix = ""
            if o.has("n") and not o.has("b") or (o.has("b") and line != ""):
                n += 1
                prefix = f"{n:>6}\t"
            ctx.out(prefix + line + ("$" if o.has("E", "e") else ""), end="\n" if text.endswith("\n") or True else "")
        if not text.endswith("\n") and text:
            ctx.chunks[-1] = (1, ctx.chunks[-1][1][:-1])        # keep a missing final newline missing
    return status


@command("tac", level=2, summary="Concatenate and print files in reverse.", usage="tac [FILE]...")
def tac(ctx, args):
    inputs, status = _inputs(ctx, args)
    for _, text in inputs:
        for line in reversed(text.splitlines()):
            ctx.out(line)
    return status


def _count_arg(ctx, o, default=10):
    v = o.get("n") or o.get("lines") or o.get("N")
    if v is None:
        return default, False
    neg = v.startswith("-") or v.startswith("+")
    try:
        return int(v), neg
    except ValueError:
        ctx.err(f"{ctx.name}: invalid number of lines: '{v}'")
        return None, False


@command("head", level=2, summary="Output the first part of files.", usage="head [OPTION]... [FILE]...",
         man="""NAME
       head - output the first part of files

SYNOPSIS
       head [OPTION]... [FILE]...

DESCRIPTION
       Print the first 10 lines of each FILE to standard output.

       -n, --lines=N   print the first N lines instead of the first 10
       -c, --bytes=N   print the first N bytes
       -q              never print headers giving file names
""", lesson="head shows the first lines of a file (10 by default). 'head -n 3 file' shows 3 lines. Great for peeking into big logs.")
def head(ctx, args):
    o = opts.parse(ctx, args, short="q", with_arg="nc", long_arg={"lines": "n", "bytes": "c"}, numeric="n")
    if o is None:
        return 2
    n, _ = _count_arg(ctx, o)
    if n is None:
        return 1
    inputs, status = _inputs(ctx, o.rest)
    for i, (name, text) in enumerate(inputs):
        if len(inputs) > 1 and not o.has("q"):
            ctx.out(("\n" if i else "") + f"==> {name} <==")
        if o.get("c"):
            ctx.out(text[:int(o.get("c"))], end="")
        else:
            lines = text.splitlines(keepends=True)
            chosen = lines[:n] if n >= 0 else lines[:n]
            ctx.out("".join(chosen), end="")
    return status


@command("tail", level=2, summary="Output the last part of files.", usage="tail [OPTION]... [FILE]...",
         man="""NAME
       tail - output the last part of files

SYNOPSIS
       tail [OPTION]... [FILE]...

DESCRIPTION
       Print the last 10 lines of each FILE to standard output.

       -n, --lines=N   output the last N lines (-n +N starts at line N)
       -c, --bytes=N   output the last N bytes
       -f              follow the file (in this simulation: print and stop)
""", lesson="tail shows the end of a file. Logs grow at the bottom, so 'tail -n 20 /var/log/auth.log' shows what happened last.")
def tail(ctx, args):
    o = opts.parse(ctx, args, short="qf", with_arg="nc", long_arg={"lines": "n", "bytes": "c"}, numeric="n")
    if o is None:
        return 2
    n, plus = _count_arg(ctx, o)
    if n is None:
        return 1
    raw = o.get("n") or "10"
    inputs, status = _inputs(ctx, o.rest)
    for i, (name, text) in enumerate(inputs):
        if len(inputs) > 1 and not o.has("q"):
            ctx.out(("\n" if i else "") + f"==> {name} <==")
        if o.get("c"):
            ctx.out(text[-int(o.get("c")):], end="")
            continue
        lines = text.splitlines(keepends=True)
        chosen = lines[int(raw) - 1:] if raw.startswith("+") else lines[-abs(int(raw)):] if int(raw) else []
        ctx.out("".join(chosen), end="")
    return status


@command("wc", level=3, summary="Print newline, word, and byte counts for each file.", usage="wc [OPTION]... [FILE]...",
         man="""NAME
       wc - print newline, word, and byte counts for each file

SYNOPSIS
       wc [OPTION]... [FILE]...

DESCRIPTION
       -l, --lines   print the newline counts
       -w, --words   print the word counts
       -c, --bytes   print the byte counts
       -m, --chars   print the character counts
""", lesson="wc counts lines (-l), words (-w) and bytes (-c). 'cat users.txt | wc -l' tells you how many users there are.")
def wc(ctx, args):
    o = opts.parse(ctx, args, short="lwcmL", long={"lines": "l", "words": "w", "bytes": "c", "chars": "m"})
    if o is None:
        return 2
    show = [c for c in "lwcm" if o.has(c)] or ["l", "w", "c"]
    inputs, status = _inputs(ctx, o.rest)
    rows, totals = [], [0, 0, 0, 0]
    for name, text in inputs:
        vals = {"l": text.count("\n"), "w": len(text.split()), "c": len(text.encode("utf-8", "replace")), "m": len(text)}
        rows.append((name, vals))
        for i, c in enumerate("lwcm"):
            totals[i] += vals[c]
    if len(rows) > 1:
        rows.append(("total", dict(zip("lwcm", totals))))
    width = max([len(str(v[c])) for _, v in rows for c in show] + [1]) if len(rows) > 1 or len(show) > 1 else 0
    for name, vals in rows:
        line = " ".join(f"{vals[c]:>{width}}" for c in show)
        shown = "" if name == "standard input" and not o.rest else f" {name}"
        ctx.out(line + shown)
    return status


# ------------------------------------------------------------------------------------------------ create / copy / move / remove
@command("mkdir", level=2, summary="Make directories.", usage="mkdir [OPTION]... DIRECTORY...",
         man="""NAME
       mkdir - make directories

SYNOPSIS
       mkdir [OPTION]... DIRECTORY...

DESCRIPTION
       -p, --parents   no error if existing, make parent directories as needed
       -m, --mode=MODE set file mode (as in chmod)
       -v, --verbose   print a message for each created directory
""", lesson="mkdir creates a new folder. Use 'mkdir -p a/b/c' to create the whole path at once.")
def mkdir(ctx, args):
    o = opts.parse(ctx, args, short="pv", with_arg="m", long={"parents": "p", "verbose": "v"}, long_arg={"mode": "m"})
    if o is None:
        return 2
    if not o.rest:
        ctx.err("mkdir: missing operand")
        ctx.err("Try 'mkdir --help' for more information.")
        return 1
    status = 0
    mode = int(o.get("m"), 8) if o.get("m") and re.fullmatch(r"[0-7]{3,4}", o.get("m")) else 0o755
    for d in o.rest:
        try:
            if o.has("p") and ctx.fs.exists(d, ctx.cwd):
                continue
            ctx.fs.mkdir(ctx.user, d, ctx.cwd, parents=o.has("p"), mode=mode)
            if o.has("v"):
                ctx.out(f"mkdir: created directory '{d}'")
            ctx.event("mkdir", path=ctx.path(d), machine=ctx.machine.id)
        except FsError as exc:
            status = ctx.fs_error(exc, d, "cannot create directory")
    return status


@command("rmdir", level=2, summary="Remove empty directories.", usage="rmdir [OPTION]... DIRECTORY...")
def rmdir(ctx, args):
    o = opts.parse(ctx, args, short="pv")
    if o is None:
        return 2
    status = 0
    for d in o.rest:
        try:
            node = ctx.fs.stat(ctx.user, d, ctx.cwd)
            if not node.is_dir:
                ctx.err(f"rmdir: failed to remove '{d}': Not a directory")
                status = 1
                continue
            ctx.fs.remove(ctx.user, d, ctx.cwd)
        except FsError as exc:
            status = ctx.fs_error(exc, d, "failed to remove")
    return status


@command("touch", level=2, summary="Change file timestamps (or create empty files).", usage="touch [OPTION]... FILE...",
         lesson="touch creates an empty file if it does not exist yet: 'touch notes.txt'.")
def touch(ctx, args):
    o = opts.parse(ctx, args, short="cam", with_arg="rtd")
    if o is None:
        return 2
    if not o.rest:
        ctx.err("touch: missing file operand")
        return 1
    status = 0
    for f in o.rest:
        try:
            node = ctx.fs.lookup(f, ctx.cwd)
            if node is None:
                if o.has("c"):
                    continue
                ctx.fs.write(ctx.user, f, "", ctx.cwd)
                ctx.event("create", path=ctx.path(f), machine=ctx.machine.id)
            else:
                if not ctx.fs.can(ctx.user, node, "w", ctx.path(f)):
                    raise FsError("EACCES", f)
                node.mtime = ctx.now()
        except FsError as exc:
            status = ctx.fs_error(exc, f, "cannot touch")
    return status


@command("cp", level=3, summary="Copy files and directories.", usage="cp [OPTION]... SOURCE... DEST",
         man="""NAME
       cp - copy files and directories

SYNOPSIS
       cp [OPTION]... SOURCE DEST
       cp [OPTION]... SOURCE... DIRECTORY

DESCRIPTION
       -r, -R, --recursive   copy directories recursively
       -f, --force           overwrite without asking
       -v, --verbose         explain what is being done
       -p                    preserve mode and timestamps
""", lesson="cp copies files: 'cp a.txt b.txt'. Add -r to copy a whole folder.")
def cp(ctx, args):
    o = opts.parse(ctx, args, short="rRfvpai", long={"recursive": "r", "force": "f", "verbose": "v"})
    if o is None:
        return 2
    if len(o.rest) < 2:
        ctx.err(f"cp: missing {'destination ' if len(o.rest) == 1 else ''}file operand" + (f" after '{o.rest[0]}'" if o.rest else ""))
        ctx.err("Try 'cp --help' for more information.")
        return 1
    *sources, dest = o.rest
    status = 0
    dest_node = ctx.fs.lookup(dest, ctx.cwd)
    if len(sources) > 1 and not (dest_node and dest_node.is_dir):
        ctx.err(f"cp: target '{dest}' is not a directory")
        return 1
    for src in sources:
        try:
            node = ctx.fs.stat(ctx.user, src, ctx.cwd)
        except FsError as exc:
            status = ctx.fs_error(exc, src, "cannot stat")
            continue
        if node.is_dir and not o.has("r", "R", "a"):
            ctx.err(f"cp: -r not specified; omitting directory '{src}'")
            status = 1
            continue
        try:
            target_name = dest if not (dest_node and dest_node.is_dir) else dest.rstrip("/") + "/" + node.name
            ctx.fs.copy(ctx.user, src, dest, ctx.cwd, recursive=o.has("r", "R", "a"))
            if o.has("v"):
                ctx.out(f"'{src}' -> '{target_name}'")
            ctx.event("copy", src=ctx.path(src), dest=ctx.path(target_name), machine=ctx.machine.id)
        except FsError as exc:
            status = ctx.fs_error(exc, dest if exc.code != "EISDIR" else src, "cannot create regular file" if exc.code in ("EACCES", "ENOENT") else "")
    return status


@command("mv", level=3, summary="Move (rename) files.", usage="mv [OPTION]... SOURCE... DEST", lesson="mv moves or renames: 'mv old.txt new.txt'.")
def mv(ctx, args):
    o = opts.parse(ctx, args, short="fvin")
    if o is None:
        return 2
    if len(o.rest) < 2:
        ctx.err(f"mv: missing {'destination ' if len(o.rest) == 1 else ''}file operand" + (f" after '{o.rest[0]}'" if o.rest else ""))
        return 1
    *sources, dest = o.rest
    status = 0
    for src in sources:
        try:
            ctx.fs.rename(ctx.user, src, dest, ctx.cwd)
            if o.has("v"):
                ctx.out(f"renamed '{src}' -> '{dest}'")
            ctx.event("move", src=ctx.path(src), dest=ctx.path(dest), machine=ctx.machine.id)
        except FsError as exc:
            status = ctx.fs_error(exc, src, "cannot stat" if exc.code == "ENOENT" else "cannot move")
    return status


@command("rm", level=3, summary="Remove files or directories.", usage="rm [OPTION]... [FILE]...",
         man="""NAME
       rm - remove files or directories

SYNOPSIS
       rm [OPTION]... [FILE]...

DESCRIPTION
       -f, --force      ignore nonexistent files, never prompt
       -r, -R           remove directories and their contents recursively
       -v, --verbose    explain what is being done
       -d               remove empty directories
""", lesson="rm deletes files. There is no trash can: 'rm file' is gone for good, and 'rm -r folder' removes a folder with everything in it. Be careful.")
def rm(ctx, args):
    o = opts.parse(ctx, args, short="frRvdi", long={"force": "f", "recursive": "r", "verbose": "v", "no-preserve-root": "N"})
    if o is None:
        return 2
    if not o.rest and not o.has("f"):
        ctx.err("rm: missing operand")
        ctx.err("Try 'rm --help' for more information.")
        return 1
    status = 0
    for f in o.rest:
        if ctx.path(f) in ("/", "C:\\") and o.has("r", "R") and not o.has("N"):
            ctx.err("rm: it is dangerous to operate recursively on '/'")
            ctx.err("rm: use --no-preserve-root to override this failsafe")
            status = 1
            continue
        try:
            node = ctx.fs.stat(ctx.user, f, ctx.cwd, follow=False)
        except FsError as exc:
            if not o.has("f") or exc.code != "ENOENT":
                status = ctx.fs_error(exc, f, "cannot remove")
            continue
        if node.is_dir and not o.has("r", "R", "d"):
            ctx.err(f"rm: cannot remove '{f}': Is a directory")
            status = 1
            continue
        try:
            ctx.fs.remove(ctx.user, f, ctx.cwd, recursive=o.has("r", "R"))
            if o.has("v"):
                ctx.out(f"removed '{f}'")
            ctx.event("delete", path=ctx.path(f), machine=ctx.machine.id)
        except FsError as exc:
            if not (o.has("f") and exc.code == "ENOENT"):
                status = ctx.fs_error(exc, f, "cannot remove")
    return status


@command("ln", level=4, summary="Make links between files.", usage="ln [OPTION]... TARGET LINK_NAME", lesson="ln -s makes a shortcut (symbolic link): 'ln -s /etc/passwd pw'.")
def ln(ctx, args):
    o = opts.parse(ctx, args, short="sfv")
    if o is None:
        return 2
    if len(o.rest) < 2:
        ctx.err("ln: missing file operand")
        return 1
    target, name = o.rest[0], o.rest[1]
    try:
        node = ctx.fs.lookup(name, ctx.cwd)
        if node is not None and node.is_dir:
            name = name.rstrip("/") + "/" + ctx.fs.basename(target)
        if o.has("f"):
            try:
                ctx.fs.remove(ctx.user, name, ctx.cwd)
            except FsError:
                pass
        if o.has("s"):
            ctx.fs.symlink(ctx.user, target, name, ctx.cwd)
        else:
            src = ctx.fs.stat(ctx.user, target, ctx.cwd)
            ctx.fs.write(ctx.user, name, src.content, ctx.cwd)
    except FsError as exc:
        return ctx.fs_error(exc, name, "failed to create symbolic link" if o.has("s") else "failed to create hard link")
    return 0


# ------------------------------------------------------------------------------------------------ permissions
def _apply_mode(spec: str, current: int, is_dir: bool) -> int | None:
    if re.fullmatch(r"[0-7]{1,4}", spec):
        return int(spec, 8)
    mode = current
    for clause in spec.split(","):
        m = re.fullmatch(r"([ugoa]*)([-+=])([rwxXst]*)", clause)
        if not m:
            return None
        who, op, perms = m.groups()
        who = who or "a"
        bits = 0
        for p in perms:
            bits |= {"r": 4, "w": 2, "x": 1, "X": 1 if is_dir or current & 0o111 else 0, "s": 0, "t": 0}[p]
        for w in ("u", "g", "o") if "a" in who else who:
            shift = {"u": 6, "g": 3, "o": 0}[w]
            mask = 7 << shift
            if op == "+":
                mode |= bits << shift
            elif op == "-":
                mode &= ~(bits << shift)
            else:
                mode = (mode & ~mask) | (bits << shift)
    return mode


@command("chmod", level=4, summary="Change file mode bits.", usage="chmod [OPTION]... MODE[,MODE]... FILE...",
         man="""NAME
       chmod - change file mode bits

SYNOPSIS
       chmod [OPTION]... MODE[,MODE]... FILE...

DESCRIPTION
       MODE is a number like 755 (owner 7 = read+write+execute, group 5 = read+execute, others 5) or letters like u+x, go-w, a=r.

       -R, --recursive   change files and directories recursively
       -v, --verbose     output a diagnostic for every file processed
""", lesson="chmod changes who may read (4), write (2) or execute (1) a file. 'chmod +x script.sh' makes it runnable; 'chmod 600 key' keeps a key private.")
def chmod(ctx, args):
    o = opts.parse(ctx, args, short="Rvcf", long={"recursive": "R", "verbose": "v"})
    if o is None:
        return 2
    if len(o.rest) < 2:
        ctx.err("chmod: missing operand" + (" after '" + o.rest[0] + "'" if o.rest else ""))
        ctx.err("Try 'chmod --help' for more information.")
        return 1
    spec, *files = o.rest
    status = 0
    for f in files:
        try:
            targets = [(p, n) for p, n in ctx.fs.walk(f, ctx.cwd)] if o.has("R") else [(ctx.path(f), ctx.fs.stat(ctx.user, f, ctx.cwd))]
            if not targets:
                raise FsError("ENOENT", f)
            for path, node in targets:
                new = _apply_mode(spec, node.mode, node.is_dir)
                if new is None:
                    ctx.err(f"chmod: invalid mode: '{spec}'")
                    ctx.err("Try 'chmod --help' for more information.")
                    return 1
                ctx.fs.chmod(ctx.user, path, new, "")
                if o.has("v"):
                    ctx.out(f"mode of '{path}' changed to {new:04o}")
                ctx.event("chmod", path=path, mode=new, machine=ctx.machine.id)
        except FsError as exc:
            status = ctx.fs_error(exc, f, "changing permissions of" if exc.code == "EACCES" else "cannot access")
    return status


@command("chown", level=5, summary="Change file owner and group.", usage="chown [OPTION]... [OWNER][:[GROUP]] FILE...",
         lesson="chown changes who owns a file: 'sudo chown alice:alice file'. Normally only root may do that.")
def chown(ctx, args):
    o = opts.parse(ctx, args, short="Rvf")
    if o is None:
        return 2
    if len(o.rest) < 2:
        ctx.err("chown: missing operand" + (" after '" + o.rest[0] + "'" if o.rest else ""))
        return 1
    spec, *files = o.rest
    owner, _, group = spec.partition(":")
    status = 0
    for f in files:
        try:
            for path, _n in (list(ctx.fs.walk(f, ctx.cwd)) if o.has("R") else [(ctx.path(f), None)]):
                ctx.fs.chown(ctx.user, path, owner or None, group or None, "")
        except FsError as exc:
            status = ctx.fs_error(exc, f, "changing ownership of" if exc.code == "EACCES" else "cannot access")
    return status


@command("stat", level=5, summary="Display file or file system status.", usage="stat [OPTION]... FILE...")
def stat(ctx, args):
    o = opts.parse(ctx, args, short="L")
    if o is None:
        return 2
    status = 0
    for f in o.rest:
        try:
            n = ctx.fs.stat(ctx.user, f, ctx.cwd, follow=False)
        except FsError as exc:
            status = ctx.fs_error(exc, f, "cannot statx")
            continue
        kind = {"dir": "directory", "link": "symbolic link"}.get(n.kind, "regular file" if n.size else "regular empty file")
        ctx.out(f"  File: {f}" + (f" -> {n.target}" if n.kind == "link" else ""))
        ctx.out(f"  Size: {n.size:<10}\tBlocks: {_blocks(n):<10} IO Block: 4096   {kind}")
        ctx.out(f"Device: 8,1\tInode: {abs(hash(ctx.path(f))) % 900000 + 100000}\tLinks: 1")
        ctx.out(f"Access: ({n.mode & 0o7777:04o}/{mode_string(n)})  Uid: ({1000 if n.owner != 'root' else 0:>5}/{n.owner:>8})   Gid: ({1000 if n.group != 'root' else 0:>5}/{n.group:>8})")
        stamp = time.strftime("%Y-%m-%d %H:%M:%S.000000000 +0000", time.gmtime(n.mtime))
        ctx.out(f"Access: {stamp}\nModify: {stamp}\nChange: {stamp}\n Birth: -")
    return status


# ------------------------------------------------------------------------------------------------ du / df / tree
@command("du", level=6, summary="Estimate file space usage.", usage="du [OPTION]... [FILE]...", lesson="du shows how much space folders use: 'du -sh *' gives one total per item.")
def du(ctx, args):
    o = opts.parse(ctx, args, short="shaclk", long={"summarize": "s", "human-readable": "h"}, with_arg="d")
    if o is None:
        return 2
    status = 0

    def size_of(path: str) -> int:
        return sum(max(4096, n.size) if not n.is_dir else 4096 for _, n in ctx.fs.walk(path, ""))
    for t in o.rest or ["."]:
        try:
            ctx.fs.stat(ctx.user, t, ctx.cwd)
        except FsError as exc:
            status = ctx.fs_error(exc, t, "cannot access")
            continue
        base = ctx.path(t)
        rows = []
        for p, n in ctx.fs.walk(base):
            if n.is_dir or o.has("a"):
                rows.append((p, size_of(p)))
        if o.has("s"):
            rows = [(base, size_of(base))]
        for p, sz in (rows if o.has("a") else reversed(rows)) if not o.has("s") else rows:
            shown = t if p == base else t.rstrip("/") + p[len(base):]
            ctx.out(f"{_human(sz) if o.has('h') else sz // 1024}\t{shown}")
    return status


@command("df", level=6, summary="Report file system space usage.", usage="df [OPTION]... [FILE]...")
def df(ctx, args):
    o = opts.parse(ctx, args, short="hTa")
    if o is None:
        return 2
    h = o.has("h")
    ctx.out("Filesystem      Size  Used Avail Use% Mounted on" if h else "Filesystem     1K-blocks     Used Available Use% Mounted on")
    rows = [("/dev/sda1", "40G", "12G", "26G", "32%", "/", 41943040, 12582912, 27262976), ("tmpfs", "1.9G", "0", "1.9G", "0%", "/dev/shm", 1992294, 0, 1992294),
            ("tmpfs", "391M", "1.1M", "390M", "1%", "/run", 400000, 1126, 398874)]
    for r in rows:
        ctx.out(f"{r[0]:<15} {r[1]:>4} {r[2]:>5} {r[3]:>5} {r[4]:>4} {r[5]}" if h else f"{r[0]:<14} {r[6]:>9} {r[7]:>8} {r[8]:>9} {r[4]:>4} {r[5]}")
    return 0


@command("tree", level=6, summary="List contents of directories in a tree-like format.", usage="tree [-adL level] [directory ...]",
         lesson="tree draws a folder and everything below it as a tree. 'tree -L 2' limits the depth.")
def tree(ctx, args):
    o = opts.parse(ctx, args, short="adf", with_arg="L")
    if o is None:
        return 2
    depth = o.num("L", 999)
    dirs = files = 0
    for t in o.rest or ["."]:
        try:
            ctx.fs.stat(ctx.user, t, ctx.cwd)
        except FsError:
            ctx.err(f"{t} [error opening dir]")
            continue
        ctx.out(t)

        def rec(path: str, prefix: str, level: int) -> None:
            nonlocal dirs, files
            if level > depth:
                return
            try:
                kids = [k for k in ctx.fs.listdir(ctx.user, path, "") if o.has("a") or not k.name.startswith(".")]
            except FsError:
                return
            for i, k in enumerate(kids):
                last = i == len(kids) - 1
                ctx.out(prefix + ("└── " if last else "├── ") + k.name + (f" -> {k.target}" if k.kind == "link" else ""))
                if k.is_dir:
                    dirs += 1
                    rec(path.rstrip("/") + "/" + k.name, prefix + ("    " if last else "│   "), level + 1)
                else:
                    files += 1
        rec(ctx.path(t), "", 1)
    ctx.out(f"\n{dirs} director{'y' if dirs == 1 else 'ies'}, {files} file{'' if files == 1 else 's'}")
    return 0


# ------------------------------------------------------------------------------------------------ find
class _FindError(Exception):
    pass


def _parse_find(ctx, tokens: list[str]):
    """Parse find expressions into a callable predicate plus action list. Supports -name -iname -type -user -group -perm -size -mtime -empty
    -readable -writable -executable -maxdepth -mindepth -print -exec -delete -ls and ( ) ! -a -o."""
    pos = [0]
    actions: list = []
    cfg = {"maxdepth": 10**6, "mindepth": 0}

    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else None

    def take():
        pos[0] += 1
        return tokens[pos[0] - 1]

    def primary():
        t = take()
        if t in ("(", "\\("):
            p = expr_or()
            if take() not in (")", "\\)"):
                raise _FindError("missing closing ')'")
            return p
        if t in ("!", "-not"):
            inner = primary()
            return lambda n, p, d: not inner(n, p, d)
        if t in ("-name", "-iname", "-path", "-ipath", "-wholename"):
            if peek() is None:
                raise _FindError(f"missing argument to `{t}'")
            pat = take()
            ci = t in ("-iname", "-ipath")
            if t in ("-name", "-iname"):
                return lambda n, p, d: fnmatch.fnmatchcase(n.name.lower() if ci else n.name, pat.lower() if ci else pat)
            return lambda n, p, d: fnmatch.fnmatchcase(p.lower() if ci else p, pat.lower() if ci else pat)
        if t == "-type":
            want = take()
            return lambda n, p, d: {"f": n.kind == "file", "d": n.is_dir, "l": n.kind == "link"}.get(want, False)
        if t == "-user":
            u = take()
            return lambda n, p, d: n.owner == u
        if t == "-group":
            g = take()
            return lambda n, p, d: n.group == g
        if t == "-perm":
            spec = take()
            if spec.startswith("-"):
                m = int(spec[1:], 8)
                return lambda n, p, d: n.mode & m == m
            if spec.startswith("/"):
                m = int(spec[1:], 8)
                return lambda n, p, d: bool(n.mode & m)
            m = int(spec, 8)
            return lambda n, p, d: n.mode & 0o7777 == m
        if t == "-size":
            spec = take()
            m = re.fullmatch(r"([+-]?)(\d+)([cbkMG]?)", spec)
            if not m:
                raise _FindError(f"invalid argument `{spec}' to `-size'")
            sign, num, unit = m.group(1), int(m.group(2)), m.group(3) or "b"
            mult = {"c": 1, "b": 512, "k": 1024, "M": 1048576, "G": 1073741824}[unit]

            def size_pred(n, p, d):
                blocks = -(-n.size // mult)
                return blocks > num if sign == "+" else blocks < num if sign == "-" else blocks == num
            return size_pred
        if t == "-mtime":
            spec = take()
            sign, num = (spec[0], int(spec[1:])) if spec[0] in "+-" else ("", int(spec))
            return lambda n, p, d: (lambda age: age > num if sign == "+" else age < num if sign == "-" else age == num)(int((ctx.now() - n.mtime) // 86400))
        if t == "-empty":
            return lambda n, p, d: (n.is_dir and not n.children) or (n.kind == "file" and n.size == 0)
        if t in ("-readable", "-writable", "-executable"):
            perm = {"-readable": "r", "-writable": "w", "-executable": "x"}[t]
            return lambda n, p, d: ctx.fs.can(ctx.user, n, perm, p)
        if t == "-maxdepth":
            cfg["maxdepth"] = int(take())
            return lambda n, p, d: True
        if t == "-mindepth":
            cfg["mindepth"] = int(take())
            return lambda n, p, d: True
        if t == "-print":
            actions.append(("print",))
            return lambda n, p, d: True
        if t == "-ls":
            actions.append(("ls",))
            return lambda n, p, d: True
        if t == "-delete":
            actions.append(("delete",))
            return lambda n, p, d: True
        if t in ("-exec", "-execdir", "-ok"):
            cmd: list[str] = []
            while peek() is not None and peek() not in (";", "\\;", "+"):
                cmd.append(take())
            if peek() is None:
                raise _FindError("missing argument to `-exec'")
            terminator = take()
            actions.append(("exec", cmd, terminator == "+"))
            return lambda n, p, d: True
        raise _FindError(f"unknown predicate `{t}'")

    def expr_and():
        left = primary()
        while peek() is not None and peek() not in ("-o", "-or", ")", "\\)"):
            if peek() in ("-a", "-and"):
                take()
            right = primary()
            left = (lambda l, r: lambda n, p, d: l(n, p, d) and r(n, p, d))(left, right)
        return left

    def expr_or():
        left = expr_and()
        while peek() in ("-o", "-or"):
            take()
            right = expr_and()
            left = (lambda l, r: lambda n, p, d: l(n, p, d) or r(n, p, d))(left, right)
        return left

    pred = expr_or() if tokens else (lambda n, p, d: True)
    if pos[0] < len(tokens):
        raise _FindError(f"paths must precede expression: `{tokens[pos[0]]}'")
    return pred, actions, cfg


@command("find", level=7, summary="Search for files in a directory hierarchy.", usage="find [starting-point...] [expression]",
         man="""NAME
       find - search for files in a directory hierarchy

SYNOPSIS
       find [starting-point...] [expression]

DESCRIPTION
       Walks the directory tree below each starting point and evaluates the expression for every file.

       -name PATTERN     file name matches the shell pattern (use quotes: -name '*.txt')
       -iname PATTERN    like -name, ignoring case
       -type f|d|l       regular file, directory, symbolic link
       -user NAME        file is owned by NAME
       -perm MODE        file permission bits are exactly MODE; -MODE = all of these bits; /MODE = any of them
       -size [+-]N[ckMG] file uses more (+) or less (-) than N units
       -maxdepth N       descend at most N levels
       -exec CMD {} \\;   run CMD for every match, {} is replaced by the file name
       -delete           delete matching files
""", lesson="find searches the whole tree: 'find / -name \"*.conf\"' lists every .conf file, 'find . -type f -size +1k' finds files bigger than 1 KB.")
def find(ctx, args):
    paths: list[str] = []
    i = 0
    while i < len(args) and not (args[i].startswith("-") or args[i] in ("!", "(", "\\(")):
        paths.append(args[i])
        i += 1
    try:
        pred, actions, cfg = _parse_find(ctx, args[i:])
    except _FindError as exc:
        ctx.err(f"find: {exc}")
        return 1
    except (ValueError, IndexError):
        ctx.err("find: invalid argument in expression")
        return 1
    status = 0
    exec_batches: dict[int, list[str]] = {}
    for start in paths or ["."]:
        try:
            ctx.fs.stat(ctx.user, start, ctx.cwd)
        except FsError as exc:
            ctx.err(f"find: '{start}': {exc.text}")
            status = 1
            continue
        base = ctx.path(start)

        def visit(path: str, node: Node, shown: str, depth: int) -> None:
            nonlocal status
            if depth > cfg["maxdepth"]:
                return
            if depth >= cfg["mindepth"] and pred(node, path, depth):
                acted = False
                for act in actions:
                    acted = True
                    if act[0] == "print":
                        ctx.out(shown)
                    elif act[0] == "ls":
                        ctx.out(f"{abs(hash(path)) % 900000 + 100000:>8} {_blocks(node) // 4:>4} {mode_string(node)} {1:>3} {node.owner:<8} {node.group:<8} {node.size:>8} {_time(node.mtime)} {shown}")
                    elif act[0] == "delete":
                        try:
                            ctx.fs.remove(ctx.user, path, "", recursive=False)
                        except FsError as exc:
                            ctx.err(f"find: cannot delete '{shown}': {exc.text}")
                            status = 1
                    elif act[0] == "exec":
                        cmd = act[1]
                        if act[2]:
                            exec_batches.setdefault(id(act), []).append(shown)
                        else:
                            line = " ".join(("'" + shown + "'") if c == "{}" else c for c in cmd) if "{}" in cmd else " ".join(cmd + [shown])
                            exec_status, res = ctx.shell.run_inner(line)
                            ctx.chunks.extend(res)
                            status = status or (exec_status and 1)
                if not acted:
                    ctx.out(shown)
                ctx.event("found", path=path, machine=ctx.machine.id)
            if node.is_dir and depth < cfg["maxdepth"]:
                if not ctx.fs.can(ctx.user, node, "r", path):
                    ctx.err(f"find: '{shown}': Permission denied")
                    status = 1
                    return
                for k in sorted(node.children.values(), key=lambda c: c.name):
                    visit(path.rstrip("/") + "/" + k.name if path != "/" else "/" + k.name, k, shown.rstrip("/") + "/" + k.name, depth + 1)
        visit(base, ctx.fs.lookup(base), start, 0)
    for act in actions:
        if act[0] == "exec" and act[2] and exec_batches.get(id(act)):
            exec_status, res = ctx.shell.run_inner(" ".join(act[1][:-1] + [f"'{x}'" for x in exec_batches[id(act)]]) if act[1] and act[1][-1] == "{}" else " ".join(act[1] + exec_batches[id(act)]))
            ctx.chunks.extend(res)
            status = status or (exec_status and 1)
    return status


# ------------------------------------------------------------------------------------------------ file / path helpers
MAGIC = [(b"\x7fELF", "ELF 64-bit LSB executable, x86-64, version 1 (SYSV), dynamically linked"), (b"\x1f\x8b", "gzip compressed data"),
         (b"PK\x03\x04", "Zip archive data, at least v2.0 to extract"), (b"\x89PNG", "PNG image data"), (b"\xff\xd8\xff", "JPEG image data, JFIF standard 1.01"),
         (b"%PDF", "PDF document, version 1.4"), (b"MZ", "PE32+ executable (console) x86-64, for MS Windows"), (b"SQLite format 3", "SQLite 3.x database"),
         (b"-----BEGIN OPENSSH PRIVATE KEY", "OpenSSH private key"), (b"-----BEGIN RSA PRIVATE KEY", "PEM RSA private key"),
         (b"-----BEGIN CERTIFICATE", "PEM certificate"), (b"BZh", "bzip2 compressed data"), (b"7z\xbc\xaf", "7-zip archive data")]


def file_type(node: Node) -> str:
    if node.is_dir:
        return "directory"
    if node.kind == "link":
        return f"symbolic link to {node.target}"
    if node.meta.get("type"):
        return node.meta["type"]
    data = node.content.encode("latin-1", "replace") if isinstance(node.content, str) else node.content
    if not data:
        return "empty"
    for sig, label in MAGIC:
        if data.startswith(sig):
            return label
    if data.startswith(b"#!"):
        first = data.split(b"\n", 1)[0].decode("latin-1")
        return f"{'Bourne-Again shell' if 'bash' in first else 'POSIX shell' if 'sh' in first else 'script'} script, ASCII text executable"
    if all(b < 128 and (b >= 32 or b in (9, 10, 13)) for b in data[:2000]):
        text = data.decode("ascii", "replace")
        if text.lstrip().startswith(("<?xml", "<html", "<!DOCTYPE")):
            return "HTML document, ASCII text" if "html" in text[:200].lower() else "XML 1.0 document, ASCII text"
        extra = ", with CRLF line terminators" if b"\r\n" in data else ""
        return "ASCII text" + extra + ("" if text.endswith("\n") else ", with no line terminators")
    return "data"


@command("file", level=5, summary="Determine file type.", usage="file [OPTION...] [FILE...]",
         lesson="file tells you what a file really is, whatever its name says. 'file mystery.dat' might reveal a zip archive or an image.")
def file_cmd(ctx, args):
    o = opts.parse(ctx, args, short="bLi")
    if o is None:
        return 2
    if not o.rest:
        ctx.err("Usage: file [OPTION...] [FILE...]")
        return 1
    for f in o.rest:
        try:
            node = ctx.fs.stat(ctx.user, f, ctx.cwd, follow=False)
            if node.kind == "file" and not ctx.fs.can(ctx.user, node, "r", ctx.path(f)):
                raise FsError("EACCES", f)
            ctx.out((f"{f}: " if not o.has("b") else "") + file_type(node))
            ctx.event("file_identified", path=ctx.path(f), machine=ctx.machine.id)
        except FsError as exc:
            ctx.out(f"{f}: cannot open `{f}' ({exc.text})")
    return 0


@command("basename", level=3, summary="Strip directory and suffix from filenames.", usage="basename NAME [SUFFIX]")
def basename(ctx, args):
    if not args:
        ctx.err("basename: missing operand")
        return 1
    name = args[0].rstrip("/").rsplit("/", 1)[-1] or "/"
    if len(args) > 1 and name.endswith(args[1]) and name != args[1]:
        name = name[:-len(args[1])]
    ctx.out(name)
    return 0


@command("dirname", level=3, summary="Strip last component from file name.", usage="dirname NAME...")
def dirname(ctx, args):
    if not args:
        ctx.err("dirname: missing operand")
        return 1
    for a in args:
        a = a.rstrip("/") or "/"
        ctx.out(a.rsplit("/", 1)[0] or "/" if "/" in a else ".")
    return 0


@command("realpath", level=5, summary="Print the resolved absolute file name.", usage="realpath FILE...")
def realpath(ctx, args):
    status = 0
    for a in [x for x in args if not x.startswith("-")]:
        try:
            node = ctx.fs.stat(ctx.user, a, ctx.cwd)
            path = ctx.path(a)
            ctx.out(path)
        except FsError as exc:
            status = ctx.fs_error(exc, a)
    return status


@command("readlink", level=5, summary="Print resolved symbolic links or canonical file names.", usage="readlink [OPTION]... FILE...")
def readlink(ctx, args):
    o = opts.parse(ctx, args, short="fenm")
    if o is None:
        return 2
    status = 1
    for a in o.rest:
        try:
            node = ctx.fs.stat(ctx.user, a, ctx.cwd, follow=False)
            if node.kind == "link":
                ctx.out(node.target)
                status = 0
            elif o.has("f"):
                ctx.out(ctx.path(a))
                status = 0
        except FsError:
            pass
    return status
