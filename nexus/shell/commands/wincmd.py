"""cmd.exe (Command Prompt) builtins and legacy console tools, family="cmd". Reachable both from a cmd.exe session and, for the
tools that have no native PowerShell cmdlet (ipconfig, net, tasklist, ...), as a fallback from PowerShell (see winshell.run_ps)."""
from __future__ import annotations

import re
import time

from ..fs import FsError
from ..registry import command
from . import win_fs_core as core
from .net import _announce, _lat, _target


def _split_flags(args: list[str]) -> tuple[list[str], set[str]]:
    flags = {a[1:].lower() for a in args if a.startswith("/")}
    rest = [a for a in args if not a.startswith("/")]
    return rest, flags


@command("dir", family="cmd", level=1, summary="Displays a list of files and subdirectories in a directory.", usage="dir [path] [/a] [/s] [/b]",
         lesson="dir lists the files in a folder — the Windows console's oldest command, going back to MS-DOS.")
def dir_cmd(ctx, args):
    rest, flags = _split_flags(args)
    path = rest[0] if rest else "."
    try:
        rows = core.list_dir(ctx, path, recurse="s" in flags)
    except FsError as exc:
        ctx.err(exc.text)
        return 1
    if "b" in flags:
        for r in rows:
            ctx.out(r["Name"])
        return 0
    ctx.out(f" Directory of {ctx.fs.norm(path, ctx.cwd)}\n")
    for r in rows:
        size = "<DIR>".rjust(14) if r["Length"] == "" else f"{r['Length']:>14,}"
        ctx.out(f"{r['LastWriteTime']}    {size} {r['Name']}")
    files = sum(1 for r in rows if r["Length"] != "")
    dirs = sum(1 for r in rows if r["Length"] == "")
    ctx.out(f"{'':>15}{files} File(s)")
    ctx.out(f"{'':>15}{dirs} Dir(s)")
    return 0


@command("cd", family="cmd", level=1, summary="Displays the name of or changes the current directory.", usage="cd [path]", aliases=("chdir",),
        lesson="cd shows or changes the current directory, same idea as on Linux: 'cd Documents' moves in, 'cd ..' moves up.")
def cd_cmd(ctx, args):
    rest, _ = _split_flags(args)
    if not rest:
        ctx.out(ctx.cwd)
        return 0
    path = rest[0]
    try:
        node = ctx.fs.stat(ctx.user, path, ctx.cwd)
    except FsError:
        ctx.err("The system cannot find the path specified.")
        return 1
    if not node.is_dir:
        ctx.err("The directory name is invalid.")
        return 1
    ctx.session.cwd = ctx.path(path)
    ctx.session.env["PWD"] = ctx.session.cwd
    return 0


@command("type", family="cmd", level=1, summary="Displays the contents of a text file.", usage="type file", lesson="type prints a file's content, the DOS ancestor of Get-Content.")
def type_cmd(ctx, args):
    rest, _ = _split_flags(args)
    if not rest:
        ctx.err("The syntax of the command is incorrect.")
        return 1
    try:
        ctx.out(ctx.read_text(rest[0]), end="")
    except FsError:
        ctx.err("The system cannot find the file specified.")
        return 1
    return 0


@command("copy", family="cmd", level=3, summary="Copies one or more files to another location.", usage="copy source destination",
        lesson="copy duplicates a file to a new location: 'copy report.txt backup\\report.txt'.")
def copy_cmd(ctx, args):
    rest, _ = _split_flags(args)
    if len(rest) < 2:
        ctx.err("The syntax of the command is incorrect.")
        return 1
    try:
        core.copy(ctx, rest[0], rest[1])
    except FsError:
        ctx.err("The system cannot find the file specified.")
        return 1
    ctx.out("        1 file(s) copied.")
    return 0


@command("move", family="cmd", level=3, summary="Moves files from one directory to another.", usage="move source destination",
        lesson="move relocates a file (or renames it, if the destination is in the same folder): 'move draft.txt done\\draft.txt'.")
