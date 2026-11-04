#!/usr/bin/env python3
"""Live Docker assertions; request sockets run inside fixed-address clients."""

import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path

CLIENT = "fd42:1618:2::a"
ALIAS = "FD42:1618:0002:0000:0000:0000:0000:000A"
INSTANCE = "fd42:1618:2::10"
API = "fd42:1618:1::10"
TOKEN = "tests-secret-token"

# Use an explicit socket family: neither Docker DNS nor a host port can hide IPv4 fallback.
REQUEST = r"""
import base64, http.client, json, socket, ssl, sys
p = json.loads(sys.argv[1])
sock = socket.socket(socket.AF_INET6 if ":" in p["host"] else socket.AF_INET)
sock.settimeout(8)
try:
    sock.connect((p["host"], p["port"]))
    peer, local = sock.getpeername()[0], sock.getsockname()[0]
    cert = ""
    if p["tls"]:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        sock = context.wrap_socket(sock, server_hostname="www.example.com")
        cert = base64.b64encode(sock.getpeercert(binary_form=True)).decode()
    headers = {"Host": p["name"], "Connection": "close", **p["headers"]}
    body = p["body"]
    if body:
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body.encode()))
    wire = p["method"] + " " + p["path"] + " HTTP/1.1\r\n"
    wire += "".join(k + ": " + v + "\r\n" for k, v in headers.items()) + "\r\n" + body
    sock.sendall(wire.encode())
    response = http.client.HTTPResponse(sock)
    response.begin()
    print(json.dumps(dict(status=response.status, body=response.read().decode(), peer=peer, local=local, cert=cert)))
except (OSError, http.client.HTTPException) as exc:
    print(json.dumps(dict(status=0, error=str(exc))))
finally:
    sock.close()
"""


def run(*argv):
    process = subprocess.run(argv, text=True, capture_output=True, timeout=40, check=False)
    assert process.returncode == 0, (argv, process.returncode, process.stdout, process.stderr)
    return process.stdout.strip()


def image_sources():
    # Other checkouts share :tests tags; verify the files actually running before each action.
    files = {
        "bunkerweb": {
            "lua/bunkerweb/" + name: "src/bw/lua/bunkerweb/" + name for name in ("api.lua", "utils.lua", "ipaddr.lua", "redisendpoints.lua", "clusterstore.lua")
        },
        "bw-scheduler": {
            "utils/common_utils.py": "src/common/utils/common_utils.py",
            "core/blacklist/jobs/blacklist-download.py": "src/common/core/blacklist/jobs/blacklist-download.py",
            "gen/Templator.py": "src/common/gen/Templator.py",
        },
    }
    for container, sources in files.items():
        expected = {"/usr/share/bunkerweb/" + target: hashlib.sha256(Path(source).read_bytes()).hexdigest() for target, source in sources.items()}
        output = run("docker", "exec", container, "sha256sum", *expected)
        actual = {line.split()[1]: line.split()[0] for line in output.splitlines()}
        assert actual == expected, ("IMAGE_SOURCE_MISMATCH", container, actual, expected)
    print("IMAGE_SOURCES_OK 8 runtime files", flush=True)


def request(client="ipv6-client", host=INSTANCE, port=80, tls=False, path="/", headers=None, name="www.example.com", method="GET", body=""):
    params = dict(host=host, port=port, tls=tls, path=path, headers=headers or {}, name=name, method=method, body=body)
    response = json.loads(run("docker", "exec", client, "python3", "-c", REQUEST, json.dumps(params)))
    print("REQUEST", client, host, port, path, json.dumps(response), flush=True)
    return response


def status(expected, **kwargs):
    result = request(**kwargs)
    assert result["status"] == expected, (expected, result)
    return result


def api(path, data=None, client="bw-scheduler"):
    return request(
        client=client,
        host=API,
        port=5000,
        path=path,
        name="bwapi",
        headers={"Authorization": "Bearer " + TOKEN},
        method="POST" if data is not None else "GET",
        body=json.dumps(data) if data is not None else "",
    )


