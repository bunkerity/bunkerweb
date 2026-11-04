#!/usr/bin/env python3
"""Probes for tests/core/stream.yml. One mode per call; prints `stream <mode>: ...` lines and exits 0 when every check passed.

  shared     the stream services that share a listen port load, and both of them answer
  tls        a stream service whose upstream settings turn TLS on reaches a TLS backend
  detect     SECURITY_MODE=detect: a banned client is still proxied, and the ban is logged as detected
  block      SECURITY_MODE=block: the same ban closes the connection, and lifting it serves the client again

The stream listeners are not published on the host (the harness maps ports 80 and 443 only), so the runner
dials the BunkerWeb container on `bw-universe`, where Docker's bridge forwards without NAT.
"""

import socket
import subprocess
import sys
import time
from re import compile, search

INSTANCE = "bunkerweb"
SCHEDULER = "bw-scheduler"
NETWORK = "bw-universe"

# nginx-hello (the `app1` fixture of tests/misc/docker/services.yml) prints this label on every GET, as HTML.
BACKEND_MARK = compile(rb"Server(&nbsp;| )name")
SHARED_PORT = 10000
OWN_PORT = 20000
TLS_PORT = 30000
REQUEST = b"GET / HTTP/1.0\r\nHost: stream.example.com\r\n\r\n"


def fail(message: str) -> None:
    print(f"stream {MODE}: {message}", file=sys.stderr)
    sys.exit(1)


def docker(*args: str, check: bool = True) -> str:
    process = subprocess.run(["docker", *args], capture_output=True, text=True, check=False)
    if check and process.returncode != 0:
        fail(f"docker {' '.join(args)} failed: {process.stderr.strip()}")
    return process.stdout + process.stderr


def instance_ip() -> str:
    return docker("inspect", "-f", f'{{{{(index .NetworkSettings.Networks "{NETWORK}").IPAddress}}}}', INSTANCE).strip()


LAST = {"fetch": ""}


