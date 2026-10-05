"""F3: staff accounts (roles, TOTP, invite codes), layered on top of the existing single admin credential.
Every pre-existing admin_only endpoint must keep working unchanged - see tests/test_admin.py for those; this file
is only the new staff-account surface."""
import time
import unittest

from tests.test_keys import ADMIN, HAVE_SERVER_DEPS, load_server


@unittest.skipUnless(HAVE_SERVER_DEPS, "server dependencies (fastapi, uvicorn, httpx) not installed")
class StaffBase(unittest.TestCase):
    def setUp(self):
        import tempfile
        from fastapi.testclient import TestClient
        self.dir = tempfile.mkdtemp()
        self.db = __import__("pathlib").Path(self.dir) / "online.db"
        self.mod = load_server(self.db)
        self.http = TestClient(self.mod.app)

    # -- helpers -------------------------------------------------------------
    def code(self, secret, offset=0):
        from server.staff_auth import totp_at
        return totp_at(secret, int(time.time() // 30) + offset)

    def bootstrap(self, username="dev1", password="correct horse battery staple"):
        r = self.http.post("/admin/staff/bootstrap", json={"username": username, "password": password}, headers=ADMIN)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def login(self, username, password, secret):
        r = self.http.post("/admin/staff/login", json={"username": username, "password": password, "totp_code": self.code(secret)})
        self.assertEqual(r.status_code, 200, r.text)
        token = r.json()["token"]
        return {"Authorization": f"Bearer {token}"}, r.json()

    def invite(self, headers, role):
        r = self.http.post("/admin/staff/invite", json={"role": role}, headers=headers)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["code"]

    def redeem(self, code, username, password="correct horse battery staple"):
        r = self.http.post("/admin/staff/redeem", json={"code": code, "username": username, "password": password})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def make_staff(self, inviter_headers, role, username, approve_headers=None):
        """Invite, redeem and (if given approval headers) approve + log in a staff member.
        Returns (headers_or_None, signup_info) - signup_info always has 'id', even before approval/login."""
        code = self.invite(inviter_headers, role)
        signup = self.redeem(code, username)
        if approve_headers is not None:
            r = self.http.post(f"/admin/staff/{signup['id']}/approve", headers=approve_headers)
            self.assertEqual(r.status_code, 200, r.text)
            headers, _ = self.login(username, "correct horse battery staple", signup["totp_secret"])
            return headers, signup
        return None, signup


class Bootstrap(StaffBase):
    def test_bootstrap_creates_a_developer_account(self):
        info = self.bootstrap()
        self.assertEqual(info["role"], "developer")
        self.assertIn("totp_secret", info)
        self.assertTrue(info["otpauth_uri"].startswith("otpauth://totp/"))

    def test_bootstrap_only_works_once(self):
        self.bootstrap()
        r = self.http.post("/admin/staff/bootstrap", json={"username": "dev2", "password": "another long password"}, headers=ADMIN)
        self.assertEqual(r.status_code, 409)

    def test_bootstrap_needs_the_legacy_admin_credential(self):
        r = self.http.post("/admin/staff/bootstrap", json={"username": "dev1", "password": "correct horse battery staple"})
        self.assertEqual(r.status_code, 401)


class LoginTests(StaffBase):
    def setUp(self):
        super().setUp()
        self.info = self.bootstrap()

    def test_correct_credentials_and_totp_log_in(self):
        headers, body = self.login("dev1", "correct horse battery staple", self.info["totp_secret"])
        self.assertEqual(body["role"], "developer")
        r = self.http.get("/admin/staff", headers=headers)
        self.assertEqual(r.status_code, 200, r.text)

    def test_wrong_password_is_rejected(self):
        r = self.http.post("/admin/staff/login", json={"username": "dev1", "password": "nope", "totp_code": self.code(self.info["totp_secret"])})
        self.assertEqual(r.status_code, 401)

    def test_wrong_totp_code_is_rejected(self):
        r = self.http.post("/admin/staff/login", json={"username": "dev1", "password": "correct horse battery staple", "totp_code": "000000"})
        self.assertEqual(r.status_code, 401)

    def test_unknown_username_is_rejected(self):
        r = self.http.post("/admin/staff/login", json={"username": "ghost", "password": "x", "totp_code": "000000"})
        self.assertEqual(r.status_code, 401)

    def test_logout_invalidates_the_session(self):
        headers, _ = self.login("dev1", "correct horse battery staple", self.info["totp_secret"])
        self.http.post("/admin/staff/logout", headers=headers)
        r = self.http.get("/admin/staff", headers=headers)
        self.assertEqual(r.status_code, 401)

    def test_no_session_at_all_is_401_not_403(self):
        self.assertEqual(self.http.get("/admin/staff").status_code, 401)


class InviteAndApproval(StaffBase):
    def setUp(self):
        super().setUp()
        self.dev_info = self.bootstrap()
        self.dev_headers, _ = self.login("dev1", "correct horse battery staple", self.dev_info["totp_secret"])

    def test_developer_can_invite_an_owner(self):
        code = self.invite(self.dev_headers, "owner")
        self.assertTrue(code.startswith("INV-"))

    def test_redeemed_account_is_not_approved_and_cannot_log_in_yet(self):
        code = self.invite(self.dev_headers, "owner")
        signup = self.redeem(code, "owner1")
        self.assertFalse(signup["approved"])
        r = self.http.post("/admin/staff/login", json={"username": "owner1", "password": "correct horse battery staple",
                                                        "totp_code": self.code(signup["totp_secret"])})
        self.assertEqual(r.status_code, 403)

    def test_approval_lets_the_account_log_in(self):
        owner_headers, _ = self.make_staff(self.dev_headers, "owner", "owner1", approve_headers=self.dev_headers)
        self.assertIsNotNone(owner_headers)
        r = self.http.get("/admin/staff", headers=owner_headers)
        self.assertEqual(r.status_code, 200)

    def test_an_invite_code_can_only_be_used_once(self):
        code = self.invite(self.dev_headers, "helper")
        self.redeem(code, "helper1")
        r = self.http.post("/admin/staff/redeem", json={"code": code, "username": "helper2", "password": "correct horse battery staple"})
        self.assertEqual(r.status_code, 400)

    def test_an_unknown_code_is_rejected(self):
        r = self.http.post("/admin/staff/redeem", json={"code": "INV-nonsense", "username": "xuser", "password": "correct horse battery staple"})
        self.assertEqual(r.status_code, 400)

    def test_redeeming_an_already_taken_username_is_rejected(self):
        code1 = self.invite(self.dev_headers, "helper")
        self.redeem(code1, "dupe")
        code2 = self.invite(self.dev_headers, "helper")
        r = self.http.post("/admin/staff/redeem", json={"code": code2, "username": "dupe", "password": "correct horse battery staple"})
        self.assertEqual(r.status_code, 409)

    def test_a_moderator_can_invite_a_helper_but_not_a_moderator_or_owner(self):
        mod_headers, _ = self.make_staff(self.dev_headers, "moderator", "mod1", approve_headers=self.dev_headers)
        code = self.invite(mod_headers, "helper")
        self.assertTrue(code)
        for role in ("moderator", "owner", "developer"):
            r = self.http.post("/admin/staff/invite", json={"role": role}, headers=mod_headers)
            self.assertIn(r.status_code, (403, 422), (role, r.text))

    def test_a_helper_cannot_invite_anyone(self):
        helper_headers, _ = self.make_staff(self.dev_headers, "helper", "helper1", approve_headers=self.dev_headers)
        r = self.http.post("/admin/staff/invite", json={"role": "helper"}, headers=helper_headers)
        self.assertEqual(r.status_code, 403)

    def test_developer_role_can_never_be_invited(self):
        r = self.http.post("/admin/staff/invite", json={"role": "developer"}, headers=self.dev_headers)
        self.assertEqual(r.status_code, 422)


class RoleAndLifecycleManagement(StaffBase):
    def setUp(self):
        super().setUp()
        self.dev_info = self.bootstrap()
        self.dev_headers, _ = self.login("dev1", "correct horse battery staple", self.dev_info["totp_secret"])
        self.owner_headers, self.owner_body = self.make_staff(self.dev_headers, "owner", "owner1", approve_headers=self.dev_headers)
        self.owner_id = self.http.get("/admin/staff", headers=self.dev_headers).json()["staff"][-1]["id"]

    def test_owner_can_change_a_subordinates_role(self):
        helper_headers, signup = self.make_staff(self.owner_headers, "helper", "helper1", approve_headers=self.owner_headers)
        r = self.http.post(f"/admin/staff/{signup['id']}/role", json={"role": "moderator"}, headers=self.owner_headers)
        self.assertEqual(r.status_code, 200, r.text)

    def test_owner_cannot_change_their_own_role(self):
        r = self.http.post(f"/admin/staff/{self.owner_id}/role", json={"role": "helper"}, headers=self.owner_headers)
        self.assertEqual(r.status_code, 403)

    def test_developer_role_cannot_be_changed(self):
        dev_id = self.http.get("/admin/staff", headers=self.dev_headers).json()["staff"][0]["id"]
        r = self.http.post(f"/admin/staff/{dev_id}/role", json={"role": "owner"}, headers=self.owner_headers)
        self.assertEqual(r.status_code, 403)

    def test_role_cannot_be_set_to_developer(self):
        r = self.http.post(f"/admin/staff/{self.owner_id}/role", json={"role": "developer"}, headers=self.dev_headers)
        self.assertEqual(r.status_code, 422)

    def test_owner_can_delete_a_subordinate(self):
        _, signup = self.make_staff(self.owner_headers, "helper", "helper1")
        r = self.http.delete(f"/admin/staff/{signup['id']}", headers=self.owner_headers)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(len(self.http.get("/admin/staff", headers=self.dev_headers).json()["staff"]), 2)       # dev + owner left

    def test_cannot_delete_self(self):
        r = self.http.delete(f"/admin/staff/{self.owner_id}", headers=self.owner_headers)
        self.assertEqual(r.status_code, 403)

    def test_cannot_delete_the_developer_account(self):
        dev_id = self.http.get("/admin/staff", headers=self.dev_headers).json()["staff"][0]["id"]
        r = self.http.delete(f"/admin/staff/{dev_id}", headers=self.owner_headers)
        self.assertEqual(r.status_code, 403)

    def test_a_helper_cannot_reach_owner_only_endpoints(self):
        helper_headers, _ = self.make_staff(self.owner_headers, "helper", "helper1", approve_headers=self.owner_headers)
        for method, path in (("GET", "/admin/staff"), ("POST", f"/admin/staff/{self.owner_id}/approve"),
                             ("DELETE", f"/admin/staff/{self.owner_id}")):
            r = self.http.request(method, path, headers=helper_headers)
            self.assertEqual(r.status_code, 403, (method, path, r.text))


class KeyLimits(StaffBase):
    def setUp(self):
        super().setUp()
        self.dev_info = self.bootstrap()
        self.dev_headers, _ = self.login("dev1", "correct horse battery staple", self.dev_info["totp_secret"])
        self.helper_headers, signup = self.make_staff(self.dev_headers, "helper", "helper1", approve_headers=self.dev_headers)
        self.helper_id = signup["id"]

    def test_unlimited_by_default(self):
        r = self.http.post("/admin/keys", json={"label": "t", "count": 5}, headers=self.helper_headers)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(len(r.json()["keys"]), 5)

    def test_limit_is_enforced(self):
        self.http.post(f"/admin/staff/{self.helper_id}/key-limit", json={"limit": 3}, headers=self.dev_headers)
        ok = self.http.post("/admin/keys", json={"label": "t", "count": 3}, headers=self.helper_headers)
        self.assertEqual(ok.status_code, 200, ok.text)
        blocked = self.http.post("/admin/keys", json={"label": "t", "count": 1}, headers=self.helper_headers)
        self.assertEqual(blocked.status_code, 403)

    def test_only_owner_plus_can_set_a_limit(self):
        r = self.http.post(f"/admin/staff/{self.helper_id}/key-limit", json={"limit": 3}, headers=self.helper_headers)
        self.assertEqual(r.status_code, 403)

    def test_reaching_the_limit_notifies_the_team_channel(self):
        srv = self.mod
        sent = []
        original = srv.notify_team
        srv.notify_team = sent.append
        try:
            self.http.post(f"/admin/staff/{self.helper_id}/key-limit", json={"limit": 2}, headers=self.dev_headers)
            self.http.post("/admin/keys", json={"label": "t", "count": 2}, headers=self.helper_headers)
            self.assertEqual(len(sent), 1)
            self.assertIn("helper1", sent[0])
        finally:
            srv.notify_team = original

    def test_legacy_admin_credential_stays_unlimited_and_unaffected(self):
        r = self.http.post("/admin/keys", json={"label": "t", "count": 10}, headers=ADMIN)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(len(r.json()["keys"]), 10)


if __name__ == "__main__":
    unittest.main()
