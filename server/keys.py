"""Admin tool for the invite-only access keys of the NEXUS online server.

    python -m server.keys create "Alice" [-n 5] [--days 30]   make keys (printed once, only a hash is stored)
    python -m server.keys list [--status unused|"in use"|revoked|expired]   all keys and who uses them
    python -m server.keys revoke <id>               deactivate a key and log its owner out
    python -m server.keys activate <id>             switch a deactivated key back on
    python -m server.keys unbind <id>               free a key from its Discord account (player switched accounts)
    python -m server.keys delete <id>               delete a key for good

Server address and admin token come from --url / --token or the environment variables NEXUS_SERVER_URL and
NEXUS_ADMIN_TOKEN (the same token that is set on the server). The token never goes into the game or the repository.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def call(url: str, token: str, method: str, path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url.rstrip("/") + path, data=data, method=method,
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "nexus-keys"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode()).get("detail", "")
        except (ValueError, OSError):
            detail = ""
        raise SystemExit(f"Server answered {exc.code}: {detail or exc.reason}")
    except urllib.error.URLError as exc:
        raise SystemExit(f"Cannot reach the server: {exc.reason}")


def stamp(value) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(value)) if value else "-"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m server.keys", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default=os.environ.get("NEXUS_SERVER_URL", ""))
    parser.add_argument("--token", default=os.environ.get("NEXUS_ADMIN_TOKEN", ""))
    sub = parser.add_subparsers(dest="cmd", required=True)
    create = sub.add_parser("create")
    create.add_argument("label", nargs="?", default="")
    create.add_argument("-n", "--count", type=int, default=1)
    create.add_argument("--days", type=int, default=0, help="days until an unused key expires (0 = never)")
    listing = sub.add_parser("list")
    listing.add_argument("--status", default="")
    for name in ("revoke", "activate", "unbind", "delete"):
        sub.add_parser(name).add_argument("id", type=int)
    args = parser.parse_args(argv)
    if not args.url or not args.token:
        parser.error("server address and admin token are required (--url/--token or NEXUS_SERVER_URL/NEXUS_ADMIN_TOKEN)")

    if args.cmd == "create":
        for key in call(args.url, args.token, "POST", "/admin/keys", {"label": args.label, "count": args.count, "expires_days": args.days})["keys"]:
            print(f"#{key['id']:<4} {key['key']}   {key['label']}")
        print("Save these now: the full keys cannot be shown again.")
    elif args.cmd == "list":
        query = "?status=" + urllib.parse.quote(args.status) if args.status else ""
        keys = call(args.url, args.token, "GET", "/admin/keys" + query)["keys"]
        print(f"{'ID':<5}{'KEY':<24}{'STATUS':<9}{'USED BY':<20}{'CREATED':<12}{'EXPIRES':<12}LABEL")
        for k in keys:
            print(f"{k['id']:<5}{k['key']:<24}{k['status']:<9}{(k['user'] or '-'):<20}{stamp(k['created_at']):<12}{stamp(k.get('expires_at')):<12}{k['label']}")
        print(f"{len(keys)} keys")
    elif args.cmd == "delete":
        result = call(args.url, args.token, "DELETE", f"/admin/keys/{args.id}")
        print(f"key #{result['id']} deleted")
    else:
        result = call(args.url, args.token, "POST", f"/admin/keys/{args.id}/{args.cmd}")
        print(f"key #{result['id']} is now {result['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
