"""PowerShell cmdlets for Windows targets (family="ps"). A small but real object pipeline: see winshell.py for how
``ctx.objects_in``/``ctx.objects_out`` and scriptblocks (``{ $_.Name -eq 'x' }``) work."""
from __future__ import annotations

import re
import time

from .. import winshell
from ..fs import FsError
from ..registry import command
from . import win_fs_core as core
from .net import _announce, _http_fetch, _lat, _target


def parse_ps_args(args: list[str], switches: set[str] = frozenset(), valued: set[str] = frozenset()):
    """(positional, {ParamName: value}, {switch names present}) — PowerShell parameter names, matched case-insensitively."""
    valued_lower = {v.lower(): v for v in valued}
    switch_lower = {v.lower(): v for v in switches}
    pos, named, flags = [], {}, set()
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("-") and len(a) > 1:
            key = a[1:].lower()
            if key in valued_lower:
                i += 1
                named[valued_lower[key]] = args[i] if i < len(args) else ""
            elif key in switch_lower:
                flags.add(switch_lower[key])
            else:
                flags.add(a[1:])
        else:
            pos.append(a)
        i += 1
    return pos, named, flags


def _items(ctx):
    return ctx.objects_in if ctx.objects_in is not None else []


# ------------------------------------------------------------------------------------------------ file system
@command("Get-ChildItem", family="ps", level=1, summary="Gets the items and child items in one or more specified locations.",
         usage="Get-ChildItem [[-Path] <path>] [-Recurse] [-Name]", aliases=("gci", "ls", "dir"),
         lesson="Get-ChildItem lists what is in a folder — it is what 'ls' is on Linux. Its own short name is 'dir', just like the old DOS command.")
def gci(ctx, args):
    pos, named, flags = parse_ps_args(args, {"Recurse", "Force", "Name", "Directory", "File"})
    path = named.get("Path") or (pos[0] if pos else ".")
    try:
        rows = core.list_dir(ctx, path, recurse="Recurse" in flags)
    except FsError as exc:
        ctx.err(f"Get-ChildItem : {core.win_text(exc)}")
        return 1
    if "Directory" in flags:
        rows = [r for r in rows if r["Mode"].startswith("d")]
    if "File" in flags:
        rows = [r for r in rows if not r["Mode"].startswith("d")]
    if "Name" in flags:
        for r in rows:
            ctx.out(r["Name"])
        return 0
    ctx.objects_out = [{"Mode": r["Mode"], "LastWriteTime": r["LastWriteTime"], "Length": r["Length"], "Name": r["Name"]} for r in rows]
    return 0


@command("Get-Content", family="ps", level=1, summary="Gets the content of a file.", usage="Get-Content [-Path] <path> [-Tail <n>] [-Raw]",
         aliases=("gc", "cat", "type"), lesson="Get-Content reads a file and prints it — 'type notes.txt' is the classic DOS spelling of the same thing.")
def get_content(ctx, args):
    pos, named, flags = parse_ps_args(args, {"Raw"}, {"Tail", "TotalCount"})
    path = named.get("Path") or (pos[0] if pos else None)
    if not path:
        ctx.err("Get-Content : Cannot bind argument to parameter 'Path' because it is an empty string.")
        return 1
    try:
        text = ctx.read_text(path)
    except FsError as exc:
        ctx.err(f"Get-Content : {core.win_text(exc)}")
        return 1
    lines = text.splitlines()
    if named.get("Tail"):
        lines = lines[-int(named["Tail"]):]
    if named.get("TotalCount"):
        lines = lines[:int(named["TotalCount"])]
    if "Raw" in flags:
        ctx.out(text, end="")
    else:
        ctx.objects_out = lines
    return 0


@command("Set-Content", family="ps", level=3, summary="Writes new content to a file, replacing anything already there.",
         usage="Set-Content [-Path] <path> -Value <text>", aliases=("sc",),
         lesson="Set-Content writes text straight to a file: 'Set-Content -Path notes.ps1 -Value \"Write-Output 1\"'. Same idea as > in bash.")
