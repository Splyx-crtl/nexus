"""PowerShell and cmd.exe command families, driven through real command lines, plus ssh from a Linux box into a Windows one."""
import unittest

from nexus.shell.machine import Process, Service, Session
from tests.shell_helpers import make_kali, make_windows


class Win(unittest.TestCase):
    def setUp(self):
        self.world, self.machine, self.session, self.shell = make_windows()

    def run_(self, line):
        return self.shell.run(line)

    def out(self, line):
        return self.shell.run(line).out

    def check(self, line, expected, status=0):
        r = self.shell.run(line)
        self.assertEqual(r.out, expected, f"{line!r}\nstderr: {r.err!r}")
        self.assertEqual(r.status, status, f"{line!r} stderr: {r.err!r}")
        return r

    def as_cmd(self):
        self.shell.session = Session(self.machine, self.session.user, "cmd")


class PowerShellBasics(Win):
    def test_identity_and_location(self):
        self.check("whoami", "winbox\\admin\n")
        self.check("hostname", "WINBOX\n")
        self.check("Get-Location", "C:\\Users\\admin\n")
        self.check("pwd", "C:\\Users\\admin\n")

    def test_navigation(self):
        self.run_("Set-Location docs")
        self.assertEqual(self.session.cwd, "C:\\Users\\admin\\docs")
        self.run_("cd ..")
        self.assertEqual(self.session.cwd, "C:\\Users\\admin")
        self.run_("cd C:\\Windows\\System32")
        self.assertEqual(self.session.cwd, "C:\\Windows\\System32")
        r = self.run_("cd C:\\nope")
        self.assertEqual(r.status, 1)
        self.assertIn("does not exist", r.err.lower())

    def test_get_childitem_table(self):
        r = self.run_("Get-ChildItem")
        self.assertIn("Mode", r.out)
        self.assertIn("docs", r.out)
        self.assertIn("notes.txt", r.out)
        r = self.run_("Get-ChildItem -Name")
        self.assertEqual(set(r.out.splitlines()), {"docs", "notes.txt"})
        r = self.run_("dir docs")
        self.assertIn("a.txt", r.out)

    def test_get_content(self):
        self.check("Get-Content notes.txt", "buy milk\npatch the server\nrotate the backup keys\n")
        self.check("type notes.txt", "buy milk\npatch the server\nrotate the backup keys\n")
        r = self.run_("Get-Content notes.txt -Tail 1")
        self.assertEqual(r.out, "rotate the backup keys\n")
        r = self.run_("cat nope.txt")
        self.assertEqual(r.status, 1)
        self.assertIn("Get-Content", r.err)

    def test_file_operations(self):
        self.run_("New-Item -ItemType Directory -Path logs")
        self.assertTrue(self.machine.fs.exists("C:\\Users\\admin\\logs"))
        self.run_("New-Item report.txt")
        self.assertTrue(self.machine.fs.exists("C:\\Users\\admin\\report.txt"))
        self.run_("Copy-Item notes.txt copy.txt")
        self.assertEqual(self.out("Get-Content copy.txt"), self.out("Get-Content notes.txt"))
        self.run_("Move-Item copy.txt moved.txt")
        self.assertFalse(self.machine.fs.exists("C:\\Users\\admin\\copy.txt"))
        self.run_("Rename-Item moved.txt final.txt")
        self.assertTrue(self.machine.fs.exists("C:\\Users\\admin\\final.txt"))
        self.run_("Remove-Item final.txt")
        self.assertFalse(self.machine.fs.exists("C:\\Users\\admin\\final.txt"))
        r = self.run_("Remove-Item docs")
        self.assertNotEqual(r.status, 0)
        self.run_("Remove-Item docs -Recurse")
        self.assertFalse(self.machine.fs.exists("C:\\Users\\admin\\docs"))

    def test_test_path(self):
        self.check("Test-Path notes.txt", "True\n")
        self.check("Test-Path nope.txt", "False\n")


