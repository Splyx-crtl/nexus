"""Text-processing and system commands through real command lines."""
import unittest

from tests.test_shell_core import Base


class Grep(Base):
    def test_basic(self):
        self.check("grep ARCHIVE notes.txt", "find the ARCHIVE key\n")
        self.check("grep -i archive notes.txt", "find the ARCHIVE key\n")
        self.check("grep -n milk notes.txt", "1:buy milk\n")
        self.check("grep -c a docs/b.txt", "2\n")
        self.check("grep -v milk notes.txt", "call Mira\nfind the ARCHIVE key\n")
        self.check("grep nomatch notes.txt", "", 1)
        self.check("grep -q milk notes.txt; echo $?", "0\n")
        self.check("grep -l beta docs/*", "docs/b.txt\n")
        self.check("cat /var/log/auth.log | grep Failed | wc -l", "2\n")

    def test_patterns(self):
        self.check("grep -E 'Failed|Accepted' /var/log/auth.log | wc -l", "3\n")
        self.check("grep 'Failed\\|Accepted' /var/log/auth.log | wc -l", "3\n")
        self.check("grep -o '10\\.0\\.0\\.[0-9]*' /var/log/auth.log", "10.0.0.5\n10.0.0.9\n10.0.0.5\n")
        self.check("grep -w beta docs/b.txt", "beta\nbeta two\n")
        self.check("grep -F 'a.b' notes.txt", "", 1)
        self.check("grep '^call' notes.txt", "call Mira\n")
        self.check("grep 'key$' notes.txt", "find the ARCHIVE key\n")
        self.check("grep '[[:digit:]]' notes.txt", "", 1)
        self.check("grep -E 'o+' docs/b.txt", "beta two\n")

    def test_context_and_multiple_files(self):
        self.check("grep -A1 milk notes.txt", "buy milk\ncall Mira\n")
        self.check("grep -B1 ARCHIVE notes.txt", "call Mira\nfind the ARCHIVE key\n")
        self.check("grep alpha docs/a.txt docs/b.txt", "docs/a.txt:alpha\n")
        self.check("grep -h alpha docs/a.txt docs/b.txt", "alpha\n")
        self.check("grep -c . docs/a.txt docs/b.txt", "docs/a.txt:1\ndocs/b.txt:2\n")

    def test_recursive(self):
        r = self.run_("grep -rn beta docs")
        self.assertEqual(r.out, "docs/b.txt:1:beta\ndocs/b.txt:2:beta two\n")
        r = self.run_("grep -r gamma .")
        self.assertEqual(r.out, "./docs/c.log:gamma\n")
        r = self.run_("grep -r alpha")
        self.assertEqual(r.out, "docs/a.txt:alpha\n")

    def test_errors(self):
        r = self.run_("grep x nofile")
        self.assertEqual((r.status, r.err), (2, "grep: nofile: No such file or directory\n"))
        r = self.run_("grep x docs")
        self.assertEqual(r.err, "grep: docs: Is a directory\n")
        r = self.run_("grep")
        self.assertEqual(r.status, 2)
        r = self.run_("grep -E '(' notes.txt")
        self.assertEqual(r.status, 2)


class SortAndFriends(Base):
    def test_sort_uniq(self):
        self.check("printf 'b\\na\\nb\\nc\\n' | sort", "a\nb\nb\nc\n")
        self.check("printf 'b\\na\\nb\\nc\\n' | sort -r", "c\nb\nb\na\n")
        self.check("printf 'b\\na\\nb\\nc\\n' | sort -u", "a\nb\nc\n")
        self.check("printf 'b\\na\\nb\\nc\\n' | sort | uniq -c", "      1 a\n      2 b\n      1 c\n")
        self.check("printf '10\\n9\\n100\\n' | sort -n", "9\n10\n100\n")
        self.check("printf '10\\n9\\n100\\n' | sort", "10\n100\n9\n")
        self.check("printf 'b\\na\\nb\\nb\\n' | sort | uniq -c | sort -nr | head -1", "      3 b\n")
        self.check("printf 'a\\na\\nb\\n' | uniq -d", "a\n")
        self.check("sort -t: -k3 -n /etc/passwd | cut -d: -f1", "root\ndaemon\nplayer\n")

    def test_cut_tr(self):
        self.check("cut -d: -f1 /etc/passwd", "root\nplayer\ndaemon\n")
        self.check("cut -d: -f1,3 /etc/passwd | head -1", "root:0\n")
        self.check("cut -c1-3 notes.txt", "buy\ncal\nfin\n")
        self.check("echo hello | tr a-z A-Z", "HELLO\n")
        self.check("echo hello | tr -d l", "heo\n")
        self.check("echo 'aaabbb' | tr -s a", "abbb\n")
        self.check("echo hello | tr 'el' 'ip'", "hippo\n")
        self.check("echo hi | rev", "ih\n")

    def test_tee_seq_nl_diff(self):
        self.check("echo data | tee /tmp/t.txt; cat /tmp/t.txt", "data\ndata\n")
        self.check("seq 3", "1\n2\n3\n")
        self.check("seq 2 4", "2\n3\n4\n")
        self.check("seq 1 2 7", "1\n3\n5\n7\n")
        self.check("echo x | nl", "     1\tx\n")
        self.check("diff docs/a.txt docs/a.txt", "")
        r = self.run_("diff docs/a.txt docs/b.txt")
        self.assertEqual(r.status, 1)
        self.assertIn("alpha", r.out)
        self.check("diff -q docs/a.txt docs/b.txt", "Files docs/a.txt and docs/b.txt differ\n", 1)

    def test_xargs(self):
        self.check("echo a b c | xargs echo x", "x a b c\n")
        self.check("find docs -name '*.txt' | xargs cat", "alpha\nbeta\nbeta two\n")
        self.check("echo a b c | xargs -n 1 echo", "a\nb\nc\n")
        self.check("printf 'x\\ny\\n' | xargs -I {} echo item-{}", "item-x\nitem-y\n")

    def test_sleep_adds_delay_not_time(self):
        r = self.run_("sleep 2")
        self.assertEqual((r.status, r.delay_ms), (0, 2000))
        self.assertEqual(self.run_("sleep abc").status, 1)