def set_content(ctx, args):
    pos, named, _ = parse_ps_args(args, valued={"Path", "Value"})
    path = named.get("Path") or (pos[0] if pos else None)
    if not path:
        ctx.err("Set-Content : Cannot bind argument to parameter 'Path'.")
        return 1
    value = named.get("Value", "")
    try:
        ctx.fs.write(ctx.user, path, value if value.endswith("\n") else value + "\n", ctx.cwd)
    except FsError as exc:
        ctx.err(f"Set-Content : {core.win_text(exc)}")
        return 1
    return 0


@command("Add-Content", family="ps", level=3, summary="Appends content to a file.", usage="Add-Content [-Path] <path> -Value <text>", aliases=("ac",),
         lesson="Add-Content adds another line to a file without erasing what's already there — same idea as >> in bash. Build a script one line at a time with it.")
def add_content(ctx, args):
    pos, named, _ = parse_ps_args(args, valued={"Path", "Value"})
    path = named.get("Path") or (pos[0] if pos else None)
    if not path:
        ctx.err("Add-Content : Cannot bind argument to parameter 'Path'.")
        return 1
    value = named.get("Value", "")
    try:
        ctx.fs.write(ctx.user, path, value if value.endswith("\n") else value + "\n", ctx.cwd, append=True)
    except FsError as exc:
        ctx.err(f"Add-Content : {core.win_text(exc)}")
        return 1
    return 0


@command("Out-File", family="ps", level=3, summary="Sends pipeline output to a file.", usage="<pipeline> | Out-File [-FilePath] <path> [-Append]",
         lesson="Out-File saves whatever came through the pipeline into a file: 'Write-Output \"hi\" | Out-File log.txt'.")
def out_file(ctx, args):
    pos, named, flags = parse_ps_args(args, {"Append"}, valued={"FilePath"})
    path = named.get("FilePath") or (pos[0] if pos else None)
    if not path:
        ctx.err("Out-File : Cannot bind argument to parameter 'FilePath'.")
        return 1
    items = ctx.objects_in if ctx.objects_in is not None else []
    text = "\n".join(str(it) for it in items)
    if text:
        text += "\n"
    try:
        ctx.fs.write(ctx.user, path, text, ctx.cwd, append="Append" in flags)
    except FsError as exc:
        ctx.err(f"Out-File : {core.win_text(exc)}")
        return 1
    return 0


@command("Get-Item", family="ps", level=2, summary="Gets the item at the specified location.", usage="Get-Item [-Path] <path>", aliases=("gi",))
def get_item(ctx, args):
    pos, named, _ = parse_ps_args(args)
    path = named.get("Path") or (pos[0] if pos else None)
    if not path:
        ctx.err("Get-Item : Cannot bind argument to parameter 'Path'.")
        return 1
    try:
        node = ctx.fs.stat(ctx.user, path, ctx.cwd, follow=False)
    except FsError as exc:
        ctx.err(f"Get-Item : {core.win_text(exc)}")
        return 1
    ctx.objects_out = [{"Mode": core.mode_string(node), "LastWriteTime": core.fmt_time(node.mtime), "Length": "" if node.is_dir else node.size, "Name": node.name}]
    return 0


@command("Get-Location", family="ps", level=1, summary="Gets information about the current working location.", usage="Get-Location", aliases=("gl", "pwd"))
def get_location(ctx, args):
    ctx.out(ctx.cwd)
    return 0


@command("Set-Location", family="ps", level=1, summary="Sets the current working location.", usage="Set-Location [-Path] <path>", aliases=("sl", "cd", "chdir"),
         lesson="Set-Location changes the current folder — 'cd' is its well-known short name, same as everywhere else.")
