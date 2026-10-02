"""Network information commands against the simulated world: ping, dig/nslookup, whois, curl/wget, netstat/ss, traceroute, ip/ifconfig, arp.

Nothing here opens a real socket. Every machine, DNS name, service and page is game data (``World``/``Machine``/``Service``); a command only
succeeds against targets the world says exist and are reachable, and every answer is built from that data, never from the real internet."""
from __future__ import annotations

import re
import time

from .. import opts
from ..registry import command


def _lat(ip: str) -> float:
    """A believable, deterministic millisecond figure from an address, so the same target always answers at roughly the same speed."""
    return 0.3 + (sum(int(p) for p in ip.split(".") if p.isdigit()) % 300) / 100.0


def _target(ctx, ref: str):
    """(machine or None, ip or None) for a name the game world knows. reachable_from() enforces the usual network-map rules."""
    ip = ctx.world.resolve(ref)
    if ip is None and re.fullmatch(r"\d+\.\d+\.\d+\.\d+", ref):
        ip = ref
    if ip is None:
        return None, None
    return ctx.world.reachable_from(ctx.machine, ip), ip


def _announce(ctx, machine) -> None:
    if machine is not None and machine.id not in ctx.world.discovered:
        ctx.world.discovered.add(machine.id)
        ctx.event("host_discovered", machine=machine.id)


# ---------------------------------------------------------------------------------------------------- ping
@command("ping", level=9, summary="Send ICMP ECHO_REQUEST to network hosts.", usage="ping [-c count] destination", category="net",
         man="""NAME
       ping - send ICMP ECHO_REQUEST to network hosts

SYNOPSIS
       ping [-c count] [-W timeout] destination

DESCRIPTION
       -c count   stop after sending count packets (default here: 4)
       -W secs    time to wait for a response
""", lesson="ping asks a machine 'are you there?' and measures how long the answer takes. No answer can mean the machine is off or hiding behind a firewall.")
def ping(ctx, args):
    o = opts.parse(ctx, args, short="nqv", with_arg="cWiws")
    if o is None:
        return 2
    if not o.rest:
        ctx.err("ping: usage error: Destination address required")
        return 2
    name = o.rest[0]
    machine, ip = _target(ctx, name)
    if ip is None:
        ctx.err(f"ping: {name}: Name or service not known")
        return 2
    count = min(int(o.get("c") or 4), 20)
    ctx.out(f"PING {name} ({ip}) 56(84) bytes of data.")
    if machine is None:
        for i in range(count):
            ctx.out(f"From {ctx.machine.ip} icmp_seq={i + 1} Destination Host Unreachable")
            ctx.wait(400)
        ctx.out(f"\n--- {name} ping statistics ---\n{count} packets transmitted, 0 received, +{count} errors, 100% packet loss, time {400 * count}ms")
        return 1
    times = []
    for i in range(count):
        t = _lat(ip) + (i % 3) * 0.07
        times.append(t)
        ctx.out(f"64 bytes from {machine.hostname} ({ip}): icmp_seq={i + 1} ttl={64 if machine.os == 'linux' else 128} time={t:.2f} ms")
        ctx.wait(350)
    ctx.out(f"\n--- {name} ping statistics ---")
    ctx.out(f"{count} packets transmitted, {count} received, 0% packet loss, time {350 * count - 1}ms")
    ctx.out(f"rtt min/avg/max/mdev = {min(times):.3f}/{sum(times) / len(times):.3f}/{max(times):.3f}/0.031 ms")
    _announce(ctx, machine)
    ctx.event("ping", machine=machine.id)
    return 0


# ---------------------------------------------------------------------------------------------------- DNS: dig / nslookup / host
def _records(ctx, name: str):
    ip = ctx.world.resolve(name)
    return ctx.world.flags.get("dns_records", {}).get(name, [("A", ip)] if ip else [])


@command("dig", level=10, summary="DNS lookup utility.", usage="dig [@server] name [type]", category="net",
         lesson="dig asks a DNS server to translate a name into an address: 'dig nexus-company.com' shows its IP, if the name exists at all.")
