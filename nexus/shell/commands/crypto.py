"""Encoding, hashing, archiving and metadata commands (B5): base64, xxd, md5sum/sha256sum, strings, tar/zip/unzip,
exiftool, binwalk, openssl, gpg. Everything here operates only on this game's virtual filesystem and made-up data —
no real cryptography is implemented. Hashes are real (Python's hashlib against the node's actual text content, so
they're reproducible and genuinely verifiable), but "encryption" (gpg, openssl enc-equivalents) is a simple reversible
scramble gated by an explicit passphrase comparison, the same simulation tier as this engine's ssh/sudo password
checks — not real crypto, and nothing here cracks anything. Password-cracking tools (john/hydra/hashcat) are
deliberately NOT built as command-line tools with real attack syntax; they belong to the B10 GUI tool windows
(brute-force module, hash lab) per the user's explicit decision (see docs/3.0-PROGRESS.md)."""
from __future__ import annotations

import base64 as _b64
import hashlib
import re

from .. import opts
from ..fs import FsError
from ..registry import command

SIGNATURES = [
    (b"\x89PNG\r\n\x1a\n", "PNG image"), (b"PK\x03\x04", "Zip archive data (PKZIP)"), (b"%PDF-", "PDF document"),
    (b"GIF89a", "GIF image"), (b"Rar!\x1a\x07", "RAR archive data"), (b"\x1f\x8b\x08", "gzip compressed data"),
    (b"NXTAR1", "nexus tar archive"), (b"-----BEGIN", "PEM-encoded data"),
]


def _bytes_of(text: str) -> bytes:
    return text.encode("latin-1", errors="replace") if isinstance(text, str) else text


# ---------------------------------------------------------------------------------------------------- base64
@command("base64", level=14, summary="Base64 encode or decode data.", usage="base64 [-d] [FILE]",
         lesson="base64 turns bytes into plain-text-safe characters: 'base64 file' encodes it, 'base64 -d' turns it back. It's encoding, not encryption — anyone can reverse it.")
def base64_cmd(ctx, args):
    o = opts.parse(ctx, args, short="d", long={"decode": "d"})
    if o is None:
        return 2
    text = ctx.read_text(o.rest[0]) if o.rest else (ctx.stdin or "")
    try:
        if o.has("d"):
            ctx.out(_b64.b64decode(text.strip()).decode("latin-1"), end="")
        else:
            ctx.out(_b64.b64encode(_bytes_of(text)).decode("ascii"))
    except (FsError, ValueError) as exc:
        if isinstance(exc, FsError):
            return ctx.fs_error(exc, o.rest[0] if o.rest else "")
        ctx.err("base64: invalid input")
        return 1
    return 0


# ---------------------------------------------------------------------------------------------------- xxd
@command("xxd", level=14, summary="Make a hex dump of a file.", usage="xxd [FILE]",
         lesson="xxd shows a file's raw bytes as hex and ASCII side by side — useful when a file isn't really text, whatever its name claims.")
def xxd(ctx, args):
    o = opts.parse(ctx, args, short="", with_arg="l")
    if o is None:
        return 2
    try:
        text = ctx.read_text(o.rest[0]) if o.rest else (ctx.stdin or "")
    except FsError as exc:
        return ctx.fs_error(exc, o.rest[0] if o.rest else "")
    data = _bytes_of(text)
    if o.get("l"):
        data = data[: int(o.get("l"))]
    for off in range(0, len(data), 16):
        chunk = data[off:off + 16]
        hexpairs = " ".join(f"{chunk[i:i + 2].hex()}" for i in range(0, len(chunk), 2))
        ascii_ = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        ctx.out(f"{off:08x}: {hexpairs:<39} {ascii_}")
    return 0


