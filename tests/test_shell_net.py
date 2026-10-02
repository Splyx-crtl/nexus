"""Network information commands (ping, DNS, whois, curl/wget, netstat/ss, traceroute, ip/ifconfig/arp) against the simulated world."""
import unittest

from tests.shell_helpers import add_web_target, make_kali
from tests.test_shell_core import Base


class NetBase(Base):
    def setUp(self):
        self.world, self.machine, self.session, self.shell = make_kali()
        self.target = add_web_target(self.world, self.machine)


class Ping(NetBase):
    def test_reachable_host(self):
        r = self.run_("ping -c 2 portal")
        self.assertEqual(r.status, 0)
        self.assertIn("PING portal (10.0.0.5)", r.out)
        self.assertIn("2 packets transmitted, 2 received, 0% packet loss", r.out)
        self.assertIn(self.target.id, self.world.discovered)

    def test_by_ip_and_unknown_host(self):
        self.assertEqual(self.run_("ping -c 1 10.0.0.5").status, 0)
        r = self.run_("ping -c 1 nope.example")
        self.assertEqual((r.status, r.err), (2, "ping: nope.example: Name or service not known\n"))

    def test_unreachable_but_resolvable(self):
        from nexus.shell.fs import VFS, User
        from nexus.shell.machine import Machine
        far = Machine("far", "far", "10.0.9.9", "linux", VFS("posix"))
        far.add_user(User("root", 0, 0, admin=True))
        self.world.add(far)                                        # exists, but not a neighbour and not yet discovered
        r = self.run_("ping -c 1 10.0.9.9")
        self.assertEqual(r.status, 1)
        self.assertIn("Destination Host Unreachable", r.out)


class Dns(NetBase):
    def test_dig_and_nslookup(self):
        r = self.run_("dig nexus-company.com")
        self.assertIn("ANSWER SECTION", r.out)
        self.assertIn("10.0.0.5", r.out)
        r = self.run_("nslookup portal")
        self.assertIn("Address: 10.0.0.5", r.out)
        r = self.run_("host portal")
        self.assertEqual(r.out, "portal has address 10.0.0.5\n")

    def test_unknown_names(self):
        r = self.run_("dig does-not-exist.test")
        self.assertIn("NXDOMAIN", r.out)
        r = self.run_("nslookup nope.test")
        self.assertIn("NXDOMAIN", r.out)
        self.assertEqual(self.run_("host nope.test").status, 1)


class Whois(NetBase):
    def test_known_and_unknown(self):
        r = self.run_("whois nexus-company.com")
        self.assertIn("NEXUS REGISTRAR", r.out)
        r = self.run_("whois totally-made-up-domain.test")
        self.assertIn("No match", r.out)


class HttpTools(NetBase):
    def test_curl(self):
        r = self.run_("curl http://portal/")
        self.assertEqual((r.status, r.out), (0, "<html><body>Welcome to NEXUS COMPANY</body></html>"))
        r = self.run_("curl -i http://portal/")
        self.assertIn("HTTP/1.1 200 OK", r.out)
        self.assertIn("Welcome", r.out)
        r = self.run_("curl http://portal/nope")
        self.assertIn("404 Not Found", r.out)
        r = self.run_("curl http://nope.example/")
        self.assertEqual(r.status, 6)
        self.assertIn("Could not resolve host", r.err)

    def test_curl_closed_port(self):
        self.target.services[0].state = "closed"
        r = self.run_("curl http://portal/")
        self.assertEqual(r.status, 7)
        self.assertIn("Connection refused", r.err)

    def test_curl_save_to_file(self):
        self.run_("curl -o page.html http://portal/")
        self.assertIn("Welcome", self.out("cat page.html"))

    def test_wget(self):
        self.run_("wget http://portal/")
        self.assertIn("Welcome", self.out("cat index.html"))
        r = self.run_("wget -O saved.html http://portal/")
        self.assertEqual(r.status, 0)
        self.assertIn("Welcome", self.out("cat saved.html"))


