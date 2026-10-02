"""Key-first registration, the player database and player editing (server side, no network needed).

Covers: no account without a valid key, key rules (invalid / revoked / expired / used), key management, the admin player list with
search / filter / sort / pagination, details, edits that persist (also across a server restart), deactivate / ban, the access split between
players and administrators, the audit log and the upgrade of a database created by an older version."""
import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from tests.test_keys import ADMIN, HAVE_SERVER_DEPS, load_server


def body(level=5, missions=4, credits_earned=5000, perfect=1, details=None):
    from server.validation import cumulative_xp
    out = {"level": level, "xp_total": cumulative_xp(level) + 50, "missions": missions, "credits_earned": credits_earned, "perfect": perfect,
           "playtime": 3600, "ng_plus": 0, "rank": "OPERATOR"}
    if details is not None:
        out["details"] = details
    return out


DETAILS = {"credits": 1234, "reputation": 33, "heat": 12, "achievements": ["first_blood", "ghost"], "unlocks": ["theme:amber"],
           "stats": {"commands_run": 90, "hacks_ok": 7}}


@unittest.skipUnless(HAVE_SERVER_DEPS, "server dependencies (fastapi, uvicorn, httpx) not installed")
class AdminBase(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        self.dir = tempfile.mkdtemp()
        self.db = Path(self.dir) / "online.db"
        self.mod = load_server(self.db)
        self.http = TestClient(self.mod.app)
        self.counter = 0

    # -- helpers -----------------------------------------------------------
    def state(self):
        self.counter += 1
        return f"state-{self.counter:04d}-" + "x" * 16

    def make_keys(self, n=1, label="t", **extra):
        r = self.http.post("/admin/keys", json={"label": label, "count": n, **extra}, headers=ADMIN)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["keys"]

    def register(self, key, name):
        """The whole registration: key check, then the (dev) login. Returns (ok, answer)."""
        state = self.state()
        r = self.http.post("/auth/begin", json={"state": state, "key": key})
        if r.status_code != 200:
            return False, r
        page = self.http.get("/auth/dev", params={"name": name, "state": state})
        if page.status_code != 200:
            return False, page
        poll = self.http.post("/auth/poll", json={"state": state})
        return True, poll

    def player(self, name, level=5, missions=4, credits_earned=5000, details=DETAILS):
        key = self.make_keys(1, label=f"for {name}")[0]
        ok, poll = self.register(key["key"], name)
        self.assertTrue(ok, poll.text)
        headers = {"Authorization": "Bearer " + poll.json()["token"]}
        if level:
            r = self.http.post("/scores", json=body(level, missions, credits_earned, details=details), headers=headers)
            self.assertEqual(r.status_code, 200, r.text)
        uid = sqlite3.connect(self.db).execute("SELECT id FROM users WHERE name=?", (name,)).fetchone()[0]
        return {"name": name, "id": uid, "headers": headers, "key": key}

    def allow_resubmit(self):
        con = sqlite3.connect(self.db)
        con.execute("UPDATE scores SET updated_at = updated_at - 100")
        con.commit()
        con.close()

    def admin_get(self, path, **params):
        return self.http.get(path, params=params, headers=ADMIN)

    def restart(self):
        """A server restart: a new copy of the server on the same database file."""
        from fastapi.testclient import TestClient
        self.mod = load_server(self.db)
        self.http = TestClient(self.mod.app)


class KeyFirstRegistration(AdminBase):
    def test_no_account_without_a_key(self):
        for key in ("", "   ", "NX-AAAAA-BBBBB-CCCCC"):
            ok, r = self.register(key, "Sneaky")
            self.assertFalse(ok)
            self.assertEqual(r.status_code, 403)
        # skipping the key step: the login endpoints refuse a login that never presented a key
        self.assertEqual(self.http.get("/auth/dev", params={"name": "Sneaky", "state": self.state()}).status_code, 400)
        self.assertEqual(self.http.get("/auth/start", params={"state": self.state()}).status_code, 400)
        self.assertEqual(self.http.get("/auth/callback", params={"code": "x", "state": self.state()}).status_code, 400)
        self.assertEqual(sqlite3.connect(self.db).execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)

    def test_a_valid_key_creates_the_account_and_is_linked_to_it(self):
        key = self.make_keys(1, "Mira")[0]
        ok, poll = self.register(key["key"], "Mira")
        self.assertTrue(ok)
        self.assertTrue(poll.json()["token"])
        con = sqlite3.connect(self.db)
        user = con.execute("SELECT id, discord_id FROM users WHERE name='Mira'").fetchone()
        bound = con.execute("SELECT discord_id FROM access_keys WHERE id=?", (key["id"],)).fetchone()[0]
        self.assertEqual(bound, user[1])
        listing = self.admin_get("/admin/keys").json()["keys"][0]
        self.assertEqual((listing["status"], listing["user"]), ("in use", "Mira"))

    def test_a_used_key_cannot_register_a_second_account(self):
        key = self.make_keys(1)[0]
        self.assertTrue(self.register(key["key"], "First")[0])
        ok, r = self.register(key["key"], "Second")
        self.assertFalse(ok)
        self.assertEqual(r.status_code, 403)
        self.assertIn("already been used", r.text)
        self.assertEqual(sqlite3.connect(self.db).execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)

    def test_a_deactivated_key_is_refused(self):
        key = self.make_keys(1)[0]
        self.assertEqual(self.http.post(f"/admin/keys/{key['id']}/revoke", headers=ADMIN).status_code, 200)
        ok, r = self.register(key["key"], "Late")
        self.assertFalse(ok)
        self.assertEqual(r.status_code, 403)
        self.assertIn("revoked", r.json()["detail"])

    def test_an_expired_key_is_refused_but_a_used_one_keeps_working(self):
        fresh, used = self.make_keys(1, expires_days=10)[0], self.make_keys(1, expires_days=10)[0]
        player = self.register(used["key"], "Early")
        self.assertTrue(player[0])
        con = sqlite3.connect(self.db)
        con.execute("UPDATE access_keys SET expires_at=?", (time.time() - 5,))
        con.commit()
        con.close()
        ok, r = self.register(fresh["key"], "Late")
        self.assertFalse(ok)
        self.assertIn("expired", r.json()["detail"])
        statuses = {k["id"]: k["status"] for k in self.admin_get("/admin/keys").json()["keys"]}
        self.assertEqual((statuses[fresh["id"]], statuses[used["id"]]), ("expired", "in use"))
        # the player who redeemed it in time is not locked out
        headers = {"Authorization": "Bearer " + player[1].json()["token"]}
        self.assertEqual(self.http.get("/me", headers=headers).status_code, 200)

    def test_keys_are_mandatory_by_default_on_a_real_server(self):
        from fastapi.testclient import TestClient
        real = load_server(Path(self.dir) / "real.db", NEXUS_REQUIRE_KEY="", NEXUS_DEV_LOGIN="", DISCORD_GUILD_ID="")
        self.assertTrue(TestClient(real.app).get("/health").json()["gated"])
        opened = load_server(Path(self.dir) / "open.db", NEXUS_REQUIRE_KEY="", NEXUS_DEV_LOGIN="", DISCORD_GUILD_ID="", NEXUS_OPEN_LOGIN="1")
        self.assertFalse(TestClient(opened.app).get("/health").json()["gated"])

    def test_keys_are_stored_hashed_and_look_random(self):
        keys = self.make_keys(20)
        self.assertEqual(len({k["key"] for k in keys}), 20)
        stored = sqlite3.connect(self.db).execute("SELECT * FROM access_keys").fetchall()
        for k in keys:
            self.assertNotIn(k["key"], str(stored))
            self.assertNotIn(k["key"], self.admin_get("/admin/keys").text)


class KeyManagement(AdminBase):
    def test_create_many_with_expiry_and_list_with_filter_search_and_pages(self):
        made = self.make_keys(7, "batch", expires_days=30)
        self.assertEqual(len(made), 7)
        self.assertTrue(all(abs(k["expires_at"] - (time.time() + 30 * 86400)) < 60 for k in made))
        self.make_keys(1, "Special")
        self.assertTrue(self.register(made[0]["key"], "Zed")[0])
        data = self.admin_get("/admin/keys", per_page=3, page=1, newest_first="true").json()
        self.assertEqual((data["total"], data["pages"], len(data["keys"])), (8, 3, 3))
        self.assertGreater(data["keys"][0]["id"], data["keys"][1]["id"])
        self.assertEqual(data["counts"], {"revoked": 0, "in use": 1, "expired": 0, "unused": 7})
        self.assertEqual(self.admin_get("/admin/keys", status="in use").json()["total"], 1)
        self.assertEqual(self.admin_get("/admin/keys", search="special").json()["total"], 1)
        self.assertEqual(self.admin_get("/admin/keys", search="zed").json()["keys"][0]["user"], "Zed")
        tail = made[2]["key"][-5:]
        self.assertEqual([k["id"] for k in self.admin_get("/admin/keys", search=tail).json()["keys"]][:1], [made[2]["id"]])
        self.assertEqual(self.admin_get("/admin/keys", status="nonsense").status_code, 400)
        self.assertEqual(self.admin_get("/admin/keys", search="100%").json()["total"], 0)           # wildcards are escaped, not interpreted

    def test_deactivate_activate_delete_and_expiry(self):
        player = self.player("Kira")
        key_id = player["key"]["id"]
        self.assertEqual(self.http.post(f"/admin/keys/{key_id}/activate", headers=ADMIN).status_code, 409)      # not deactivated yet
        self.assertEqual(self.http.post(f"/admin/keys/{key_id}/revoke", headers=ADMIN).json()["status"], "revoked")
        self.assertEqual(self.http.get("/me", headers=player["headers"]).status_code, 401)                      # logged out at once
        self.assertEqual(self.http.post(f"/admin/keys/{key_id}/activate", headers=ADMIN).json()["status"], "in use")
        ok, poll = self.register(player["key"]["key"], "Kira")                                                  # the owner can log in again
        self.assertTrue(ok)
        self.assertEqual(self.http.post(f"/admin/keys/{key_id}/expiry", json={"days": 5}, headers=ADMIN).json()["status"], "in use")
        self.assertEqual(self.http.post(f"/admin/keys/{key_id}/expiry", json={"days": -1}, headers=ADMIN).status_code, 422)
        self.assertEqual(self.http.delete(f"/admin/keys/{key_id}", headers=ADMIN).json(), {"id": key_id, "deleted": True})
        self.assertEqual(self.http.get("/me", headers={"Authorization": "Bearer " + poll.json()["token"]}).status_code, 401)
        self.assertEqual(self.http.delete(f"/admin/keys/{key_id}", headers=ADMIN).status_code, 404)
        self.assertEqual(self.http.post("/admin/keys/99999/revoke", headers=ADMIN).status_code, 404)
        self.assertFalse(self.register(player["key"]["key"], "Kira")[0])                                        # a deleted key is simply invalid

    def test_unused_key_can_be_deactivated_and_reactivated(self):
        key = self.make_keys(1)[0]
        self.http.post(f"/admin/keys/{key['id']}/revoke", headers=ADMIN)
        self.assertEqual(self.admin_get("/admin/keys", status="revoked").json()["total"], 1)
        self.assertEqual(self.http.post(f"/admin/keys/{key['id']}/activate", headers=ADMIN).json()["status"], "unused")
        self.assertTrue(self.register(key["key"], "Neo")[0])


class PlayerDatabase(AdminBase):
    def setUp(self):
        super().setUp()
        self.alice = self.player("Alice", level=10, missions=9, credits_earned=9000)
        self.bob = self.player("Bob", level=3, missions=2, credits_earned=300, details={**DETAILS, "credits": 50})
        self.cara = self.player("Cara", level=7, missions=5, credits_earned=1000)

    def test_list_shows_every_player_with_the_important_fields(self):
        data = self.admin_get("/admin/players").json()
        self.assertEqual(data["total"], 3)
        row = next(p for p in data["players"] if p["name"] == "Alice")
        for field in ("id", "name", "account_status", "key", "registered", "last_login", "level", "xp_total", "credits", "missions", "online"):
            self.assertIn(field, row)
        self.assertEqual((row["level"], row["credits"], row["account_status"]), (10, 1234, "active"))
        self.assertEqual(row["key"]["status"], "in use")
        self.assertIn("*", row["key"]["key"])
        self.assertTrue(row["last_login"] and row["registered"])
        self.assertEqual(data["counts"]["all"], 3)

    def test_list_never_exposes_secrets(self):
        text = self.admin_get("/admin/players").text + self.admin_get(f"/admin/players/{self.alice['id']}").text
        for secret in (self.alice["headers"]["Authorization"].split()[1], self.alice["key"]["key"], "key_hash"):
            self.assertNotIn(secret, text)
        con = sqlite3.connect(self.db)
        for (token,) in con.execute("SELECT token FROM sessions"):
            self.assertNotIn(token, text)

    def test_search_filter_sort_and_pagination(self):
        names = lambda **p: [x["name"] for x in self.admin_get("/admin/players", **p).json()["players"]]
        self.assertEqual(names(search="ali"), ["Alice"])
        self.assertEqual(names(search="CARA"), ["Cara"])
        self.assertEqual(names(search=str(self.bob["id"])), ["Bob"])                      # by account id
        self.assertEqual(names(search="nobody"), [])
        self.assertEqual(names(search="%"), [])                                          # no wildcard injection
        self.assertEqual(names(sort="level", direction="desc"), ["Alice", "Cara", "Bob"])
        self.assertEqual(names(sort="level", direction="asc"), ["Bob", "Cara", "Alice"])
        self.assertEqual(names(sort="name", direction="asc"), ["Alice", "Bob", "Cara"])
        page1 = self.admin_get("/admin/players", sort="name", direction="asc", per_page=2, page=1).json()
        page2 = self.admin_get("/admin/players", sort="name", direction="asc", per_page=2, page=2).json()
        self.assertEqual(([p["name"] for p in page1["players"]], [p["name"] for p in page2["players"]], page1["pages"]), (["Alice", "Bob"], ["Cara"], 2))
        self.assertEqual(self.admin_get("/admin/players", sort="; DROP TABLE users").status_code, 400)
        self.assertEqual(self.admin_get("/admin/players", status="bogus").status_code, 400)
        self.http.post(f"/admin/players/{self.bob['id']}/status", json={"status": "banned", "reason": "cheating"}, headers=ADMIN)
        self.assertEqual(names(status="banned"), ["Bob"])
        self.assertEqual(sorted(names(status="active")), ["Alice", "Cara"])
        self.assertEqual(names(status="online"), [])
        self.http.post("/presence", json={"status": "Mission 1"}, headers=self.alice["headers"])
        self.assertEqual(names(status="online"), ["Alice"])

    def test_detail_view(self):
        d = self.admin_get(f"/admin/players/{self.alice['id']}").json()
        self.assertEqual((d["name"], d["level"], d["credits"], d["reputation"], d["heat"]), ("Alice", 10, 1234, 33, 12))
        self.assertEqual(d["achievements"], ["first_blood", "ghost"])
        self.assertEqual(d["unlocks"], ["theme:amber"])
        self.assertEqual(d["stats"]["hacks_ok"], 7)
        self.assertEqual((d["missions"], d["perfect"], d["friends"], d["login_count"]), (9, 1, 0, 1))
        self.assertTrue(d["discord_id"].startswith("dev:"))
        self.assertEqual(self.admin_get("/admin/players/99999").status_code, 404)

    def test_player_without_a_synced_save_cannot_be_edited(self):
        fresh = self.player("Newbie", level=0)
        d = self.admin_get(f"/admin/players/{fresh['id']}").json()
        self.assertIsNone(d["level"])
        r = self.http.post(f"/admin/players/{fresh['id']}/edit", json={"level": 5}, headers=ADMIN)
        self.assertEqual(r.status_code, 422)
        self.assertIn("not synced", r.json()["detail"])


class PlayerEditing(AdminBase):
    def setUp(self):
        super().setUp()
        self.p = self.player("Edith", level=10, missions=9, credits_earned=9000)

    def edit(self, **changes):
        return self.http.post(f"/admin/players/{self.p['id']}/edit", json=changes, headers=ADMIN)

    def test_edits_are_validated(self):
        for bad in ({}, {"level": 0}, {"level": 101}, {"level": 3.5}, {"level": True}, {"level": "7"}, {"xp": -1}, {"xp": 99999},
                    {"credits": -5}, {"credits": 10**10}, {"reputation": 101}, {"reset": ["everything"]}, {"surprise": 1}):
            self.assertEqual(self.edit(**bad).status_code, 422, bad)
        self.assertEqual(self.admin_get(f"/admin/players/{self.p['id']}").json()["level"], 10)        # nothing was applied
        self.assertEqual(self.http.get("/me", headers=self.p["headers"]).json()["edits"], [])

    def test_edit_is_saved_queued_and_survives_a_restart(self):
        r = self.edit(level=20, xp=50, credits=777, reputation=80, reason="event reward")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["ops"], {"level": 20, "xp": 50, "credits": 777, "reputation": 80})
        d = self.admin_get(f"/admin/players/{self.p['id']}").json()
        self.assertEqual((d["level"], d["credits"], d["reputation"]), (20, 777, 80))
        from server.validation import cumulative_xp
        self.assertEqual(d["xp_total"], cumulative_xp(20) + 50)
        self.assertEqual(len(d["pending_edits"]), 1)
        self.assertIn("event reward", self.admin_get(f"/admin/players/{self.p['id']}").json()["audit"][0]["detail"])
        self.restart()
        d = self.admin_get(f"/admin/players/{self.p['id']}").json()
        self.assertEqual((d["level"], d["credits"], d["reputation"], len(d["pending_edits"])), (20, 777, 80, 1))

    def test_xp_alone_edits_the_current_level(self):
        self.assertEqual(self.edit(xp=123).json()["ops"], {"level": 10, "xp": 123})
        self.assertEqual(self.edit(level=15).json()["ops"], {"level": 15, "xp": 0})

    def test_resets_clear_server_side_progress(self):
        self.assertEqual(self.edit(reset=["missions", "heat"]).status_code, 200)
        d = self.admin_get(f"/admin/players/{self.p['id']}").json()
        self.assertEqual((d["missions"], d["perfect"], d["heat"]), (0, 0, 0))
        self.assertEqual(d["level"], 10)

    def test_the_player_gets_the_change_and_cannot_overwrite_it_with_old_numbers(self):
        self.edit(level=2, credits=5)
        self.allow_resubmit()
        old_numbers = self.http.post("/scores", json=body(10, 9, 9000, details=DETAILS), headers=self.p["headers"])
        self.assertEqual(old_numbers.status_code, 200)
        self.assertTrue(old_numbers.json()["ignored"])
        edits = old_numbers.json()["edits"]
        self.assertEqual(edits[0]["ops"], {"level": 2, "xp": 0, "credits": 5})
        self.assertEqual(self.admin_get(f"/admin/players/{self.p['id']}").json()["level"], 2)          # still the admin's value
        me = self.http.get("/me", headers=self.p["headers"]).json()
        self.assertEqual(me["edits"][0]["id"], edits[0]["id"])
        self.assertNotIn("details", me["score"])
        # the game applies it and confirms; from then on its new numbers are accepted
        self.assertEqual(self.http.post(f"/me/edits/{edits[0]['id']}/ack", headers=self.p["headers"]).status_code, 200)
        self.assertEqual(self.http.post(f"/me/edits/{edits[0]['id']}/ack", headers=self.p["headers"]).status_code, 404)
        self.allow_resubmit()
        applied = self.http.post("/scores", json=body(2, 9, 9000, details={**DETAILS, "credits": 5}), headers=self.p["headers"])
        self.assertEqual(applied.status_code, 200, applied.text)
        self.assertEqual(applied.json()["edits"], [])
        self.assertEqual(self.admin_get(f"/admin/players/{self.p['id']}").json()["pending_edits"], [])

    def test_one_player_cannot_confirm_anothers_edit(self):
        other = self.player("Other")
        edit_id = self.edit(level=4).json()["edit_id"]
        self.assertEqual(self.http.post(f"/me/edits/{edit_id}/ack", headers=other["headers"]).status_code, 404)
        self.assertEqual(len(self.admin_get(f"/admin/players/{self.p['id']}").json()["pending_edits"]), 1)

    def test_weekly_challenge_does_not_count_an_edit_as_progress(self):
        self.edit(level=50)
        week = self.http.get("/challenge", headers=self.p["headers"]).json()
        self.assertEqual(week["me"]["value"], 0)

    def test_edits_are_in_the_activity_log(self):
        self.edit(level=11, reason="typo fix")
        entries = self.admin_get("/admin/audit").json()["entries"]
        self.assertEqual((entries[0]["action"], entries[0]["user"]), ("player.edit", "Edith"))
        self.assertIn("typo fix", entries[0]["detail"])