def set_location(ctx, args):
    pos, named, _ = parse_ps_args(args)
    path = named.get("Path") or (pos[0] if pos else ctx.env.get("HOMEPATH") and ctx.env.get("HOMEDRIVE", "C:") + ctx.env.get("HOMEPATH", "\\"))
    if not path:
        return 0
    try:
        node = ctx.fs.stat(ctx.user, path, ctx.cwd)
    except FsError as exc:
        ctx.err(f"Set-Location : {core.win_text(exc)}")
        return 1
    if not node.is_dir:
        ctx.err(f"Set-Location : The path '{path}' is not a container.")
        return 1
    full = ctx.path(path)
    if not ctx.fs.can(ctx.user, node, "x", full):
        ctx.err("Set-Location : Access to the path is denied.")
        return 1
    ctx.session.cwd = full
    ctx.session.env["PWD"] = full
    return 0


@command("New-Item", family="ps", level=3, summary="Creates a new item (file or directory).", usage="New-Item [-Path] <path> [-ItemType File|Directory]",
         aliases=("ni", "mkdir", "md"), lesson="New-Item makes a new file or folder: 'New-Item -ItemType Directory logs' (or just 'mkdir logs').")
def new_item(ctx, args):
    pos, named, _ = parse_ps_args(args, valued={"Path", "ItemType", "Name"})
    path = named.get("Path") or (pos[0] if pos else None)
    if named.get("Name"):
        path = (path.rstrip("\\") + "\\" + named["Name"]) if path else named["Name"]
    if not path:
        ctx.err("New-Item : Cannot bind argument to parameter 'Path'.")
        return 1
    is_dir = named.get("ItemType", "").lower() in ("directory", "dir") or ctx.name.lower() in ("mkdir", "md")
    try:
        core.new_item(ctx, path, is_dir)
    except FsError as exc:
        ctx.err(f"New-Item : {core.win_text(exc)}")
        return 1
    ctx.event("create", path=ctx.path(path), machine=ctx.machine.id)
    return 0


@command("Remove-Item", family="ps", level=3, summary="Deletes an item.", usage="Remove-Item [-Path] <path> [-Recurse]", aliases=("ri", "rm", "del", "erase", "rd", "rmdir"),
         lesson="Remove-Item deletes a file or folder, no trash can — the classic names 'del' and 'rmdir' still work.")
def remove_item(ctx, args):
    pos, named, flags = parse_ps_args(args, {"Recurse", "Force"}, {"Path"})
    status = 0
    for path in ([named["Path"]] if named.get("Path") else pos) or []:
        try:
            core.remove(ctx, path, "Recurse" in flags)
            ctx.event("delete", path=ctx.path(path), machine=ctx.machine.id)
        except FsError as exc:
            ctx.err(f"Remove-Item : {core.win_text(exc)}")
            status = 1
    if not pos and not named.get("Path"):
        ctx.err("Remove-Item : Cannot bind argument to parameter 'Path'.")
        return 1
    return status


@command("Copy-Item", family="ps", level=3, summary="Copies an item from one location to another.", usage="Copy-Item [-Path] <src> [-Destination] <dst> [-Recurse]",
         aliases=("cpi", "cp", "copy"), lesson="Copy-Item copies a file or, with -Recurse, a whole folder.")
def copy_item(ctx, args):
    pos, named, flags = parse_ps_args(args, {"Recurse"}, {"Path", "Destination"})
    src = named.get("Path") or (pos[0] if pos else None)
    dst = named.get("Destination") or (pos[1] if len(pos) > 1 else None)
    if not src or not dst:
        ctx.err("Copy-Item : Cannot bind argument to parameter 'Destination'.")
        return 1
    try:
        core.copy(ctx, src, dst, "Recurse" in flags)
    except FsError as exc:
        ctx.err(f"Copy-Item : {core.win_text(exc)}")
        return 1
    return 0


@command("Move-Item", family="ps", level=3, summary="Moves an item from one location to another.", usage="Move-Item [-Path] <src> [-Destination] <dst>",
         aliases=("mi", "mv", "move"))
