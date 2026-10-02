"""Game key activation: Ed25519 (RFC 8032 vectors), signed offline licences, and the server's /license/activate rules."""
import base64
import json
import os
import secrets
import tempfile
import time
import unittest
from pathlib import Path

from nexus import ed25519, license
from tests.test_keys import ADMIN, HAVE_SERVER_DEPS, load_server
from tests.test_online import FakeSettings

SEED = secrets.token_bytes(32)
PUBLIC = ed25519.public_key(SEED).hex()
DEVICE = "a" * 32
OTHER = "b" * 32


class Ed25519Vectors(unittest.TestCase):
    def test_rfc8032_vectors(self):
        vectors = [
            ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60", "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "",
             "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
            ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb", "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c", "72",
             "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
        ]
        for secret, public, message, signature in vectors:
            seed, msg = bytes.fromhex(secret), bytes.fromhex(message)
            self.assertEqual(ed25519.public_key(seed).hex(), public)
            self.assertEqual(ed25519.sign(seed, msg).hex(), signature)
            self.assertTrue(ed25519.verify(bytes.fromhex(public), msg, bytes.fromhex(signature)))
            self.assertFalse(ed25519.verify(bytes.fromhex(public), msg + b"x", bytes.fromhex(signature)))

    def test_bad_input_is_rejected_not_raised(self):
        sig = ed25519.sign(SEED, b"m")
        self.assertFalse(ed25519.verify(b"short", b"m", sig))
        self.assertFalse(ed25519.verify(bytes.fromhex(PUBLIC), b"m", sig[:-1]))
        self.assertFalse(ed25519.verify(bytes.fromhex(PUBLIC), b"m", b"\xff" * 64))
        self.assertFalse(ed25519.verify(ed25519.public_key(secrets.token_bytes(32)), b"m", sig))             # another key


def make_token(device=DEVICE, exp_in=86400, seed=SEED, key_id=1, version=1):
    now = int(time.time())
    payload = json.dumps({"v": version, "kid": key_id, "dev": device, "iat": now, "exp": now + exp_in}, separators=(",", ":")).encode()
    b64 = lambda raw: base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    return f"{b64(payload)}.{b64(ed25519.sign(seed, payload))}"


