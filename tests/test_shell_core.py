"""bash interpreter and the file commands, driven through real command lines."""
import unittest

from tests.shell_helpers import make_kali


class Base(unittest.TestCase):
    def setUp(self):
        self.world, self.machine, self.session, self.shell = make_kali()

    def run_(self, line):
        return self.shell.run(line)

    def out(self, line):
        return self.shell.run(line).out

    def check(self, line, expected, status=0):
        r = self.shell.run(line)
        self.assertEqual(r.out, expected, f"{line!r}\nstderr: {r.err!r}")
        self.assertEqual(r.status, status, f"{line!r} stderr: {r.err!r}")
        return r


class Interpreter(Base):
    def test_echo_and_quotes(self):
        self.check("echo hello   world", "hello world\n")
        self.check("echo 'a  b' \"c  d\"", "a  b c  d\n")
        self.check("echo -n hi", "hi")
        self.check(r"echo -e 'a\tb'", "a\tb\n")

    def test_variables(self):
        self.check("X=5; echo $X ${X}x", "5 5x\n")
        self.check("echo ${NOPE:-fallback} ${HOME}", "fallback /home/player\n")
        self.check("echo ${#HOME}", "12\n")
        self.check("F=/a/b/file.txt; echo ${F%.txt} ${F##*/}", "/a/b/file /file.txt\n".replace("/file.txt", "file.txt"))
        self.check("echo $USER $HOSTNAME", "player kali\n")
        self.check("A=1 B=2 true; echo [$A$B]", "[]\n")                                     # temporary assignment does not stay

    def test_command_substitution_and_arithmetic(self):
        self.check("echo $(echo inner) `echo tick`", "inner tick\n")
        self.check("echo $((2+3*4)) $((10/3)) $((7%4)) $((2**5))", "14 3 3 32\n")
        self.check("N=4; echo $((N*N))", "16\n")
        self.check("echo \"$(pwd)\"", "/home/player\n")

    def test_status_and_lists(self):
        self.check("true && echo yes || echo no", "yes\n")
        self.check("false && echo yes || echo no", "no\n")
        self.check("false; echo $?", "1\n")
        self.check("! false && echo negated", "negated\n")
        r = self.run_("nosuchcommand")
        self.assertEqual((r.status, r.err), (127, "bash: nosuchcommand: command not found\n"))

    def test_pipes_and_redirects(self):
        self.check("echo hi | cat", "hi\n")
        self.check("echo one > /tmp/o.txt; echo two >> /tmp/o.txt; cat /tmp/o.txt", "one\ntwo\n")
        self.check("cat < /tmp/o.txt | wc -l", "2\n")
        r = self.run_("ls /nonexistent 2>/dev/null; echo done")
        self.assertEqual((r.out, r.err), ("done\n", ""))
        r = self.run_("ls /nonexistent 2>&1 | cat")
        self.assertEqual(r.out, "ls: cannot access '/nonexistent': No such file or directory\n")
        r = self.run_("cat /nonexistent > /tmp/x 2>&1; cat /tmp/x")
        self.assertIn("No such file", r.out)
        r = self.run_("echo hi > /root/forbidden")
        self.assertEqual((r.status, r.err), (1, "bash: /root/forbidden: Permission denied\n"))

    def test_globbing(self):
        self.check("echo docs/*.txt", "docs/a.txt docs/b.txt\n")
        self.check("echo docs/?.log", "docs/c.log\n")
        self.check("echo '*.txt'", "*.txt\n")
        self.check("echo *.nothing", "*.nothing\n")
        self.check("cd docs; echo *", "a.txt b.txt c.log\n")

    def test_control_flow(self):
        self.check("for i in 1 2 3; do echo n$i; done", "n1\nn2\nn3\n")
        self.check("i=0; while [ $i -lt 3 ]; do echo $i; i=$((i+1)); done", "0\n1\n2\n")
        self.check("if [ -f notes.txt ]; then echo exists; else echo missing; fi", "exists\n")
        self.check("if [ -d nope ]; then echo d; elif [ -f notes.txt ]; then echo f; fi", "f\n")
        self.check("for f in docs/*.txt; do echo $f; done", "docs/a.txt\ndocs/b.txt\n")
        self.check("case hello in h*) echo starts-h;; *) echo other;; esac", "starts-h\n")
        self.check("for i in 1 2 3 4; do if [ $i -eq 3 ]; then break; fi; echo $i; done", "1\n2\n")
        self.check("for i in 1 2 3; do [ $i -eq 2 ] && continue; echo $i; done", "1\n3\n")

    def test_functions(self):
        self.check("greet() { echo hello $1; }; greet world", "hello world\n")
        self.check("add() { echo $(($1+$2)); }; add 2 3", "5\n")
        self.check('f() { return 3; }; f; echo $?', "3\n")
        self.check('f() { for x in "$@"; do echo "[$x]"; done; }; f "a b" c', "[a b]\n[c]\n")

    def test_test_builtin(self):
        for cond, expected in [("[ 3 -gt 2 ]", 0), ("[ 'a' = 'b' ]", 1), ("[ -z '' ]", 0), ("[ -n '' ]", 1), ("[ -e /etc/passwd ]", 0), ("[ -r /root/flag.txt ]", 1),
                               ("[ ! -e /nope ]", 0), ("[ 1 -eq 1 -a 2 -eq 2 ]", 0), ("[[ abc == a* ]]", 0), ("test -d /tmp", 0), ("[ -x tools/scan.sh ]", 0)]:
            self.assertEqual(self.run_(cond).status, expected, cond)

    def test_cd_and_pwd(self):
        self.check("cd /var/log; pwd", "/var/log\n")
        self.check("cd; pwd", "/home/player\n")
        self.check("cd /tmp; cd -", "/home/player\n")
        self.check("cd ..; pwd", "/home\n")
        r = self.run_("cd /nope")
        self.assertEqual((r.status, r.err), (1, "bash: cd: /nope: No such file or directory\n"))
        r = self.run_("cd /root")
        self.assertEqual(r.err, "bash: cd: /root: Permission denied\n")
        r = self.run_("cd /home/player/notes.txt")
        self.assertEqual(r.err, "bash: cd: /home/player/notes.txt: Not a directory\n")

    def test_scripts(self):
        self.check("./tools/scan.sh 10.0.0.9", "scanning 10.0.0.9\n")
        self.check("bash_script_missing=1; ./nope.sh", "", 127)
        r = self.run_("./notes.txt")
        self.assertEqual(r.err, "bash: ./notes.txt: Permission denied\n")
        self.machine.fs.write(self.session.user, "/home/player/loop.sh", "while true; do :; done\n")
        self.machine.fs.chmod(self.session.user, "/home/player/loop.sh", 0o755)
        r = self.run_("./loop.sh")
        self.assertIn("too many operations", r.err)

    def test_syntax_errors(self):
        r = self.run_("if true; then echo x")
        self.assertEqual(r.status, 2)
        self.assertIn("syntax error", r.err)

    def test_history_and_aliases(self):
        self.run_("echo one")
        self.run_("echo two")
        self.assertIn("echo one", self.out("history"))
        self.check("alias ll='ls -l'; alias ll", "alias ll='ls -l'\n")

    def test_subshell_does_not_leak(self):
        self.check("(cd /tmp; X=1); pwd; echo [$X]", "/home/player\n[]\n")
        self.check("{ cd /tmp; }; pwd", "/tmp\n")


