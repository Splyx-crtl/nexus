"""System commands: whoami id groups hostname uname date env printenv ps kill which whereis man help clear sudo uptime free w who last bash sh."""
from __future__ import annotations

import re
import time

from .. import opts, registry
from ..fs import FsError
from ..registry import command, lookup, specs


@command("whoami", level=1, summary="Print effective user name.", usage="whoami", lesson="whoami tells you which user you are right now. Always check it after logging into a new machine.")
def whoami(ctx, args):
    ctx.out(ctx.user.name)
    return 0


@command("id", level=1, summary="Print real and effective user and group IDs.", usage="id [OPTION]... [USER]...", lesson="id shows your user number, your group and every group you belong to. Groups decide what you may do.")
def id_cmd(ctx, args):
    o = opts.parse(ctx, args, short="ugGn")
    if o is None:
        return 2
    u = ctx.machine.user(o.rest[0]) if o.rest else ctx.user
    if u is None:
        ctx.err(f"id: '{o.rest[0]}': no such user")
        return 1
    groups = list(dict.fromkeys((u.name,) + tuple(u.groups)))
    gids = {g: (0 if g == "root" else 1000 + i) for i, g in enumerate(groups)}
    if u.is_root and "root" not in gids:
        gids["root"] = 0
    if o.has("u"):
        ctx.out(u.name if o.has("n") else str(u.uid))
    elif o.has("G", "g"):
        ctx.out(" ".join(groups if o.has("n") else [str(gids[g]) for g in groups]))
    else:
        ctx.out(f"uid={u.uid}({u.name}) gid={u.gid}({groups[0]}) groups=" + ",".join(f"{gids[g]}({g})" for g in groups))
    return 0


@command("groups", level=1, summary="Print the groups a user is in.", usage="groups [USER]...")
def groups(ctx, args):
    u = ctx.machine.user(args[0]) if args else ctx.user
    if u is None:
        ctx.err(f"groups: '{args[0]}': no such user")
        return 1
    ctx.out(f"{u.name} : " * bool(args) + " ".join(dict.fromkeys((u.name,) + tuple(u.groups))))
    return 0


@command("hostname", level=1, summary="Show or set the system's host name.", usage="hostname [OPTION]", lesson="hostname prints the name of the machine you are on. -I prints its IP address.")
def hostname(ctx, args):
    o = opts.parse(ctx, args, short="IifsdFa")
    if o is None:
        return 2
    ctx.out(ctx.machine.ip if o.has("I", "i") else ctx.machine.hostname)
    return 0


@command("uname", level=1, summary="Print system information.", usage="uname [OPTION]...", lesson="uname -a prints the kernel and system details: useful to know which exploits or tools fit a target.")
def uname(ctx, args):
    o = opts.parse(ctx, args, short="asnrvmpio")
    if o is None:
        return 2
    kernel = ctx.machine.data.get("kernel", "6.8.11-amd64")
    full = ["Linux", ctx.machine.hostname, kernel, f"#1 SMP PREEMPT_DYNAMIC Kali {kernel}-1kali1 (2050-01-01)", "x86_64", "GNU/Linux"]
    if o.has("a"):
        ctx.out(" ".join(full))
    else:
        picked = []
        if o.has("s") or not o.flags:
            picked.append("Linux")
        if o.has("n"):
            picked.append(ctx.machine.hostname)
        if o.has("r"):
            picked.append(kernel)
        if o.has("v"):
            picked.append(full[3])
        if o.has("m"):
            picked.append("x86_64")
        ctx.out(" ".join(picked))
    return 0


@command("date", level=2, summary="Print or set the system date and time.", usage="date [OPTION]... [+FORMAT]")
def date(ctx, args):
    o = opts.parse(ctx, args, short="uRI", with_arg="d")
    if o is None:
        return 2
    fmt = next((a[1:] for a in o.rest if a.startswith("+")), None)
    t = time.gmtime(ctx.now())
    ctx.out(time.strftime(fmt, t) if fmt else time.strftime("%a %b %e %H:%M:%S UTC %Y", t))
    return 0