class OfflineLicenceCheck(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("NEXUS_LICENSE_PUBKEY")
        os.environ["NEXUS_LICENSE_PUBKEY"] = PUBLIC
        self.settings = FakeSettings(device_id=DEVICE)

    def tearDown(self):
        os.environ.pop("NEXUS_LICENSE_PUBKEY") if self._saved is None else os.environ.__setitem__("NEXUS_LICENSE_PUBKEY", self._saved)

    def test_builds_without_a_public_key_need_no_key(self):
        os.environ["NEXUS_LICENSE_PUBKEY"] = ""
        self.assertFalse(license.enabled())
        self.assertTrue(license.check(FakeSettings()).ok)

    def test_not_activated_yet(self):
        s = license.check(self.settings)
        self.assertEqual((s.ok, s.reason), (False, "none"))

    def test_a_genuine_licence_works_offline_and_reports_the_days_left(self):
        self.settings.set("license_token", make_token(exp_in=10 * 86400 + 60))
        s = license.check(self.settings)
        self.assertTrue(s.ok)
        self.assertEqual(s.days_left, 10)

    def test_tampering_is_detected(self):
        good = make_token()
        payload, sig = good.split(".")
        forged_payload = base64.urlsafe_b64encode(json.dumps({"v": 1, "kid": 1, "dev": DEVICE, "iat": 0, "exp": 4102444800}).encode()).rstrip(b"=").decode()
        for bad in ("", "garbage", payload, payload + ".", "." + sig, forged_payload + "." + sig, payload + "." + sig[:-4] + "AAAA", good + "x",
                    make_token(seed=secrets.token_bytes(32)),                                    # signed by somebody else
                    make_token(version=2)):
            self.settings.set("license_token", bad)
            self.assertFalse(license.check(self.settings).ok, bad[:30])
        self.assertEqual(license.check(self.settings).reason, "bad")

    def test_a_licence_for_another_computer_is_refused(self):
        self.settings.set("license_token", make_token(device=OTHER))
        self.assertEqual(license.check(self.settings).reason, "device")

    def test_an_expired_licence_asks_for_a_connection(self):
        self.settings.set("license_token", make_token(exp_in=-5))
        s = license.check(self.settings)
        self.assertEqual((s.ok, s.reason), (False, "expired"))
        self.assertIn("internet", s.message)
        self.assertTrue(license.check(self.settings, now=time.time() - 3600).ok)             # clock set back: still verifies against its own dates

    def test_store_only_keeps_licences_that_verify(self):
        self.assertFalse(license.store(self.settings, make_token(device=OTHER), "NX-1").ok)
        self.assertFalse(license.store(self.settings, "nonsense", "NX-1").ok)
        self.assertEqual(self.settings.get("license_token"), None)
        status = license.store(self.settings, make_token(), " NX-AAAAA-BBBBB-CCCCC ")
        self.assertTrue(status.ok)
        self.assertEqual((self.settings.get("license_key"), self.settings.get("online_key")), ("NX-AAAAA-BBBBB-CCCCC", "NX-AAAAA-BBBBB-CCCCC"))

    def test_device_id_is_created_once_and_repaired_if_edited(self):
        fresh = FakeSettings()
        first = license.device_id(fresh)
        self.assertRegex(first, r"^[0-9a-f]{32}$")
        self.assertEqual(license.device_id(fresh), first)
        fresh.set("device_id", "hacked")
        self.assertRegex(license.device_id(fresh), r"^[0-9a-f]{32}$")
        self.assertNotEqual(license.device_id(fresh), "hacked")

    def test_a_packaged_game_ignores_the_environment(self):
        import nexus.license as lic
        original = lic.FROZEN
        lic.FROZEN = True
        try:
            os.environ["NEXUS_LICENSE_PUBKEY"] = ""
            from nexus.version import LICENSE_PUBLIC_KEY
            self.assertEqual(lic.public_key_hex(), LICENSE_PUBLIC_KEY.lower() if len(LICENSE_PUBLIC_KEY) == 64 else "")
        finally:
            lic.FROZEN = original

    def test_the_shipped_game_has_a_public_key(self):
        from nexus.version import LICENSE_PUBLIC_KEY
        self.assertRegex(LICENSE_PUBLIC_KEY, r"^[0-9a-f]{64}$")


@unittest.skipUnless(HAVE_SERVER_DEPS, "server dependencies (fastapi, uvicorn, httpx) not installed")
class ServerActivation(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        self.dir = tempfile.mkdtemp()
        self.db = Path(self.dir) / "online.db"
        self.mod = load_server(self.db, NEXUS_LICENSE_SEED=SEED.hex())
        self.http = TestClient(self.mod.app)

    def key(self, **extra):
        r = self.http.post("/admin/keys", json={"label": "t", **extra}, headers=ADMIN)
        return r.json()["keys"][0]

    def activate(self, key, device=DEVICE):
        return self.http.post("/license/activate", json={"key": key, "device": device})

    def test_needs_the_signing_seed(self):
        from fastapi.testclient import TestClient
        bare = TestClient(load_server(Path(self.dir) / "bare.db", NEXUS_LICENSE_SEED="").app)
        self.assertFalse(bare.get("/health").json()["license"])
        self.assertEqual(bare.post("/license/activate", json={"key": "x", "device": DEVICE}).status_code, 503)
        self.assertTrue(self.http.get("/health").json()["license"])

    def test_no_licence_without_a_valid_key(self):
        for key in ("", "  ", "NX-AAAAA-BBBBB-CCCCC"):
            r = self.activate(key)
            self.assertEqual(r.status_code, 403, key)
            self.assertNotIn("token", r.json())
        self.assertEqual(self.http.post("/license/activate", json={"key": "NX-AAAAA-BBBBB-CCCCC", "device": "x"}).status_code, 422)     # bad device id
        self.assertEqual(self.http.post("/license/activate", json={"key": "NX-AAAAA-BBBBB-CCCCC"}).status_code, 422)

    def test_a_valid_key_gives_a_licence_the_game_can_verify(self):
        k = self.key()
        r = self.activate(k["key"])
        self.assertEqual(r.status_code, 200, r.text)
        data = license.read_token(r.json()["token"], PUBLIC)
        self.assertEqual((data["kid"], data["dev"]), (k["id"], DEVICE))
        self.assertAlmostEqual(data["exp"] - data["iat"], 30 * 86400, delta=5)
        listing = self.http.get("/admin/keys", headers=ADMIN).json()["keys"][0]
        self.assertEqual((listing["status"], listing["device"]), ("in use", True))
        self.assertIsNone(license.read_token(r.json()["token"], ed25519.public_key(secrets.token_bytes(32)).hex()))      # not valid under another key
        self.assertNotIn(k["key"], str(__import__("sqlite3").connect(self.db).execute("SELECT * FROM access_keys").fetchall()))

    def test_the_key_belongs_to_the_first_computer(self):
        k = self.key()
        self.assertEqual(self.activate(k["key"]).status_code, 200)
        self.assertEqual(self.activate(k["key"]).status_code, 200)                         # renewing on the same computer is fine
        r = self.activate(k["key"], OTHER)
        self.assertEqual(r.status_code, 403)
        self.assertIn("another computer", r.json()["detail"])
        self.http.post(f"/admin/keys/{k['id']}/unbind", headers=ADMIN)                     # the admin frees it ...
        self.assertEqual(self.http.get("/admin/keys", headers=ADMIN).json()["keys"][0]["status"], "unused")
        self.assertEqual(self.activate(k["key"], OTHER).status_code, 200)                  # ... and the new computer can take it
        self.assertEqual(self.activate(k["key"]).status_code, 403)

    def test_deactivated_deleted_and_expired_keys_get_no_licence(self):
        a, b, c = self.key(), self.key(), self.key(expires_days=5)
        self.assertEqual(self.activate(a["key"]).status_code, 200)
        self.http.post(f"/admin/keys/{a['id']}/revoke", headers=ADMIN)
        r = self.activate(a["key"])
        self.assertEqual(r.status_code, 403)                                               # a renewal after deactivation is refused
        self.assertIn("revoked", r.json()["detail"])
        self.http.post(f"/admin/keys/{a['id']}/activate", headers=ADMIN)
        self.assertEqual(self.activate(a["key"]).status_code, 200)                         # and works again once reactivated
        self.activate(b["key"])
        self.http.delete(f"/admin/keys/{b['id']}", headers=ADMIN)
        self.assertEqual(self.activate(b["key"]).status_code, 403)
        con = __import__("sqlite3").connect(self.db)
        con.execute("UPDATE access_keys SET expires_at=? WHERE id=?", (time.time() - 5, c["id"]))
        con.commit()
        con.close()
        r = self.activate(c["key"])
        self.assertEqual(r.status_code, 403)
        self.assertIn("expired", r.json()["detail"])

    def test_one_key_for_the_offline_licence_and_the_online_account(self):
        k = self.key()
        self.assertEqual(self.activate(k["key"]).status_code, 200)
        def begin(device):
            return self.http.post("/auth/begin", json={"state": "s" * 20, "key": k["key"], "device": device})
        self.assertEqual(begin(DEVICE).status_code, 200)                                   # the activated computer can log in online
        r = begin(OTHER)
        self.assertEqual(r.status_code, 403)                                               # a copy of the key on another computer cannot
        self.assertIn("another computer", r.json()["detail"])
        self.assertEqual(begin("").status_code, 200)                                       # (older games send no device and keep working)

    def test_logging_in_online_first_binds_the_computer_too(self):
        k = self.key()
        self.assertEqual(self.http.post("/auth/begin", json={"state": "t" * 20, "key": k["key"], "device": DEVICE}).status_code, 200)
        self.assertEqual(self.activate(k["key"], OTHER).status_code, 403)

    def test_banned_accounts_get_no_licence(self):
        k = self.key()
        state = "u" * 20
        self.http.post("/auth/begin", json={"state": state, "key": k["key"], "device": DEVICE})
        self.http.get("/auth/dev", params={"name": "Bad", "state": state})
        uid = __import__("sqlite3").connect(self.db).execute("SELECT id FROM users").fetchone()[0]
        self.assertEqual(self.activate(k["key"]).status_code, 200)
        self.http.post(f"/admin/players/{uid}/status", json={"status": "banned", "reason": "cheating"}, headers=ADMIN)
        r = self.activate(k["key"])
        self.assertEqual(r.status_code, 403)
        self.assertIn("banned", r.json()["detail"])

    def test_key_guessing_is_rate_limited(self):
        codes = [self.activate(f"NX-AAAAA-AAAAA-{i:05d}"[:20]).status_code for i in range(15)]
        self.assertIn(429, codes)


if __name__ == "__main__":
    unittest.main()