def move_cmd(ctx, args):
    rest, _ = _split_flags(args)
    if len(rest) < 2:
        ctx.err("The syntax of the command is incorrect.")
        return 1
    try:
        core.move(ctx, rest[0], rest[1])
    except FsError:
        ctx.err("The system cannot find the file specified.")
        return 1
    ctx.out("        1 file(s) moved.")
    return 0


@command("del", family="cmd", level=3, summary="Deletes one or more files.", usage="del file", aliases=("erase",),
        lesson="del deletes a file for good, no trash can: 'del old.txt'. Same idea as Linux's 'rm'.")
def del_cmd(ctx, args):
    rest, flags = _split_flags(args)
    status = 0
    for f in rest:
        try:
            core.remove(ctx, f, False)
        except FsError:
            ctx.err("Could Not Find " + ctx.fs.norm(f, ctx.cwd))
            status = 1
    return status


@command("ren", family="cmd", level=3, summary="Renames a file.", usage="ren oldname newname", aliases=("rename",),
        lesson="ren renames a file: 'ren draft.txt final.txt'.")
def ren_cmd(ctx, args):
    rest, _ = _split_flags(args)
    if len(rest) < 2:
        ctx.err("The syntax of the command is incorrect.")
        return 1
    dst = ctx.fs.join(ctx.fs.absolute(rest[0], ctx.cwd)[:-1] + [rest[1]])
    try:
        core.move(ctx, rest[0], dst)
    except FsError:
        ctx.err("The system cannot find the file specified.")
        return 1
    return 0


@command("md", family="cmd", level=2, summary="Creates a directory.", usage="md path", aliases=("mkdir",),
        lesson="md (same as mkdir) creates a new directory: 'md jobs'.")
def md_cmd(ctx, args):
    rest, _ = _split_flags(args)
    if not rest:
        ctx.err("The syntax of the command is incorrect.")
        return 1
    try:
        core.new_item(ctx, rest[0], True)
    except FsError:
        ctx.err("A subdirectory or file already exists.")
        return 1
    return 0


@command("rd", family="cmd", level=3, summary="Removes a directory.", usage="rd path [/s]", aliases=("rmdir",),
        lesson="rd removes a directory: 'rd old_folder'. Add '/s' to remove one that still has files inside.")
def rd_cmd(ctx, args):
    rest, flags = _split_flags(args)
    if not rest:
        ctx.err("The syntax of the command is incorrect.")
        return 1
    try:
        core.remove(ctx, rest[0], "s" in flags)
    except FsError:
        ctx.err("The system cannot find the file specified.")
        return 1
    return 0


@command("echo", family="cmd", level=1, summary="Displays messages.", usage="echo message",
        lesson="echo prints text back to the screen, or toggles command-echoing on/off in a batch script: 'echo Hello'.")
def echo_cmd(ctx, args):
    ctx.out(" ".join(args))
    return 0


@command("cls", family="cmd", level=1, summary="Clears the screen.", usage="cls",
        lesson="cls clears the screen — the Windows equivalent of Linux's 'clear'.")
def cls_cmd(ctx, args):
    ctx.request("clear")
    return 0


@command("ver", family="cmd", level=1, summary="Displays the Windows version.", usage="ver",
        lesson="ver prints the Windows version this machine reports itself as running.")
def ver_cmd(ctx, args):
    ctx.out("\nMicrosoft Windows [Version 11.0.30000.2050]")
    return 0


@command("vol", family="cmd", level=2, summary="Displays the disk volume label and serial number.", usage="vol",
        lesson="vol shows the disk's volume label and serial number.")
def vol_cmd(ctx, args):
    ctx.out(" Volume in drive C has no label.")
    ctx.out(f" Volume Serial Number is {abs(hash(ctx.machine.id)) % 0xFFFF:04X}-{abs(hash(ctx.machine.hostname)) % 0xFFFF:04X}")
    return 0


