"""A HUP sent to the all-in-one container while an install is in progress waits, then reloads.

The install sentinel is planted by hand, exactly as pushswap and the generator leave it for the length of
an install, because a real install lasts well under a second and cannot be held open from outside.
"""

import json
import subprocess
import time

import requests

CONTAINER = "bunkerweb-all-in-one"
SENTINEL = "/etc/nginx/.bw-install-incomplete"
SESSION = requests.Session()
SESSION.trust_env = False


def say(*parts):
    print(*parts, flush=True)


def docker(*argv, check=True):
    result = subprocess.run(["docker", *argv], capture_output=True, text=True)
    if check and result.returncode != 0:
        raise SystemExit(f"docker {' '.join(argv)} failed: {result.stderr}")
    return result


def inside(script, check=True):
    return docker("exec", CONTAINER, "sh", "-c", script, check=check)


def health():
    """The instance's own state, asked from inside: the AIO instance API listens on loopback only."""
    result = inside("curl -s -H 'Host: bwapi' -H 'Authorization: Bearer tests-secret-token' http://127.0.0.1:5000/health", check=False)
    try:
        return json.loads(result.stdout).get("msg", "?")
    except ValueError:
        return "down"


def wait_for(description, predicate, timeout, step=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(step)
    raise SystemExit(f"timed out waiting for {description}")


def policy(label):
    for agent, expected in (("ordinary-client", 200), ("BWReloadProbe", 403)):
        status = SESSION.get("http://127.0.0.1/", headers={"Host": "www.example.com", "User-Agent": agent}, timeout=10).status_code
        say(f"policy[{label}] {agent} -> {status}")
        if status != expected:
            raise SystemExit(f"policy[{label}]: {agent} got {status}, expected {expected}")


def nginx_pid():
    return inside("cat /var/run/bunkerweb/nginx.pid", check=False).stdout.strip()


def logs_since(epoch):
    result = docker("logs", "--since", str(epoch), CONTAINER)
    return result.stdout + result.stderr


wait_for("the instance to report ok", lambda: health() == "ok", 300)
policy("before")
pid = wait_for("a nginx pid", nginx_pid, 30)
say("nginx master before:", pid)
inside(f"touch {SENTINEL}")
epoch = int(time.time())
docker("kill", "-s", "HUP", CONTAINER)
wait_for("the reload to start waiting", lambda: "waiting for it before reloading" in logs_since(epoch), 30)
say("the HUP is waiting for the install")
time.sleep(10)
text = logs_since(epoch)
if "Reload successful" in text or "supervisorctl" in text:
    raise SystemExit("the reload ran while the install was in progress")
if nginx_pid() != pid:
    raise SystemExit("the services were restarted while the install was in progress")
policy("during the wait")
say("nginx master after 10 s of waiting:", nginx_pid())
inside(f"rm -f {SENTINEL}")
wait_for("the reload to finish", lambda: "Reload successful" in logs_since(epoch), 180)
new_pid = wait_for("a new nginx pid", lambda: (nginx_pid() not in ("", pid)) and nginx_pid(), 120)
say("nginx master after the reload:", new_pid)
wait_for("the instance to report ok", lambda: health() == "ok", 300)
policy("after the reload")
say("hup-waits: the services were left alone until the install ended")
