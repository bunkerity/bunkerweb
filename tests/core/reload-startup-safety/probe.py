"""Live probes for the startup half of reload safety, run against the harness's bunkerweb container.

Each subcommand prints what it observed and exits nonzero on the first broken promise:

- ``failed-render``: a template that fails to render in the worker ships nothing, so the instance keeps its
  files, keeps answering ``ok`` and keeps denying the blacklisted request.
- ``interrupted-install``: a restart that finds the install sentinel boots the loading configuration
  instead of the interrupted tree. A plain restart is run first as the control: it keeps the tree.
- ``kept-config-failure``: a preserved configuration whose ``init_by_lua`` fails (``nginx -t`` still says
  fine) falls back to the loading configuration once and the instance recovers.
"""

import io
import re
import subprocess
import sys
import tarfile
import time

import requests

INSTANCE = "http://127.0.0.1:5001"
CONTROL = "http://127.0.0.1:8888"
HEADERS = {"Host": "bwapi", "Authorization": "Bearer tests-secret-token"}
CONTAINER = "bunkerweb"
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
    """The instance's own state: ok, loading, reloading, needs_config, or down when unreachable."""
    try:
        response = SESSION.get(INSTANCE + "/health", headers=HEADERS, timeout=3)
        return response.json().get("msg", "?")
    except (requests.RequestException, ValueError):
        return "down"