@command("set", family="cmd", level=2, summary="Displays, sets, or removes environment variables.", usage="set [name=value]",
        lesson="set shows or sets environment variables: 'set NAME=value' defines one, 'set' alone lists them all.")
def set_cmd(ctx, args):
    if not args:
        for k, v in sorted(ctx.env.items()):
            ctx.out(f"{k}={v}")
        return 0
    return 0                                            # var assignment is handled by the cmd runner itself


@command("whoami", family="cmd", level=1, summary="Displays the current user name.", usage="whoami",
        lesson="whoami prints the currently logged-in user's name.")
def whoami_cmd(ctx, args):
    ctx.out(f"{ctx.machine.hostname.lower()}\\{ctx.user.name}")
    return 0


@command("hostname", family="cmd", level=1, summary="Prints the computer's name.", usage="hostname",
        lesson="hostname prints the computer's own name on the network.")
def hostname_cmd(ctx, args):
    ctx.out(ctx.machine.hostname)
    return 0


@command("tree", family="cmd", level=5, summary="Graphically displays the folder structure of a drive or path.", usage="tree [path]",
        lesson="tree draws a folder and everything inside it as a tree, same idea as the Linux command of the same name.")
def tree_cmd(ctx, args):
    rest, _ = _split_flags(args)
    path = rest[0] if rest else "."
    ctx.out(f"Folder PATH listing")
    ctx.out(ctx.fs.norm(path, ctx.cwd))

    def rec(p: str, prefix: str) -> None:
        try:
            kids = [k for k in ctx.fs.listdir(ctx.user, p, "") if k.is_dir]
        except FsError:
            return
        for i, k in enumerate(kids):
            last = i == len(kids) - 1
            ctx.out(prefix + ("\\---" if last else "+---") + k.name)
            rec(ctx.fs.norm(k.name, p), prefix + ("    " if last else "|   "))
    rec(ctx.path(path), "")
    return 0


@command("findstr", family="cmd", level=8, summary="Searches for strings in files.", usage="findstr pattern file", lesson="findstr is cmd.exe's version of grep.")
def findstr_cmd(ctx, args):
    rest, flags = _split_flags(args)
    if len(rest) < 2:
        ctx.err("FINDSTR: Cannot open " + (rest[0] if rest else ""))
        return 2
    pattern, files = rest[0], rest[1:]
    try:
        rx = re.compile(re.escape(pattern) if "l" in flags or True else pattern, re.I if "i" in flags else 0)
    except re.error:
        return 2
    found = False
    for f in files:
        try:
            text = ctx.read_text(f)
        except FsError:
            ctx.err(f"FINDSTR: Cannot open {f}")
            continue
        for line in text.splitlines():
            if rx.search(line):
                found = True
                ctx.out((f"{f}:" if len(files) > 1 else "") + line)
    return 0 if found else 1


@command("attrib", family="cmd", level=6, summary="Displays or changes file attributes.", usage="attrib [path]",
        lesson="attrib shows or changes a file's attributes (read-only, hidden, system, archive) — the Windows equivalent of Linux permission bits, just a different set of flags.")
def attrib_cmd(ctx, args):
    rest, _ = _split_flags(args)
    path = rest[0] if rest else "."
    try:
        node = ctx.fs.stat(ctx.user, path, ctx.cwd, follow=False)
    except FsError:
        ctx.err("File not found")
        return 1
    bits = ("A" if not node.is_dir else " ") + ("R" if not (node.mode & 0o200) else " ") + ("H" if node.name.startswith(".") else " ")
    ctx.out(f"{bits}        {ctx.fs.norm(path, ctx.cwd)}")
    return 0


@command("more", family="cmd", level=2, summary="Displays output one screen at a time.", usage="more file",
        lesson="more shows a file one screen at a time instead of dumping it all at once — useful for a file too long to fit the window.")
def more_cmd(ctx, args):
    rest, _ = _split_flags(args)
    if rest:
        try:
            ctx.out(ctx.read_text(rest[0]), end="")
        except FsError:
            ctx.err("Cannot find " + rest[0])
            return 1
    elif ctx.stdin:
        ctx.out(ctx.stdin, end="")
    return 0