class Pipeline(Win):
    def test_where_object_scriptblock(self):
        r = self.run_("Get-ChildItem | Where-Object {$_.Name -eq 'notes.txt'}")
        self.assertIn("notes.txt", r.out)
        self.assertNotIn("docs", r.out)

    def test_where_object_simple_syntax(self):
        r = self.run_("Get-Service | Where-Object Status -eq Running")
        self.assertIn("Spooler", r.out)
        self.assertNotIn("wuauserv", r.out)

    def test_foreach_object(self):
        r = self.run_("Get-ChildItem | ForEach-Object {$_.Name}")
        self.assertEqual(set(r.out.splitlines()), {"docs", "notes.txt"})

    def test_select_object(self):
        r = self.run_("Get-ChildItem | Select-Object Name")
        self.assertIn("Name", r.out)
        self.assertNotIn("Mode", r.out)
        r = self.run_("Get-ChildItem | Select-Object -First 1")
        self.assertEqual(len(r.out.strip().splitlines()), 3)          # header, separator, one row

    def test_sort_object(self):
        r = self.run_("Get-Process | Sort-Object CPU -Descending | Select-Object -First 1")
        self.assertIn("spoolsv.exe", r.out)
        r = self.run_("Get-Process | Sort-Object CPU | Select-Object -First 1")
        self.assertIn("notepad.exe", r.out)

    def test_measure_object(self):
        r = self.run_("Get-Process | Measure-Object -Property CPU -Sum")
        self.assertIn("Count", r.out)
        self.assertIn("3", r.out)

    def test_chained_pipeline(self):
        r = self.run_("Get-Service | Where-Object {$_.Status -eq 'Running'} | ForEach-Object {$_.Name}")
        self.assertEqual(r.out, "Spooler\n")

    def test_select_string(self):
        r = self.run_("Select-String -Pattern server notes.txt")
        self.assertIn("patch the server", r.out)
        self.assertIn("notes.txt", r.out)
        r = self.run_("sls milk notes.txt")
        self.assertIn("buy milk", r.out)


class ProcessesAndServices(Win):
    def test_get_process(self):
        r = self.run_("Get-Process")
        self.assertIn("spoolsv.exe", r.out)
        self.assertIn("Id", r.out)

    def test_stop_process_permission(self):
        r = self.run_("Stop-Process -Id 1")                   # owned by SYSTEM
        self.assertEqual(r.status, 1)
        self.assertIn("Access is denied", r.err)
        r = self.run_("Stop-Process -Id 820")                  # owned by admin (the current user)
        self.assertEqual(r.status, 0)
        self.assertNotIn("820", self.out("Get-Process"))

    def test_get_service_and_net_start_stop(self):
        r = self.run_("Get-Service")
        self.assertIn("Spooler", r.out)
        self.assertIn("Running", r.out)
        self.as_cmd()
        self.run_("net stop Spooler")
        self.shell.session = Session(self.machine, self.session.user, "powershell")
        r = self.run_("Get-Service -Name Spooler")
        self.assertIn("Stopped", r.out)


class Misc(Win):
    def test_write_output_and_host(self):
        self.check("Write-Output hello", "hello\n")
        self.check("echo hi there", "hi\nthere\n")                    # each argument becomes its own pipeline object
        self.check("Write-Host hi there", "hi there\n")

    def test_get_date_and_help(self):
        self.assertIn("2050", self.out("Get-Date"))
        r = self.run_("Get-Help Get-ChildItem")
        self.assertIn("Get-ChildItem", r.out)
        r = self.run_("Get-Help totally-unknown-cmdlet")
        self.assertEqual(r.status, 1)

    def test_get_local_user(self):
        r = self.run_("Get-LocalUser")
        self.assertIn("Administrator", r.out)
        self.assertIn("guest", r.out)

    def test_unknown_cmdlet(self):
        r = self.run_("Frobnicate-Everything")
        self.assertEqual(r.status, 1)
        self.assertIn("is not recognized", r.err)

    def test_level_gating(self):
        self.shell.level = lambda: 1
        r = self.run_("Select-String x notes.txt")
        self.assertEqual(r.status, 1)
        self.assertEqual(self.run_("Get-ChildItem").status, 0)
        self.shell.level = lambda: 50
        self.assertEqual(self.run_("Select-String -Pattern milk notes.txt").status, 0)

    def test_logical_operators(self):
        self.run_("New-Item ok.txt")
        r = self.run_("Get-ChildItem ok.txt && echo yes")
        self.assertIn("yes", r.out)
        r = self.run_("Get-ChildItem nope.txt || echo fallback")
        self.assertIn("fallback", r.out)


