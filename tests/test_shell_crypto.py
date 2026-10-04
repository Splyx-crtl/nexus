"""Encoding, hashing, archiving and metadata commands (B5): base64, xxd, md5sum/sha256sum, strings, tar/zip/unzip,
exiftool, binwalk, openssl, gpg."""
import hashlib
import unittest

from tests.test_shell_core import Base


class Base64(Base):
    def test_roundtrip_via_stdin_and_file(self):
        self.shell.run("echo -n 'hello nexus' > msg.txt")
        encoded = self.out("base64 msg.txt").strip()
        self.assertNotIn("hello", encoded)
        self.check(f"echo -n {encoded} | base64 -d", "hello nexus")

    def test_missing_file(self):
        r = self.run_("base64 nope.txt")
        self.assertEqual(r.status, 1)
        self.assertIn("No such file", r.err)


class Xxd(Base):
    def test_hex_dump_format(self):
        self.shell.run("echo -n AB > two.bin")
        out = self.out("xxd two.bin")
        self.assertIn("00000000:", out)
        self.assertIn("4142", out)        # 'A'=0x41 'B'=0x42
        self.assertIn("AB", out)          # ascii column


class Sums(Base):
    def test_md5sum_matches_real_hashlib(self):
        self.shell.run("echo -n 'check me' > f.txt")
        expected = hashlib.md5(b"check me").hexdigest()
        out = self.out("md5sum f.txt")
        self.assertEqual(out, f"{expected}  f.txt\n")

    def test_sha256sum_matches_real_hashlib(self):
        self.shell.run("echo -n 'check me' > f.txt")
        expected = hashlib.sha256(b"check me").hexdigest()
        out = self.out("sha256sum f.txt")
        self.assertEqual(out, f"{expected}  f.txt\n")

    def test_check_mode_ok_and_failed(self):
        self.shell.run("echo -n 'original' > a.txt")
        self.shell.run("sha256sum a.txt > sums.txt")
        r = self.run_("sha256sum -c sums.txt")
        self.assertEqual(r.status, 0)
        self.assertIn("a.txt: OK", r.out)
        self.shell.run("echo -n 'tampered' > a.txt")
        r = self.run_("sha256sum -c sums.txt")
        self.assertEqual(r.status, 1)
        self.assertIn("a.txt: FAILED", r.out)


class Strings(Base):
    def test_extracts_runs_above_minimum_length(self):
        self.shell.run("echo -ne 'ab\\x00\\x01secretpass\\x02\\x03cd' > blob.bin")
        out = self.out("strings blob.bin")
        self.assertIn("secretpass", out)

    def test_min_length_flag(self):
        self.shell.run("echo -ne 'xx\\x00yy\\x00thisislong' > blob.bin")
        out = self.out("strings -n 8 blob.bin")
        self.assertIn("thisislong", out)
        self.assertNotIn("xx", out.replace("thisislong", ""))
        self.assertNotIn("yy", out.replace("thisislong", ""))


class TarZip(Base):
    def test_tar_create_list_extract_roundtrip(self):
        self.shell.run("echo -n 'one' > one.txt")
        self.shell.run("echo -n 'two' > two.txt")
        r = self.run_("tar -cf bundle.tar one.txt two.txt")
        self.assertEqual(r.status, 0)
        listing = self.out("tar -tf bundle.tar")
        self.assertIn("one.txt", listing)
        self.assertIn("two.txt", listing)
        self.shell.run("mkdir out")
        r = self.run_("tar -xf bundle.tar -C out")
        self.assertEqual(r.status, 0)
        self.check("cat out/one.txt", "one")
        self.check("cat out/two.txt", "two")

    def test_zip_unzip_roundtrip(self):
        self.shell.run("echo -n 'zipped' > z.txt")
        r = self.run_("zip pack.zip z.txt")
        self.assertEqual(r.status, 0)
        self.shell.run("mkdir unpacked")
        r = self.run_("unzip pack.zip -d unpacked")
        self.assertEqual(r.status, 0)
        self.check("cat unpacked/z.txt", "zipped")


class Exiftool(Base):
    def test_no_metadata(self):
        self.shell.run("echo hi > plain.txt")
        self.assertIn("No metadata found", self.out("exiftool plain.txt"))

    def test_reads_node_meta(self):
        self.machine.fs.load({"photo.jpg": {"content": "fakebytes", "meta": {"Camera": "Nexus-7", "GPS": "40.7,-74.0"}}}, base=self.session.cwd)
        out = self.out("exiftool photo.jpg")
        self.assertIn("Camera", out)
        self.assertIn("Nexus-7", out)


class Binwalk(Base):
    def test_finds_embedded_signature(self):
        self.shell.run("echo -ne 'junkjunk\\x89PNG\\x0d\\x0a\\x1a\\x0amorejunk' > hidden.bin")
        out = self.out("binwalk hidden.bin")
        self.assertIn("PNG image", out)

    def test_no_signatures(self):
        self.shell.run("echo -n 'just plain text' > plain.bin")
        out = self.out("binwalk plain.bin")
        self.assertIn("no known signatures", out)


class Openssl(Base):
    def test_dgst_sha256(self):
        self.shell.run("echo -n 'hash me' > h.txt")
        expected = hashlib.sha256(b"hash me").hexdigest()
        out = self.out("openssl dgst -sha256 h.txt")
        self.assertIn(expected, out)

    def test_base64_roundtrip(self):
        self.shell.run("echo -n 'secret' > s.txt")
        encoded = self.out("openssl base64 -in s.txt").strip()
        self.shell.run(f"echo -n {encoded} > enc.txt")
        self.check("openssl base64 -d -in enc.txt", "secret")


class Gpg(Base):
    def test_symmetric_roundtrip(self):
        self.shell.run("echo -n 'top secret plan' > plan.txt")
        r = self.run_("gpg --symmetric --batch --passphrase hunter2 -o plan.txt.gpg plan.txt")
        self.assertEqual(r.status, 0)
        cat_out = self.out("cat plan.txt.gpg")
        self.assertNotIn("top secret plan", cat_out)
        r = self.run_("gpg --decrypt --batch --passphrase hunter2 -o revealed.txt plan.txt.gpg")
        self.assertEqual(r.status, 0)
        self.check("cat revealed.txt", "top secret plan")

    def test_wrong_passphrase_fails(self):
        self.shell.run("echo -n 'data' > d.txt")
        self.shell.run("gpg --symmetric --batch --passphrase right -o d.txt.gpg d.txt")
        r = self.run_("gpg --decrypt --batch --passphrase wrong -o out.txt d.txt.gpg")
        self.assertEqual(r.status, 2)
        self.assertIn("Bad session key", r.err)


if __name__ == "__main__":
    unittest.main()
