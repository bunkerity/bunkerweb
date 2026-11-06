#!/usr/bin/env python3
"""Native IPv6 Docker checks; reuse dual-stack transport without IPv4 fallback."""

import base64
import hashlib
import importlib.util
import ipaddress
import json
import os
import subprocess
import sys
import time
from pathlib import Path

spec = importlib.util.spec_from_file_location("ipv6_probe", Path(__file__).parents[1] / "ipv6/check.py")
assert spec and spec.loader
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
ROOT = Path(os.environ["BW_TESTS_IPV6_ONLY_DIR"])
# (container, netid, local address) of the only IPv4 wildcard listeners tolerated: the core's HTTP, HTTPS and QUIC sockets.
ALLOWED_IPV4_WILDCARDS = {("bunkerweb", "tcp", "0.0.0.0:80"), ("bunkerweb", "tcp", "0.0.0.0:443"), ("bunkerweb", "udp", "0.0.0.0:443")}
CONTAINERS = ("redis", "dnsmasq", "bunkerweb", "bw-scheduler", "app1", "ipv6-client", "ipv6-other", "ipv6-untrusted", "ipv6-backend")


def topology():
    print("DOCKER_SERVER_VERSION", probe.run("docker", "version", "--format", "{{.Server.Version}}"), flush=True)
    print("COMPOSE_VERSION", probe.run("docker", "compose", "version", "--short"), flush=True)
    daemon = Path("/etc/docker/daemon.json")
    print("DAEMON_JSON_SHA256", hashlib.sha256(daemon.read_bytes()).hexdigest() if daemon.exists() else "ABSENT", flush=True)
    for network in ("bw-universe", "bw-services", "bw-db", "ipv6-backend"):
        data = json.loads(probe.run("docker", "network", "inspect", network))[0]
        print("NETWORK", network, json.dumps(data), flush=True)
        assert data["EnableIPv6"] and not data["EnableIPv4"], data
        assert all(":" in entry["Subnet"] for entry in data["IPAM"]["Config"]), data
    for container in CONTAINERS:
        print("IMAGE_ID", container, probe.run("docker", "inspect", "--format", "{{.Image}}", container), flush=True)
        networks = json.loads(probe.run("docker", "inspect", "--format", "{{json .NetworkSettings.Networks}}", container))
        assert networks and all(not net["IPAddress"] and net["GlobalIPv6Address"] for net in networks.values()), (container, networks)
    print("TOPOLOGY_OK 9 containers; 4 networks; IPv4 disabled", flush=True)


def source_hashes():
    probe.image_sources()
    expected = hashlib.sha256(Path("src/bw/entrypoint.sh").read_bytes()).hexdigest()
    actual = probe.run("docker", "exec", "bunkerweb", "sha256sum", "/usr/share/bunkerweb/entrypoint.sh").split()[0]
    assert expected == actual, ("IMAGE_SOURCE_MISMATCH entrypoint", expected, actual)
    print("ENTRYPOINT_SOURCE_OK", actual, flush=True)


def logs(container):
    process = subprocess.run(["docker", "logs", container], text=True, capture_output=True, timeout=40, check=True)
    return process.stdout + process.stderr


def sockets(since=0, timeout=90):
    deadline = time.monotonic() + timeout
    while True:
        # The writer can be mid-append; only newline-terminated JSONL records are complete.
        lines = (ROOT / "sockets.jsonl").read_text().split("\n")[:-1]
        rows = [json.loads(line) for line in lines]
        pending = check_socket_samples(rows, since)
        if pending is None:
            return
        remaining = deadline - time.monotonic()
        assert remaining > 0, pending
        time.sleep(min(1, remaining))


def check_socket_samples(rows, since):
    pending = None
    for container in CONTAINERS:
        samples = [row for row in rows if row["container"] == container]
        if not any(row["code"] == 0 for row in samples):
            pending = pending or ("NO_SOCKET_SAMPLES", container)
        for family in ("-4", "-6"):
            if not any(row["code"] == 0 and row["time"] >= since and row["command"][0:2] == ["ss", family] for row in samples):
                pending = pending or ("NO_POST_RELOAD_SAMPLE", container, family)
        last_success = {tuple(row["command"]): index for index, row in enumerate(samples) if row["code"] == 0}
        for index, row in enumerate(samples):
            if row["code"]:
                # Restarts can interrupt any probe; require the same command to recover before accepting the capture.
                if index >= last_success.get(tuple(row["command"]), -1):
                    pending = pending or ("CAPTURE_FAILED", row)
                continue
            if row["command"] == ["ip", "-j", "addr"]:
                addresses = [
                    ipaddress.ip_address(addr["local"])
                    for interface in json.loads(row["out"])
                    for addr in interface.get("addr_info", [])
                    if addr["family"] == "inet"
                ]
                assert all(addr.is_loopback for addr in addresses), (container, addresses)
            elif row["command"] == ["ip", "-j", "-4", "route"]:
                assert not json.loads(row["out"]), (container, row)
            elif row["command"][0:2] == ["ss", "-4"]:
                for line in row["out"].splitlines()[1:]:
                    fields = line.split()
                    for endpoint in fields[4:6]:
                        host = endpoint.rsplit(":", 1)[0]
                        if host in ("*", "0.0.0.0"):
                            continue  # Wildcard listeners are recorded separately; they have no peer.
                        assert ipaddress.ip_address(host).is_loopback, ("NON_LOOPBACK_IPV4_SOCKET", container, line)
    found = {
        (row["container"], line.split()[0], line.split()[4]): row["container"] + ": " + line
        for row in rows
        if row["code"] == 0 and row["command"][0:2] == ["ss", "-4"]
        for line in row["out"].splitlines()[1:]
        if line.split()[4].rsplit(":", 1)[0] in ("0.0.0.0", "*")
    }
    wildcards = sorted(set(found.values()))
    (ROOT / "ipv4-wildcard-listeners.json").write_text(json.dumps(wildcards, indent=2))
    # Known product limitation: the core renders IPv4 `listen` directives next to the IPv6 ones. On an IPv4-disabled
    # network they carry no traffic. Remove this allowlist once the product can drop them.
    unexpected = sorted(found[key] for key in found if key not in ALLOWED_IPV4_WILDCARDS)
    assert not unexpected, ("STRICT_LOOPBACK_ONLY_SOCKET_GATE", unexpected)
    if pending is None:
        print("SOCKET_SAMPLES_OK", len(rows), "snapshots; no non-loopback IPv4 address/route/peer", flush=True)
        print("IPV4_WILDCARD_LISTENERS", json.dumps(wildcards), flush=True)
    return pending