class Sed(Base):
    def test_substitute(self):
        self.check("sed 's/milk/water/' notes.txt", "buy water\ncall Mira\nfind the ARCHIVE key\n")
        self.check("echo aaa | sed 's/a/b/'", "baa\n")
        self.check("echo aaa | sed 's/a/b/g'", "bbb\n")
        self.check("echo 'hello world' | sed 's/\\(hello\\) \\(world\\)/\\2 \\1/'", "world hello\n")
        self.check("echo 'a.b' | sed 's|\\.|-|'", "a-b\n")
        self.check("echo hello | sed -E 's/(l+)/[\\1]/'", "he[ll]o\n")
        self.check("echo abc | sed 's/b/[&]/'", "a[b]c\n")

    def test_addresses_and_commands(self):
        self.check("sed -n 2p notes.txt", "call Mira\n")
        self.check("sed 2d notes.txt", "buy milk\nfind the ARCHIVE key\n")
        self.check("sed -n '/call/p' notes.txt", "call Mira\n")
        self.check("sed -n '2,3p' notes.txt", "call Mira\nfind the ARCHIVE key\n")
        self.check("sed '$d' notes.txt", "buy milk\ncall Mira\n")
        self.check("sed -n '$p' notes.txt", "find the ARCHIVE key\n")
        self.check("sed '/milk/d' notes.txt", "call Mira\nfind the ARCHIVE key\n")
        self.check("sed -e 's/buy/get/' -e 's/milk/tea/' notes.txt | head -1", "get tea\n")
        self.check("echo abc | sed 'y/abc/xyz/'", "xyz\n")

    def test_in_place(self):
        self.check("cp notes.txt n2.txt; sed -i 's/milk/oat milk/' n2.txt; head -1 n2.txt", "buy oat milk\n")


class Awk(Base):
    def test_fields(self):
        self.check("awk '{print $1}' notes.txt", "buy\ncall\nfind\n")
        self.check("awk '{print $2, $1}' notes.txt | head -1", "milk buy\n")
        self.check("awk -F: '{print $1}' /etc/passwd", "root\nplayer\ndaemon\n")
        self.check("awk -F: '{print $1 \" -> \" $7}' /etc/passwd | head -1", "root -> /bin/bash\n")
        self.check("awk '{print $NF}' notes.txt", "milk\nMira\nkey\n")
        self.check("awk '{print NR \": \" $0}' docs/b.txt", "1: beta\n2: beta two\n")
        self.check("echo 'a b c' | awk '{print NF}'", "3\n")

    def test_patterns_and_blocks(self):
        self.check("awk 'NR==2' notes.txt", "call Mira\n")
        self.check("awk '/Failed/ {n++} END {print n}' /var/log/auth.log", "2\n")
        self.check("awk -F: '$3 >= 1000 {print $1}' /etc/passwd", "player\n")
        self.check("awk '{s += NF} END {print s}' notes.txt", "8\n")
        self.check("awk 'BEGIN {print \"start\"} {print $1} END {print \"end\"}' docs/a.txt", "start\nalpha\nend\n")
        self.check("awk 'length($0) > 9' notes.txt", "find the ARCHIVE key\n")
        self.check("awk '{print toupper($1)}' docs/a.txt", "ALPHA\n")
        self.check("awk -v n=2 'NR==n {print}' notes.txt", "call Mira\n")
        self.check("awk '{ if ($1 == \"call\") print \"match\"; else print \"no\" }' notes.txt", "no\nmatch\nno\n")
        self.check("awk '!/milk/' notes.txt", "call Mira\nfind the ARCHIVE key\n")

    def test_printf_and_arrays(self):
        self.check("echo 'x 3' | awk '{printf \"%s=%d\\n\", $1, $2}'", "x=3\n")
        self.check("printf 'a\\nb\\na\\n' | awk '{c[$1]++} END {for (k in c) print k, c[k]}' | sort", "a 2\nb 1\n")
        self.check("awk 'BEGIN {x = 2 + 3 * 4; print x}'", "14\n")


