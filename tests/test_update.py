"""Updater tests (no real network): version logic, release parsing, host restrictions, checksum verification."""
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from nexus import updater
from nexus.security import audit_package

ROOT = Path(__file__).resolve().parent.parent

RELEASE = {
    "tag_name": "v9.0.0", "body": "Big update", "html_url": "https://github.com/x/y/releases/tag/v9.0.0", "draft": False, "prerelease": False,
    "assets": [
        {"name": "NEXUS-Setup.exe", "browser_download_url": "https://github.com/x/y/releases/download/v9.0.0/NEXUS-Setup.exe"},
        {"name": "NEXUS-Setup.exe.sha256", "browser_download_url": "https://github.com/x/y/releases/download/v9.0.0/NEXUS-Setup.exe.sha256"},
    ],
}


class FakeResponse(io.BytesIO):
    def __init__(self, data: bytes):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class UpdaterTests(unittest.TestCase):
    def test_version_comparison(self):
        self.assertTrue(updater.is_newer("2.1.1", "2.1.0"))
        self.assertTrue(updater.is_newer("v2.10.0", "2.9.9"))
        self.assertFalse(updater.is_newer("2.1.0", "2.1.0"))
        self.assertFalse(updater.is_newer("2.0.9", "2.1.0"))

    def test_release_parsing_and_detection(self):
        info = updater.pick_release(RELEASE)
        self.assertEqual(info["version"], "9.0.0")
        self.assertTrue(info["sha256_url"])
        self.assertIsNone(updater.pick_release({**RELEASE, "prerelease": True}))
        self.assertIsNone(updater.pick_release({**RELEASE, "assets": []}))
        self.assertEqual(updater.check_for_update("x/y", fetch=lambda url: RELEASE)["version"], "9.0.0")
        old = {**RELEASE, "tag_name": "v0.0.1"}
        self.assertIsNone(updater.check_for_update("x/y", fetch=lambda url: old))

    def test_disabled_and_offline_are_silent(self):
        self.assertIsNone(updater.check_for_update("", fetch=lambda url: 1 / 0))

        def offline(url):
            raise OSError("no network")
        self.assertIsNone(updater.check_for_update("x/y", fetch=offline))

    def test_only_github_https_is_allowed(self):
        for bad in ("http://github.com/a", "https://evil.example.com/NEXUS-Setup.exe", "ftp://github.com/x", "https://github.com.evil.io/x"):
            with self.assertRaises(ValueError, msg=bad):
                updater._check_url(bad)
        updater._check_url("https://github.com/x/y/releases/download/v1/NEXUS-Setup.exe")
        evil = {**RELEASE, "assets": [{"name": "NEXUS-Setup.exe", "browser_download_url": "https://evil.example.com/NEXUS-Setup.exe"}]}
        self.assertIsNone(updater.check_for_update("x/y", fetch=lambda url: evil))

    def test_download_verifies_checksum(self):
        payload = b"installer-bytes" * 1000
        good = hashlib.sha256(payload).hexdigest()
        release = updater.pick_release(RELEASE)

        def fake_open(url, timeout):
            return FakeResponse(good.encode() + b"  NEXUS-Setup.exe" if url.endswith(".sha256") else payload)

        with mock.patch.object(updater, "_open", fake_open):
            dest = Path(tempfile.mkdtemp()) / "NEXUS-Setup.exe"
            progress = []
            updater.download(release, dest, lambda d, t: progress.append((d, t)))
            self.assertEqual(dest.read_bytes(), payload)
            self.assertTrue(progress)

        def tampered(url, timeout):
            return FakeResponse(b"0" * 64 if url.endswith(".sha256") else payload)

        with mock.patch.object(updater, "_open", tampered):
            dest2 = Path(tempfile.mkdtemp()) / "NEXUS-Setup.exe"
            with self.assertRaises(ValueError):
                updater.download(release, dest2)
            self.assertFalse(dest2.exists())

    def test_network_code_is_confined_to_the_updater(self):
        self.assertEqual(audit_package(ROOT / "nexus", ROOT / "ui"), [])
        text = (ROOT / "nexus" / "game_engine.py").read_text(encoding="utf-8") + (ROOT / "nexus" / "commands.py").read_text(encoding="utf-8")
        self.assertNotIn("urllib", text)

    def test_feature_is_off_until_a_repo_is_configured(self):
        from nexus import version
        if not version.GITHUB_REPO:
            self.assertIsNone(updater.check_for_update())


if __name__ == "__main__":
    unittest.main()
