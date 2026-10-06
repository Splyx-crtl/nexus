"""F3: staff password hashing and TOTP (server/staff_auth.py). Pure logic, no FastAPI/DB - the actual staff
endpoints are tested against a real server in tests/test_staff.py."""
import time
import unittest

from server.staff_auth import (
    INVITABLE_ROLES, ROLES, hash_password, new_totp_secret, provisioning_uri, role_rank, totp_at,
    verify_password, verify_totp,
)


class PasswordHashingTests(unittest.TestCase):
    def test_correct_password_verifies(self):
        self.assertTrue(verify_password("correct horse battery staple", hash_password("correct horse battery staple")))

    def test_wrong_password_is_rejected(self):
        self.assertFalse(verify_password("wrong", hash_password("correct horse battery staple")))

    def test_two_hashes_of_the_same_password_differ(self):
        # random salt per hash - this is the whole point, otherwise identical passwords look identical in the DB
        self.assertNotEqual(hash_password("same"), hash_password("same"))

    def test_garbage_stored_value_never_crashes_verification(self):
        for garbage in ("", "not-even-close", "pbkdf2$abc$def", "md5$1$2$3"):
            self.assertFalse(verify_password("anything", garbage))


class TotpTests(unittest.TestCase):
    def test_the_current_code_verifies(self):
        secret = new_totp_secret()
        now = time.time()
        code = totp_at(secret, int(now // 30))
        self.assertTrue(verify_totp(secret, code, now))

    def test_a_code_from_a_different_secret_fails(self):
        now = time.time()
        code = totp_at(new_totp_secret(), int(now // 30))
        self.assertFalse(verify_totp(new_totp_secret(), code, now))

    def test_a_code_one_step_old_still_verifies_within_the_drift_window(self):
        secret = new_totp_secret()
        now = time.time()
        old_code = totp_at(secret, int(now // 30) - 1)
        self.assertTrue(verify_totp(secret, old_code, now, window=1))

    def test_a_code_far_outside_the_window_fails(self):
        secret = new_totp_secret()
        now = time.time()
        stale_code = totp_at(secret, int(now // 30) - 5)
        self.assertFalse(verify_totp(secret, stale_code, now, window=1))

    def test_non_numeric_code_is_rejected_without_crashing(self):
        self.assertFalse(verify_totp(new_totp_secret(), "not-a-code", time.time()))

    def test_provisioning_uri_contains_the_secret_and_username(self):
        uri = provisioning_uri("JBSWY3DPEHPK3PXP", "alice")
        self.assertTrue(uri.startswith("otpauth://totp/"))
        self.assertIn("JBSWY3DPEHPK3PXP", uri)
        self.assertIn("alice", uri)


class RoleRankTests(unittest.TestCase):
    def test_roles_rank_in_the_documented_order(self):
        self.assertEqual(list(ROLES), ["helper", "moderator", "owner", "developer"])
        self.assertLess(role_rank("helper"), role_rank("moderator"))
        self.assertLess(role_rank("moderator"), role_rank("owner"))
        self.assertLess(role_rank("owner"), role_rank("developer"))

    def test_unknown_role_ranks_below_everything(self):
        self.assertLess(role_rank("nonsense"), role_rank("helper"))

    def test_developer_is_not_invitable(self):
        self.assertNotIn("developer", INVITABLE_ROLES)
        self.assertEqual(set(INVITABLE_ROLES), {"helper", "moderator", "owner"})


if __name__ == "__main__":
    unittest.main()