def fetch(port: int, timeout: float = 8.0) -> bytes:
    """What the service sends back after a GET: empty when the connection is closed or reset."""
    LAST["fetch"] = f":{port} no attempt"
    try:
        with socket.create_connection((instance_ip(), port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(REQUEST)
            data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    LAST["fetch"] = f":{port} closed after {len(data)} bytes, starting {data[:60]!r}"
                    return data
                data += chunk
    except OSError as error:
        LAST["fetch"] = f":{port} {type(error).__name__}: {error}"
        return b""


def peer() -> str:
    """The address BunkerWeb sees for this runner: the bridge gateway, which differs per host.

    /proc/net/tcp of the instance states it without parsing a log: the one ESTABLISHED client of the shared port.
    """
    sock = socket.create_connection((instance_ip(), SHARED_PORT), timeout=5)
    try:
        time.sleep(1)
        table = docker("exec", INSTANCE, "cat", "/proc/net/tcp")
        addresses = set()
        for line in table.splitlines()[1:]:
            fields = line.split()
            if len(fields) > 3 and fields[3] == "01" and int(fields[1].split(":")[1], 16) == SHARED_PORT:
                addresses.add(socket.inet_ntoa(bytes.fromhex(fields[2].split(":")[0])[::-1]))
        if len(addresses) != 1:
            rows = [" ".join(line.split()[1:4]) for line in table.splitlines()[1:] if ":2710 " in line]
            seen = [line[-200:] for line in logs("60s").splitlines() if ":10000" in line][-4:]
            fail(f"expected exactly one client of :{SHARED_PORT}, got {sorted(addresses)}; tcp rows {rows}; log {seen}")
        return addresses.pop()
    finally:
        sock.close()


def wait_for(check, what: str, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(1)
    fail(f"timed out waiting for {what} (last attempt {LAST['fetch']})")


def served(port: int) -> bool:
    return BACKEND_MARK.search(fetch(port)) is not None


def logs(since: str) -> str:
    return docker("logs", "--since", since, INSTANCE, check=False)


def shared() -> None:
    rendered = docker("exec", INSTANCE, "nginx", "-T")
    listens = [line.strip() for line in rendered.splitlines() if search(rf"^\s*listen\s+\S*:{SHARED_PORT}\b", line)]
    if len(listens) < 2:
        fail(f"expected at least two listen directives on :{SHARED_PORT} (one per service), got {listens}")
    owners = [line for line in listens if "reuseport" in line]
    if len(owners) != 1:
        fail(f"expected exactly one reuseport on :{SHARED_PORT}, got {len(owners)}: {listens}")
    print(f"stream {MODE}: one reuseport among {len(listens)} listeners on :{SHARED_PORT}")
    # SSL ports are set empty on every stream service: no listener may be emitted for them.
    empty = [line.strip() for line in rendered.splitlines() if search(r"^\s*listen\s+\S*:(?!\d)", line)]
    if empty:
        fail(f"a listen directive was rendered without a port: {empty}")
    wait_for(lambda: served(SHARED_PORT), f"an answer on the shared port :{SHARED_PORT}")
    wait_for(lambda: served(OWN_PORT), f"an answer on the second service's own port :{OWN_PORT}")
    print(f"stream {MODE}: both services answer (:{SHARED_PORT}, :{OWN_PORT})")


def tls() -> None:
    # The backend is BunkerWeb's own HTTPS listener: a client speaking TLS to it gets HTTP, and plaintext gets
    # nginx's "400 plain HTTP request was sent to HTTPS port". Only `proxy_ssl on` tells the two apart.
    def answer() -> bytes:
        return fetch(TLS_PORT)

    wait_for(lambda: answer().startswith(b"HTTP/"), f"an HTTP answer on :{TLS_PORT}")
    reply = answer()
    status = reply.split(b"\r\n", 1)[0].decode(errors="replace")
    if b"plain HTTP request was sent to HTTPS port" in reply or b" 400 " in reply.split(b"\r\n", 1)[0]:
        fail(f"the backend received plaintext on its TLS port: {status}")
    print(f"stream {MODE}: the upstream speaks TLS to its backend ({status})")


def ban(ip: str) -> None:
    docker("exec", SCHEDULER, "bwcli", "ban", ip, "-exp", "3600")


def unban(ip: str) -> None:
    docker("exec", SCHEDULER, "bwcli", "unban", ip, check=False)


def detect(ip: str, since: str) -> None:
    ban(ip)
    try:
        # Each attempt is proxied; the log line proves the ban was seen once it reached the instance.
        wait_for(lambda: served(SHARED_PORT) and f"detected IP {ip} ban with reason" in logs(since), "a proxied connection and the detect-mode log line")
        if f"IP {ip} is banned with reason" in logs(since):
            fail("detect mode logged an enforced ban")
        print(f"stream {MODE}: the banned client {ip} is still proxied and the ban is logged as detected")
    finally:
        unban(ip)


def block(ip: str, since: str) -> None:
    wait_for(lambda: served(SHARED_PORT), "a served connection before the ban")
    ban(ip)
    try:
        wait_for(lambda: not served(SHARED_PORT), "the banned client to be refused")
        if f"IP {ip} is banned with reason" not in logs(since):
            fail("no 'is banned with reason' line in the instance logs")
        print(f"stream {MODE}: the banned client {ip} is refused")
    finally:
        unban(ip)
    wait_for(lambda: served(SHARED_PORT), "the unbanned client to be served again")
    print(f"stream {MODE}: unbanned, served again")


MODE = sys.argv[1] if len(sys.argv) > 1 else ""

if MODE == "shared":
    shared()
elif MODE == "tls":
    tls()
elif MODE in ("detect", "block"):
    # A reload keeps the stream block's shared memory, and an unban reaches only the HTTP block's: the previous
    # mode's ban stays enforced here for its cache lifetime (about 30 s). Wait it out before reading the address.
    wait_for(lambda: served(SHARED_PORT), "the shared port to serve this runner")
    client = peer()
    # Read the logs from here on only: the lingering ban above is logged too.
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print(f"stream {MODE}: BunkerWeb sees this runner as {client}")
    (detect if MODE == "detect" else block)(client, started)
else:
    sys.exit(f"usage: {sys.argv[0]} shared|tls|detect|block")
print(f"stream {MODE}: all checks passed")
