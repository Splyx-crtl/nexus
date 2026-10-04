"""B8: .ps1 script files and .bat/.cmd batch files — control flow (if/foreach/for/while, if/for) on top of the
single-line PowerShell and cmd.exe engines."""
import unittest

from tests.shell_helpers import make_windows


class Win(unittest.TestCase):
    def setUp(self):
        self.world, self.machine, self.session, self.shell = make_windows()

    def run_(self, line):
        return self.shell.run(line)

    def out(self, line):
        return self.shell.run(line).out

    def write_ps1(self, name, text):
        self.machine.fs.write(self.session.user, name, text, self.session.cwd)


class PsAuthoring(Win):
    """Set-Content/Add-Content/Out-File — writing a .ps1 script from inside the game itself, no Python shortcut."""

    def test_set_content_then_run_as_script(self):
        self.run_("Set-Content -Path t.ps1 -Value 'Write-Output \"built in game\"'")
        self.assertEqual(self.out(".\\t.ps1"), "built in game\n")

    def test_add_content_builds_a_multiline_script(self):
        self.run_("Set-Content -Path t.ps1 -Value 'Write-Output \"line1\"'")
        self.run_("Add-Content -Path t.ps1 -Value 'Write-Output \"line2\"'")
        self.assertEqual(self.out(".\\t.ps1"), "line1\nline2\n")

    def test_add_content_can_build_control_flow(self):
        self.run_("Set-Content -Path t.ps1 -Value 'foreach ($x in 1..3) {'")
        self.run_("Add-Content -Path t.ps1 -Value 'Write-Output $x'")
        self.run_("Add-Content -Path t.ps1 -Value '}'")
        self.assertEqual(self.out(".\\t.ps1"), "1\n2\n3\n")

    def test_out_file_from_a_pipeline(self):
        self.run_('Write-Output "piped" | Out-File -FilePath o.txt')
        self.assertEqual(self.out("Get-Content o.txt"), "piped\n")

    def test_out_file_append(self):
        self.run_('Write-Output "one" | Out-File -FilePath o.txt')
        self.run_('Write-Output "two" | Out-File -FilePath o.txt -Append')
        self.assertEqual(self.out("Get-Content o.txt"), "one\ntwo\n")


class PsIfElse(Win):
    def test_if_true_branch(self):
        self.write_ps1("t.ps1", "if (1 -eq 1) { Write-Output 'yes' } else { Write-Output 'no' }\n")
        r = self.run_(".\\t.ps1")
        self.assertEqual(r.out, "yes\n")
        self.assertEqual(r.status, 0)

    def test_if_false_branch_runs_else(self):
        self.write_ps1("t.ps1", "if (1 -eq 2) { Write-Output 'yes' } else { Write-Output 'no' }\n")
        self.assertEqual(self.out(".\\t.ps1"), "no\n")

    def test_elseif_chain(self):
        self.write_ps1("t.ps1", "$x = 2\nif ($x -eq 1) { Write-Output 'one' } elseif ($x -eq 2) { Write-Output 'two' } else { Write-Output 'other' }\n")
        self.assertEqual(self.out(".\\t.ps1"), "two\n")

    def test_no_else_and_condition_false_does_nothing(self):
        self.write_ps1("t.ps1", "if (1 -eq 2) { Write-Output 'yes' }\nWrite-Output 'after'\n")
        self.assertEqual(self.out(".\\t.ps1"), "after\n")


class PsLoops(Win):
    def test_foreach_over_array_literal(self):
        self.write_ps1("t.ps1", "foreach ($x in @(1,2,3)) { Write-Output $x }\n")
        self.assertEqual(self.out(".\\t.ps1"), "1\n2\n3\n")

    def test_foreach_over_range(self):
        self.write_ps1("t.ps1", "foreach ($x in 1..3) { Write-Output $x }\n")
        self.assertEqual(self.out(".\\t.ps1"), "1\n2\n3\n")

    def test_foreach_over_variable_set_earlier(self):
        self.write_ps1("t.ps1", "$names = @('a','b')\nforeach ($n in $names) { Write-Output $n }\n")
        self.assertEqual(self.out(".\\t.ps1"), "a\nb\n")

    def test_classic_for_loop(self):
        self.write_ps1("t.ps1", "for ($i = 0; $i -lt 3; $i++) { Write-Output $i }\n")
        self.assertEqual(self.out(".\\t.ps1"), "0\n1\n2\n")

    def test_while_loop(self):
        self.write_ps1("t.ps1", "$i = 0\nwhile ($i -lt 3) { Write-Output $i; $i = $i + 1 }\n")
        self.assertEqual(self.out(".\\t.ps1"), "0\n1\n2\n")

    def test_loop_accumulator_with_plus_equals(self):
        self.write_ps1("t.ps1", "$total = 0\nforeach ($x in @(1,2,3)) { $total += $x }\nWrite-Output $total\n")
        self.assertEqual(self.out(".\\t.ps1"), "6\n")


