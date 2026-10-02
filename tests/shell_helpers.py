"""Shared test setup for the shell engine: a small Kali-like player machine and a few targets."""
from nexus.shell import commands  # noqa: F401  (registers all commands)
from nexus.shell.fs import VFS, User
from nexus.shell.interp import Shell
from nexus.shell.machine import Machine, Process, Service, Session, World

EPOCH = 2524608000.0          # 2050-01-01 00:00:00 UTC


def kali_tree() -> dict:
    return {
        "etc": {"passwd": ["root:x:0:0:root:/root:/bin/bash", "player:x:1000:1000:Player:/home/player:/bin/bash", "daemon:x:1:1::/usr/sbin:/usr/sbin/nologin"],
                "shadow": {"content": ["root:$6$salt$hash:19000:0:99999:7:::", "player:$6$x$y:19000:0:99999:7:::"], "mode": "640", "group": "shadow"},
                "hostname": "kali", "os-release": ['PRETTY_NAME="Kali GNU/Linux Rolling"', 'ID=kali']},
        "home": {"player": {"_owner": "player", "_group": "player", "notes.txt": ["buy milk", "call Mira", "find the ARCHIVE key"],
                            ".bash_history": ["ls", "cd /var/log"], "docs": {"a.txt": "alpha\n", "b.txt": "beta\nbeta two\n", "c.log": "gamma\n"},
                            "tools": {"scan.sh": {"content": ["#!/bin/bash", "echo scanning $1"], "mode": "755"}}}},
        "var": {"log": {"auth.log": ["Oct  1 10:00:01 kali sshd[1]: Failed password for root from 10.0.0.5", "Oct  1 10:00:09 kali sshd[1]: Accepted password for player from 10.0.0.9",
                                      "Oct  1 10:01:00 kali sshd[1]: Failed password for admin from 10.0.0.5"]}},
        "tmp": {"_mode": "777"},
        "usr": {"share": {"wordlists": {"rockyou.txt": ["123456", "password", "letmein", "qwerty", "nexus2050"]}}},
        "root": {"_owner": "root", "_mode": "700", "flag.txt": "root only"},
    }


def make_kali(clock=lambda: EPOCH, level=lambda: 10**6):
    world = World(clock=clock)
    m = Machine("kali", "kali", "10.0.0.2", "linux", VFS("posix", clock=clock))
    m.fs.load(kali_tree())
    m.add_user(User("root", 0, 0, ("root",), "/root", admin=True, password="toor"))
    m.add_user(User("player", 1000, 1000, ("player", "sudo"), "/home/player", password="hunter2"))
    world.add(m)
    session = Session(m, m.users["player"], "bash")
    shell = Shell(world, session, level=level)
    return world, m, session, shell


def add_web_target(world: World, source: Machine, ip: str = "10.0.0.5", hostname: str = "portal", domain: str = "nexus-company.com", open_80: bool = True) -> Machine:
    """A second machine, reachable from ``source``, serving one web page. Used by the network-command tests."""
    target = Machine(hostname, hostname, ip, "linux", VFS("posix", clock=world.clock))
    target.domain = domain
    target.add_user(User("root", 0, 0, ("root",), "/root", admin=True, password="toor"))
    target.add_user(User("alice", 1000, 1000, ("alice",), "/home/alice", password="wonderland"))
    target.fs.load({"home": {"alice": {"_owner": "alice", "_group": "alice", "todo.txt": "patch the server\n"}},
                    "root": {"_owner": "root", "_mode": "700", "flag.txt": "flag{server_pwned}\n"}})
    target.data["authorized_keys"] = {"alice": "ssh-ed25519 AAAAexamplekey alice@kali"}
    target.services = [Service(80, "http", "Apache/2.4.58", "open" if open_80 else "closed", banner="Apache/2.4.58 (Debian)",
                               data={"pages": {"/": {"body": "<html><body>Welcome to NEXUS COMPANY</body></html>", "status": 200}}}),
                       Service(22, "ssh", "OpenSSH 9.6", "open")]
    world.add(target)
    source.neighbors.append(target.id)
    world.dns[hostname] = ip
    world.dns[domain] = ip
    world.whois[domain] = "Domain Name: NEXUS-COMPANY.COM\nRegistrar: NEXUS REGISTRAR\nUpdated Date: 2049-11-03T00:00:00Z\nCreation Date: 2041-02-17T00:00:00Z"
    return target


def windows_tree() -> dict:
    return {
        "Users": {"admin": {"_owner": "admin", "_group": "admin", "notes.txt": ["buy milk", "patch the server", "rotate the backup keys"],
                            "docs": {"a.txt": "alpha\n", "b.txt": "beta\nbeta two\n", "c.log": "gamma\n"}},
                 "Public": {}},
        "Windows": {"System32": {}},
        "inetpub": {"wwwroot": {}},
    }


def make_windows(clock=lambda: EPOCH, level=lambda: 10**6, hostname: str = "winbox", ip: str = "10.0.0.9") -> tuple:
    """A standalone Windows machine with its own world: used by the PowerShell/cmd command tests."""
    world = World(clock=clock)
    m = Machine(hostname, hostname, ip, "windows", VFS("windows", clock=clock))
    m.domain = "NEXUSCORP"
    m.fs.load(windows_tree(), "C:\\")
    m.add_user(User("Administrator", 500, 500, ("Administrators",), "C:\\Users\\admin", admin=True, password="Winter2050!"))
    m.add_user(User("admin", 1000, 1000, ("Users",), "C:\\Users\\admin", password="Winter2050!"))
    m.add_user(User("guest", 1001, 1001, ("Guests",), "C:\\Users\\guest", locked=True))
    m.processes = [Process(1, "SYSTEM", "lsass.exe", "C:\\Windows\\System32\\lsass.exe", cpu=0.1, mem=0.05),
                   Process(820, "admin", "notepad.exe", "notepad.exe", cpu=0.0, mem=0.02),
                   Process(1240, "SYSTEM", "spoolsv.exe", "C:\\Windows\\System32\\spoolsv.exe", cpu=12.5, mem=0.08)]
    m.data["winservices"] = [{"Status": "Running", "Name": "Spooler", "DisplayName": "Print Spooler"},
                             {"Status": "Stopped", "Name": "wuauserv", "DisplayName": "Windows Update"}]
    world.add(m)
    session = Session(m, m.users["admin"], m.shell)
    shell = Shell(world, session, level=level)
    return world, m, session, shell


def sh(shell, line):
    return shell.run(line)