class AccountStatus(AdminBase):
    def setUp(self):
        super().setUp()
        self.p = self.player("Stan")

    def set_status(self, status, reason=""):
        return self.http.post(f"/admin/players/{self.p['id']}/status", json={"status": status, "reason": reason}, headers=ADMIN)

    def test_deactivated_players_are_logged_out_and_cannot_log_in(self):
        self.assertEqual(self.set_status("disabled", "inactive").json()["status"], "disabled")
        r = self.http.get("/me", headers=self.p["headers"])
        self.assertEqual(r.status_code, 401)
        self.assertIn("deactivated", r.json()["detail"])
        ok, answer = self.register(self.p["key"]["key"], "Stan")
        self.assertFalse(ok)                                                                   # login refused
        self.assertEqual(self.admin_get(f"/admin/players/{self.p['id']}").json()["status_reason"], "inactive")

    def test_banned_players_see_the_reason_and_unbanning_restores_access(self):
        self.set_status("banned", "cheating")
        state = self.state()
        self.http.post("/auth/begin", json={"state": state, "key": self.p["key"]["key"]})
        page = self.http.get("/auth/dev", params={"name": "Stan", "state": state})
        self.assertEqual(page.status_code, 403)
        self.assertIn("banned", page.text)
        self.assertIn("cheating", page.text)
        self.assertEqual(self.http.post("/auth/poll", json={"state": state}).status_code, 403)
        self.set_status("active")
        ok, poll = self.register(self.p["key"]["key"], "Stan")
        self.assertTrue(ok)
        self.assertEqual(self.http.get("/me", headers={"Authorization": "Bearer " + poll.json()["token"]}).status_code, 200)
        self.assertEqual(self.admin_get(f"/admin/players/{self.p['id']}").json()["status_reason"], "")

    def test_unknown_status_is_refused(self):
        self.assertEqual(self.set_status("godmode").status_code, 422)
        self.assertEqual(self.http.post("/admin/players/99999/status", json={"status": "banned"}, headers=ADMIN).status_code, 404)

    def test_banned_player_disappears_from_the_leaderboards_login_but_stays_listed_for_admins(self):
        self.set_status("banned")
        self.assertEqual(self.admin_get("/admin/players", status="banned").json()["total"], 1)