def dig(ctx, args):
    rest = [a for a in args if not a.startswith("@") and not a.startswith("-")]
    if not rest:
        ctx.out("; <<>> DiG 9.18 <<>>")
        ctx.out(";; global options: +cmd")
        return 0
    name, qtype = rest[0], (rest[1].upper() if len(rest) > 1 else "A")
    ctx.out("; <<>> DiG 9.18 <<>>" + " " + " ".join(args))
    ctx.out(";; global options: +cmd")
    records = [r for r in _records(ctx, name) if r[0] == qtype] or ([("A", ctx.world.resolve(name))] if qtype == "A" and ctx.world.resolve(name) else [])
    status = "NOERROR" if records else "NXDOMAIN"
    ctx.out(f";; Got answer:\n;; ->>HEADER<<- opcode: QUERY, status: {status}, id: {abs(hash(name)) % 60000}")
    ctx.out(f";; flags: qr rd ra; QUERY: 1, ANSWER: {len(records)}, AUTHORITY: 0, ADDITIONAL: 1\n")
    ctx.out(";; QUESTION SECTION:")
    ctx.out(f";{name}.\t\t\tIN\t{qtype}\n")
    if records:
        ctx.out(";; ANSWER SECTION:")
        for rtype, value in records:
            ctx.out(f"{name}.\t\t300\tIN\t{rtype}\t{value}")
    ctx.out(f"\n;; Query time: {int(_lat(ctx.machine.ip) * 10)} msec")
    ctx.out(f";; SERVER: 10.0.0.1#53(10.0.0.1)")
    ctx.out(f";; WHEN: {time.strftime('%a %b %e %H:%M:%S UTC %Y', time.gmtime(ctx.now()))}")
    ctx.out(f";; MSG SIZE  rcvd: {28 + len(name)}")
    return 0


@command("nslookup", level=10, summary="Query Internet name servers interactively.", usage="nslookup name", category="net",
         lesson="nslookup is an older, simpler way to turn a name into an address than dig.")
def nslookup(ctx, args):
    rest = [a for a in args if not a.startswith("-")]
    if not rest:
        ctx.err("Usage: nslookup name")
        return 1
    name = rest[0]
    ip = ctx.world.resolve(name)
    ctx.out("Server:\t\t10.0.0.1")
    ctx.out("Address:\t10.0.0.1#53\n")
    if ip is None:
        ctx.out("** server can't find " + name + ": NXDOMAIN")
        return 1
    ctx.out(f"Name:\t{name}")
    ctx.out(f"Address: {ip}")
    return 0


@command("host", level=10, summary="DNS lookup utility (simple output).", usage="host name", category="net")
def host_cmd(ctx, args):
    rest = [a for a in args if not a.startswith("-")]
    if not rest:
        ctx.err("Usage: host [-v] name")
        return 1
    name = rest[0]
    ip = ctx.world.resolve(name)
    if ip is None:
        ctx.out(f"Host {name} not found: 3(NXDOMAIN)")
        return 1
    ctx.out(f"{name} has address {ip}")
    return 0


# ---------------------------------------------------------------------------------------------------- whois
@command("whois", level=10, summary="Client for the whois directory service.", usage="whois object", category="net",
         lesson="whois looks up who registered a domain: owner, registrar, important dates. Useful for the first picture of a target.")
def whois(ctx, args):
    rest = [a for a in args if not a.startswith("-")]
    if not rest:
        ctx.err("whois: missing object")
        return 1
    name = rest[0]
    data = ctx.world.whois.get(name)
    if data:
        ctx.out(data)
        return 0
    if ctx.world.resolve(name) is None and not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", name):
        ctx.out(f"No match for \"{name.upper()}\".")
        return 1
    ctx.out(f"Domain Name: {name.upper()}\nRegistrar: UNKNOWN REGISTRAR\nUpdated Date: 2049-11-03T00:00:00Z\nCreation Date: 2041-02-17T00:00:00Z")
    ctx.out("Registry Expiry Date: 2051-02-17T00:00:00Z\nDomain Status: clientTransferProhibited")
    return 0


