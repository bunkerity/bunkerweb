"""A service named by an IPv4 literal: routed by Host on HTTP and on stream, and CRS 920350 not scored for its own literal.

One mode per call, because each mode is a configuration and the framework restarts the stack between actions.
Docker only: the CRS verdicts are read from the `bunkerweb` container's log, the stream service is reached from inside it.

  multisite   two literals as services: both route, ordinary requests pass, an attack is blocked, 920350 never scored
  single      one literal as the only service: its own Host passes, any other numeric Host is scored (920350 + 920330)
  stream      a stream service named by a literal proxies to its upstream, next to an HTTP service
"""

import http.client
from datetime import datetime, timezone
import subprocess
import sys
import time

INSTANCE = "bunkerweb"
OWN = "192.0.2.10"
OTHER = "198.51.100.7"
# An empty User-Agent adds 920330 (2) to a 920350 hit (3): over the CRS threshold of 5, so a numeric Host that is not
# the service's own literal is refused. The own literal must stay at zero.
QUIET = {"User-Agent": "", "Accept": "*/*"}
NORMAL = {"User-Agent": "sn-probe/1.0", "Accept": "*/*"}


def diagnostics():
    """What the instance rendered for the rule that must remove 920350: shown on every failure, so a red run explains itself."""
    script = (
        "find /etc/nginx -path '*modsec-crs*' -type f | head -20; "
        'for f in $(find /etc/nginx -name \'ip-host*\' -type f); do echo "== $f"; cat "$f"; done; '
        "grep -rn 'modsec-crs\\|ip-host\\|1007783' /etc/nginx --include='*modsecurity*' | head -20"
    )
    process = subprocess.run(["docker", "exec", INSTANCE, "sh", "-c", script], text=True, capture_output=True, timeout=60, check=False)
    print("DIAGNOSTICS", process.stdout, process.stderr, file=sys.stderr, flush=True)


def fail(message):
    print(f"server-name-ip-literal: {message}", file=sys.stderr)
    diagnostics()
    sys.exit(1)


def get(host, headers, path="/"):
    connection = http.client.HTTPConnection("127.0.0.1", 80, timeout=15)
    try:
        connection.putrequest("GET", path, skip_host=True, skip_accept_encoding=True)
        connection.putheader("Host", host)
        for key, value in headers.items():
            connection.putheader(key, value)
        connection.endheaders()
        return connection.getresponse().status
    finally:
        connection.close()


def expect(status, host, headers, path="/"):
    got = get(host, headers, path)
    print(f"GET {path} Host={host} UA={headers['User-Agent']!r} -> {got}", flush=True)
    if got != status:
        fail(f"Host {host!r} {path}: expected {status}, got {got}")


def logs(since):
    # The container logs through syslog; `docker logs` still answers for it (local cache), the same way the framework's `log:` check reads it.
    process = subprocess.run(["docker", "logs", "--since", since, INSTANCE], text=True, capture_output=True, timeout=60, check=False)
    return process.stdout + process.stderr


def now():
    return datetime.now(timezone.utc).isoformat()


def multisite():
    since = now()
    for host in (OWN, "192.0.2.11"):
        expect(200, host, QUIET)
        expect(200, host, NORMAL)
        expect(403, host, NORMAL, "/?id=/etc/passwd")
    time.sleep(2)
    output = logs(since)
    print("MODSEC_LINES", [line[:300] for line in output.splitlines() if "ModSecurity" in line], flush=True)
    if '[id "930120"]' not in output:
        fail("the attack was not blocked by CRS (rule 930120 absent from the log)")
    if '[id "920350"]' in output:
        fail("CRS 920350 was scored for a service's own literal")


def single():
    since = now()
    expect(200, OWN, QUIET)
    time.sleep(2)
    own_log = logs(since)
    if '[id "920350"]' in own_log:
        fail("CRS 920350 was scored for the service's own literal")
    since = now()
    expect(403, OTHER, QUIET)
    time.sleep(2)
    other_log = logs(since)
    print("MODSEC_LINES", [line[:300] for line in other_log.splitlines() if "ModSecurity" in line], flush=True)
    if '[id "920350"]' not in other_log or '[id "920330"]' not in other_log:
        fail("another numeric Host must keep scoring 920350 and 920330")


def stream():
    since = now()
    expect(200, "www.example.com", NORMAL)
    # The upstream is nginx-hello (its page is titled "Hello World"): it answers any HTTP request on the raw TCP connection the stream service proxies.
    deadline = time.time() + 60
    body = ""
    while time.time() < deadline:
        process = subprocess.run(
            ["docker", "exec", INSTANCE, "curl", "-sS", "--max-time", "10", "http://127.0.0.1:10000/"], text=True, capture_output=True, timeout=30, check=False
        )
        body = process.stdout
        print("STREAM_PROBE rc", process.returncode, repr(body[:120]), repr(process.stderr[:200]), flush=True)
        if "Hello World" in body:
            break
        time.sleep(3)
    else:
        fail("the stream service named by an IPv4 literal does not proxy to its upstream")
    output = logs(since)
    if "invalid port in upstream" in output:
        fail("nginx refused the stream upstream: invalid port in upstream")


MODES = {"multisite": multisite, "single": single, "stream": stream}
mode = sys.argv[1] if len(sys.argv) > 1 else ""
if mode not in MODES:
    fail(f"unknown mode {mode!r}")
MODES[mode]()
print(f"IP_LITERAL_OK {mode}")
