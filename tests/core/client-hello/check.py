"""The per-service TLS ClientHello hook runs for a NAMED service, live.

A test plugin (tests/core/client-hello/plugin/hellotest) exports a module-level `client_hello(hello)`. It is
listed in PLUGINS_ORDER_SSL_CLIENT_HELLO, installed on the instance through the instance API (the way
reload-readiness.yml installs a plugin) and loaded by a reload. It closes the handshake for the service
`drop.example.com` and only reports for the other named services. Both are named services of a multisite stack,
so a reset for drop.example.com and a "service=www.example.com" report can only come from the per-service hook.
Before the plugin is installed the same handshake completes: the reset comes from the plugin, not from the setup.
"""

import io
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
API = "http://127.0.0.1:5001"
HEADERS = {"Host": "bwapi", "Authorization": "Bearer tests-secret-token"}
session = requests.Session()
session.trust_env = False


def fail(message):
    print(f"client-hello: {message}", file=sys.stderr)
    for container in ("bunkerweb",):
        process = subprocess.run(["docker", "logs", "--tail", "60", container], text=True, capture_output=True, timeout=60, check=False)
        print((process.stdout + process.stderr)[-6000:], file=sys.stderr)
    sys.exit(1)


def handshake(host):
    """(curl exit code, http status) of a TLS handshake whose SNI is `host`."""
    process = subprocess.run(
        ["curl", "-sk", "--max-time", "10", "--resolve", f"{host}:443:127.0.0.1", "-o", "/dev/null", "-w", "%{http_code}", f"https://{host}/"],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    return process.returncode, process.stdout.strip() or "000"


def request(method, path, **kwargs):
    response = session.request(method, API + path, headers=HEADERS, timeout=(5, 60), **kwargs)
    print(method, path, response.status_code, response.text[:300], flush=True)
    return response


def install_plugin():
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as bundle:
        for path in sorted((HERE / "plugin").rglob("*")):
            if path.is_file():
                bundle.add(path, arcname=str(path.relative_to(HERE / "plugin")))
    archive.seek(0)
    response = request("POST", "/plugins", files={"archive.tar.gz": ("archive.tar.gz", archive, "application/gzip")})
    if response.status_code != 200:
        fail(f"plugin upload refused: {response.status_code} {response.text}")


# The handshake completes for both services before the plugin exists.
for host in ("www.example.com", "drop.example.com"):
    rc, code = handshake(host)
    print(f"before: {host} -> curl {rc} http {code}", flush=True)
    if rc != 0:
        fail(f"before the plugin is installed the handshake for {host} must complete, curl exit {rc}")

install_plugin()
response = request("POST", "/reload?test=yes")
if response.status_code != 200:
    fail(f"reload after the plugin install failed: {response.status_code} {response.text}")

deadline = time.time() + 60
rc = 0
while time.time() < deadline:
    rc, code = handshake("drop.example.com")
    print(f"after: drop.example.com -> curl {rc} http {code}", flush=True)
    if rc in (35, 56):
        break
    time.sleep(3)
else:
    fail(f"the handshake for the named service drop.example.com was not reset (last curl exit {rc}): the per-service ClientHello hook did not run the plugin")

rc, code = handshake("www.example.com")
print(f"after: www.example.com -> curl {rc} http {code}", flush=True)
if rc != 0:
    fail(f"a service the plugin only reports for must still be served, curl exit {rc}")

logs = subprocess.run(["docker", "logs", "--since", "10m", "bunkerweb"], text=True, capture_output=True, timeout=60, check=False)
text = logs.stdout + logs.stderr
for needle in ("plugin hellotest dropped", "hellotest service=drop.example.com", "plugin hellotest would drop", "hellotest service=www.example.com"):
    if needle not in text:
        fail(f"log line missing: {needle!r}")
print("CLIENT_HELLO_OK named service")
