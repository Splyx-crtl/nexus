"""Virtual file system: paths, permissions (Linux and Windows flavour), symlinks, globbing, copy/move/remove."""
import unittest

from nexus.shell.fs import VFS, FsError, User, mode_string

ROOT = User("root", 0, 0, ("root",), "/root", admin=True)
ALICE = User("alice", 1000, 1000, ("alice", "staff"), "/home/alice")
BOB = User("bob", 1001, 1001, ("bob",), "/home/bob")

TREE = {
    "etc": {"passwd": "root:x:0:0\nalice:x:1000:1000\n", "shadow": {"content": "root:$6$abc\n", "mode": "640", "group": "shadow"}, "motd": "welcome\n"},
    "home": {
        "alice": {"_owner": "alice", "_group": "alice", "notes.txt": "hello\n", ".secret": "hidden\n", "docs": {"a.txt": "A", "b.log": "B", "c.txt": "C"},
                  "private": {"_mode": "700", "key.pem": {"content": "KEY", "mode": "600"}}},
        "bob": {"_owner": "bob", "_group": "bob", "todo": "x"},
    },
    "var": {"log": {"auth.log": "Failed password for root\nAccepted password for alice\n"}},
    "tmp": {"_mode": "1777"},
    "bin": {"tool": {"content": "#!/bin/sh", "mode": "755"}},
    "link_to_notes": {"link": "/home/alice/notes.txt"},
}


def linux() -> VFS:
    fs = VFS("posix", clock=lambda: 1000.0)
    fs.load(TREE)
    fs.stat(None, "/tmp").mode = 0o777
    return fs


class Paths(unittest.TestCase):
    def test_normalisation(self):
        fs = linux()
        self.assertEqual(fs.norm("/home/alice/../bob/./todo"), "/home/bob/todo")
        self.assertEqual(fs.norm("docs/a.txt", "/home/alice"), "/home/alice/docs/a.txt")
        self.assertEqual(fs.norm("../../etc", "/home/alice"), "/etc")
        self.assertEqual(fs.norm("/../.."), "/")
        self.assertEqual(fs.basename("/a/b/c.txt"), "c.txt")
        self.assertEqual(fs.dirname("/a/b/c.txt"), "/a/b")

    def test_windows_paths(self):
        fs = VFS("windows")
        self.assertEqual(fs.norm("c:/users/bob\\docs"), "C:\\users\\bob\\docs")
        self.assertEqual(fs.norm("..\\x", "C:\\Users\\bob"), "C:\\Users\\x")
        self.assertEqual(fs.norm("\\temp", "D:\\data"), "D:\\temp")
        self.assertEqual(fs.norm("..\\..\\..", "C:\\Users\\bob"), "C:\\")