@command("env", level=3, summary="Run a program in a modified environment (or print it).", usage="env [OPTION]... [NAME=VALUE]... [COMMAND [ARG]...]",
         lesson="env prints your environment variables. They hold things like your home folder and sometimes secrets such as API keys.")
def env(ctx, args):
    env_vars = dict(ctx.env)
    rest = list(args)
    while rest and "=" in rest[0] and not rest[0].startswith("-"):
        k, _, v = rest.pop(0).partition("=")
        env_vars[k] = v
    if rest:
        saved = dict(ctx.env)
        ctx.env.update(env_vars)
        try:
            ctx.chunks.extend(ctx.shell.run_inner(" ".join(rest)))
        finally:
            ctx.env.clear()
            ctx.env.update(saved)
        return 0
    for k, v in env_vars.items():
        ctx.out(f"{k}={v}")
    return 0


@command("printenv", level=3, summary="Print all or part of environment.", usage="printenv [OPTION]... [VARIABLE]...")
def printenv(ctx, args):
    if not args:
        for k, v in ctx.env.items():
            ctx.out(f"{k}={v}")
        return 0
    status = 0
    for a in args:
        if a in ctx.env:
            ctx.out(ctx.env[a])
        else:
            status = 1
    return status


@command("ps", level=6, summary="Report a snapshot of the current processes.", usage="ps [options]",
         man="""NAME
       ps - report a snapshot of the current processes

SYNOPSIS
       ps [options]

DESCRIPTION
       ps displays information about running processes.

       ps          processes of the current terminal
       ps aux      every process of every user, with CPU and memory
       ps -ef      full-format listing of all processes
""", lesson="ps lists running programs. 'ps aux' shows all of them with their owner and ID (PID) so you can spot interesting services.")
def ps(ctx, args):
    flat = [a.lstrip("-") for a in args]
    procs = ctx.machine.processes or []
    me = ctx.session.pid
    if any(f in ("aux", "ax", "auxww", "-aux") or f == "aux" for f in flat) or "aux" in "".join(flat):
        ctx.out("USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND")
        for p in procs:
            ctx.out(f"{p.user:<10} {p.pid:>5} {p.cpu:>4.1f} {p.mem:>4.1f} {12000 + p.pid * 7:>6} {4000 + p.pid * 3:>5} ?        Ss   00:00   0:00 {p.cmd or p.name}")
        ctx.out(f"{ctx.user.name:<10} {me:>5}  0.0  0.1  10224  3380 pts/0    R+   00:00   0:00 ps {' '.join(args)}".rstrip())
        return 0
    if "ef" in "".join(flat) or "e" in flat:
        ctx.out("UID          PID    PPID  C STIME TTY          TIME CMD")
        for p in procs:
            ctx.out(f"{p.user:<8} {p.pid:>7} {1:>7}  0 00:00 ?        00:00:00 {p.cmd or p.name}")
        return 0
    ctx.out("    PID TTY          TIME CMD")
    ctx.out(f"{me - 1:>7} pts/0    00:00:00 {ctx.session.env.get('SHELL', '/bin/bash').rsplit('/', 1)[-1]}")
    ctx.out(f"{me:>7} pts/0    00:00:00 ps")
    return 0


@command("kill", level=6, summary="Send a signal to a process.", usage="kill [-s SIGNAL | -SIGNAL] PID...")
def kill(ctx, args):
    pids = [a for a in args if re.fullmatch(r"\d+", a)]
    if not pids:
        ctx.err("kill: usage: kill [-s sigspec | -n signum | -sigspec] pid | jobspec ... or kill -l [sigspec]")
        return 2
    status = 0
    for a in pids:
        proc = next((p for p in ctx.machine.processes if p.pid == int(a)), None)
        if proc is None:
            ctx.err(f"bash: kill: ({a}) - No such process")
            status = 1
        elif proc.user != ctx.user.name and not ctx.user.is_root:
            ctx.err(f"bash: kill: ({a}) - Operation not permitted")
            status = 1
        else:
            ctx.machine.processes.remove(proc)
            ctx.event("process_killed", pid=proc.pid, name=proc.name, machine=ctx.machine.id)
    return status