# ---------------------------------------------------------------------------------------------------- md5sum / sha256sum
def _sum_cmd(algo: str):
    def run(ctx, args):
        o = opts.parse(ctx, args, short="c", long={"check": "c"})
        if o is None:
            return 2
        if o.has("c"):
            if not o.rest:
                ctx.err(f"{ctx.name}: no file specified")
                return 1
            try:
                manifest = ctx.read_text(o.rest[0])
            except FsError as exc:
                return ctx.fs_error(exc, o.rest[0])
            status = 0
            for line in manifest.splitlines():
                m = re.match(r"([0-9a-f]+)\s+(.+)", line.strip())
                if not m:
                    continue
                expected, fname = m.group(1), m.group(2)
                try:
                    actual = hashlib.new(algo, _bytes_of(ctx.read_text(fname))).hexdigest()
                except FsError:
                    ctx.out(f"{fname}: FAILED open or read")
                    status = 1
                    continue
                if actual == expected:
                    ctx.out(f"{fname}: OK")
                else:
                    ctx.out(f"{fname}: FAILED")
                    status = 1
            return status
        if not o.rest:
            ctx.out(f"{hashlib.new(algo, _bytes_of(ctx.stdin or '')).hexdigest()}  -")
            return 0
        status = 0
        for f in o.rest:
            try:
                digest = hashlib.new(algo, _bytes_of(ctx.read_text(f))).hexdigest()
                ctx.out(f"{digest}  {f}")
            except FsError as exc:
                ctx.fs_error(exc, f)
                status = 1
        return status
    return run


command("md5sum", level=15, summary="Compute and check MD5 message digests.", usage="md5sum [-c] [FILE]...",
        lesson="md5sum fingerprints a file's exact contents: 'md5sum file' prints its hash. 'md5sum -c list.txt' checks files against hashes saved earlier — the standard way to prove a file hasn't changed.")(_sum_cmd("md5"))
command("sha256sum", level=15, summary="Compute and check SHA256 message digests.", usage="sha256sum [-c] [FILE]...",
        lesson="sha256sum is md5sum's stronger, modern cousin — same idea, a longer and harder-to-fake fingerprint.")(_sum_cmd("sha256"))


# ---------------------------------------------------------------------------------------------------- strings
@command("strings", level=16, summary="Print the printable character sequences in a file.", usage="strings [-n MIN] FILE",
         lesson="strings pulls readable text out of a file that isn't meant to be read as text — the fastest way to find a password, URL or flag buried in something that looks like noise.")
def strings_cmd(ctx, args):
    o = opts.parse(ctx, args, with_arg="n")
    if o is None:
        return 2
    if not o.rest:
        ctx.err("strings: missing file operand")
        return 1
    min_len = int(o.get("n") or 4)
    try:
        text = ctx.read_text(o.rest[0])
    except FsError as exc:
        return ctx.fs_error(exc, o.rest[0])
    for run in re.findall(r"[ -~]{%d,}" % min_len, text):
        ctx.out(run)
    return 0


# ---------------------------------------------------------------------------------------------------- tar / zip / unzip
def _pack(ctx, entries: list[tuple[str, str]]) -> str:
    out = ["NXTAR1"]
    for name, data in entries:
        out.append(f"--ENTRY-- {name} {len(data)}")
        out.append(data)
    return "\n".join(out) + "\n"


def _unpack(text: str) -> list[tuple[str, str]]:
    lines = text.split("\n")
    if not lines or lines[0] != "NXTAR1":
        raise ValueError("not a nexus archive")
    entries, i = [], 1
    while i < len(lines):
        header = lines[i]
        if not header:
            i += 1
            continue
        m = re.match(r"--ENTRY-- (\S+) (\d+)", header)
        if not m:
            raise ValueError(f"corrupt archive header: {header!r}")
        name, size = m.group(1), int(m.group(2))
        body = "\n".join(lines[i + 1:])[:size]
        entries.append((name, body))
        i += 1 + body.count("\n") + 1
    return entries