class ReadWrite(unittest.TestCase):
    def test_read_and_list(self):
        fs = linux()
        self.assertEqual(fs.read(ALICE, "notes.txt", "/home/alice"), "hello\n")
        names = [n.name for n in fs.listdir(ALICE, "/home/alice")]
        self.assertEqual(names, [".secret", "docs", "notes.txt", "private"])

    def test_error_wording_matches_the_real_tools(self):
        fs = linux()
        with self.assertRaises(FsError) as cm:
            fs.read(ALICE, "/nope")
        self.assertEqual((cm.exception.code, str(cm.exception)), ("ENOENT", "/nope: No such file or directory"))
        with self.assertRaises(FsError) as cm:
            fs.read(ALICE, "/home/alice")
        self.assertEqual(cm.exception.code, "EISDIR")
        with self.assertRaises(FsError) as cm:
            fs.read(ALICE, "/home/alice/notes.txt/x")
        self.assertEqual(cm.exception.code, "ENOTDIR")

    def test_write_append_and_overwrite(self):
        fs = linux()
        fs.write(ALICE, "new.txt", "one\n", "/home/alice")
        fs.write(ALICE, "new.txt", "two\n", "/home/alice", append=True)
        self.assertEqual(fs.read(ALICE, "/home/alice/new.txt"), "one\ntwo\n")
        node = fs.stat(ALICE, "/home/alice/new.txt")
        self.assertEqual((node.owner, node.mode), ("alice", 0o644))
        fs.write(ALICE, "/home/alice/new.txt", "x")
        self.assertEqual(fs.read(ALICE, "/home/alice/new.txt"), "x")

    def test_mkdir_remove_rename_copy(self):
        fs = linux()
        fs.mkdir(ALICE, "/home/alice/a/b/c", parents=True)
        with self.assertRaises(FsError) as cm:
            fs.mkdir(ALICE, "/home/alice/a")
        self.assertEqual(cm.exception.code, "EEXIST")
        with self.assertRaises(FsError) as cm:
            fs.remove(ALICE, "/home/alice/a")
        self.assertEqual(cm.exception.code, "ENOTEMPTY")
        fs.remove(ALICE, "/home/alice/a", recursive=True)
        self.assertFalse(fs.exists("/home/alice/a"))
        fs.copy(ALICE, "/home/alice/notes.txt", "/home/alice/docs")
        self.assertEqual(fs.read(ALICE, "/home/alice/docs/notes.txt"), "hello\n")
        fs.rename(ALICE, "/home/alice/docs/notes.txt", "/home/alice/moved.txt")
        self.assertTrue(fs.exists("/home/alice/moved.txt") and not fs.exists("/home/alice/docs/notes.txt"))
        fs.copy(ALICE, "/home/alice/docs", "/home/alice/docs2", recursive=True)
        self.assertEqual(fs.read(ALICE, "/home/alice/docs2/a.txt"), "A")
        with self.assertRaises(FsError) as cm:
            fs.copy(ALICE, "/home/alice/docs", "/home/alice/docs3")
        self.assertEqual(cm.exception.code, "EISDIR")


class Permissions(unittest.TestCase):
    def test_other_users_files(self):
        fs = linux()
        self.assertEqual(fs.read(BOB, "/home/alice/notes.txt"), "hello\n")              # world readable
        with self.assertRaises(FsError) as cm:
            fs.read(BOB, "/home/alice/private/key.pem")                                 # directory 700
        self.assertEqual(cm.exception.code, "EACCES")
        with self.assertRaises(FsError):
            fs.write(BOB, "/home/alice/notes.txt", "hacked")                            # 644 owned by alice
        with self.assertRaises(FsError):
            fs.write(BOB, "/home/alice/evil.txt", "x")                                  # directory not writable for others

    def test_group_and_root(self):
        fs = linux()
        with self.assertRaises(FsError):
            fs.read(ALICE, "/etc/shadow")                                               # 640 group shadow, alice not in it
        self.assertEqual(fs.read(ROOT, "/etc/shadow"), "root:$6$abc\n")
        fs.stat(None, "/etc/shadow").group = "staff"
        self.assertEqual(fs.read(ALICE, "/etc/shadow"), "root:$6$abc\n")                # now alice is in the group

    def test_chmod_and_chown(self):
        fs = linux()
        fs.chmod(ALICE, "/home/alice/notes.txt", 0o600)
        with self.assertRaises(FsError):
            fs.read(BOB, "/home/alice/notes.txt")
        with self.assertRaises(FsError):
            fs.chmod(BOB, "/home/alice/notes.txt", 0o777)
        with self.assertRaises(FsError):
            fs.chown(ALICE, "/home/alice/notes.txt", "bob", None)
        fs.chown(ROOT, "/home/alice/notes.txt", "bob", None)
        self.assertEqual(fs.read(BOB, "/home/alice/notes.txt"), "hello\n")

    def test_mode_string(self):
        fs = linux()
        self.assertEqual(mode_string(fs.stat(ROOT, "/bin/tool")), "-rwxr-xr-x")
        self.assertEqual(mode_string(fs.stat(ROOT, "/home/alice/private")), "drwx------")
        self.assertEqual(mode_string(fs.stat(ROOT, "/link_to_notes", follow=False)), "lrwxrwxrwx")