def move_item(ctx, args):
    pos, named, _ = parse_ps_args(args, valued={"Path", "Destination"})
    src = named.get("Path") or (pos[0] if pos else None)
    dst = named.get("Destination") or (pos[1] if len(pos) > 1 else None)
    if not src or not dst:
        ctx.err("Move-Item : Cannot bind argument to parameter 'Destination'.")
        return 1
    try:
        core.move(ctx, src, dst)
    except FsError as exc:
        ctx.err(f"Move-Item : {core.win_text(exc)}")
        return 1
    return 0


@command("Rename-Item", family="ps", level=3, summary="Renames an item.", usage="Rename-Item [-Path] <path> [-NewName] <name>", aliases=("rni", "ren", "rename"))
def rename_item(ctx, args):
    pos, named, _ = parse_ps_args(args, valued={"Path", "NewName"})
    src = named.get("Path") or (pos[0] if pos else None)
    new = named.get("NewName") or (pos[1] if len(pos) > 1 else None)
    if not src or not new:
        ctx.err("Rename-Item : Cannot bind argument to parameter 'NewName'.")
        return 1
    dst = ctx.fs.join(ctx.fs.absolute(src, ctx.cwd)[:-1] + [new])
    try:
        core.move(ctx, src, dst)
    except FsError as exc:
        ctx.err(f"Rename-Item : {core.win_text(exc)}")
        return 1
    return 0


@command("Test-Path", family="ps", level=2, summary="Determines whether all elements of a path exist.", usage="Test-Path [-Path] <path>")
def test_path(ctx, args):
    pos, named, _ = parse_ps_args(args, valued={"Path"})
    path = named.get("Path") or (pos[0] if pos else "")
    ctx.out("True" if ctx.fs.exists(path, ctx.cwd) else "False")
    return 0


# ------------------------------------------------------------------------------------------------ text search
@command("Select-String", family="ps", level=8, summary="Finds text in strings and files.", usage="Select-String -Pattern <pattern> [-Path] <file>...",
         aliases=("sls",), lesson="Select-String searches text, the same job as 'grep' on Linux: 'Select-String -Pattern error log.txt'.")
def select_string(ctx, args):
    pos, named, flags = parse_ps_args(args, {"CaseSensitive", "NotMatch"}, {"Pattern"})
    pattern = named.get("Pattern") or (pos[0] if pos else None)
    files = pos[1:] if not named.get("Pattern") else pos
    if not pattern:
        ctx.err("Select-String : Cannot bind argument to parameter 'Pattern'.")
        return 1
    try:
        rx = re.compile(pattern, 0 if "CaseSensitive" in flags else re.I)
    except re.error as exc:
        ctx.err(f"Select-String : {exc}")
        return 1
    rows = []
    for f in files or []:
        try:
            text = ctx.read_text(f)
        except FsError as exc:
            ctx.err(f"Select-String : {core.win_text(exc)}")
            continue
        for n, line in enumerate(text.splitlines(), 1):
            hit = rx.search(line) is not None
            if hit != ("NotMatch" in flags):
                rows.append({"Path": f, "LineNumber": n, "Line": line})
    ctx.objects_out = rows
    return 0


# ------------------------------------------------------------------------------------------------ pipeline cmdlets
@command("Where-Object", family="ps", level=9, summary="Selects objects from a collection based on their property values.",
         usage="Where-Object { scriptblock } | Where-Object Property -eq Value", aliases=("?", "where"),
         lesson="Where-Object filters a list of objects: 'Get-Process | Where-Object {$_.CPU -gt 10}' keeps only the busy ones.")
def where_object(ctx, args):
    items = _items(ctx)
    if args and args[0].startswith("{"):
        ctx.objects_out = [it for it in items if winshell.eval_scriptblock(args[0], ctx.shell, it)]
        return 0
    if len(args) >= 2:
        prop, op = args[0], args[1]
        value = args[2] if len(args) > 2 else ""
        ev = winshell._PsExprEval.__new__(winshell._PsExprEval)
        ctx.objects_out = [it for it in items if ev._compare(op if op.startswith("-") else "-" + op, ev._property(it, prop) if isinstance(it, dict) else it, value)]
        return 0
    ctx.objects_out = items
    return 0