@command("tar", level=17, summary="Archive files together.", usage="tar -cf archive.tar FILE... | tar -xf archive.tar | tar -tf archive.tar",
         man="""NAME
       tar - archive files together

SYNOPSIS
       tar -cf archive.tar FILE...     create an archive
       tar -xf archive.tar             extract an archive into the current folder
       tar -tf archive.tar             list an archive's contents without extracting
""", lesson="tar bundles several files into one: 'tar -cf backup.tar file1 file2' packs them, 'tar -xf backup.tar' unpacks them, 'tar -tf backup.tar' just lists what's inside.")
def tar_cmd(ctx, args):
    o = opts.parse(ctx, args, short="cxtvf", with_arg="C")
    if o is None:
        return 2
    archive = o.rest[0] if o.rest else None
    if not archive:
        ctx.err("tar: refusing to read archive contents from terminal (missing -f)")
        return 2
    if o.has("c"):
        entries = []
        for f in o.rest[1:]:
            try:
                entries.append((f, ctx.read_text(f)))
            except FsError as exc:
                return ctx.fs_error(exc, f)
        try:
            ctx.fs.write(ctx.user, archive, _pack(ctx, entries), ctx.cwd)
        except FsError as exc:
            return ctx.fs_error(exc, archive)
        if o.has("v"):
            for f, _ in entries:
                ctx.out(f)
        return 0
    if o.has("t") or o.has("x"):
        try:
            entries = _unpack(ctx.read_text(archive))
        except (FsError, ValueError) as exc:
            if isinstance(exc, FsError):
                return ctx.fs_error(exc, archive)
            ctx.err(f"tar: {archive}: not a valid archive")
            return 2
        if o.has("t"):
            for name, _ in entries:
                ctx.out(name)
            return 0
        base = o.get("C") or ""
        for name, data in entries:
            dest = (base.rstrip("/") + "/" + name) if base else name
            try:
                ctx.fs.write(ctx.user, dest, data, ctx.cwd)
            except FsError as exc:
                ctx.fs_error(exc, dest)
            if o.has("v"):
                ctx.out(name)
        return 0
    ctx.err("tar: you must specify one of -c, -x or -t")
    return 2


@command("zip", level=17, summary="Package files into a zip archive.", usage="zip archive.zip FILE...",
         lesson="zip does the same job as tar -c, in the format most non-Linux tools expect: 'zip bundle.zip file1 file2'.")
def zip_cmd(ctx, args):
    if len(args) < 2:
        ctx.err("zip: nothing to do (need an archive name and at least one file)")
        return 2
    archive, files = args[0], args[1:]
    entries = []
    for f in files:
        try:
            entries.append((f, ctx.read_text(f)))
        except FsError as exc:
            return ctx.fs_error(exc, f)
    try:
        ctx.fs.write(ctx.user, archive, "NXZIP1\n" + _pack(ctx, entries)[len("NXTAR1\n"):], ctx.cwd)
    except FsError as exc:
        return ctx.fs_error(exc, archive)
    ctx.out(f"  adding: " + " \n  adding: ".join(files))
    return 0


@command("unzip", level=17, summary="Extract files from a zip archive.", usage="unzip archive.zip",
         lesson="unzip reverses zip, same idea as tar -x in the other format.")
def unzip_cmd(ctx, args):
    o = opts.parse(ctx, args, with_arg="d")
    if o is None:
        return 2
    if not o.rest:
        ctx.err("unzip: missing archive operand")
        return 2
    archive = o.rest[0]
    try:
        text = ctx.read_text(archive)
    except FsError as exc:
        return ctx.fs_error(exc, archive)
    if not text.startswith("NXZIP1\n"):
        ctx.err(f"unzip: {archive}: not a valid zip archive (or this game's imitation of one)")
        return 2
    try:
        entries = _unpack("NXTAR1\n" + text[len("NXZIP1\n"):])
    except ValueError:
        ctx.err(f"unzip: {archive}: corrupt archive")
        return 2
    base = o.get("d") or ""
    for name, data in entries:
        dest = (base.rstrip("/") + "/" + name) if base else name
        try:
            ctx.fs.write(ctx.user, dest, data, ctx.cwd)
            ctx.out(f"  inflating: {dest}")
        except FsError as exc:
            ctx.fs_error(exc, dest)
    return 0