def wait_for(description, predicate, timeout, step=0.5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(step)
    raise SystemExit(f"timed out waiting for {description}")


def policy(label):
    """The blacklisted request is denied and an ordinary one is served."""
    for agent, expected in (("ordinary-client", 200), ("BWReloadProbe", 403)):
        status = SESSION.get("http://127.0.0.1/", headers={"Host": "www.example.com", "User-Agent": agent}, timeout=10).status_code
        say(f"policy[{label}] {agent} -> {status}")
        if status != expected:
            raise SystemExit(f"policy[{label}]: {agent} got {status}, expected {expected}")


def tree_digest():
    """Content digest of the served configuration, without the generator's own bookkeeping."""
    return inside("cd /etc/nginx && find . -type f ! -name '.bw-*' ! -path './.bw-*' | sort | xargs sha256sum | sha256sum").stdout.split()[0]


def settled():
    """Wait until the instance enforces its pushed configuration."""
    wait_for("the instance to report ok", lambda: health() == "ok", 240)


def logs_since(epoch):
    result = docker("logs", "--since", str(epoch), CONTAINER)
    return result.stdout + result.stderr


def restart_and_watch():
    """Restart the container, return (epoch, first state it answered with, its variables.env IS_LOADING)."""
    epoch = int(time.time())
    docker("restart", CONTAINER)
    states = []

    def first_answer():
        state = health()
        if state != "down":
            states.append(state)
            return True
        return False

    wait_for("the instance to answer after the restart", first_answer, 120, step=0.2)
    return epoch, states[0], inside("grep -c '^IS_LOADING=yes' /etc/nginx/variables.env", check=False).stdout.strip()


def restart_count():
    return int(docker("inspect", "--format", "{{.RestartCount}}", CONTAINER).stdout.strip())


def plugin_archive():
    archive = io.BytesIO()
    plugin = (
        b'{"id": "renderfail", "name": "Render failure probe", "description": "Template that cannot render", '
        b'"version": "1.0", "stream": "no", "settings": {}}'
    )
    with tarfile.open(fileobj=archive, mode="w:gz") as bundle:
        for name, content in (("renderfail/plugin.json", plugin), ("renderfail/confs/http/renderfail.conf", b"{{ 1 / 0 }}\n")):
            entry = tarfile.TarInfo(name)
            entry.size = len(content)
            entry.mode = 0o640
            bundle.addfile(entry, io.BytesIO(content))
    archive.seek(0)
    return archive


def failed_render():
    settled()
    policy("before")
    before = tree_digest()
    say("digest before:", before)
    epoch = int(time.time())
    response = SESSION.post(
        CONTROL + "/plugins/upload",
        headers={"Authorization": HEADERS["Authorization"]},
        files={"files": ("renderfail.tar.gz", plugin_archive(), "application/gzip")},
        data={"method": "ui"},
        timeout=60,
    )
    say("upload", response.status_code, response.text)
    if response.status_code not in (200, 201):
        raise SystemExit("the probe plugin was not accepted")
    try:
        # The scheduler queues push-configs, the worker renders and fails
        def render_failed():
            logs = docker("logs", "--since", str(epoch), "bw-worker")
            return re.search(r"Error rendering template .*renderfail|division by zero", logs.stdout + logs.stderr)

        wait_for("the worker to report the render failure", render_failed, 240, step=2)
        say("worker reported the render failure")
        time.sleep(10)
        after = tree_digest()
        say("digest after:", after)
        if after != before:
            raise SystemExit("a failed render changed the served configuration")
        state = health()
        say("health after the failed render:", state)
        if state != "ok":
            raise SystemExit(f"instance left the ok state: {state}")
        policy("after the failed render")
    finally:
        removed = SESSION.delete(CONTROL + "/plugins/renderfail", headers={"Authorization": HEADERS["Authorization"]}, timeout=60)
        say("cleanup: delete plugin", removed.status_code)
    settled()
    policy("after cleanup")
    say("failed-render: the failed render shipped nothing and the blacklisted request stayed denied")


def interrupted_install():
    settled()
    policy("before")
    # Control: a plain restart keeps the tree and keeps enforcing from the first answer
    epoch, state, loading = restart_and_watch()
    text = logs_since(epoch)
    say("control restart: first state", state, "IS_LOADING=yes lines", loading)
    if "Preserving current config on restart" not in text:
        raise SystemExit("control restart did not keep the configuration")
    if state == "loading" or loading != "0":
        raise SystemExit("control restart served the loading configuration")
    policy("right after the control restart")
    settled()
    # An install killed half way leaves its sentinel; pushswap creates it before the first replaced file
    inside("touch /etc/nginx/.bw-install-incomplete")
    epoch, state, loading = restart_and_watch()
    text = logs_since(epoch)
    say("interrupted restart: first state", state, "IS_LOADING=yes lines", loading)
    if "Interrupted configuration install, regenerating the loading configuration" not in text:
        raise SystemExit("the interrupted install was not detected")
    if "Preserving current config on restart" in text:
        raise SystemExit("the interrupted install was kept")
    if state != "loading" or loading != "1":
        raise SystemExit("the restart did not boot the loading configuration")
    if inside("test -e /etc/nginx/.bw-install-incomplete", check=False).returncode == 0:
        raise SystemExit("the sentinel survived a complete loading render")
    settled()
    policy("after the scheduler pushed again")
    say("interrupted-install: the interrupted tree was not kept; the scheduler restored the configuration")


def kept_config_failure():
    settled()
    policy("before")
    # nginx -t does not run init_by_lua, so a fault only init trips passes it: multisite without a
    # SERVER_NAME makes init index a nil value
    inside("sed -i '/^SERVER_NAME=/d' /etc/nginx/variables.env && echo 'MULTISITE=yes' >> /etc/nginx/variables.env")
    check = inside("/usr/sbin/nginx -t -e /var/log/bunkerweb/error.log -c /etc/nginx/nginx.conf", check=False)
    say("nginx -t", check.returncode, check.stderr.strip().splitlines()[-1:])
    if check.returncode != 0:
        raise SystemExit("the fault must pass nginx -t, or the probe proves nothing about init")
    restarts = restart_count()
    epoch, state, loading = restart_and_watch()
    text = logs_since(epoch)
    say("fallback restart: first state", state, "IS_LOADING=yes lines", loading)
    fallbacks = text.count("The preserved configuration failed to start nginx")
    starts = text.count("Starting nginx ...")
    say("fallback notices", fallbacks, "nginx starts", starts)
    if fallbacks != 1 or starts != 2:
        raise SystemExit("expected exactly one fallback and two nginx starts")
    if state != "loading" or loading != "1":
        raise SystemExit("the fallback did not boot the loading configuration")
    if inside("grep -c '^MULTISITE=yes' /etc/nginx/variables.env", check=False).stdout.strip() != "0":
        raise SystemExit("the broken kept configuration is still installed")
    if restart_count() != restarts:
        raise SystemExit("the container restarted on its own: the entrypoint exited")
    settled()
    policy("after the scheduler pushed again")
    say("kept-config-failure: the failing kept configuration fell back once and the instance recovered")


COMMANDS = {"failed-render": failed_render, "interrupted-install": interrupted_install, "kept-config-failure": kept_config_failure}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        raise SystemExit("usage: probe.py " + "|".join(COMMANDS))
    COMMANDS[sys.argv[1]]()
