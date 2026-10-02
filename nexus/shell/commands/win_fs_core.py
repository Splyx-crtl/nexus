"""Shared file-system logic for the Windows command families (ps and cmd): both Get-ChildItem/dir, Remove-Item/del, Copy-Item/copy etc.
call these so the two syntaxes stay consistent and are tested once."""
from __future__ import annotations

import time

from ..fs import FsError, Node


def mode_string(node: Node) -> str:
    """PowerShell's Mode column: d/l + a(rchive)/r(eadonly)/h(idden)/s(ystem), e.g. 'd-----' or '-a----'."""
    kind = "l" if node.kind == "link" else ("d" if node.is_dir else "-")
    archive = "a" if not node.is_dir else "-"
    readonly = "r" if not (node.mode & 0o200) else "-"
    hidden = "h" if node.name.startswith(".") or node.meta.get("hidden") else "-"
    system = "s" if node.meta.get("system") else "-"
    return kind + archive + readonly + hidden + system + "-"


def fmt_time(ts: float) -> str:
    return time.strftime("%m/%d/%Y %H:%M", time.gmtime(ts))


def list_dir(ctx, path: str, recurse: bool = False) -> list[dict]:
    """[{Mode, LastWriteTime, Length, Name, FullName}] for Get-ChildItem/dir. A path that names a single file lists just that
    file (like the real tools), child-first for directories."""
    node = ctx.fs.stat(ctx.user, path, ctx.cwd)
    if not node.is_dir:
        return [{"Mode": mode_string(node), "LastWriteTime": fmt_time(node.mtime), "Length": node.size, "Name": node.name, "FullName": ctx.fs.norm(path, ctx.cwd)}]
    rows = []

    def one(p: str, cwd: str) -> None:
        base = ctx.fs.norm(p, cwd)
        for k in ctx.fs.listdir(ctx.user, p, cwd):
            full = ctx.fs.norm(k.name, base)
            rows.append({"Mode": mode_string(k), "LastWriteTime": fmt_time(k.mtime), "Length": "" if k.is_dir else k.size, "Name": k.name, "FullName": full})
            if recurse and k.is_dir:
                one(full, "")
    one(path, ctx.cwd)
    return rows


WIN_TEXT = {"ENOENT": "Cannot find path because it does not exist.", "EACCES": "Access to the path is denied.",
            "EEXIST": "Cannot create a file when that file already exists.", "ENOTDIR": "The specified path is invalid.",
            "EISDIR": "The specified path is a directory, not a file.", "ENOTEMPTY": "The directory is not empty."}


def win_text(exc: FsError) -> str:
    """The error's message in Windows/PowerShell wording instead of the POSIX one ``FsError.text`` carries."""
    return WIN_TEXT.get(exc.code, exc.text)


def remove(ctx, path: str, recursive: bool) -> None:
    node = ctx.fs.stat(ctx.user, path, ctx.cwd, follow=False)
    ctx.fs.remove(ctx.user, path, ctx.cwd, recursive=recursive or not node.is_dir)


def copy(ctx, src: str, dst: str, recursive: bool = False) -> None:
    ctx.fs.copy(ctx.user, src, dst, ctx.cwd, recursive=recursive)


def move(ctx, src: str, dst: str) -> None:
    ctx.fs.rename(ctx.user, src, dst, ctx.cwd)


def new_item(ctx, path: str, is_dir: bool) -> None:
    if is_dir:
        ctx.fs.mkdir(ctx.user, path, ctx.cwd, parents=True)
    else:
        ctx.fs.write(ctx.user, path, "", ctx.cwd)