# ---------------------------------------------------------------------------------------------------- exiftool
@command("exiftool", level=18, summary="Read metadata embedded in a file.", usage="exiftool FILE",
         lesson="exiftool reads the hidden metadata a file carries alongside its visible content — camera model, author, GPS coordinates, timestamps nobody scrubbed.")
def exiftool_cmd(ctx, args):
    rest = [a for a in args if not a.startswith("-")]
    if not rest:
        ctx.err("exiftool: no file specified")
        return 2
    status = 0
    for f in rest:
        try:
            node = ctx.fs.stat(ctx.user, f, ctx.cwd)
        except FsError as exc:
            ctx.fs_error(exc, f)
            status = 1
            continue
        if not node.meta:
            ctx.out(f"{f}: No metadata found")
            continue
        ctx.out(f"======== {f}")
        for k, v in node.meta.items():
            if k.startswith("_"):
                continue
            ctx.out(f"{k:<24}: {v}")
        ctx.event("file_identified", path=ctx.path(f), machine=ctx.machine.id)
    return status


# ---------------------------------------------------------------------------------------------------- binwalk
@command("binwalk", level=19, summary="Scan a file for embedded file signatures.", usage="binwalk FILE",
         lesson="binwalk scans a file for the telltale first bytes of other file formats hiding inside it — the classic way to find something smuggled inside an image or document.")
def binwalk_cmd(ctx, args):
    rest = [a for a in args if not a.startswith("-")]
    if not rest:
        ctx.err("binwalk: no file specified")
        return 1
    try:
        text = ctx.read_text(rest[0])
    except FsError as exc:
        return ctx.fs_error(exc, rest[0])
    data = _bytes_of(text)
    ctx.out("DECIMAL       HEXADECIMAL     DESCRIPTION")
    ctx.out("--------------------------------------------------------------")
    found = False
    for sig, desc in SIGNATURES:
        idx = data.find(sig)
        if idx != -1:
            found = True
            ctx.out(f"{idx:<13} 0x{idx:<13X} {desc}")
    if not found:
        ctx.out("(no known signatures found)")
    return 0


# ---------------------------------------------------------------------------------------------------- openssl
@command("openssl", level=20, summary="Cryptography toolkit: digests and encoding.", usage="openssl dgst -sha256 FILE | openssl base64 [-d] [-in FILE]",
         man="""NAME
       openssl - cryptography and TLS toolkit

SYNOPSIS
       openssl dgst -md5|-sha256 FILE
       openssl base64 [-d] [-in FILE]

DESCRIPTION
       Only the dgst and base64 subcommands exist here — the parts of openssl an administrator actually uses day to
       day for checking a file's integrity or encoding. There is no 'enc' here: that is a GUI job in this game (B10).
""", lesson="openssl dgst -sha256 file hashes a file, the same job as sha256sum but spelled the way openssl spells it. openssl base64 encodes/decodes exactly like the base64 command.")
def openssl_cmd(ctx, args):
    if not args:
        ctx.err("openssl: no command specified")
        return 1
    sub, rest = args[0], args[1:]
    if sub == "dgst":
        algo = "sha256"
        files = []
        for a in rest:
            if a in ("-md5", "-sha1", "-sha256"):
                algo = a[1:]
            elif not a.startswith("-"):
                files.append(a)
        if not files:
            ctx.err("openssl: dgst: no file specified")
            return 1
        status = 0
        for f in files:
            try:
                digest = hashlib.new(algo, _bytes_of(ctx.read_text(f))).hexdigest()
                ctx.out(f"{algo.upper()}({f})= {digest}")
            except FsError as exc:
                ctx.fs_error(exc, f)
                status = 1
        return status
    if sub == "base64":
        decode = "-d" in rest or "-decode" in rest
        in_file = None
        for i, a in enumerate(rest):
            if a == "-in" and i + 1 < len(rest):
                in_file = rest[i + 1]
        try:
            text = ctx.read_text(in_file) if in_file else (ctx.stdin or "")
        except FsError as exc:
            return ctx.fs_error(exc, in_file or "")
        if decode:
            try:
                ctx.out(_b64.b64decode(text.strip()).decode("latin-1"), end="")
            except ValueError:
                ctx.err("openssl: base64: invalid input")
                return 1
        else:
            ctx.out(_b64.b64encode(_bytes_of(text)).decode("ascii"))
        return 0
    ctx.err(f"openssl: '{sub}' is not an openssl command (only dgst and base64 exist in this game)")
    return 1


