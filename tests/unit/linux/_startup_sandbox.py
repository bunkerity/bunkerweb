"""Run the shipped Docker entrypoint and Linux start script against a temporary root.

Every absolute path of the script is rewritten under ``root``. ``nginx`` and ``python3`` are stubs that log
what they were asked to do, so a test reads the ordering of renders and starts from ``calls.log``.

Stub controls, one file each under ``root/ctl``:
- ``render_rc``: exit status of ``gen/main.py`` (default 0). A success writes ``config.kind = loading``.
- ``render_sleep``: seconds ``gen/main.py`` sleeps first.
- ``nginx_mode``: ``ok``, ``kept-fails`` (init rejects the preserved config only), ``slow-kept-fails``
  (same, after 1.5 s) or ``all-fail``.
"""

from pathlib import Path
import os
import re
import signal
import stat
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
PATHS = re.compile(r"(?<![\w.])(/usr/share/bunkerweb|/etc/nginx|/etc/bunkerweb|/var/tmp|/var/run|/var/log|/tmp/variables\.env)")

UTILS = """
log() { echo "log: $*" >> "$SANDBOX/calls.log"; }
handle_docker_secrets() { :; }
redeem_enrollment_code() { :; }
check_instance_credential() { return 0; }
generate_default_server_cert() { return 0; }
generate_api_server_cert() { return 0; }
get_python_bin() { echo python3; }
get_bunkerweb_pythonpath() { echo /unused; }
get_nginx_bin() { echo nginx; }
get_nginx_conf_dir() { echo "$SANDBOX/etc/nginx"; }
run_as_nginx() { "$@"; }
"""

PYTHON3 = """#!/bin/bash
case "$1" in
*/gen/main.py)
    echo "render $*" >> "$SANDBOX/calls.log"
    [ -f "$SANDBOX/ctl/render_sleep" ] && sleep "$(cat "$SANDBOX/ctl/render_sleep")"
    rc=0
    [ -f "$SANDBOX/ctl/render_rc" ] && rc="$(cat "$SANDBOX/ctl/render_rc")"
    [ "$rc" -eq 0 ] && echo loading > "$SANDBOX/etc/nginx/config.kind"
    exit "$rc"
    ;;
*/modsecurity_audit.py)
    exit 0
    ;;
esac
exec /usr/bin/python3 "$@"
"""

NGINX = """#!/bin/bash
pid_file="$SANDBOX/var/run/bunkerweb/nginx.pid"
mode="$(cat "$SANDBOX/ctl/nginx_mode" 2>/dev/null || echo ok)"
kind="$(cat "$SANDBOX/etc/nginx/config.kind" 2>/dev/null || echo kept)"
if [ "$1" = "-s" ]; then
    echo "nginx -s $2" >> "$SANDBOX/calls.log"
    [ -f "$pid_file" ] || exit 1
    kill -TERM "$(cat "$pid_file")" 2>/dev/null
    exit 0
fi
echo "nginx start kind=$kind" >> "$SANDBOX/calls.log"
fails=no
case "$mode" in
all-fail) fails=yes ;;
kept-fails) [ "$kind" = kept ] && fails=yes ;;
slow-kept-fails) [ "$kind" = kept ] && { fails=yes ; sleep 1.5 ; } ;;
esac
master() {
    sleep 0.3
    echo "$BASHPID" > "$pid_file"
    trap 'rm -f "$pid_file"; exit 0' TERM QUIT INT
    while :; do sleep 0.1; done
}
if [ "$fails" = yes ]; then
    echo "nginx: [emerg] init_by_lua error" >&2
    exit 1
fi
if [ "$1" = "-g" ]; then
    # Docker: nginx stays in the foreground and is the entrypoint's child
    master
else
    # Linux: nginx daemonizes once it parsed the configuration and ran init_by_lua
    master > /dev/null 2>&1 < /dev/null &
    exit 0
fi
"""

CURL = "#!/bin/bash\necho loading\n"
NOOP = "#!/bin/bash\nexit 0\n"