@command("which", level=2, summary="Locate a command.", usage="which [-a] filename ...")
def which(ctx, args):
    status = 0
    for a in [x for x in args if not x.startswith("-")]:
        spec = lookup("bash", a)
        if spec is not None and ctx.shell.installed(spec):
            ctx.out(f"/usr/bin/{a}")
        else:
            status = 1
    return status


@command("whereis", level=4, summary="Locate the binary, source, and manual page files for a command.", usage="whereis [options] name...")
def whereis(ctx, args):
    for a in args:
        spec = lookup("bash", a)
        ctx.out(f"{a}:" + (f" /usr/bin/{a} /usr/share/man/man1/{a}.1.gz" if spec else ""))
    return 0


BUILTIN_HELP = {
    "cd": "cd: cd [-L|[-P [-e]] [-@]] [dir]\n    Change the shell working directory.\n    Change the current directory to DIR. The default DIR is the value of the HOME shell variable. `cd -' goes back to the previous directory.",
    "echo": "echo: echo [-neE] [arg ...]\n    Write arguments to the standard output.\n    -n  do not append a newline;  -e  enable interpretation of backslash escapes like \\n and \\t.",
    "export": "export: export [-fn] [name[=value] ...]\n    Set export attribute for shell variables, so programs started from this shell can see them.",
    "pwd": "pwd: pwd [-LP]\n    Print the name of the current working directory.",
    "history": "history: history [-c] [n]\n    Display the command history list with line numbers. -c clears it.",
    "exit": "exit: exit [n]\n    Exit the shell with status n.",
    "source": "source: source filename [arguments]\n    Execute commands from a file in the current shell.",
    "alias": "alias: alias [-p] [name[=value] ... ]\n    Define or display aliases.",
    "read": "read: read [-p prompt] [name ...]\n    Read a line from standard input and split it into fields.",
    "test": "test: test [expr]\n    Evaluate conditional expression. -e FILE exists, -f regular file, -d directory, -z STRING empty, INT1 -eq INT2, ...",
}


@command("man", level=2, summary="An interface to the system reference manuals.", usage="man [OPTION]... [PAGE]...",
         lesson="man opens the manual of a command: 'man ls'. Every real command has one, and it is the best way to learn the options. Run 'man man' for help with the manual itself.")
def man(ctx, args):
    names = [a for a in args if not a.startswith("-")]
    if not names:
        ctx.err("What manual page do you want?")
        ctx.err("For example, try 'man man'.")
        return 1
    status = 0
    for name in names:
        spec = lookup("bash", name)
        if spec is None or not ctx.shell.installed(spec):
            if name in BUILTIN_HELP:
                ctx.out(f"BASH BUILTIN COMMANDS: {name}\n\n" + BUILTIN_HELP[name])
                continue
            ctx.err(f"No manual entry for {name}")
            status = 16
            continue
        if spec.level > ctx.shell.level():
            ctx.err(f"No manual entry for {name}")
            status = 16
            continue
        text = spec.man or f"NAME\n       {name} - {spec.summary.rstrip('.').lower()}\n\nSYNOPSIS\n       {spec.usage}\n\nDESCRIPTION\n       {spec.summary}\n       See '{name} --help' for the available options."
        ctx.out(f"{name.upper()}(1)\t\t\t\tUser Commands\t\t\t\t{name.upper()}(1)\n")
        ctx.out(text)
        ctx.event("man_read", name=name)
    return status


@command("help", level=1, summary="Display information about builtin commands.", usage="help [pattern ...]")
def help_cmd(ctx, args):
    if args:
        for a in args:
            if a in BUILTIN_HELP:
                ctx.out(BUILTIN_HELP[a])
            else:
                ctx.err(f"bash: help: no help topics match `{a}'.  Try `help help' or `man -k {a}' or `info {a}'.")
        return 0
    ctx.out("GNU bash, version 5.2.15(1)-release (x86_64-pc-linux-gnu)")
    ctx.out("These shell commands are defined internally. Type `help' to see this list.")
    ctx.out("Type `help name' to find out more about the function `name'.")
    ctx.out("Use `man -k' or `info' to find out more about commands not in this list.\n")
    names = sorted(BUILTIN_HELP) + ["alias", "break", "continue", "eval", "false", "let", "printf", "return", "set", "shift", "true", "type", "unset"]
    for n in sorted(set(names)):
        ctx.out(f" {n}")
    ctx.out("\nCommands you have unlocked so far:")
    ctx.out("  " + "  ".join(sorted(s.name for s in specs("bash") if s.level <= ctx.shell.level() and ctx.shell.installed(s))))
    return 0


