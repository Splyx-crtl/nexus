"""Invite-only login: Discord server membership + role + admin-issued access keys (server side, no network needed)."""
import contextlib
import importlib.util
import io
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

HAVE_SERVER_DEPS = all(importlib.util.find_spec(m) for m in ("fastapi", "uvicorn", "httpx"))
ROOT = Path(__file__).resolve().parent.parent
ADMIN = {"Authorization": "Bearer admin-token-for-tests"}
ADMIN_USER, ADMIN_PASSWORD = "boss", "correct horse battery"
ENV = {"NEXUS_ADMIN_USER": ADMIN_USER, "NEXUS_ADMIN_PASSWORD": ADMIN_PASSWORD, "NEXUS_DEV_LOGIN": "1", "NEXUS_REQUIRE_KEY": "1", "NEXUS_ADMIN_TOKEN": "admin-token-for-tests", "DISCORD_GUILD_ID": "1000",
       "DISCORD_ROLE_ID": "777", "DISCORD_CLIENT_ID": "cid", "DISCORD_CLIENT_SECRET": "secret", "PUBLIC_URL": "https://nexus.test"}


def load_server(db_path, **env):
    """Import a private copy of server/app.py with its own configuration (it reads the environment at import time)."""
    saved = {k: os.environ.get(k) for k in [*ENV, "NEXUS_DB"]}
    os.environ.update({**ENV, **env, "NEXUS_DB": str(db_path)})
    for key in [k for k in ENV if k in env and env[k] is None]:
        os.environ.pop(key, None)
    try:
        spec = importlib.util.spec_from_file_location("server.app_keys_test", ROOT / "server" / "app.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code, self._body = status, body or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("bad", request=None, response=None)

    def json(self):
        return self._body


def fake_discord(user_id="42", member_status=200, roles=("777",)):
    class Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, **kw):
            return FakeResponse(200, {"access_token": "tok"})

        def get(self, url, **kw):
            if url.endswith("/users/@me"):
                return FakeResponse(200, {"id": user_id, "username": "player" + user_id})
            if "/guilds/" in url:
                return FakeResponse(member_status, {"roles": list(roles)} if member_status == 200 else {})
            return FakeResponse(404)
    return Client


