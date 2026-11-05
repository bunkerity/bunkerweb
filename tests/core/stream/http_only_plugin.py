#!/usr/bin/env python3
"""Probe for the `http_only_plugin_does_not_stop_a_stream_service` action of tests/core/stream.yml.

Installs an HTTP-only external plugin (`"stream": "no"`, its module raises when required in the stream Lua VM) next
to the running stream services, restarts the scheduler so it ships the plugin and reloads the instance, then checks
that the stream init loaded the plugin's metadata without requiring it, and that the stream service still answers.

A rejected reload keeps the last working configuration, which still answers; the checks therefore also read the
instance log since the restart for the abort line and for the plugin being loaded by both init phases.
"""

import socket
from re import compile
import subprocess
import sys
import time
from pathlib import Path

INSTANCE = "bunkerweb"
SCHEDULER = "bw-scheduler"
NETWORK = "bw-universe"
PLUGIN = "http_only_probe"
PORT = 10000
FIXTURE = Path(__file__).resolve().parent / PLUGIN
# nginx-hello (the `app1` fixture) prints this label on every GET, as HTML.
BACKEND_MARK = compile(rb"Server(&nbsp;| )name")
REQUEST = b"GET / HTTP/1.0\r\nHost: stream.example.com\r\n\r\n"


def fail(message: str) -> None:
    print(f"stream http_only_plugin: {message}", file=sys.stderr)
    sys.exit(1)


def docker(*args: str, check: bool = True) -> str:
    process = subprocess.run(["docker", *args], capture_output=True, text=True, check=False)
    if check and process.returncode != 0:
        fail(f"docker {' '.join(args)} failed: {process.stderr.strip()}")
    return process.stdout + process.stderr


def served() -> bool:
    ip = docker("inspect", "-f", f'{{{{(index .NetworkSettings.Networks "{NETWORK}").IPAddress}}}}', INSTANCE).strip()
    try:
        with socket.create_connection((ip, PORT), timeout=8) as sock:
            sock.settimeout(8)
            sock.sendall(REQUEST)
            data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    return BACKEND_MARK.search(data) is not None
                data += chunk
    except OSError:
        return False


def wait_for(check, what: str, timeout: float = 180.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(2)
    fail(f"timed out waiting for {what}")


started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
docker("cp", str(FIXTURE), f"{SCHEDULER}:/data/plugins/")
docker("restart", SCHEDULER)
print(f"stream http_only_plugin: installed {PLUGIN} in {SCHEDULER}, scheduler restarted")


def on_instance() -> bool:
    probe = subprocess.run(["docker", "exec", INSTANCE, "test", "-f", f"/etc/bunkerweb/plugins/{PLUGIN}/plugin.json"], capture_output=True, check=False)
    return probe.returncode == 0


wait_for(on_instance, "the plugin to reach the instance")


def loaded_by_both_inits() -> bool:
    return docker("logs", "--since", started, INSTANCE, check=False).count(f"loaded plugin {PLUGIN} ") >= 2


try:
    wait_for(loaded_by_both_inits, "the http and stream init phases to load the plugin")
except SystemExit:
    log = docker("logs", "--since", started, INSTANCE, check=False)
    aborted = [line for line in log.splitlines() if "can't load plugin" in line or "ngx_lua 0.9.5+ required" in line]
    fail(f"the plugin was not loaded by both init phases; {aborted[-3:] or 'no abort line either'}")
print(f"stream http_only_plugin: both init phases loaded {PLUGIN}")

log = docker("logs", "--since", started, INSTANCE, check=False)
if "ngx_lua 0.9.5+ required" in log:
    fail("a require of the HTTP-only plugin ran in a Lua VM that must skip it")
wait_for(served, f"an answer on the stream port :{PORT}")
print(f"stream http_only_plugin: the stream service answers on :{PORT}")
print("stream http_only_plugin: all checks passed")