@command("clear", level=1, summary="Clear the terminal screen.", usage="clear", lesson="clear wipes the screen. Ctrl+L does the same.")
def clear(ctx, args):
    ctx.request("clear")
    return 0


@command("uptime", level=4, summary="Tell how long the system has been running.", usage="uptime [OPTION]")
def uptime(ctx, args):
    t = time.gmtime(ctx.now())
    ctx.out(f" {time.strftime('%H:%M:%S', t)} up 3 days,  4:12,  1 user,  load average: 0.08, 0.03, 0.01")
    return 0


@command("free", level=6, summary="Display amount of free and used memory in the system.", usage="free [options]")
def free(ctx, args):
    o = opts.parse(ctx, args, short="hmgbk")
    if o is None:
        return 2
    h = o.has("h")
    ctx.out("               total        used        free      shared  buff/cache   available")
    ctx.out("Mem:           3.8Gi       1.2Gi       1.5Gi        20Mi       1.1Gi       2.4Gi" if h else "Mem:         3984120     1257312     1573428       21044     1153380     2493704")
    ctx.out("Swap:          1.0Gi          0B       1.0Gi" if h else "Swap:        1048572           0     1048572")
    return 0


@command("who", level=6, summary="Show who is logged on.", usage="who [OPTION]...")
def who(ctx, args):
    ctx.out(f"{ctx.user.name:<9}pts/0        {time.strftime('%Y-%m-%d %H:%M', time.gmtime(ctx.now() - 600))} (10.0.0.9)")
    return 0


@command("w", level=6, summary="Show who is logged on and what they are doing.", usage="w [options]")
def w_cmd(ctx, args):
    t = time.gmtime(ctx.now())
    ctx.out(f" {time.strftime('%H:%M:%S', t)} up 3 days,  4:12,  1 user,  load average: 0.08, 0.03, 0.01")
    ctx.out("USER     TTY      FROM             LOGIN@   IDLE   JCPU   PCPU WHAT")
    ctx.out(f"{ctx.user.name:<8} pts/0    10.0.0.9         {time.strftime('%H:%M', time.gmtime(ctx.now() - 600))}    0.00s  0.04s  0.00s w")
    return 0


@command("last", level=8, summary="Show a listing of last logged in users.", usage="last [options]", lesson="last shows who logged in recently, from where, and for how long: the footprints other users left.")
def last(ctx, args):
    lines = ctx.machine.data.get("last") or [f"{ctx.user.name:<9}pts/0        10.0.0.9         {time.strftime('%a %b %e %H:%M', time.gmtime(ctx.now() - 600))}   still logged in"]
    for l in lines:
        ctx.out(l)
    ctx.out(f"\nwtmp begins {time.strftime('%a %b %e %H:%M:%S %Y', time.gmtime(ctx.now() - 86400 * 30))}")
    return 0


def _sudoers(ctx):
    data = ctx.machine.data.get("sudoers")
    if data is None:
        data = {u.name: {"commands": "ALL", "nopasswd": True} for u in ctx.machine.users.values() if "sudo" in u.groups} if ctx.machine.id == "kali" else {}
    return data