class Sandbox:
    def __init__(self, tmp_path: Path, variant: str):
        self.root = tmp_path / "root"
        self.variant = variant
        self.relative = {"docker": "src/bw/entrypoint.sh", "linux": "src/linux/scripts/start.sh"}[variant]
        for directory in (
            "usr/share/bunkerweb/helpers",
            "usr/share/bunkerweb/gen",
            "usr/share/bunkerweb/utils",
            "etc/nginx",
            "etc/bunkerweb",
            "var/tmp/bunkerweb",
            "var/run/bunkerweb",
            "var/log/bunkerweb",
            "tmp",
            "ctl",
            "bin",
        ):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        base = self.root / "usr/share/bunkerweb"
        (base / "VERSION").write_text("1.7.0\n")
        (base / "helpers/utils.sh").write_text(UTILS)
        self._executable(base / "helpers/data.sh", NOOP)
        for name, content in (("python3", PYTHON3), ("nginx", NGINX), ("curl", CURL), ("chown", NOOP), ("setcap", NOOP)):
            self._executable(self.root / "bin" / name, content)
        script = PATHS.sub(lambda match: str(self.root) + match.group(1), (ROOT / self.relative).read_text())
        self.script = self.root / "script.sh"
        self._executable(self.script, script)
        (self.root / "calls.log").touch()
        (self.root / "etc/bunkerweb/variables.env").write_text("KEEP_CONFIG_ON_RESTART=yes\n")

    @staticmethod
    def _executable(path: Path, content: str) -> None:
        path.write_text(content)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def control(self, name: str, value: str) -> None:
        (self.root / "ctl" / name).write_text(value)

    def keep_a_config(self, *, interrupted: bool = False) -> None:
        """Leave what a previous run installed: a startup env file and a config of kind ``kept``."""
        tmp_env = self.root / ("var/tmp/bunkerweb/tmp.env" if self.variant == "linux" else "tmp/variables.env")
        tmp_env.write_text("IS_LOADING=yes\n")
        (self.root / "etc/nginx/config.kind").write_text("kept\n")
        if interrupted:
            (self.root / "etc/nginx/.bw-install-incomplete").touch()

    @property
    def startup_env(self) -> dict:
        """The settings the script handed to the generator for the loading configuration."""
        path = self.root / ("var/tmp/bunkerweb/tmp.env" if self.variant == "linux" else "tmp/variables.env")
        return dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)

    @property
    def calls(self) -> list[str]:
        return [line for line in (self.root / "calls.log").read_text().splitlines() if not line.startswith("log: ")]

    @property
    def log_lines(self) -> list[str]:
        return [line for line in (self.root / "calls.log").read_text().splitlines() if line.startswith("log: ")]

    @property
    def pid_file(self) -> Path:
        return self.root / "var/run/bunkerweb/nginx.pid"

    def start(self, extra_env: dict | None = None) -> subprocess.Popen:
        env = {
            "PATH": f"{self.root}/bin:/usr/bin:/bin",
            "SANDBOX": str(self.root),
            "SKIP_ASCII_BANNER": "yes",
            "KEEP_CONFIG_ON_RESTART": (self.root / "ctl/keep").read_text() if (self.root / "ctl/keep").exists() else "yes",
            "HOME": str(self.root),
            **(extra_env or {}),
        }
        args = ["bash", str(self.script)] + (["start"] if self.variant == "linux" else [])
        return subprocess.Popen(args, env=env, stdout=(self.root / "out.log").open("w"), stderr=subprocess.STDOUT, start_new_session=True)

    def wait_for(self, predicate, timeout: float = 15.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.05)
        raise AssertionError(f"timed out; calls={self.calls} log={self.log_lines}")

    def stop_nginx(self) -> None:
        """End a running stub master the way an operator's stop would."""
        pid = int(self.pid_file.read_text())
        os.kill(pid, signal.SIGTERM)

    def finish(self, process: subprocess.Popen, timeout: float = 20.0) -> int:
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            raise