def redis(*args):
    return run("docker", "exec", "redis", "redis-cli", "-n", "1", "--raw", *args)


def cli(*args):
    process = subprocess.run(["docker", "exec", "bw-scheduler", "bwcli", *args], text=True, capture_output=True, timeout=40, check=False)
    assert process.returncode == 0, (process.returncode, process.stdout, process.stderr)
    output = process.stdout + process.stderr
    print("BWCLI", *args, output, flush=True)
    return output


def bans(writer):
    # Read actual traffic and Redis, not only the management response.
    status(200)
    try:
        if writer == "api":
            response = api("/ban", {"ip": ALIAS, "exp": 120, "reason": "ipv6-spec"})
            assert response["status"] == 200, response
        else:
            assert "has been banned" in cli("ban", ALIAS, "-exp", "120", "-reason", "ipv6-spec")
        status(403)
        keys = redis("KEYS", "bans_ip_*").splitlines()
        print("BAN_KEYS", keys, flush=True)
        assert "bans_ip_" + CLIENT in keys, keys
        assert not any(ALIAS in key for key in keys), keys
    finally:
        if writer == "api":
            response = api("/unban", {"ip": CLIENT})
            assert response["status"] == 200, response
        else:
            assert "has been unbanned" in cli("unban", CLIENT)
    status(200)
    keys = redis("KEYS", "bans_*").splitlines()
    print("AFTER_UNBAN_KEYS", keys, flush=True)
    assert not keys, keys


def limit():
    # Delete only this spec's counters, so preceding endpoint variants cannot pollute this burst.
    for ip in (CLIENT, "fd42:1618:2::b"):
        redis("DEL", "plugin_limit_www.example.com" + ip + "/")
    statuses = [request()["status"] for _ in range(6)]
    print("BURST", statuses, flush=True)
    assert statuses[0] == 200 and 429 in statuses, statuses
    status(200, client="ipv6-other")