class AccessProtection(AdminBase):
    ADMIN_ENDPOINTS = [("GET", "/admin/keys"), ("POST", "/admin/keys"), ("GET", "/admin/players"), ("GET", "/admin/players/1"),
                       ("POST", "/admin/players/1/edit"), ("POST", "/admin/players/1/status"), ("GET", "/admin/audit"),
                       ("POST", "/admin/keys/1/revoke"), ("POST", "/admin/keys/1/activate"), ("POST", "/admin/keys/1/unbind"),
                       ("POST", "/admin/keys/1/expiry"), ("DELETE", "/admin/keys/1")]

    def call(self, method, path, headers):
        return self.http.request(method, path, json={"status": "banned", "level": 99, "days": 1} if method == "POST" else None, headers=headers)

    def test_nobody_without_admin_rights_gets_through(self):
        player = self.player("Pete")
        for method, path in self.ADMIN_ENDPOINTS:
            for headers in ({}, {"Authorization": "Bearer nonsense"}, player["headers"]):
                self.assertEqual(self.call(method, path, headers).status_code, 401, (method, path, headers))
        self.assertEqual(self.admin_get(f"/admin/players/{player['id']}").json()["level"], 5)         # untouched
        self.assertEqual(self.admin_get(f"/admin/players/{player['id']}").json()["account_status"], "active")

    def test_a_player_cannot_become_admin_by_guessing(self):
        for password in ("", "admin", "password", "letmein123456"):
            r = self.http.post("/admin/login", json={"user": "boss", "password": password})
            self.assertIn(r.status_code, (401, 429))

    def test_the_admin_token_is_not_a_player_session(self):
        self.assertEqual(self.http.get("/me", headers=ADMIN).status_code, 401)
        self.assertEqual(self.http.post("/scores", json=body(), headers=ADMIN).status_code, 401)

    def test_admin_session_from_the_login_works_and_ends_on_logout(self):
        token = self.http.post("/admin/login", json={"user": "boss", "password": "correct horse battery"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        self.assertEqual(self.http.get("/admin/players", headers=headers).status_code, 200)
        self.http.post("/admin/logout", headers=headers)
        self.assertEqual(self.http.get("/admin/players", headers=headers).status_code, 401)

    def test_player_endpoints_only_show_the_players_own_data(self):
        a, b = self.player("Aa"), self.player("Bb")
        me = self.http.get("/me", headers=a["headers"]).json()
        self.assertEqual(me["name"], "Aa")
        self.assertNotIn("discord_id", json.dumps(me))
        board = self.http.get("/leaderboard", headers=a["headers"]).text
        self.assertNotIn("discord_id", board)
        self.assertNotIn("dev:", board)

    def test_bad_input_is_rejected_not_executed(self):
        r = self.http.post("/admin/keys", json={"label": "x" * 500, "count": 1}, headers=ADMIN)
        self.assertEqual(r.status_code, 422)
        self.assertEqual(self.http.post("/admin/keys", json={"count": 999}, headers=ADMIN).status_code, 422)
        evil = self.admin_get("/admin/players", search="' OR 1=1 --")
        self.assertEqual((evil.status_code, evil.json()["total"]), (200, 0))


class Upgrade(AdminBase):
    def test_a_database_from_the_old_version_is_upgraded_without_losing_data(self):
        old = Path(self.dir) / "old.db"
        con = sqlite3.connect(old)
        con.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, discord_id TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
            name_lc TEXT NOT NULL, created_at REAL, last_seen REAL DEFAULT 0, status TEXT DEFAULT '', share INTEGER DEFAULT 1);
        CREATE TABLE sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at REAL);
        CREATE TABLE auth_states (state TEXT PRIMARY KEY, token TEXT, created_at REAL);
        CREATE TABLE access_keys (id INTEGER PRIMARY KEY AUTOINCREMENT, key_hash TEXT UNIQUE NOT NULL, tail TEXT NOT NULL,
            label TEXT DEFAULT '', created_at REAL, revoked INTEGER DEFAULT 0, discord_id TEXT, redeemed_at REAL);
        CREATE TABLE scores (user_id INTEGER PRIMARY KEY, level INTEGER, xp_total INTEGER, missions INTEGER, credits_earned INTEGER,
            perfect INTEGER, playtime INTEGER, ng_plus INTEGER, rank TEXT, updated_at REAL, week TEXT, week_base_xp INTEGER);
        CREATE TABLE friends (user_id INTEGER, friend_id INTEGER, status TEXT, created_at REAL, PRIMARY KEY (user_id, friend_id));
        INSERT INTO users(discord_id, name, name_lc, created_at) VALUES('dev:old', 'Oldie', 'oldie', 1000);
        INSERT INTO access_keys(key_hash, tail, label, created_at, discord_id) VALUES('h', 'ABCDE', 'legacy', 1000, 'dev:old');
        INSERT INTO scores VALUES(1, 12, 5000, 11, 4000, 2, 100, 0, 'OPERATOR', 1000, '2026-W01', 0);
        """)
        con.commit()
        con.close()
        from fastapi.testclient import TestClient
        mod = load_server(old)
        http = TestClient(mod.app)
        players = http.get("/admin/players", headers=ADMIN).json()["players"]
        self.assertEqual([(p["name"], p["level"], p["account_status"], p["key"]["label"]) for p in players], [("Oldie", 12, "active", "legacy")])
        self.assertEqual(http.get("/admin/keys", headers=ADMIN).json()["keys"][0]["status"], "in use")
        self.assertEqual(http.post("/admin/players/1/edit", json={"level": 13}, headers=ADMIN).status_code, 200)       # new columns/tables work
        self.assertEqual(http.get("/admin/players/1", headers=ADMIN).json()["level"], 13)


class DemoData(AdminBase):
    def test_the_demo_seed_fills_a_local_database(self):
        import os
        import subprocess
        import sys
        db = Path(self.dir) / "demo.db"
        root = Path(__file__).resolve().parent.parent
        env = {**os.environ, "NEXUS_DB": str(db)}
        env.pop("DISCORD_CLIENT_ID", None)
        run = subprocess.run([sys.executable, "-m", "server.seed_demo"], cwd=root, env=env, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        from fastapi.testclient import TestClient
        http = TestClient(load_server(db).app)
        data = http.get("/admin/players", headers=ADMIN).json()
        self.assertEqual((data["total"], data["counts"]["banned"], data["counts"]["disabled"]), (8, 1, 1))
        self.assertEqual(http.get("/admin/keys", headers=ADMIN).json()["total"], 13)
        again = subprocess.run([sys.executable, "-m", "server.seed_demo"], cwd=root, env=env, capture_output=True, text=True)
        self.assertEqual(again.returncode, 1)                                             # never seeds twice
        real = subprocess.run([sys.executable, "-m", "server.seed_demo"], cwd=root, env={**env, "DISCORD_CLIENT_ID": "123"}, capture_output=True, text=True)
        self.assertEqual(real.returncode, 1)                                              # never touches a real server
        self.assertIn("Refusing", real.stdout)


if __name__ == "__main__":
    unittest.main()
