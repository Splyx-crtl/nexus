"""UI test: the 3.0 shell engine's Qt terminal (ui/shell_terminal.py) — prompt per shell, colours, history, tab completion,
and an ssh login into a Windows target switching the prompt live. Run with QT_QPA_PLATFORM=windows (offscreen has no fonts)."""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ["NEXUS_NO_AUDIO"] = "1"
os.environ["NEXUS_LICENSE_PUBKEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from nexus.shell.machine import Service, Session
from ui.shell_terminal import ShellTerminal, make_shell
from ui.widgets import build_stylesheet, load_custom_fonts
from tests.shell_helpers import make_kali, make_windows

OUT = Path(os.environ.get("NEXUS_SHOTS", tempfile.mkdtemp(prefix="nexus_shots_")))
OUT.mkdir(exist_ok=True)
app = QApplication([])
load_custom_fonts()
app.setStyleSheet(build_stylesheet(12))

world, kali, session, shell = make_kali()
_, win, _, _ = make_windows(clock=world.clock, hostname="winbox", ip="10.0.0.9")
win.services.append(Service(22, "ssh", "OpenSSH for Windows 9.6", "open"))
world.add(win)
kali.neighbors.append(win.id)

term = ShellTerminal(shell)
term.resize(900, 560)
term.show()


def pump(ms=120):
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("ok:", msg)


pump(200)
check(term.prompt_label.text() == session.prompt(), "prompt shows the bash two-line Kali style")
check("kali" in term.prompt_label.text(), "prompt names the machine")

term.run_command("whoami")
pump()
check("player" in term.output.toPlainText(), "command output appears in the console")

term.run_command("cat /nope")
pump()
check("No such file or directory" in term.output.toPlainText(), "stderr is shown too")
cursor_html = term.output.toHtml().lower()
check("#ff3860" in cursor_html or "rgb(255" in cursor_html, "stderr line is coloured red")

term.run_command("cd docs")
pump()
check("docs" in term.prompt_label.text(), "the prompt updates after cd")

# tab completion: command name
term.input.setText("ec")
term._complete()
check(term.input.text() == "echo ", "tab-completes a unique command name")

# tab completion: file name
term.input.setText("ls a")
term._complete()
check(term.input.text() == "ls a.txt ", "tab-completes a unique file name")

# history recall
term.input.setText("")
term.input.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier))
pump()
check(term.input.text() == session.history[-1], "Up arrow recalls the last command")

term.grab().save(str(OUT / "shell_terminal_bash.png"))

# switch the whole widget to a fresh PowerShell session (what C2 will do per machine later)
ps_shell = make_shell(world, Session(win, win.users["admin"], "powershell"))
term2 = ShellTerminal(ps_shell)
term2.resize(900, 560)
term2.show()
pump(200)
check(term2.prompt_label.text() == "PS C:\\Users\\admin> ", "a PowerShell session gets the PS prompt")
term2.run_command("Get-ChildItem | Where-Object {$_.Name -eq 'notes.txt'}")
pump()
check("notes.txt" in term2.output.toPlainText(), "the PowerShell object pipeline renders a table in the console")
term2.grab().save(str(OUT / "shell_terminal_powershell.png"))
term2.close()

# ssh from the bash terminal into the Windows machine: prompt and family switch live, in the SAME widget
term.run_command("sshpass -p Winter2050! ssh Administrator@winbox")
pump(300)
check(term.prompt_label.text() == "PS C:\\Users\\admin> ", "ssh into a Windows target switches this terminal to its PowerShell prompt")
term.run_command("whoami")
pump()
check("winbox\\Administrator" in term.output.toPlainText(), "commands after ssh run on the remote Windows machine")
term.grab().save(str(OUT / "shell_terminal_ssh_windows.png"))

term.run_command("exit")
pump(200)
check("kali" in term.prompt_label.text() and "~/docs" in term.prompt_label.text(), "exit returns to the kali session, in the same directory as before")

print("SHELL TERMINAL UI OK")
sys.stdout.flush()
os._exit(0)
