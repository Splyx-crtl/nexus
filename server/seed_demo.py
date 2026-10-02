"""Fills a LOCAL test database with demo players and keys, so the admin panel can be tried out.

    set NEXUS_DB=demo.db
    python -m server.seed_demo
    set NEXUS_DEV_LOGIN=1  &  python -m uvicorn server.app:app --port 8000     (admin: set NEXUS_ADMIN_USER / NEXUS_ADMIN_PASSWORD)

It writes straight into the database file and refuses to run when the Discord application is configured, so it can never
put fake players into a real server by accident.
"""
from __future__ import annotations

import json
import os
import sys
import time

DEMO = [  # name, level, credits, missions, status
    ("Mira", 12, 5200, 11, "active"), ("Zoe", 4, 300, 3, "active"), ("Kai", 20, 99000, 24, "active"), ("Lena", 7, 1200, 6, "active"),
    ("Omar", 15, 8000, 17, "disabled"), ("Pia", 2, 50, 1, "active"), ("Rex", 31, 250000, 40, "banned"), ("Nova", 9, 2400, 8, "active"),
]


def main() -> int:
    if os.environ.get("DISCORD_CLIENT_ID"):
        print("Refusing to seed a server that has a Discord application configured (that would be a real server).")
        return 1
    if not os.environ.get("NEXUS_DB"):
        print("Set NEXUS_DB to the demo database file first (for example: set NEXUS_DB=demo.db).")
        return 1
    from . import app as server
    from .validation import cumulative_xp

    now = time.time()
    with server.db() as conn:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            print("This database already has players. Use a fresh file.")
            return 1
        for i, (name, level, credits, missions, status) in enumerate(DEMO):
            discord_id = f"demo:{name.lower()}"
            created = now - (len(DEMO) - i) * 86400
            uid = conn.execute("INSERT INTO users(discord_id, name, name_lc, created_at, last_login, login_count, account_status, status_reason) VALUES(?,?,?,?,?,?,?,?)",
                               (discord_id, name, name.lower(), created, now - i * 3600, 1 + i, status, "demo" if status != "active" else "")).lastrowid
            key = server.new_key()
            conn.execute("INSERT INTO access_keys(key_hash, tail, label, created_at, discord_id, redeemed_at) VALUES(?,?,?,?,?,?)",
                         (server.hash_key(key), key[-5:], f"demo {name}", created, discord_id, created))
            details = {"credits": credits, "reputation": 10 + level, "heat": i * 3, "achievements": ["first_blood"] * 0 + [f"ach_{n}" for n in range(level // 3)],
                       "unlocks": ["theme:amber"] if level > 8 else [], "stats": {"commands_run": level * 40, "hacks_ok": missions * 2}}
            conn.execute("INSERT INTO scores(user_id, level, xp_total, missions, credits_earned, perfect, playtime, ng_plus, rank, updated_at, week, week_base_xp, details) "
                         "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (uid, level, cumulative_xp(level) + 40, missions, credits * 2, missions // 3, level * 1800, 0,
                                                                "OPERATOR", now - i * 600, server.week_key(), 0, json.dumps(details)))
        for n in range(5):
            key = server.new_key()
            conn.execute("INSERT INTO access_keys(key_hash, tail, label, created_at, expires_at) VALUES(?,?,?,?,?)",
                         (server.hash_key(key), key[-5:], "unused demo key", now, now + 30 * 86400 if n % 2 else None))
    print(f"Seeded {len(DEMO)} demo players and {len(DEMO) + 5} keys into {os.environ['NEXUS_DB']}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