class SystemCommands(Base):
    def test_identity(self):
        self.check("whoami", "player\n")
        self.check("id", "uid=1000(player) gid=1000(player) groups=1000(player),1001(sudo)\n")
        self.check("id -u", "1000\n")
        self.check("groups", "player sudo\n")
        self.check("hostname", "kali\n")
        self.check("hostname -I", "10.0.0.2\n")
        self.check("uname", "Linux\n")
        self.assertTrue(self.out("uname -a").startswith("Linux kali "))
        self.check("date", "Sat Jan  1 00:00:00 UTC 2050\n")
        self.check("date +%Y-%m-%d", "2050-01-01\n")

    def test_environment(self):
        self.check("env | grep ^HOME", "HOME=/home/player\n")
        self.check("printenv USER", "player\n")
        self.check("export FOO=bar; printenv FOO", "bar\n")
        self.check("env FOO=1 printenv FOO", "1\n")
        self.check("echo $FOO", "bar\n")                       # an exported variable stays for the rest of the session
        self.check("unset FOO; echo [$FOO]", "[]\n")

    def test_which_man_help(self):
        self.check("which ls", "/usr/bin/ls\n")
        self.check("which nothing", "", 1)
        r = self.run_("man ls")
        self.assertIn("list directory contents", r.out)
        r = self.run_("man doesnotexist")
        self.assertEqual((r.status, r.err), (16, "No manual entry for doesnotexist\n"))
        self.assertIn("cd:", self.out("help cd"))
        self.assertIn("ls", self.out("help"))
        self.check("type cd", "cd is a shell builtin\n")
        self.check("type ls", "ls is /usr/bin/ls\n")
        self.check("command -v ls", "/usr/bin/ls\n")

    def test_processes(self):
        from nexus.shell.machine import Process
        self.machine.processes = [Process(1, "root", "init", "/sbin/init"), Process(412, "root", "sshd", "/usr/sbin/sshd -D"), Process(900, "player", "bash", "-bash")]
        out = self.out("ps aux")
        self.assertIn("/usr/sbin/sshd -D", out)
        self.assertTrue(out.startswith("USER         PID %CPU %MEM"))
        r = self.run_("kill 412")
        self.assertEqual(r.err, "bash: kill: (412) - Operation not permitted\n")
        self.assertEqual(self.run_("kill 900").status, 0)
        self.assertNotIn("900", self.out("ps aux").split("ps aux")[0])
        self.assertEqual(self.run_("kill 9999").status, 1)

    def test_sudo(self):
        self.check("sudo whoami", "root\n")
        self.check("whoami", "player\n")
        self.assertIn("root:$6$", self.out("sudo cat /etc/shadow"))
        r = self.run_("sudo -l")
        self.assertIn("(ALL : ALL) NOPASSWD: ALL", r.out)
        self.check("sudo -u root id -u", "0\n")
        self.session.user = self.machine.users["root"]
        self.check("cat /root/flag.txt", "root only")
        self.session.user = self.machine.users["player"]
        self.machine.data["sudoers"] = {}
        r = self.run_("sudo whoami")
        self.assertEqual((r.status, r.err), (1, "player is not in the sudoers file.\n"))
        self.machine.data["sudoers"] = {"player": {"commands": "/usr/bin/find", "nopasswd": True}}
        self.check("sudo find /root -name flag.txt", "/root/flag.txt\n")
        r = self.run_("sudo cat /etc/shadow")
        self.assertIn("not allowed to execute", r.err)

    def test_scripts_with_bash_command(self):
        self.check("bash tools/scan.sh 1.2.3.4", "scanning 1.2.3.4\n")
        self.check("bash -c 'echo hi; echo there'", "hi\nthere\n")
        r = self.run_("bash nofile.sh")
        self.assertEqual(r.status, 127)

    def test_level_gating(self):
        self.shell.level = lambda: 2
        r = self.run_("grep a notes.txt")
        self.assertEqual((r.status, r.err), (127, "bash: grep: command not found\n"))
        self.assertEqual(self.run_("ls").status, 0)
        self.assertEqual(self.run_("man grep").status, 16)
        hints = []
        self.shell.locked_hint = lambda spec: f"(locked until level {spec.level})"
        self.assertIn("locked until level 8", self.out("grep a notes.txt"))
        self.shell.level = lambda: 50
        self.assertEqual(self.run_("grep milk notes.txt").status, 0)


if __name__ == "__main__":
    unittest.main()