@command("ForEach-Object", family="ps", level=9, summary="Performs an operation on each item in a collection.", usage="ForEach-Object { scriptblock }",
         aliases=("%", "foreach"), lesson="ForEach-Object runs a small script once per item: 'Get-ChildItem | ForEach-Object {$_.Name}' prints just the names.")
def foreach_object(ctx, args):
    items = _items(ctx)
    if not args or not args[0].startswith("{"):
        ctx.objects_out = items
        return 0
    ctx.objects_out = [winshell.eval_scriptblock(args[0], ctx.shell, it) for it in items]
    return 0


@command("Select-Object", family="ps", level=9, summary="Selects objects or object properties.", usage="Select-Object [-Property] <names> [-First n] [-Last n]",
         aliases=("select",))
def select_object(ctx, args):
    pos, named, _ = parse_ps_args(args, valued={"Property", "First", "Last"})
    items = _items(ctx)
    if named.get("First"):
        items = items[:int(named["First"])]
    if named.get("Last"):
        items = items[-int(named["Last"]):]
    props = named.get("Property") or (pos[0] if pos else None)
    if props:
        names = props.split(",")
        items = [{n: (it.get(n, "") if isinstance(it, dict) else it) for n in names} for it in items]
    ctx.objects_out = items
    return 0


@command("Sort-Object", family="ps", level=9, summary="Sorts objects by property values.", usage="Sort-Object [-Property] <name> [-Descending]", aliases=("sort",))
def sort_object(ctx, args):
    pos, named, flags = parse_ps_args(args, {"Descending", "Unique"}, {"Property"})
    prop = named.get("Property") or (pos[0] if pos else None)
    items = list(_items(ctx))

    def key(it):
        v = it.get(prop, "") if isinstance(it, dict) and prop else it
        try:
            return (0, float(v))
        except (TypeError, ValueError):
            return (1, str(v))
    items.sort(key=key, reverse="Descending" in flags)
    if "Unique" in flags:
        seen, uniq = set(), []
        for it in items:
            k = str(it)
            if k not in seen:
                seen.add(k)
                uniq.append(it)
        items = uniq
    ctx.objects_out = items
    return 0


@command("Measure-Object", family="ps", level=9, summary="Calculates numeric properties of objects.", usage="Measure-Object [-Property] <name>", aliases=("measure",))
def measure_object(ctx, args):
    pos, named, flags = parse_ps_args(args, {"Sum", "Average", "Maximum", "Minimum"}, {"Property"})
    prop = named.get("Property") or (pos[0] if pos else None)
    items = _items(ctx)
    values = []
    for it in items:
        v = it.get(prop, "") if isinstance(it, dict) and prop else it
        try:
            values.append(float(v))
        except (TypeError, ValueError):
            pass
    row = {"Count": len(items)}
    if values:
        row.update({"Sum": sum(values), "Average": sum(values) / len(values), "Maximum": max(values), "Minimum": min(values)})
    ctx.objects_out = [row]
    return 0


# ------------------------------------------------------------------------------------------------ output
@command("Write-Output", family="ps", level=1, summary="Sends the specified objects to the next command in the pipeline.", usage="Write-Output <object>...",
         aliases=("echo", "write"))
def write_output(ctx, args):
    if not args:
        ctx.out("")
        return 0
    ctx.objects_out = list(args)
    return 0


@command("Write-Host", family="ps", level=1, summary="Writes customized output to the console.", usage="Write-Host <object>...")
def write_host(ctx, args):
    ctx.out(" ".join(a for a in args if not a.startswith("-")))
    return 0