# ---------------------------------------------------------------------------------------------------- gpg
def _scramble(text: str) -> str:
    return _b64.b64encode(_bytes_of(text)[::-1]).decode("ascii")


def _unscramble(text: str) -> str:
    return _b64.b64decode(text.strip())[::-1].decode("latin-1")


@command("gpg", level=21, summary="Encrypt or decrypt a file with a passphrase.", usage="gpg --symmetric --batch --passphrase PASS -o OUT FILE | gpg --decrypt --batch --passphrase PASS -o OUT FILE",
         man="""NAME
       gpg - OpenPGP encryption (symmetric mode only, in this game)

SYNOPSIS
       gpg --symmetric --batch --passphrase PASS -o OUT.gpg FILE
       gpg --decrypt --batch --passphrase PASS -o OUT FILE.gpg

DESCRIPTION
       Only symmetric (passphrase-based) encryption exists here — no keypairs, no keyrings. --batch --passphrase is
       the real, documented way to script gpg without an interactive prompt, same idea as sshpass for ssh.
""", lesson="gpg --symmetric locks a file behind a passphrase; gpg --decrypt with the same passphrase opens it again. Wrong passphrase, no file — there's no shortcut around that here.")
def gpg_cmd(ctx, args):
    o = opts.parse(ctx, args, long={"symmetric": "symmetric", "decrypt": "decrypt", "batch": "batch"},
                   long_arg={"passphrase": "passphrase"}, with_arg="o")
    if o is None:
        return 2
    rest = list(o.rest)
    if not rest:
        ctx.err("gpg: no input file given")
        return 2
    src = rest[0]
    pass_val = o.get("passphrase")
    if pass_val is None:
        ctx.err("gpg: no passphrase given (use --batch --passphrase PASS)")
        return 2
    if o.has("symmetric"):
        try:
            data = ctx.read_text(src)
        except FsError as exc:
            return ctx.fs_error(exc, src)
        out_path = o.get("o") or (src + ".gpg")
        node = ctx.fs.write(ctx.user, out_path, _scramble(data), ctx.cwd)
        node.meta["gpg_pass"] = pass_val
        ctx.out(f"gpg: encrypted to '{out_path}'")
        return 0
    if o.has("decrypt"):
        try:
            node = ctx.fs.stat(ctx.user, src, ctx.cwd)
            data = ctx.read_text(src)
        except FsError as exc:
            return ctx.fs_error(exc, src)
        if node.meta.get("gpg_pass") != pass_val:
            ctx.err("gpg: decryption failed: Bad session key")
            return 2
        try:
            plain = _unscramble(data)
        except ValueError:
            ctx.err(f"gpg: {src}: not a valid encrypted file")
            return 2
        out_path = o.get("o")
        if out_path:
            ctx.fs.write(ctx.user, out_path, plain, ctx.cwd)
            ctx.out(f"gpg: decrypted to '{out_path}'")
        else:
            ctx.out(plain, end="")
        return 0
    ctx.err("gpg: specify --symmetric (to encrypt) or --decrypt")
    return 2