class FileCommands(Base):
    def test_ls_variants(self):
        self.check("ls", "docs  notes.txt  tools\n")
        self.check("ls -1", "docs\nnotes.txt\ntools\n")
        self.check("ls -a", ".  ..  .bash_history  docs  notes.txt  tools\n")
        self.check("ls -A", ".bash_history  docs  notes.txt  tools\n")
        self.check("ls -F", "docs/  notes.txt  tools/\n")
        self.check("ls docs", "a.txt  b.txt  c.log\n")
        self.check("ls | cat", "docs\nnotes.txt\ntools\n")
        self.check("ls -d docs", "docs\n")
        self.check("ls -r docs", "c.log  b.txt  a.txt\n")

    def test_ls_long(self):
        r = self.run_("ls -l docs")
        self.assertEqual(r.out, "total 12\n-rw-r--r-- 1 player player  6 Jan  1 00:00 a.txt\n-rw-r--r-- 1 player player 14 Jan  1 00:00 b.txt\n"
                                "-rw-r--r-- 1 player player  6 Jan  1 00:00 c.log\n")
        r = self.run_("ls -la tools")
        lines = r.out.splitlines()
        self.assertEqual(lines[0], "total 12")
        self.assertTrue(lines[1].startswith("drwxr-xr-x") and lines[1].endswith(" ."))
        self.assertTrue(lines[3].startswith("-rwxr-xr-x") and lines[3].endswith("scan.sh"))

    def test_ls_errors_and_multiple(self):
        r = self.run_("ls /nope")
        self.assertEqual((r.status, r.err), (2, "ls: cannot access '/nope': No such file or directory\n"))
        r = self.run_("ls /root")
        self.assertEqual((r.status, r.err), (2, "ls: cannot open directory '/root': Permission denied\n"))
        self.check("ls docs tools", "docs:\na.txt  b.txt  c.log\n\ntools:\nscan.sh\n")
        r = self.run_("ls -z")
        self.assertEqual((r.status, r.err), (2, "ls: invalid option -- 'z'\nTry 'ls --help' for more information.\n"))

    def test_ls_recursive(self):
        self.check("ls -R tools docs", "docs:\na.txt  b.txt  c.log\n\ntools:\nscan.sh\n")
        r = self.run_("ls -R ..")
        self.assertIn("../player:", r.out)

    def test_cat_and_friends(self):
        self.check("cat notes.txt", "buy milk\ncall Mira\nfind the ARCHIVE key\n")
        self.check("cat -n docs/b.txt", "     1\tbeta\n     2\tbeta two\n")
        self.check("cat docs/a.txt docs/c.log", "alpha\ngamma\n")
        self.check("head -n 2 notes.txt", "buy milk\ncall Mira\n")
        self.check("head -1 notes.txt", "buy milk\n")
        self.check("tail -n 1 notes.txt", "find the ARCHIVE key\n")
        self.check("tail -n +3 notes.txt", "find the ARCHIVE key\n")
        self.check("cat notes.txt | wc -l", "3\n")
        self.check("wc -l notes.txt", "3 notes.txt\n")
        self.check("wc notes.txt", " 3  8 40 notes.txt\n")
        r = self.run_("cat nope")
        self.assertEqual((r.status, r.err), (1, "cat: nope: No such file or directory\n"))
        r = self.run_("cat docs")
        self.assertEqual(r.err, "cat: docs: Is a directory\n")
        r = self.run_("cat /etc/shadow")
        self.assertEqual(r.err, "cat: /etc/shadow: Permission denied\n")

    def test_create_copy_move_remove(self):
        self.check("mkdir -p a/b/c; ls a/b", "c\n")
        self.check("touch f1 f2; ls f*", "f1  f2\n")
        self.check("cp docs/a.txt copy.txt; cat copy.txt", "alpha\n")
        self.check("mv copy.txt moved.txt; ls moved.txt", "moved.txt\n")
        r = self.run_("cp docs docs2")
        self.assertEqual(r.err, "cp: -r not specified; omitting directory 'docs'\n")
        self.check("cp -r docs docs2; ls docs2", "a.txt  b.txt  c.log\n")
        self.check("rm moved.txt; ls moved.txt 2>&1", "ls: cannot access 'moved.txt': No such file or directory\n", 2)
        r = self.run_("rm docs2")
        self.assertEqual(r.err, "rm: cannot remove 'docs2': Is a directory\n")
        self.check("rm -r docs2; ls docs2 2>/dev/null; echo $?", "2\n")
        r = self.run_("rm nothing")
        self.assertEqual((r.status, r.err), (1, "rm: cannot remove 'nothing': No such file or directory\n"))
        self.check("rm -f nothing; echo $?", "0\n")
        r = self.run_("mkdir docs")
        self.assertEqual(r.err, "mkdir: cannot create directory 'docs': File exists\n")
        r = self.run_("rm -rf /")
        self.assertIn("dangerous", r.err)

    def test_permissions(self):
        self.check("chmod 600 notes.txt; ls -l notes.txt", "-rw------- 1 player player 40 Jan  1 00:00 notes.txt\n")
        self.check("chmod u+x,g+w notes.txt; ls -l notes.txt", "-rwx-w---- 1 player player 40 Jan  1 00:00 notes.txt\n")
        self.check("chmod a+x notes.txt; ls -l notes.txt", "-rwx-wx--x 1 player player 40 Jan  1 00:00 notes.txt\n")
        r = self.run_("chmod 999 notes.txt")
        self.assertEqual(r.err, "chmod: invalid mode: '999'\nTry 'chmod --help' for more information.\n")
        r = self.run_("chmod 777 /etc/passwd")
        self.assertEqual(r.err, "chmod: changing permissions of '/etc/passwd': Operation not permitted\n")

    def test_find(self):
        self.check("find docs -name '*.txt'", "docs/a.txt\ndocs/b.txt\n")
        self.check("find . -name '*.log' -type f", "./docs/c.log\n")
        self.check("find docs -type d", "docs\n")
        self.check("find . -maxdepth 1 -type d", ".\n./docs\n./tools\n")
        self.check("find . -name 'a*' -o -name 'c*'", "./docs/a.txt\n./docs/c.log\n")
        self.check("find docs -name '*.txt' -exec cat {} \\;", "alpha\nbeta\nbeta two\n")
        self.check("find /var -name auth.log", "/var/log/auth.log\n")
        r = self.run_("find /root -name x")
        self.assertEqual(r.err, "find: '/root': Permission denied\n")
        r = self.run_("find . -bogus")
        self.assertEqual(r.err, "find: unknown predicate `-bogus'\n")
        self.check("find tools -perm -100 -type f", "tools/scan.sh\n")

    def test_file_and_stat(self):
        self.check("file notes.txt", "notes.txt: ASCII text\n")
        self.check("file docs", "docs: directory\n")
        self.check("file tools/scan.sh", "tools/scan.sh: Bourne-Again shell script, ASCII text executable\n")
        self.check("file -b notes.txt", "ASCII text\n")
        self.assertIn("Size: 40", self.out("stat notes.txt"))
        self.check("basename /a/b/c.txt .txt; dirname /a/b/c.txt", "c\n/a/b\n")

    def test_tree(self):
        r = self.run_("tree docs")
        self.assertEqual(r.out, "docs\n├── a.txt\n├── b.txt\n└── c.log\n\n0 directories, 3 files\n")

    def test_help(self):
        r = self.run_("ls --help")
        self.assertTrue(r.out.startswith("Usage: ls [OPTION]... [FILE]..."))


if __name__ == "__main__":
    unittest.main()