# ------------------------------------------------------------------------------------------------ system
@command("Get-Process", family="ps", level=6, summary="Gets the processes running on the local computer.", usage="Get-Process [-Name <name>]", aliases=("gps", "ps"))
def get_process(ctx, args):
    pos, named, _ = parse_ps_args(args, valued={"Name"})
    name = named.get("Name") or (pos[0] if pos else None)
    rows = [{"Id": p.pid, "ProcessName": p.name, "CPU": round(p.cpu, 2), "WS(K)": int(p.mem * 1024)} for p in ctx.machine.processes
            if not name or p.name.lower() == name.lower()]
    ctx.objects_out = rows
    return 0


@command("Stop-Process", family="ps", level=6, summary="Stops one or more running processes.", usage="Stop-Process [-Id] <id> | -Name <name>", aliases=("spps", "kill"))
def stop_process(ctx, args):
    pos, named, _ = parse_ps_args(args, valued={"Id", "Name"})
    pid = named.get("Id") or (pos[0] if pos else None)
    name = named.get("Name")
    target = next((p for p in ctx.machine.processes if (pid and str(p.pid) == str(pid)) or (name and p.name.lower() == name.lower())), None)
    if target is None:
        ctx.err("Stop-Process : Cannot find a process.")
        return 1
    if target.user != ctx.user.name and not ctx.user.is_root:
        ctx.err(f"Stop-Process : Cannot stop process \"{target.name} ({target.pid})\" because of the following error: Access is denied.")
        return 1
    ctx.machine.processes.remove(target)
    ctx.event("process_killed", pid=target.pid, name=target.name, machine=ctx.machine.id)
    return 0


@command("Get-Service", family="ps", level=8, summary="Gets the services on the computer.", usage="Get-Service [-Name <name>]",
         lesson="Get-Service lists Windows services (background programs) and whether they are running.")
def get_service(ctx, args):
    pos, named, _ = parse_ps_args(args, valued={"Name"})
    name = named.get("Name") or (pos[0] if pos else None)
    rows = [s for s in ctx.machine.data.get("winservices", []) if not name or s["Name"].lower() == name.lower()]
    ctx.objects_out = [{"Status": s["Status"], "Name": s["Name"], "DisplayName": s["DisplayName"]} for s in rows]
    return 0


@command("Get-LocalUser", family="ps", level=6, summary="Gets local user accounts.", usage="Get-LocalUser")
def get_local_user(ctx, args):
    ctx.objects_out = [{"Name": u.name, "Enabled": not u.locked, "Description": ""} for u in ctx.machine.users.values()]
    return 0


@command("whoami", family="ps", level=1, summary="Prints the current user name.", usage="whoami",
        lesson="whoami prints the currently logged-in user's name — same command as in cmd and bash, PowerShell just falls back to it directly.")
def whoami_ps(ctx, args):
    ctx.out(f"{ctx.machine.hostname}\\{ctx.user.name}" if "/" not in args and "--upn" not in args else ctx.user.name)
    return 0


@command("hostname", family="ps", level=1, summary="Prints the computer name.", usage="hostname",
        lesson="hostname prints this computer's name on the network — same command PowerShell falls back to from cmd.")
def hostname_ps(ctx, args):
    ctx.out(ctx.machine.hostname.upper())
    return 0


@command("Get-Date", family="ps", level=2, summary="Gets the current date and time.", usage="Get-Date")
def get_date(ctx, args):
    ctx.out(time.strftime("%A, %B %d, %Y %H:%M:%S", time.gmtime(ctx.now())))
    return 0


@command("Get-Random", family="ps", level=3, summary="Gets a random number.", usage="Get-Random [-Minimum n] [-Maximum n]")
def get_random(ctx, args):
    pos, named, _ = parse_ps_args(args, valued={"Minimum", "Maximum"})
    lo, hi = int(named.get("Minimum", 0)), int(named.get("Maximum", 2**31 - 1))
    ctx.out(str(lo + (abs(hash((ctx.now(), ctx.session.pid, len(ctx.session.history)))) % max(1, hi - lo))))
    return 0


@command("Clear-Host", family="ps", level=1, summary="Clears the display in the host program.", usage="Clear-Host", aliases=("cls", "clear"))
def clear_host(ctx, args):
    ctx.request("clear")
    return 0