@command("sudo", level=5, summary="Execute a command as another user.", usage="sudo [-u user] [-l] command",
         man="""NAME
       sudo - execute a command as another user

SYNOPSIS
       sudo [-u user] command
       sudo -l

DESCRIPTION
       sudo allows a permitted user to execute a command as the superuser or another user, as specified by the security policy.

       -u USER   run the command as USER instead of root
       -l        list the commands the invoking user is allowed to run
""", lesson="sudo runs one command with administrator (root) rights: 'sudo cat /etc/shadow'. It only works for users the system trusts, and 'sudo -l' lists what you may do.")
def sudo(ctx, args):
    o = opts.parse(ctx, args, short="lSkvEH", with_arg="u", stop_at_positional=True)
    if o is None:
        return 2
    rules = _sudoers(ctx).get(ctx.user.name)
    if ctx.user.is_root:
        rules = {"commands": "ALL", "nopasswd": True}
    if o.has("l"):
        if not rules:
            ctx.err(f"Sorry, user {ctx.user.name} may not run sudo on {ctx.machine.hostname}.")
            return 1
        ctx.out(f"Matching Defaults entries for {ctx.user.name} on {ctx.machine.hostname}:\n    env_reset, mail_badpass, secure_path=/usr/local/sbin\\:/usr/local/bin\\:/usr/sbin\\:/usr/bin\\:/sbin\\:/bin\n")
        ctx.out(f"User {ctx.user.name} may run the following commands on {ctx.machine.hostname}:")
        ctx.out(f"    (ALL : ALL) {'NOPASSWD: ' if rules.get('nopasswd') else ''}{rules.get('commands', 'ALL')}")
        ctx.event("sudo_list", machine=ctx.machine.id)
        return 0
    if not o.rest:
        ctx.err("usage: sudo -h | -K | -k | -V")
        return 1
    if not rules:
        ctx.err(f"{ctx.user.name} is not in the sudoers file.")
        ctx.event("sudo_denied", machine=ctx.machine.id)
        return 1
    allowed = rules.get("commands", "ALL")
    cmd = o.rest[0]
    if allowed != "ALL" and cmd not in [c.strip().rsplit("/", 1)[-1] for c in str(allowed).split(",")]:
        ctx.err(f"Sorry, user {ctx.user.name} is not allowed to execute '{' '.join(o.rest)}' as root on {ctx.machine.hostname}.")
        return 1
    if not rules.get("nopasswd") and not ctx.session.env.get("_SUDO_OK"):
        ctx.err(f"sudo: a password is required")
        ctx.request("password", for_user=ctx.user.name, then=" ".join(o.rest), kind="sudo")
        return 1
    target = ctx.machine.user(o.get("u") or "root")
    if target is None:
        ctx.err(f"sudo: unknown user {o.get('u')}")
        return 1
    saved = ctx.session.user
    ctx.session.user = target
    saved_env = dict(ctx.session.env)
    ctx.session.env.update({"USER": target.name, "LOGNAME": target.name})
    try:
        line = " ".join("'" + a.replace("'", "'\\''") + "'" if re.search(r"[\s*?\[\]$;&|<>()]", a) else a for a in o.rest)
        ctx.chunks.extend(ctx.shell.run_inner(line))
    finally:
        ctx.session.user = saved
        ctx.session.env.clear()
        ctx.session.env.update(saved_env)
    ctx.event("sudo_used", machine=ctx.machine.id, command=cmd)
    return 0


@command("bash", level=10, summary="GNU Bourne-Again SHell.", usage="bash [option] [script-file [argument ...]]", aliases=("sh",),
         lesson="bash script.sh runs a script file; 'bash -c \"command\"' runs a command string.")
def bash_cmd(ctx, args):
    o = opts.parse(ctx, args, short="xeulvi", with_arg="c", stop_at_positional=True)
    if o is None:
        return 2
    if o.get("c"):
        ctx.chunks.extend(ctx.shell.run_inner(o.get("c")))
        return 0
    if not o.rest:
        ctx.err(f"{ctx.name}: interactive subshells are not available here; give a script file")
        return 1
    try:
        text = ctx.read_text(o.rest[0])
    except FsError as exc:
        ctx.err(f"{ctx.name}: {o.rest[0]}: {exc.text}")
        return 127
    chunks: list = []
    status = ctx.shell.run_script_text(text, o.rest[1:], o.rest[0], ctx.stdin, chunks)
    ctx.chunks.extend(chunks)
    return status