# ---------------------------------------------------------------------------------------------------- curl / wget
def _http_fetch(ctx, url: str):
    """Resolve a URL against the game world's web pages (``Service.data['pages']``). Returns (status_code, headers, body) or None."""
    m = re.match(r"^(https?)://([^/:]+)(?::(\d+))?(/.*)?$", url)
    if not m:
        return None
    scheme, host, port_s, path = m.groups()
    path = path or "/"
    machine, ip = _target(ctx, host)
    port = int(port_s) if port_s else (443 if scheme == "https" else 80)
    if machine is None:
        return None
    svc = machine.service(port)
    if svc is None or svc.state != "open":
        return "refused", {}, ""
    pages = svc.data.get("pages", {})
    if path in pages:
        page = pages[path]
        body = page.get("body", "") if isinstance(page, dict) else page
        status = page.get("status", 200) if isinstance(page, dict) else 200
        headers = page.get("headers", {"Server": svc.banner or svc.name, "Content-Type": "text/html"}) if isinstance(page, dict) else {"Server": svc.banner or svc.name}
        _announce(ctx, machine)
        ctx.event("http_fetch", machine=machine.id, path=path)
        return status, headers, body
    return 404, {"Server": svc.banner or svc.name}, "<html><body><h1>404 Not Found</h1></body></html>"


@command("curl", level=11, summary="Transfer a URL.", usage="curl [OPTION]... URL", category="net",
         man="""NAME
       curl - transfer a URL

SYNOPSIS
       curl [OPTION]... URL

DESCRIPTION
       -s, --silent    don't show progress or error messages
       -I, --head      fetch headers only
       -i               include response headers in the output
       -o FILE          write output to FILE instead of stdout
       -X METHOD        request method (GET, POST, ...)
       -d DATA          send DATA in a POST request
       -H HEADER        add a custom header
""", lesson="curl fetches whatever a web address serves: 'curl http://target/' downloads the page's text straight to your terminal.")
def curl(ctx, args):
    o = opts.parse(ctx, args, short="sSiIvkL", with_arg="oXdH", long={"silent": "s", "head": "I", "include": "i"}, long_arg={"output": "o", "request": "X", "data": "d"})
    if o is None:
        return 2
    if not o.rest:
        ctx.err("curl: try 'curl --help' for more information")
        return 2
    result = _http_fetch(ctx, o.rest[0])
    if result is None:
        ctx.err(f"curl: (6) Could not resolve host: {o.rest[0]}")
        return 6
    if result[0] == "refused":
        ctx.err(f"curl: (7) Failed to connect to {o.rest[0]} port; Connection refused")
        return 7
    status, headers, body = result
    text = []
    if o.has("i", "I"):
        text.append(f"HTTP/1.1 {status} {'OK' if status == 200 else 'Not Found'}")
        text.extend(f"{k}: {v}" for k, v in headers.items())
        text.append("")
    if not o.has("I"):
        text.append(body)
    out = "\n".join(text)
    if o.get("o"):
        ctx.fs.write(ctx.user, o.get("o"), out, ctx.cwd)
        if not o.has("s"):
            ctx.err(f"  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current")
            ctx.err(f"100 {len(out):>5}  100 {len(out):>5}    0     0  {len(out) + 400}      0 --:--:-- --:--:-- --:--:-- {len(out) + 400}")
    else:
        ctx.out(out, end="" if not out.endswith("\n") else "")
    return 0


@command("wget", level=11, summary="Non-interactive network downloader.", usage="wget [OPTION]... URL", category="net",
         lesson="wget downloads a file or page to disk: 'wget http://target/secret.zip' saves it under its own name in the current folder.")