class Links(unittest.TestCase):
    def test_symlink_followed(self):
        fs = linux()
        self.assertEqual(fs.read(ALICE, "/link_to_notes"), "hello\n")
        self.assertEqual(fs.stat(ALICE, "/link_to_notes").name, "notes.txt")
        self.assertEqual(fs.stat(ALICE, "/link_to_notes", follow=False).kind, "link")

    def test_loops_are_stopped(self):
        fs = linux()
        fs.symlink(ROOT, "/loop_b", "/loop_a")
        fs.symlink(ROOT, "/loop_a", "/loop_b")
        with self.assertRaises(FsError) as cm:
            fs.read(ROOT, "/loop_a")
        self.assertEqual(cm.exception.code, "ELOOP")

    def test_directory_symlink(self):
        fs = linux()
        fs.symlink(ALICE, "/home/alice/docs", "/home/alice/d")
        self.assertEqual(fs.read(ALICE, "/home/alice/d/a.txt"), "A")


class Globbing(unittest.TestCase):
    def test_patterns(self):
        fs = linux()
        self.assertEqual(fs.glob("*.txt", "/home/alice/docs"), ["a.txt", "c.txt"])
        self.assertEqual(fs.glob("/home/alice/docs/?.log"), ["/home/alice/docs/b.log"])
        self.assertEqual(fs.glob("*", "/home/alice"), ["docs", "notes.txt", "private"])           # hidden files are not matched by *
        self.assertEqual(fs.glob(".*", "/home/alice"), [".secret"])
        self.assertEqual(fs.glob("/home/*/todo"), ["/home/bob/todo"])
        self.assertEqual(fs.glob("*.nothing", "/home/alice/docs"), ["*.nothing"])                 # no match: pattern stays (bash behaviour)
        self.assertEqual(fs.glob("[ab].*", "/home/alice/docs"), ["a.txt", "b.log"])

    def test_walk(self):
        fs = linux()
        paths = [p for p, _ in fs.walk("/home/alice/docs")]
        self.assertEqual(paths, ["/home/alice/docs", "/home/alice/docs/a.txt", "/home/alice/docs/b.log", "/home/alice/docs/c.txt"])


class WindowsFlavour(unittest.TestCase):
    def setUp(self):
        self.fs = VFS("windows", clock=lambda: 5.0)
        self.fs.load({"Users": {"bob": {"notes.txt": "bob notes"}, "alice": {"diary.txt": "alice diary"}, "Public": {"readme.txt": "hi"}},
                      "Windows": {"System32": {"config": {"SAM": {"content": "secret", "acl": {"SYSTEM": "rw", "Administrators": "r"}}}}},
                      "Program Files": {"app": {"app.exe": "MZ"}}}, "C:\\")
        self.bob = User("bob", 1001, 1001, ("Users",), "C:\\Users\\bob")
        self.admin = User("Administrator", 500, 500, ("Administrators",), "C:\\Users\\Administrator", admin=True)

    def test_case_insensitive(self):
        self.assertEqual(self.fs.read(self.bob, "c:\\USERS\\BOB\\Notes.TXT"), "bob notes")
        self.assertTrue(self.fs.exists("C:\\users\\public\\README.txt"))

    def test_profiles_are_private(self):
        with self.assertRaises(FsError):
            self.fs.read(self.bob, "C:\\Users\\alice\\diary.txt")
        self.assertEqual(self.fs.read(self.admin, "C:\\Users\\alice\\diary.txt"), "alice diary")
        self.assertEqual(self.fs.read(self.bob, "C:\\Users\\Public\\readme.txt"), "hi")

    def test_system_folders_are_read_only_and_acls_apply(self):
        with self.assertRaises(FsError):
            self.fs.write(self.bob, "C:\\Windows\\evil.dll", "x")
        with self.assertRaises(FsError):
            self.fs.read(self.bob, "C:\\Windows\\System32\\config\\SAM")
        self.assertEqual(self.fs.read(self.admin, "C:\\Windows\\System32\\config\\SAM"), "secret")
        self.fs.write(self.bob, "C:\\Users\\bob\\new.txt", "ok")
        self.assertEqual(self.fs.read(self.bob, "C:\\Users\\bob\\new.txt"), "ok")

    def test_windows_glob(self):
        self.assertEqual(self.fs.glob("*.txt", "C:\\Users\\bob"), ["notes.txt"])


if __name__ == "__main__":
    unittest.main()