class PsScriptMisc(Win):
    def test_sequential_cmdlets_run_in_order(self):
        self.write_ps1("t.ps1", "Write-Output 'first'\nWrite-Output 'second'\n")
        self.assertEqual(self.out(".\\t.ps1"), "first\nsecond\n")

    def test_comments_and_blank_lines_ignored(self):
        self.write_ps1("t.ps1", "# a comment\n\nWrite-Output 'hi'\n# trailing\n")
        self.assertEqual(self.out(".\\t.ps1"), "hi\n")

    def test_missing_script_reports_error(self):
        r = self.run_(".\\missing.ps1")
        self.assertEqual(r.status, 1)
        self.assertIn("missing.ps1", r.err)

    def test_real_cmdlet_inside_loop_body(self):
        self.write_ps1("t.ps1", "foreach ($x in 1..2) { Get-Process | Measure-Object }\n")
        r = self.run_(".\\t.ps1")
        self.assertEqual(r.status, 0)

    def test_script_lines_do_not_pollute_history_individually(self):
        self.write_ps1("t.ps1", "Write-Output 'a'\nWrite-Output 'b'\n")
        self.run_(".\\t.ps1")
        self.assertEqual(self.session.history[-1], ".\\t.ps1")
        self.assertNotIn("Write-Output 'a'", self.session.history)


class CmdBatch(Win):
    def write_bat(self, name, text):
        self.machine.fs.write(self.session.user, name, text, self.session.cwd)

    def as_cmd(self):
        from nexus.shell.machine import Session
        self.shell.session = Session(self.machine, self.session.user, "cmd")
        self.session = self.shell.session

    def test_sequential_commands(self):
        self.as_cmd()
        self.write_bat("t.bat", "echo first\necho second\n")
        self.assertEqual(self.out("t.bat"), "first\nsecond\n")

    def test_echo_off_and_rem_are_ignored(self):
        self.as_cmd()
        self.write_bat("t.bat", "@echo off\nrem a comment\necho hi\n")
        self.assertEqual(self.out("t.bat"), "hi\n")

    def test_if_equal_true_branch(self):
        self.as_cmd()
        self.write_bat("t.bat", "set X=1\nif %X%==1 (\necho yes\n) else (\necho no\n)\n")
        self.assertEqual(self.out("t.bat"), "yes\n")

    def test_if_equal_false_branch_runs_else(self):
        self.as_cmd()
        self.write_bat("t.bat", "set X=2\nif %X%==1 (\necho yes\n) else (\necho no\n)\n")
        self.assertEqual(self.out("t.bat"), "no\n")

    def test_if_exist(self):
        self.as_cmd()
        self.write_bat("t.bat", "echo hi > present.txt\nif exist present.txt (\necho found\n) else (\necho missing\n)\n")
        self.assertEqual(self.out("t.bat"), "found\n")

    def test_if_not_exist(self):
        self.as_cmd()
        self.write_bat("t.bat", "if not exist nope.txt (\necho missing\n) else (\necho found\n)\n")
        self.assertEqual(self.out("t.bat"), "missing\n")

    def test_for_loop_over_list(self):
        self.as_cmd()
        self.write_bat("t.bat", "for %%v in (alpha beta gamma) do echo %%v\n")
        self.assertEqual(self.out("t.bat"), "alpha\nbeta\ngamma\n")

    def test_missing_batch_file_reports_error(self):
        self.as_cmd()
        r = self.run_("missing.bat")
        self.assertEqual(r.status, 1)
        self.assertIn("not recognized", r.err)


if __name__ == "__main__":
    unittest.main()