def wget(ctx, args):
    o = opts.parse(ctx, args, short="qSv", with_arg="O")
    if o is None:
        return 2
    if not o.rest:
        ctx.err("wget: missing URL")
        return 1
    url = o.rest[0]
    result = _http_fetch(ctx, url)
    if not o.has("q"):
        ctx.err(f"--{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(ctx.now()))}--  {url}")
    if result is None:
        ctx.err(f"Resolving {url.split('/')[2] if '/' in url else url} (...)... failed: Name or service not known.")
        return 4
    if result[0] == "refused":
        ctx.err("Connecting to ... failed: Connection refused.")
        return 4
    status, headers, body = result
    name = o.get("O") or (url.rsplit("/", 1)[-1] or "index.html")
    if status != 200:
        ctx.err(f"ERROR {status}: Not Found.")
        return 8
    ctx.fs.write(ctx.user, name, body, ctx.cwd)
    if not o.has("q"):
        ctx.err(f"Length: {len(body)} [text/html]")
        ctx.err(f"Saving to: '{name}'\n")
        ctx.err(f"{name}  100%[===================>]  {len(body)}  --.-KB/s    in 0s\n")
        ctx.err(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(ctx.now()))} (1.0 MB/s) - '{name}' saved [{len(body)}/{len(body)}]")
    return 0


# ---------------------------------------------------------------------------------------------------- netstat / ss
def _connections(ctx):
    return ctx.machine.data.get("connections", [])


@command("netstat", level=12, summary="Print network connections, routing tables, interface statistics.", usage="netstat [OPTION]...", category="net",
         lesson="netstat lists network connections and listening ports on this machine: it tells you what is talking to whom right now.")
def netstat(ctx, args):
    o = opts.parse(ctx, args, short="tulpanv", long={"tcp": "t", "udp": "u", "listening": "l", "all": "a", "programs": "p", "numeric": "n"})
    if o is None:
        return 2
    ctx.out("Active Internet connections" + (" (servers and established)" if o.has("a") else " (only servers)" if o.has("l") else ""))
    ctx.out("Proto Recv-Q Send-Q Local Address           Foreign Address         State" + ("       PID/Program name" if o.has("p") else ""))
    for svc in ctx.machine.services:
        if svc.state != "open":
            continue
        proto = "tcp" if svc.proto == "tcp" else "udp"
        if (o.has("t") and proto != "tcp") or (o.has("u") and proto != "udp"):
            continue
        pid = f"       {1000 + svc.port}/{svc.name}" if o.has("p") else ""
        ctx.out(f"{proto:<5} {0:>6} {0:>6} {ctx.machine.ip}:{svc.port}{'':<13} 0.0.0.0:*{'':<15} LISTEN{pid}")
    if o.has("a"):
        for c in _connections(ctx):
            ctx.out(f"tcp        0      0 {ctx.machine.ip}:{c.get('local_port', 0)}{'':<9} {c.get('peer', '0.0.0.0')}:{c.get('peer_port', 0)}{'':<9} {c.get('state', 'ESTABLISHED')}")
    return 0


@command("ss", level=12, summary="Another utility to investigate sockets.", usage="ss [OPTION]...", category="net")
def ss_cmd(ctx, args):
    o = opts.parse(ctx, args, short="tulpan")
    if o is None:
        return 2
    ctx.out("Netid  State   Recv-Q  Send-Q   Local Address:Port    Peer Address:Port")
    for svc in ctx.machine.services:
        if svc.state == "open":
            ctx.out(f"{'tcp' if svc.proto == 'tcp' else 'udp':<6} LISTEN  0       128      {ctx.machine.ip}:{svc.port}         0.0.0.0:*")
    return 0


# ---------------------------------------------------------------------------------------------------- traceroute
@command("traceroute", level=12, summary="Print the route packets trace to a network host.", usage="traceroute destination", category="net",
         lesson="traceroute shows every hop a connection passes through on its way to a target, hop by hop with its own response time.")