def jobs():
    code = """import sqlite3,json
db=sqlite3.connect('file:/var/lib/bunkerweb/db.sqlite3?mode=ro',uri=True)
db.row_factory=sqlite3.Row
print(json.dumps([dict(r) for r in db.execute('SELECT j.name,j.plugin_id,j.every,r.success,r.start_date,r.end_date FROM bw_jobs j LEFT JOIN bw_jobs_runs r ON r.id=(SELECT MAX(id) FROM bw_jobs_runs WHERE job_name=j.name) ORDER BY j.name')]))
"""
    rows = json.loads(probe.run("docker", "exec", "bw-scheduler", "python3", "-c", code))
    assert rows and any(row["end_date"] for row in rows), rows
    (ROOT / "jobs.json").write_text(json.dumps(rows, indent=2))
    print("JOBS", json.dumps(rows), flush=True)


def check(name):
    ROOT.mkdir(parents=True, exist_ok=True)
    source_hashes()
    if name == "o1_bootstrap":
        topology()
        response = probe.api("/health")
        assert response["status"] == 200 and json.loads(response["body"])["msg"] == "ok", response
        assert response["local"] == "fd42:1618:1::24" and response["peer"] == probe.API, response
        assert "BunkerWeb is ready" in logs("bunkerweb"), "No final configuration loaded"
        jobs()
        (ROOT / "jobs-first.json").write_bytes((ROOT / "jobs.json").read_bytes())
    elif name == "o2_http_tls":
        response = probe.status(200)
        assert response["local"] == probe.CLIENT and response["peer"] == probe.INSTANCE, response
        response = probe.status(200, port=443, tls=True)
        cert = subprocess.run(
            ["openssl", "x509", "-inform", "DER", "-noout", "-subject", "-issuer"], input=base64.b64decode(response["cert"]), capture_output=True, check=True
        ).stdout.decode()
        print("TLS_CERT", cert, flush=True)
        assert "CN=www.example.com" in cert.replace(" ", ""), cert
        assert cert.splitlines()[0].removeprefix("subject=") == cert.splitlines()[1].removeprefix("issuer="), cert
        time.sleep(1)
        access = [
            line for line in logs("bunkerweb").splitlines() if line.startswith("www.example.com " + probe.CLIENT + " - ") and '"GET / HTTP/1.1" 200' in line
        ]
        assert access, "IPv6 peer absent from successful access log"
        print("IPV6_ACCESS_LOG", json.dumps(access), flush=True)
    elif name == "o3_api":
        response = probe.api("/health")
        assert response["status"] == 200 and json.loads(response["body"])["msg"] == "ok", response
        probe.status(200, client="ipv6-untrusted", host=probe.API)
        for client, host, token in [
            ("bw-scheduler", "wrong.example.com", probe.TOKEN),
            ("bw-scheduler", "bwapi", "wrong-token"),
            ("ipv6-untrusted", "bwapi", probe.TOKEN),
        ]:
            response = probe.request(client=client, host=probe.API, port=5000, path="/health", name=host, headers={"Authorization": "Bearer " + token})
            assert response["status"] in (0, 401, 403, 404), response
    elif name == "o4_blacklist":
        probe.status(403)
        probe.status(200, client="ipv6-other")
    elif name == "o4_waf":
        probe.status(200)
        probe.status(403, path="/?id=1%20UNION%20SELECT%20password%20FROM%20users")
    elif name == "o4_ban":
        probe.status(200)
        try:
            assert probe.api("/ban", {"ip": probe.CLIENT, "exp": 120, "reason": "ipv6-only-spec"})["status"] == 200
            probe.status(403)
        finally:
            assert probe.api("/unban", {"ip": probe.CLIENT})["status"] == 200
        probe.status(200)
    elif name in ("o5_dns", "o5_a_only"):
        response = probe.request()
        if name == "o5_dns":
            assert response["status"] == 200, response
            assert json.loads(response["body"])["peer"] == "fd42:1618:3::10", response
        else:
            assert response["status"] == 502, response
        print("DNS_QUERIES", logs("dnsmasq"), flush=True)
    elif name == "o6_sockets":
        topology()
        response = probe.api("/reload", {})
        assert response["status"] == 200 and json.loads(response["body"]).get("confirmed") is True, response
        reloaded = time.time()
        probe.status(200)
        sockets(reloaded)
    elif name == "o7_jobs":
        jobs()
    else:
        raise AssertionError(name)
    print("IPV6_ONLY_OK", name, flush=True)


if __name__ == "__main__":
    check(sys.argv[1])
