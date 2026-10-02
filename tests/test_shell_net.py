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


class LevelGating(NetBase):
    def test_locked_until_level(self):
        self.shell.level = lambda: 1
        r = self.run_("ping portal")
        self.assertEqual(r.status, 127)
        self.shell.level = lambda: 20
        self.assertEqual(self.run_("ping -c 1 portal").status, 0)


if __name__ == "__main__":
    unittest.main()