def traceroute(ctx, args):
    o = opts.parse(ctx, args, short="nv", with_arg="m")
    if o is None:
        return 2
    if not o.rest:
        ctx.err("traceroute: missing host operand")
        return 1
    name = o.rest[0]
    machine, ip = _target(ctx, name)
    if ip is None:
        ctx.err(f"traceroute: unknown host {name}")
        return 1
    ctx.out(f"traceroute to {name} ({ip}), 30 hops max, 60 byte packets")
    hops = ctx.machine.data.get("route_to", {}).get(ip) or [f"10.0.{i}.1" for i in range(1, 3)]
    for i, hop in enumerate(hops + [ip], 1):
        t = _lat(hop if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", hop) else ip) + i * 0.4
        ctx.out(f" {i}  {hop} ({hop})  {t:.3f} ms  {t + 0.1:.3f} ms  {t + 0.2:.3f} ms")
        ctx.wait(150)
    if machine is None:
        ctx.out(" *  *  *")
        return 1
    _announce(ctx, machine)
    return 0


# ---------------------------------------------------------------------------------------------------- ip / ifconfig / arp
@command("ip", level=9, summary="Show / manipulate routing, network devices and interfaces.", usage="ip [OPTIONS] OBJECT {COMMAND}", category="net",
         lesson="ip addr shows this machine's own network interfaces and addresses — the modern replacement for ifconfig.")
def ip_cmd(ctx, args):
    rest = [a for a in args if not a.startswith("-")]
    obj = rest[0] if rest else "addr"
    if obj in ("addr", "a", "address"):
        ctx.out("1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000")
        ctx.out("    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00")
        ctx.out("    inet 127.0.0.1/8 scope host lo")
        ctx.out("2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000")
        ctx.out(f"    link/ether {_mac(ctx.machine.ip)} brd ff:ff:ff:ff:ff:ff")
        ctx.out(f"    inet {ctx.machine.ip}/24 brd {ctx.machine.ip.rsplit('.', 1)[0]}.255 scope global eth0")
        return 0
    if obj in ("route", "r"):
        base = ctx.machine.ip.rsplit(".", 1)[0]
        ctx.out(f"default via {base}.1 dev eth0")
        ctx.out(f"{base}.0/24 dev eth0 proto kernel scope link src {ctx.machine.ip}")
        return 0
    if obj in ("link", "l"):
        ctx.out("1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536")
        ctx.out(f"2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 link/ether {_mac(ctx.machine.ip)}")
        return 0
    ctx.err(f"Object \"{obj}\" is unknown, try \"ip help\".")
    return 1


def _mac(seed: str) -> str:
    n = abs(hash(seed))
    parts = [(n >> (i * 8)) & 0xFF for i in range(6)]
    parts[0] = (parts[0] & 0xFE) | 0x02           # locally administered, unicast
    return ":".join(f"{p:02x}" for p in parts)


@command("ifconfig", level=9, summary="Configure a network interface.", usage="ifconfig [interface]", category="net")
def ifconfig(ctx, args):
    base = ctx.machine.ip.rsplit(".", 1)[0]
    ctx.out(f"eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500")
    ctx.out(f"        inet {ctx.machine.ip}  netmask 255.255.255.0  broadcast {base}.255")
    ctx.out(f"        ether {_mac(ctx.machine.ip)}  txqueuelen 1000  (Ethernet)")
    ctx.out(f"        RX packets 48213  bytes 52108342 (49.6 MiB)")
    ctx.out(f"        TX packets 31044  bytes 8291004 (7.9 MiB)\n")
    ctx.out(f"lo: flags=73<UP,LOOPBACK,RUNNING>  mtu 65536")
    ctx.out(f"        inet 127.0.0.1  netmask 255.0.0.0")
    return 0


@command("arp", level=11, summary="Manipulate the system ARP cache.", usage="arp [-a]", category="net",
         lesson="arp -a lists which machines on your local network this computer has recently talked to, each with its hardware address.")
def arp(ctx, args):
    o = opts.parse(ctx, args, short="an")
    if o is None:
        return 2
    neighbors = [ctx.world.machines[mid] for mid in ctx.machine.neighbors if mid in ctx.world.machines]
    if not neighbors:
        ctx.out("No ARP entries found.") if not o.has("a") else None
        return 0
    for m in neighbors:
        ctx.out(f"{m.hostname} ({m.ip}) at {_mac(m.ip)} [ether] on eth0")
    return 0