@command("exit", family="cmd", level=1, summary="Quits the CMD.EXE program or the current batch script.", usage="exit [code]",
        lesson="exit closes the current cmd session (or stops a running batch script).")
def exit_cmd(ctx, args):
    status = int(args[0]) if args and args[0].isdigit() else ctx.session.last_status
    if ctx.session.parent is not None:
        host = ctx.session.machine.ip
        ctx.shell.pop_session()
        ctx.out("logout")
        ctx.out(f"Connection to {host} closed.")
    return status


# ------------------------------------------------------------------------------------------------ legacy network / admin tools
@command("ipconfig", family="cmd", level=9, summary="Displays IP configuration.", usage="ipconfig [/all]",
        lesson="ipconfig shows this machine's network configuration: 'ipconfig /all' adds more detail — the Windows equivalent of Linux's 'ip'/'ifconfig'.")
def ipconfig_cmd(ctx, args):
    base = ctx.machine.ip.rsplit(".", 1)[0]
    ctx.out("Windows IP Configuration\n")
    ctx.out("Ethernet adapter Ethernet:\n")
    ctx.out("   Connection-specific DNS Suffix  . :")
    if "/all" in args or "all" in args:
        ctx.out(f"   Description . . . . . . . . . . . : Realtek PCIe GbE Family Controller")
        ctx.out(f"   Physical Address. . . . . . . . . : {abs(hash(ctx.machine.ip)) % 0xFFFFFFFFFFFF:012X}")
    ctx.out(f"   IPv4 Address. . . . . . . . . . . : {ctx.machine.ip}")
    ctx.out(f"   Subnet Mask . . . . . . . . . . . : 255.255.255.0")
    ctx.out(f"   Default Gateway . . . . . . . . . : {base}.1")
    return 0


@command("ping", family="cmd", level=9, summary="Sends ICMP echo requests (Windows format).", usage="ping [-n count] destination",
         lesson="Windows ping looks a bit different from the Linux one, but it asks the same question: is the machine there?")
def ping_cmd(ctx, args):
    rest, flags = _split_flags(args)
    count = 4
    if "-n" in rest:
        i = rest.index("-n")
        if i + 1 < len(rest) and rest[i + 1].isdigit():
            count = min(int(rest[i + 1]), 20)
            rest = rest[:i] + rest[i + 2:]
    if not rest:
        ctx.err("Usage: ping [-n count] target_name")
        return 1
    name = rest[0]
    machine, ip = _target(ctx, name)
    if ip is None:
        ctx.out(f"Ping request could not find host {name}. Please check the name and try again.")
        return 1
    ctx.out(f"\nPinging {name} [{ip}] with 32 bytes of data:")
    if machine is None:
        for _ in range(count):
            ctx.out("Request timed out.")
            ctx.wait(1000)
        ctx.out(f"\nPing statistics for {ip}:\n    Packets: Sent = {count}, Received = 0, Lost = {count} (100% loss),")
        return 1
    times = []
    for _ in range(count):
        t = _lat(ip)
        times.append(t)
        ctx.out(f"Reply from {ip}: bytes=32 time={max(1, round(t)):d}ms TTL=128")
        ctx.wait(350)
    ctx.out(f"\nPing statistics for {ip}:")
    ctx.out(f"    Packets: Sent = {count}, Received = {count}, Lost = 0 (0% loss),")
    ctx.out("Approximate round trip times in milli-seconds:")
    ctx.out(f"    Minimum = {round(min(times))}ms, Maximum = {round(max(times))}ms, Average = {round(sum(times) / len(times))}ms")
    _announce(ctx, machine)
    return 0


@command("tasklist", family="cmd", level=6, summary="Displays running processes.", usage="tasklist",
        lesson="tasklist shows every running process, similar to Linux's 'ps aux', just formatted the Windows way.")