@unittest.skipUnless(HAVE_SERVER_DEPS, "server dependencies (fastapi, uvicorn, httpx) not installed")
class InviteOnlyLogin(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        self.dir = tempfile.mkdtemp()
        self.db = Path(self.dir) / "online.db"
        self.mod = load_server(self.db)
        self.http = TestClient(self.mod.app)
        self.counter = 0

    # -- helpers -----------------------------------------------------------
    def make_keys(self, n=1, label="t"):
        r = self.http.post("/admin/keys", json={"label": label, "count": n}, headers=ADMIN)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["keys"]

    def state(self):
        self.counter += 1
        return f"state-{self.counter:04d}-" + "x" * 16

    def begin(self, key, state=None):
        state = state or self.state()
        return state, self.http.post("/auth/begin", json={"state": state, "key": key})

    def dev_login(self, key, name):
        state, r = self.begin(key)
        self.assertEqual(r.status_code, 200, r.text)
        page = self.http.get("/auth/dev", params={"name": name, "state": state})
        return state, page

    def token(self, state):
        r = self.http.post("/auth/poll", json={"state": state})
        return r

    # -- tests -------------------------------------------------------------
    def test_health_reports_invite_only(self):
        self.assertTrue(self.http.get("/health").json()["gated"])

    def test_login_needs_a_valid_key(self):
        self.assertEqual(self.begin("")[1].status_code, 403)
        r = self.begin("NX-AAAAA-BBBBB-CCCCC")[1]
        self.assertEqual(r.status_code, 403)
        self.assertIn("not valid", r.json()["detail"])

    def test_admin_api_is_protected(self):
        self.assertEqual(self.http.post("/admin/keys", json={}).status_code, 401)
        self.assertEqual(self.http.get("/admin/keys", headers={"Authorization": "Bearer nope"}).status_code, 401)
        self.assertEqual(self.http.get("/admin/keys", headers=ADMIN).status_code, 200)

    def test_admin_api_is_off_without_a_token(self):
        from fastapi.testclient import TestClient
        mod = load_server(Path(self.dir) / "other.db", NEXUS_ADMIN_TOKEN="", NEXUS_ADMIN_USER="")
        self.assertEqual(TestClient(mod.app).get("/admin/keys", headers=ADMIN).status_code, 404)

    def test_keys_look_right_and_are_stored_hashed(self):
        keys = self.make_keys(3)
        self.assertEqual(len({k["key"] for k in keys}), 3)
        for k in keys:
            self.assertRegex(k["key"], r"^NX-[A-Z2-9]{5}-[A-Z2-9]{5}-[A-Z2-9]{5}$")
        raw = sqlite3.connect(self.db).execute("SELECT key_hash FROM access_keys").fetchall()
        self.assertTrue(all(len(h[0]) == 64 for h in raw))
        self.assertNotIn(keys[0]["key"], str(sqlite3.connect(self.db).execute("SELECT * FROM access_keys").fetchall()))
        listing = self.http.get("/admin/keys", headers=ADMIN).json()["keys"]
        self.assertTrue(all(k["status"] == "unused" and "*" in k["key"] for k in listing))

    def test_full_login_with_a_key(self):
        key = self.make_keys()[0]["key"]
        state, page = self.dev_login(key, "Alice")
        self.assertEqual(page.status_code, 200)
        token = self.token(state).json()["token"]
        me = self.http.get("/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me.json()["name"], "Alice")
        listing = self.http.get("/admin/keys", headers=ADMIN).json()["keys"][0]
        self.assertEqual((listing["status"], listing["user"]), ("in use", "Alice"))

    def test_key_is_forgiving_about_typing(self):
        key = self.make_keys()[0]["key"]
        sloppy = key.lower().replace("-", " ")
        state, page = self.dev_login("  " + sloppy + " ", "Alice")
        self.assertEqual(page.status_code, 200)

    def test_same_account_can_log_in_again_with_the_same_key(self):
        key = self.make_keys()[0]["key"]
        self.dev_login(key, "Alice")
        state, page = self.dev_login(key, "Alice")
        self.assertEqual(page.status_code, 200)

    def test_a_key_cannot_be_shared(self):
        key = self.make_keys()[0]["key"]
        self.dev_login(key, "Alice")
        state, page = self.dev_login(key, "Bob")
        self.assertEqual(page.status_code, 403)
        r = self.token(state)
        self.assertEqual(r.status_code, 403)
        self.assertIn("another Discord account", r.json()["detail"])

    def test_one_account_cannot_collect_two_keys(self):
        a, b = (k["key"] for k in self.make_keys(2))
        self.dev_login(a, "Alice")
        state, page = self.dev_login(b, "Alice")
        self.assertEqual(page.status_code, 403)
        self.assertIn("already uses another key", self.token(state).json()["detail"])

    def test_revoking_a_key_logs_the_player_out_at_once(self):
        k = self.make_keys()[0]
        state, _ = self.dev_login(k["key"], "Alice")
        headers = {"Authorization": "Bearer " + self.token(state).json()["token"]}
        self.assertEqual(self.http.get("/me", headers=headers).status_code, 200)
        self.assertEqual(self.http.post(f"/admin/keys/{k['id']}/revoke", headers=ADMIN).status_code, 200)
        self.assertEqual(self.http.get("/me", headers=headers).status_code, 401)
        r = self.begin(k["key"])[1]
        self.assertEqual(r.status_code, 403)
        self.assertIn("revoked", r.json()["detail"])

    def test_unbinding_hands_the_key_to_someone_else(self):
        k = self.make_keys()[0]
        state, _ = self.dev_login(k["key"], "Alice")
        headers = {"Authorization": "Bearer " + self.token(state).json()["token"]}
        self.http.post(f"/admin/keys/{k['id']}/unbind", headers=ADMIN)
        self.assertEqual(self.http.get("/me", headers=headers).status_code, 401)
        state, page = self.dev_login(k["key"], "Bob")
        self.assertEqual(page.status_code, 200)

    def test_unknown_key_id_is_a_404(self):
        self.assertEqual(self.http.post("/admin/keys/999/revoke", headers=ADMIN).status_code, 404)
        self.assertEqual(self.http.post("/admin/keys/999/unbind", headers=ADMIN).status_code, 404)

    def test_old_clients_and_shortcuts_are_refused(self):
        r = self.http.get("/auth/start", params={"state": self.state()}, follow_redirects=False)
        self.assertEqual(r.status_code, 400)
        r = self.http.get("/auth/dev", params={"name": "Eve", "state": self.state()})
        self.assertEqual(r.status_code, 400)

    def test_oauth_redirect_asks_for_the_membership_scope(self):
        key = self.make_keys()[0]["key"]
        state, r = self.begin(key)
        go = self.http.get("/auth/start", params={"state": state}, follow_redirects=False)
        self.assertEqual(go.status_code, 307)
        self.assertIn("guilds.members.read", go.headers["location"])
        self.assertIn(state, go.headers["location"])

    def test_key_guessing_is_rate_limited(self):
        codes = [self.begin("NX-AAAAA-AAAAA-AAAAA")[1].status_code for _ in range(16)]
        self.assertIn(429, codes)

    def test_old_sessions_expire(self):
        key = self.make_keys()[0]["key"]
        state, _ = self.dev_login(key, "Alice")
        token = self.token(state).json()["token"]
        con = sqlite3.connect(self.db)
        con.execute("UPDATE sessions SET created_at=?", (time.time() - 40 * 86400,))
        con.commit()
        self.assertEqual(self.http.get("/me", headers={"Authorization": f"Bearer {token}"}).status_code, 401)

    # -- admin login (used by the panel inside the game) ---------------------
    def admin_login(self, user=ADMIN_USER, password=ADMIN_PASSWORD):
        return self.http.post("/admin/login", json={"user": user, "password": password})

    def test_admin_login_gives_a_working_session(self):
        r = self.admin_login()
        self.assertEqual(r.status_code, 200)
        headers = {"Authorization": "Bearer " + r.json()["token"]}
        self.assertEqual(self.http.post("/admin/keys", json={"label": "x"}, headers=headers).status_code, 200)
        self.assertEqual(self.http.get("/admin/keys", headers=headers).status_code, 200)

    def test_admin_login_rejects_wrong_credentials(self):
        self.assertEqual(self.admin_login(password="wrong password!!").status_code, 401)
        self.assertEqual(self.admin_login(user="nobody").status_code, 401)
        self.assertEqual(self.admin_login(user="", password="").status_code, 401)

    def test_admin_password_guessing_is_rate_limited(self):
        codes = [self.admin_login(password=f"guess number {i} here").status_code for i in range(9)]
        self.assertIn(429, codes)
        self.assertEqual(self.admin_login().status_code, 429)          # even the right password waits while locked

    def test_admin_logout_ends_the_session(self):
        headers = {"Authorization": "Bearer " + self.admin_login().json()["token"]}
        self.assertEqual(self.http.post("/admin/logout", headers=headers).status_code, 200)
        self.assertEqual(self.http.get("/admin/keys", headers=headers).status_code, 401)

    def test_admin_sessions_expire(self):
        token = self.admin_login().json()["token"]
        self.mod._admin_sessions[token] = time.time() - 1
        self.assertEqual(self.http.get("/admin/keys", headers={"Authorization": f"Bearer {token}"}).status_code, 401)

    def test_a_player_session_is_not_an_admin_session(self):
        key = self.make_keys()[0]["key"]
        state, _ = self.dev_login(key, "Alice")
        player = {"Authorization": "Bearer " + self.token(state).json()["token"]}
        self.assertEqual(self.http.get("/admin/keys", headers=player).status_code, 401)

    def test_admin_login_is_off_with_a_short_password_or_no_user(self):
        from fastapi.testclient import TestClient
        for env in ({"NEXUS_ADMIN_PASSWORD": "short"}, {"NEXUS_ADMIN_USER": ""}):
            mod = load_server(Path(self.dir) / f"x{len(env)}{list(env)[0]}.db", NEXUS_ADMIN_TOKEN="", **env)
            r = TestClient(mod.app).post("/admin/login", json={"user": ADMIN_USER, "password": ADMIN_PASSWORD})
            self.assertEqual(r.status_code, 404, env)
            self.assertFalse(TestClient(mod.app).get("/health").json()["admin"])

    def test_health_says_whether_an_admin_exists(self):
        self.assertTrue(self.http.get("/health").json()["admin"])

    # -- the Discord side (membership + role), with Discord's answers faked ----
    def discord_login(self, key, **discord):
        self.mod.httpx.Client = fake_discord(**discord)
        state, r = self.begin(key)
        self.assertEqual(r.status_code, 200, r.text)
        page = self.http.get("/auth/callback", params={"code": "abc", "state": state})
        return state, page

    def test_member_with_the_role_gets_in(self):
        key = self.make_keys()[0]["key"]
        state, page = self.discord_login(key, user_id="42", roles=("777", "5"))
        self.assertEqual(page.status_code, 200)
        self.assertIn("successful", page.text)
        self.assertIn("token", self.token(state).json())
        self.assertEqual(self.http.get("/admin/keys", headers=ADMIN).json()["keys"][0]["status"], "in use")

    def test_member_without_the_role_is_refused_and_the_key_stays_free(self):
        key = self.make_keys()[0]["key"]
        state, page = self.discord_login(key, roles=("5",))
        self.assertEqual(page.status_code, 403)
        r = self.token(state)
        self.assertEqual(r.status_code, 403)
        self.assertIn("required role", r.json()["detail"])
        self.assertEqual(self.http.get("/admin/keys", headers=ADMIN).json()["keys"][0]["status"], "unused")

    def test_someone_not_on_the_server_is_refused(self):
        key = self.make_keys()[0]["key"]
        state, page = self.discord_login(key, member_status=404)
        self.assertEqual(page.status_code, 403)
        self.assertIn("not on the NEXUS Discord server", self.token(state).json()["detail"])

    def test_leaving_the_server_blocks_the_next_login(self):
        key = self.make_keys()[0]["key"]
        self.discord_login(key, user_id="42")                      # fine while on the server
        state, page = self.discord_login(key, user_id="42", member_status=404)
        self.assertEqual(page.status_code, 403)

    def test_a_refused_attempt_cannot_be_reused(self):
        key = self.make_keys()[0]["key"]
        state, page = self.discord_login(key, member_status=404)
        again = self.http.get("/auth/callback", params={"code": "abc", "state": state})
        self.assertEqual(again.status_code, 400)

    def test_database_of_an_older_version_is_upgraded(self):
        old = Path(self.dir) / "old.db"
        con = sqlite3.connect(old)
        con.execute("CREATE TABLE auth_states (state TEXT PRIMARY KEY, token TEXT, created_at REAL)")
        con.commit()
        con.close()
        load_server(old)
        cols = {r[1] for r in sqlite3.connect(old).execute("PRAGMA table_info(auth_states)")}
        self.assertTrue({"key_id", "error"} <= cols)

    def test_admin_command_line_tool(self):
        import server.keys as tool

        def via_testclient(url, token, method, path, payload=None):
            r = self.http.request(method, path, json=payload, headers={"Authorization": f"Bearer {token}"})
            return r.json()

        original, tool.call = tool.call, via_testclient
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                tool.main(["--url", "http://x", "--token", "admin-token-for-tests", "create", "Alice", "-n", "2"])
                tool.main(["--url", "http://x", "--token", "admin-token-for-tests", "list"])
                tool.main(["--url", "http://x", "--token", "admin-token-for-tests", "revoke", "1"])
            text = out.getvalue()
        finally:
            tool.call = original
        self.assertEqual(text.count("NX-"), 2 + 2)                  # 2 created + 2 masked in the list
        self.assertIn("revoked", text)
        self.assertIn("2 keys", text)


if __name__ == "__main__":
    unittest.main()