class Cmd(Win):
    def setUp(self):
        super().setUp()
        self.as_cmd()

    def test_dir_and_type(self):
        r = self.run_("dir")
        self.assertIn("Directory of", r.out)
        self.assertIn("notes.txt", r.out)
        r = self.run_("dir /b")
        self.assertEqual(set(r.out.splitlines()), {"docs", "notes.txt"})
        self.check("type notes.txt", "buy milk\npatch the server\nrotate the backup keys\n")

    def test_file_ops(self):
        self.run_("md logs")
        self.assertTrue(self.machine.fs.exists("C:\\Users\\admin\\logs"))
        self.run_("copy notes.txt copy.txt")
        self.assertTrue(self.machine.fs.exists("C:\\Users\\admin\\copy.txt"))
        self.run_("ren copy.txt renamed.txt")
        self.assertTrue(self.machine.fs.exists("C:\\Users\\admin\\renamed.txt"))
        self.run_("move renamed.txt logs\\renamed.txt")
        self.assertTrue(self.machine.fs.exists("C:\\Users\\admin\\logs\\renamed.txt"))
        self.run_("del logs\\renamed.txt")
        self.assertFalse(self.machine.fs.exists("C:\\Users\\admin\\logs\\renamed.txt"))
        self.run_("rd logs")
        self.assertFalse(self.machine.fs.exists("C:\\Users\\admin\\logs"))

    def test_echo_cls_ver_whoami(self):
        self.check("echo hello world", "hello world\n")
        self.check("whoami", "winbox\\admin\n")
        self.assertIn("Windows", self.out("ver"))

    def test_connectors(self):
        r = self.run_("echo one & echo two")
        self.assertEqual(r.out, "one\ntwo\n")
        r = self.run_("dir notes.txt && echo found")
        self.assertIn("found", r.out)
        r = self.run_("dir ghost.txt || echo missing")
        self.assertIn("missing", r.out)

    def test_set_and_expansion(self):
        self.run_("set GREETING=hi")
        self.check("echo %GREETING%", "hi\n")

    def test_redirection(self):
        self.run_("echo saved > out.txt")
        self.assertEqual(self.out("type out.txt"), "saved\n")

    def test_findstr(self):
        r = self.run_("findstr milk notes.txt")
        self.assertIn("buy milk", r.out)
        r = self.run_("findstr nowhere notes.txt")
        self.assertEqual(r.status, 1)

    def test_tasklist_taskkill(self):
        r = self.run_("tasklist")
        self.assertIn("spoolsv.exe", r.out)
        r = self.run_("taskkill /PID 1")
        self.assertEqual(r.status, 1)
        self.assertIn("Access is denied", r.err)
        r = self.run_("taskkill /PID 820")
        self.assertEqual(r.status, 0)

    def test_net_user_and_services(self):
        r = self.run_("net user")
        self.assertIn("admin", r.out)
        r = self.run_("net user admin")
        self.assertIn("User name", r.out)
        self.assertEqual(self.run_("net user nope").status, 2)

    def test_ipconfig_ping(self):
        r = self.run_("ipconfig")
        self.assertIn("10.0.0.9", r.out)
        r = self.run_("ping 10.0.0.9")
        self.assertIn("Pinging 10.0.0.9", r.out)
        self.assertIn("Lost = 0", r.out)
        r = self.run_("ping -n 2 10.0.0.9")
        self.assertEqual(r.out.count("Reply from"), 2)

    def test_tree_and_attrib(self):
        r = self.run_("tree")
        self.assertIn("docs", r.out)
        r = self.run_("attrib notes.txt")
        self.assertIn("notes.txt", r.out)

    def test_unknown_command(self):
        r = self.run_("notacommand")
        self.assertEqual(r.status, 1)
        self.assertIn("is not recognized", r.out)

    def test_powershell_falls_back_to_legacy_cmd_tools(self):
        self.shell.session = Session(self.machine, self.session.user, "powershell")
        r = self.run_("ipconfig")                               # no native PS cmdlet for this; PowerShell can still run it
        self.assertIn("10.0.0.9", r.out)
        r = self.run_("net user admin")
        self.assertIn("User name", r.out)


class SshIntoWindows(unittest.TestCase):
    def setUp(self):
        self.world, self.kali, self.session, self.shell = make_kali()
        _, self.win, _, _ = make_windows(clock=self.world.clock, hostname="winbox", ip="10.0.0.9")
        self.win.services.append(Service(22, "ssh", "OpenSSH for Windows 9.6", "open"))
        self.world.add(self.win)
        self.kali.neighbors.append(self.win.id)

    def test_login_gets_the_target_shell_and_cwd(self):
        r = self.shell.run("sshpass -p Winter2050! ssh Administrator@winbox")
        self.assertEqual(r.status, 0)
        self.assertEqual(self.shell.session.machine.id, "winbox")
        self.assertEqual(self.shell.session.shell, "powershell")
        self.assertEqual(self.shell.session.cwd, "C:\\Users\\admin")
        self.assertEqual(self.shell.run("whoami").out, "winbox\\Administrator\n")
        r = self.shell.run("Get-ChildItem | ForEach-Object {$_.Name}")
        self.assertEqual(set(r.out.splitlines()), {"docs", "notes.txt"})
        r = self.shell.run("exit")
        self.assertIn("Connection to 10.0.0.9 closed", r.out)
        self.assertEqual(self.shell.session.machine.id, "kali")
        self.assertEqual(self.shell.run("whoami").out, "player\n")

    def test_one_shot_remote_command_uses_the_target_shell(self):
        r = self.shell.run("sshpass -p Winter2050! ssh Administrator@winbox whoami")
        self.assertEqual(r.status, 0)
        self.assertIn("winbox\\Administrator", r.out)
        self.assertEqual(self.shell.session.machine.id, "kali")              # one-shot: back home immediately

    def test_wrong_credentials(self):
        r = self.shell.run("sshpass -p wrong ssh Administrator@winbox")
        self.assertEqual(r.status, 255)
        self.assertIn("Permission denied", r.err)


if __name__ == "__main__":
    unittest.main()