def tasklist_cmd(ctx, args):
    ctx.out("Image Name                     PID Session Name        Session#    Mem Usage")
    ctx.out("========================= ======== ================ =========== ============")
    for p in ctx.machine.processes:
        ctx.out(f"{p.name:<26} {p.pid:>8} Console                    1    {int(p.mem * 1024):>8} K")
    return 0


@command("taskkill", family="cmd", level=6, summary="Terminates a process.", usage="taskkill /PID pid",
        lesson="taskkill stops a running process by its PID: 'taskkill /PID 4821' — the Windows equivalent of Linux's 'kill'.")
def taskkill_cmd(ctx, args):
    pid = None
    for i, a in enumerate(args):
        if a.upper() == "/PID" and i + 1 < len(args):
            pid = args[i + 1]
    if pid is None:
        ctx.err("ERROR: Invalid syntax.")
        return 1
    proc = next((p for p in ctx.machine.processes if str(p.pid) == pid), None)
    if proc is None:
        ctx.err(f"ERROR: The process \"{pid}\" not found.")
        return 128
    if proc.user != ctx.user.name and not ctx.user.is_root:
        ctx.err(f"ERROR: The process with PID {pid} could not be terminated.\nReason: Access is denied.")
        return 1
    ctx.machine.processes.remove(proc)
    ctx.out(f"SUCCESS: The process with PID {pid} has been terminated.")
    ctx.event("process_killed", pid=proc.pid, name=proc.name, machine=ctx.machine.id)
    return 0


@command("systeminfo", family="cmd", level=8, summary="Displays detailed configuration information.", usage="systeminfo",
        lesson="systeminfo dumps detailed configuration about the machine — OS version, memory, network and more, all in one report.")
def systeminfo_cmd(ctx, args):
    ctx.out(f"Host Name:                 {ctx.machine.hostname.upper()}")
    ctx.out("OS Name:                   Microsoft Windows 11 Enterprise")
    ctx.out("OS Version:                10.0.30000 N/A Build 30000")
    ctx.out(f"System Boot Time:          {time.strftime('%m/%d/%Y, %I:%M:%S %p', time.gmtime(ctx.now() - 86400 * 3))}")
    return 0


@command("net", family="cmd", level=9, summary="Manages network resources (users, shares, services).", usage="net user|view|share|start|stop ...",
         lesson="net is an old but still common admin tool: 'net user' lists local accounts, 'net view' lists shares on the network.")
def net_cmd(ctx, args):
    if not args:
        ctx.err("The syntax of this command is:\nNET HELP command")
        return 1
    sub = args[0].lower()
    if sub == "user":
        if len(args) > 1:
            u = ctx.machine.user(args[1])
            if u is None:
                ctx.err(f"The user name could not be found.")
                return 2
            ctx.out(f"User name                    {u.name}")
            ctx.out(f"Account active               {'No' if u.locked else 'Yes'}")
            ctx.out(f"Local Group Memberships      {' '.join('*' + g for g in u.groups) or '*None'}")
            return 0
        ctx.out("\nUser accounts for \\\\" + ctx.machine.hostname.upper() + "\n")
        ctx.out("-" * 40)
        for u in ctx.machine.users.values():
            ctx.out(u.name)
        return 0
    if sub == "view":
        ctx.out(f"Server Name            Remark\n\n\\\\{ctx.machine.hostname.upper():<22}")
        return 0
    if sub in ("start", "stop"):
        services = ctx.machine.data.setdefault("winservices", [])
        svc = next((s for s in services if s["Name"].lower() == (args[1].lower() if len(args) > 1 else "")), None)
        if svc is None:
            ctx.err("The service name is invalid.")
            return 2
        svc["Status"] = "Running" if sub == "start" else "Stopped"
        ctx.out(f"The {svc['DisplayName']} service was {'started' if sub == 'start' else 'stopped'} successfully.")
        return 0
    ctx.err("The syntax of this command is:\nNET HELP command")
    return 1