def check(name):
    image_sources()
    if name == "l1_disabled":
        ipv4 = json.loads(run("docker", "inspect", "bunkerweb"))[0]["NetworkSettings"]["Networks"]["bw-services"]["IPAddress"]
        status(200, host=ipv4)
        assert request()["status"] == 0, "USE_IPV6=no must refuse IPv6"
        sockets = run("docker", "exec", "bunkerweb", "cat", "/proc/net/tcp6")
        assert not any(row.split()[1].endswith(":0050") and row.split()[3] == "0A" for row in sockets.splitlines()[1:]), sockets
    elif name == "l1_enabled":
        result = status(200)
        assert result["local"] == CLIENT and result["peer"] == INSTANCE, result
        # Resolve the instance's IPv4 endpoint from its own namespace, not host NAT.
        ipv4 = json.loads(run("docker", "inspect", "bunkerweb"))[0]["NetworkSettings"]["Networks"]["bw-services"]["IPAddress"]
        status(200, host=ipv4)
    elif name == "l2":
        result = status(200, port=443, tls=True)
        cert = subprocess.run(
            ["openssl", "x509", "-inform", "DER", "-noout", "-subject", "-issuer"],
            input=base64.b64decode(result["cert"]),
            capture_output=True,
            check=True,
        ).stdout.decode()
        print("TLS_CERT", cert, flush=True)
        assert "CN=www.example.com" in cert.replace(" ", ""), cert
        assert cert.splitlines()[0].removeprefix("subject=") == cert.splitlines()[1].removeprefix("issuer="), cert
    elif name == "l5":
        response = api("/health")
        assert response["status"] == 200 and json.loads(response["body"])["msg"] == "ok", response
        assert response["local"] == "fd42:1618:1::24", response
        status(200, client="ipv6-untrusted", host=API)
        denied = api("/ping", client="ipv6-untrusted")
        assert denied["status"] in (0, 403), denied
    elif name == "c1":
        forwarded = {"X-Forwarded-For": "2001:0DB8:0:0:0:0:0:A"}
        trusted = status(200, headers=forwarded)
        assert json.loads(trusted["body"])["xff"] == "2001:db8::a", trusted
        untrusted = status(200, client="ipv6-untrusted", host=API, headers=forwarded)
        assert json.loads(untrusted["body"])["xff"] == "fd42:1618:1::b", untrusted
    elif name == "blacklist":
        status(403)
        status(200, client="ipv6-untrusted", host=API)
    elif name == "whitelist":
        status(200)
        status(403, client="ipv6-untrusted", host=API)
    elif name == "c4":
        status(403)
        status(200, client="ipv6-untrusted", host=API)
        cache = run(
            "docker",
            "exec",
            "bw-scheduler",
            "sh",
            "-c",
            "cat /var/cache/bunkerweb/blacklist/*/IP.list /var/cache/bunkerweb/blacklist/IP.list 2>/dev/null || true",
        )
        print("FEED_CACHE", cache, flush=True)
        assert "fd42:1618:2::/64" in cache and "%eth0" not in cache, cache
    elif name == "c5":
        status(403, headers={"X-Forwarded-For": "::ffff:192.0.2.7"})
        status(200, headers={"X-Forwarded-For": "::ffff:192.0.3.7"})
    elif name in ("b1_api", "b1_cli"):
        bans(name.removeprefix("b1_"))
    elif name == "b3":
        limit()
    elif name == "u1":
        response = status(200)
        body = json.loads(response["body"])
        assert body["fixture"] == "ipv6-only" and body["peer"] == "fd42:1618:3::10", response
        backend = json.loads(run("docker", "inspect", "ipv6-backend"))[0]["NetworkSettings"]["Networks"]
        assert all(not value["IPAddress"] and value["GlobalIPv6Address"] for value in backend.values()), backend
    elif name in ("r1_bans", "r1_limits"):
        for key in redis("KEYS", "plugin_limit_*").splitlines():
            redis("DEL", key)
        if name == "r1_bans":
            bans("api")
        else:
            limit()
            keys = redis("KEYS", "plugin_limit_*").splitlines()
            print("REDIS_LIMIT_KEYS", keys, flush=True)
            assert "plugin_limit_www.example.com" + CLIENT + "/" in keys, keys
        clients = redis("CLIENT", "LIST")
        print("REDIS_CLIENTS", clients, flush=True)
        assert "fd42:1618:1::10" in clients, clients
    elif name == "network":
        version = run("docker", "version", "--format", "{{.Server.Version}}")
        print("DOCKER_SERVER_VERSION", version, flush=True)
        daemon_args = run("ps", "-C", "dockerd", "-o", "args=").split()
        print("DAEMON_IPV6_FLAG", any(arg.split("=")[0] == "--ipv6" for arg in daemon_args), flush=True)
        print("DAEMON_CUSTOM_CONFIG_FLAG", any(arg.split("=")[0] == "--config-file" for arg in daemon_args), flush=True)
        for network in ("bw-universe", "bw-services", "ipv6-backend", "bw-db"):
            data = json.loads(run("docker", "network", "inspect", network))[0]
            print("NETWORK", network, json.dumps(data), flush=True)
            assert data["EnableIPv6"], data
        daemon = Path("/etc/docker/daemon.json")
        print("DAEMON_JSON_SHA256", hashlib.sha256(daemon.read_bytes()).hexdigest() if daemon.exists() else "ABSENT", flush=True)
        print("DAEMON_JSON_IPV6", json.loads(daemon.read_text()).get("ipv6", False) if daemon.exists() else False, flush=True)
    else:
        raise AssertionError("unknown check: " + name)
    print("IPV6_CHECK_OK", name, flush=True)


if __name__ == "__main__":
    check(sys.argv[1])