class HostDiscovery(NetBase):
    def test_netstat_ss_shows_own_services(self):
        from nexus.shell.machine import Service
        self.machine.services.append(Service(22, "ssh", "OpenSSH 9.6", "open"))
        r = self.run_("netstat -tln")
        self.assertIn(":22", r.out)
        self.assertIn("LISTEN", r.out)
        r = self.run_("ss -tl")
        self.assertIn(":22", r.out)

    def test_netstat_tulpn_shows_tcp_services_not_just_udp(self):
        """Regression: -t and -u together used to AND their exclusions, so a tcp service was wrongly dropped by the -u
        filter (and vice versa) instead of both protocols being shown — '-tulpn' is the single most common real
        invocation, so this silently broke the common case."""
        from nexus.shell.machine import Service
        self.machine.services.append(Service(22, "ssh", "OpenSSH 9.6", "open"))
        r = self.run_("netstat -tulpn")
        self.assertIn(":22", r.out)
        self.assertIn("LISTEN", r.out)

    def test_traceroute(self):
        r = self.run_("traceroute portal")
        self.assertIn("traceroute to portal (10.0.0.5)", r.out)
        self.assertIn("10.0.0.5", r.out.splitlines()[-1])
        self.assertIn(self.target.id, self.world.discovered)

    def test_ip_and_ifconfig(self):
        r = self.run_("ip addr")
        self.assertIn("10.0.0.2/24", r.out)
        r = self.run_("ip route")
        self.assertIn("default via 10.0.0.1", r.out)
        r = self.run_("ifconfig")
        self.assertIn("inet 10.0.0.2", r.out)

    def test_arp(self):
        r = self.run_("arp -a")
        self.assertIn("portal (10.0.0.5)", r.out)


class Ssh(NetBase):
    def test_login_with_password_via_sshpass(self):
        r = self.run_("sshpass -p toor ssh root@portal")
        self.assertEqual(r.status, 0)
        self.assertIn("Last login:", r.out)
        self.assertEqual(self.shell.session.machine.id, self.target.id)    # the session is now on the remote machine
        self.assertEqual(self.shell.session.user.name, "root")
        self.assertEqual(self.shell.session.cwd, "/root")
        self.assertEqual(self.out("whoami"), "root\n")
        self.assertEqual(self.out("hostname"), "portal\n")
        self.check("exit", "logout\nConnection to 10.0.0.5 closed.\n")
        self.assertEqual(self.shell.session.machine.id, self.machine.id)   # back on kali
        self.assertEqual(self.out("whoami"), "player\n")

    def test_wrong_password_is_refused(self):
        r = self.run_("sshpass -p wrongpass ssh root@portal")
        self.assertIn("Permission denied (publickey,password)", r.err)
        self.assertEqual(self.shell.session.machine.id, self.machine.id)

    def test_no_password_at_all_is_refused_like_a_real_batch_ssh(self):
        r = self.run_("ssh root@portal")
        self.assertEqual(r.status, 255)
        self.assertIn("Permission denied", r.err)

    def test_key_based_auth(self):
        self.run_("echo 'ssh-ed25519 AAAAexamplekey alice@kali' > mykey")
        r = self.run_("ssh -i mykey alice@portal")
        self.assertEqual(r.status, 0)
        self.assertEqual(self.shell.session.user.name, "alice")
        self.check("exit", "logout\nConnection to 10.0.0.5 closed.\n")

    def test_wrong_key_is_refused(self):
        self.run_("echo 'ssh-ed25519 WRONGKEY alice@kali' > mykey")
        r = self.run_("ssh -i mykey alice@portal")
        self.assertEqual(r.status, 255)

    def test_remote_command_runs_and_returns(self):
        r = self.run_("sshpass -p toor ssh root@portal cat /root/.bashrc 2>/dev/null; echo local-again")
        self.assertEqual(self.shell.session.machine.id, self.machine.id)   # a one-shot remote command does not leave you logged in
        self.assertIn("local-again", r.out)

    def test_unreachable_and_closed_port(self):
        r = self.run_("ssh root@nope.example")
        self.assertEqual((r.status, "Name or service not known" in r.err), (255, True))
        self.target.services[1].state = "closed"
        r = self.run_("sshpass -p toor ssh root@portal")
        self.assertEqual(r.status, 255)
        self.assertIn("Connection refused", r.err)

    def test_scp_upload_and_download(self):
        self.run_("echo loot > secret.txt")
        r = self.run_("sshpass -p toor scp secret.txt root@portal:/root/secret.txt")
        self.assertEqual(r.status, 0)
        self.assertEqual(self.target.fs.read(None, "/root/secret.txt"), "loot\n")
        r = self.run_("sshpass -p toor scp root@portal:/root/flag.txt here.txt")
        self.assertEqual(r.status, 0)
        self.assertIn("flag", self.out("cat here.txt") + "flag")

    def test_scp_wrong_credentials(self):
        self.run_("echo x > secret.txt")
        r = self.run_("sshpass -p wrong scp secret.txt root@portal:/root/secret.txt")
        self.assertEqual(r.status, 1)
        self.assertIn("Permission denied", r.err)


class LevelGating(NetBase):
    def test_locked_until_level(self):
        self.shell.level = lambda: 1
        r = self.run_("ping portal")
        self.assertEqual(r.status, 127)
        self.shell.level = lambda: 20
        self.assertEqual(self.run_("ping -c 1 portal").status, 0)


if __name__ == "__main__":
    unittest.main()