@command("Get-Help", family="ps", level=1, summary="Displays information about PowerShell cmdlets.", usage="Get-Help [[-Name] <cmdlet>]")
def get_help(ctx, args):
    from ..registry import lookup, specs
    if not args:
        ctx.out("TOPIC\n    Windows PowerShell Help System\n\nSHORT DESCRIPTION\n    Displays help about PowerShell cmdlets. Try 'Get-Help Get-ChildItem'.")
        return 0
    spec = lookup("ps", args[0])
    if spec is None:
        ctx.err(f"Get-Help : Get-Help could not find help for topic '{args[0]}'.")
        return 1
    ctx.out(f"NAME\n    {spec.name}\n\nSYNTAX\n    {spec.usage}\n\nDESCRIPTION\n    {spec.summary}")
    return 0


@command("Get-Command", family="ps", level=1, summary="Gets all commands installed on the computer.", usage="Get-Command")
def get_command(ctx, args):
    from ..registry import specs
    ctx.objects_out = [{"CommandType": "Cmdlet", "Name": s.name} for s in specs("ps") if s.level <= ctx.shell.level()]
    return 0


@command("exit", family="ps", level=1, summary="Exits the current session.", usage="exit [code]", aliases=("Exit-PSSession",),
         lesson="exit leaves the current session: if you logged into another machine, it takes you back to where you came from.")
def ps_exit(ctx, args):
    status = int(args[0]) if args and args[0].isdigit() else ctx.session.last_status
    if ctx.session.parent is not None:
        host = ctx.session.machine.ip
        ctx.shell.pop_session()
        ctx.out("logout")
        ctx.out(f"Connection to {host} closed.")
        return status
    ctx.shell.ps_exit = status
    return status


# ------------------------------------------------------------------------------------------------ network (reuses net.py's simulated world helpers)
@command("Test-Connection", family="ps", level=9, summary="Sends ICMP echo request packets.", usage="Test-Connection [-ComputerName] <name>", aliases=("tnc",))
def test_connection(ctx, args):
    pos, named, _ = parse_ps_args(args, valued={"ComputerName", "Count"})
    name = named.get("ComputerName") or (pos[0] if pos else None)
    if not name:
        ctx.err("Test-Connection : Cannot bind argument to parameter 'ComputerName'.")
        return 1
    machine, ip = _target(ctx, name)
    if ip is None:
        ctx.err(f"Test-Connection : Testing connection to computer '{name}' failed: Name or service not known")
        return 1
    count = min(int(named.get("Count", 4)), 10)
    rows = []
    for i in range(count):
        ctx.wait(300)
        rows.append({"Source": ctx.machine.hostname, "Destination": name, "Latency": round(_lat(ip) + i * 0.05, 2) if machine else None, "Status": "Success" if machine else "TimedOut"})
    ctx.objects_out = rows
    if machine:
        _announce(ctx, machine)
    return 0 if machine else 1


@command("Invoke-WebRequest", family="ps", level=11, summary="Gets content from a web page on the Internet.", usage="Invoke-WebRequest [-Uri] <url>",
         aliases=("iwr", "curl", "wget"), lesson="Invoke-WebRequest fetches a web page, PowerShell's version of curl/wget.")
def invoke_webrequest(ctx, args):
    pos, named, _ = parse_ps_args(args, valued={"Uri"})
    url = named.get("Uri") or (pos[0] if pos else None)
    if not url:
        ctx.err("Invoke-WebRequest : Cannot bind argument to parameter 'Uri'.")
        return 1
    result = _http_fetch(ctx, url)
    if result is None:
        ctx.err(f"Invoke-WebRequest : The remote name could not be resolved.")
        return 1
    if result[0] == "refused":
        ctx.err("Invoke-WebRequest : Unable to connect to the remote server")
        return 1
    status, headers, body = result
    ctx.objects_out = [{"StatusCode": status, "StatusDescription": "OK" if status == 200 else "Not Found", "Content": body}]
    return 0 if status == 200 else 1
