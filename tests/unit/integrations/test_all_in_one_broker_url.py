"""Execute the shipped AIO worker blocks with the Docker image environment.

Fresh healthcheck and bwcli processes inherit image ENV, not entrypoint exports. WAF Redis
settings must never choose their Celery broker; explicit broker URLs remain authoritative.
"""

from configparser import ConfigParser
from os import geteuid
from pathlib import Path
from shlex import split
from subprocess import run
from sys import executable

import pytest

ROOT = Path(__file__).resolve().parents[3]
AIO = ROOT / "src" / "all-in-one"
HEALTHCHECK = ROOT / "src" / "common" / "helpers" / "healthcheck-all-in-one.sh"
LOCAL_BROKER = "redis://127.0.0.1:6380/0"
EXTERNAL_BROKER = "rediss://worker:fake%40password@broker.example:6381/3?ssl_cert_reqs=required&ssl_ca_certs=/etc/my ca/ca.pem"


def image_env():
    return dict(
        split(line.removeprefix("ENV "))[0].split("=", 1)
        for line in (AIO / "Dockerfile").read_text().rsplit("\nFROM ", 1)[1].splitlines()
        if line.startswith("ENV ")
    )


def worker_block(which):
    path, start, end = {
        "entrypoint": (AIO / "entrypoint.sh", "# Worker service defaults", "# The scheduler and autoconf"),
        "healthcheck": (HEALTHCHECK, "# Check the worker only", "# Check autoconf service"),
    }[which]
    text = path.read_text()
    begin = text.index(start)
    stop = text.index(end, begin)
    return text[begin:stop]


def execute(which, tmp_path, env=None, *, broker_state="RUNNING", worker_state="RUNNING", pong="PONG", worker_ok=True):
    """Keep real shell conditionals and sed; replace only container paths and external probes."""
    units = tmp_path / "supervisor.d"
    units.mkdir(exist_ok=True)
    for unit in (AIO / "supervisor.d").glob("*.ini"):
        (units / unit.name).write_text(unit.read_text())
    block = worker_block(which).replace("/etc/supervisor.d", str(units)).replace("/data/broker", str(tmp_path / "broker"))
    script = (
        r"""log() { printf '%s\n' "$*"; }
supervisorctl() {
  printf 'status:%s\n' "$2" >> "$TRACE_FILE"
  if [ "$2" = broker ]; then printf 'broker %s\n' "$BROKER_STATE";
  else printf 'worker %s\n' "$WORKER_STATE"; fi
}
redis-cli() {
  printf 'redis-cli:%s\nredis-auth:%s\n' "$*" "${REDISCLI_AUTH-}" >> "$TRACE_FILE"
  printf '%s\n' "$PONG"
}
bash() { printf 'worker-url:%s\n' "$CELERY_BROKER_URL" >> "$TRACE_FILE"; return "$WORKER_EXIT"; }
"""
        + block
        + r"""
printf 'RESULT:broker=%s\nRESULT:redis=%s\n' "${CELERY_BROKER_URL-}" "${USE_REDIS-}"
"""
    )
    trace = tmp_path / "trace"
    proc = run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            **image_env(),
            "TRACE_FILE": str(trace),
            "BROKER_STATE": broker_state,
            "WORKER_STATE": worker_state,
            "PONG": pong,
            "WORKER_EXIT": "0" if worker_ok else "1",
            **(env or {}),
        },
    )
    results = dict(line.removeprefix("RESULT:").split("=", 1) for line in proc.stdout.splitlines() if line.startswith("RESULT:"))
    return proc, results, trace.read_text() if trace.exists() else ""


def unit_config(tmp_path, unit):
    config = ConfigParser(interpolation=None)
    config.read(tmp_path / "supervisor.d" / f"{unit}.ini")
    return config[f"program:{unit}"]


def test_image_environment_reaches_a_new_process():
    result = run(["bash", "-c", 'printf %s "$CELERY_BROKER_URL"'], env={"PATH": "/usr/bin:/bin", **image_env()}, capture_output=True, text=True, check=True)
    assert result.stdout == LOCAL_BROKER


def test_shipped_broker_config_preserves_queue_data():
    directives = dict((tokens[0], tokens[1:]) for line in (AIO / "conf" / "broker.conf").read_text().splitlines() if (tokens := split(line, comments=True)))
    expected = {
        "bind": ["127.0.0.1"],
        "port": ["6380"],
        "maxmemory": ["256mb"],
        "maxmemory-policy": ["noeviction"],
        "save": [""],
        "appendonly": ["yes"],
        "dir": ["/data/broker"],
    }
    assert {name: directives.get(name) for name in expected} == expected


@pytest.mark.parametrize("override", [None, "postgresql+psycopg://worker@database.example/bunkerweb"])
def test_image_database_uri_initializes_a_fresh_worker(override):
    # Run the actual child initializer without importing Celery or opening a database.
    script = """
import ast
import os
import sys
from pathlib import Path
from types import SimpleNamespace

tree = ast.parse(Path(sys.argv[1]).read_text())
initializer = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "init_worker_db")
initializer.decorator_list = []
sys.modules["Database"] = SimpleNamespace(Database=lambda logger: os.environ["DATABASE_URI"])
sys.modules["logger"] = SimpleNamespace(setup_logger=lambda name: None)
sys.modules["plugin_extensions"] = SimpleNamespace(register_plugin_models=lambda *args, **kwargs: None)
exec(compile(ast.Module(body=[initializer], type_ignores=[]), sys.argv[1], "exec"))
init_worker_db()
print(_worker_db)
"""
    env = {"PATH": "/usr/bin:/bin", **image_env()}
    if override is not None:
        env["DATABASE_URI"] = override
    result = run([executable, "-c", script, str(ROOT / "src" / "worker" / "app.py")], env=env, capture_output=True, text=True, check=True)
    assert result.stdout.strip() == (override or "sqlite:////var/lib/bunkerweb/db.sqlite3")


@pytest.mark.parametrize("which", ["entrypoint", "healthcheck"])
@pytest.mark.parametrize(
    "env",
    [
        {},
        {"USE_REDIS": "no"},
        {"USE_REDIS": "yes", "REDIS_HOST": "waf-redis.example", "REDIS_PORT": "6390", "REDIS_PASSWORD": "waf-only", "REDISCLI_AUTH": "waf-cli-only"},
        {"REDIS_HOST": "valkey", "REDIS_SSL": "yes", "REDIS_SSL_VERIFY": "no", "REDIS_SSL_CA": "/waf-ca.pem"},
    ],
)
def test_waf_settings_do_not_choose_the_broker(which, tmp_path, env):
    proc, values, trace = execute(which, tmp_path, env)
    assert proc.returncode == 0, proc.stderr
    assert values == {"broker": LOCAL_BROKER, "redis": env.get("USE_REDIS", "yes")}
    if which == "entrypoint":
        assert unit_config(tmp_path, "broker").getboolean("autostart")
        assert unit_config(tmp_path, "broker").getboolean("autorestart")
        assert (tmp_path / "broker").is_dir()
        assert (tmp_path / "broker").stat().st_mode & 0o777 == 0o770
    else:
        assert "status:broker" in trace
        assert "redis-cli:-h 127.0.0.1 -p 6380 ping" in trace
        assert "redis-auth:\n" in trace
        assert f"worker-url:{LOCAL_BROKER}" in trace


@pytest.mark.parametrize("which", ["entrypoint", "healthcheck"])
@pytest.mark.parametrize("url", ["redis://external:6379/3", EXTERNAL_BROKER, "rediss://external:6380/0?ssl_cert_reqs=none"])
def test_explicit_broker_url_is_preserved(which, tmp_path, url):
    proc, values, trace = execute(which, tmp_path, {"CELERY_BROKER_URL": url, "REDIS_SSL": "yes", "REDIS_HOST": "waf-redis"})
    assert proc.returncode == 0, proc.stderr
    assert values["broker"] == url
    if which == "entrypoint":
        assert not unit_config(tmp_path, "broker").getboolean("autostart")
        assert not (tmp_path / "broker").exists()
        assert "fake%40password" not in proc.stdout.split("RESULT:")[0]
    else:
        assert "status:broker" not in trace
        assert "redis-cli:" not in trace
        assert f"worker-url:{url}" in trace


@pytest.mark.parametrize("which", ["entrypoint", "healthcheck"])
@pytest.mark.parametrize("env", [{"SERVICE_WORKER": "no"}, {"SERVICE_SCHEDULER": "no"}, {"SERVICE_WORKER": ""}])
def test_disabled_worker_needs_no_broker(which, tmp_path, env):
    proc, _, trace = execute(which, tmp_path, {**env, "CELERY_BROKER_URL": "", "USE_REDIS": "no"})
    assert proc.returncode == 0, proc.stderr
    if which == "entrypoint":
        assert not unit_config(tmp_path, "worker").getboolean("autostart")
        assert not unit_config(tmp_path, "broker").getboolean("autostart")
        assert not (tmp_path / "broker").exists()
    else:
        assert not trace


@pytest.mark.parametrize("which", ["entrypoint", "healthcheck"])
def test_worker_can_be_enabled_without_scheduler(which, tmp_path):
    proc, values, trace = execute(which, tmp_path, {"SERVICE_SCHEDULER": "no", "SERVICE_WORKER": "yes"})
    assert proc.returncode == 0, proc.stderr
    assert values["broker"] == LOCAL_BROKER
    if which == "entrypoint":
        assert unit_config(tmp_path, "broker").getboolean("autostart")
        assert unit_config(tmp_path, "worker").getboolean("autorestart")
    else:
        assert "status:broker" in trace


@pytest.mark.parametrize("which", ["entrypoint", "healthcheck"])
def test_empty_broker_url_is_rejected_with_worker_enabled(which, tmp_path):
    proc, _, _ = execute(which, tmp_path, {"CELERY_BROKER_URL": ""})
    assert proc.returncode != 0
    assert "CELERY_BROKER_URL" in proc.stdout
    assert "empty" in proc.stdout.lower()


def test_unusable_broker_data_directory_fails_startup(tmp_path):
    (tmp_path / "broker").write_text("not a directory")
    proc, _, _ = execute("entrypoint", tmp_path)
    assert proc.returncode != 0
    assert "broker data directory" in proc.stdout.lower()


@pytest.mark.parametrize("mode", [0o500, 0o600])
@pytest.mark.skipif(geteuid() == 0, reason="directory permission checks require the unprivileged AIO runtime")
def test_broker_data_requires_write_and_search_permissions(tmp_path, mode):
    broker = tmp_path / "broker"
    broker.mkdir(mode=mode)
    try:
        proc, _, _ = execute("entrypoint", tmp_path)
        assert proc.returncode != 0
        assert "broker data directory" in proc.stdout.lower()
    finally:
        broker.chmod(0o700)


@pytest.mark.parametrize(
    "failure,diagnostic",
    [
        ({"broker_state": "FATAL"}, "broker"),
        ({"pong": "LOADING"}, "PING"),
        ({"worker_state": "FATAL"}, "worker"),
        ({"worker_ok": False}, "Worker health check failed"),
    ],
)
def test_healthcheck_detects_failed_broker_or_worker(tmp_path, failure, diagnostic):
    proc, _, _ = execute("healthcheck", tmp_path, **failure)
    assert proc.returncode != 0
    assert diagnostic in proc.stdout


def test_the_ca_reaches_every_client_that_reads_this_url(tmp_path):
    redis_parse = pytest.importorskip("redis.connection").parse_url
    kombu_parse = pytest.importorskip("kombu.utils.url").parse_url
    proc, values, _ = execute("entrypoint", tmp_path, {"CELERY_BROKER_URL": EXTERNAL_BROKER})
    assert proc.returncode == 0
    assert redis_parse(values["broker"])["ssl_ca_certs"] == "/etc/my ca/ca.pem"
    assert kombu_parse(values["broker"])["ssl"]["ssl_ca_certs"] == "/etc/my ca/ca.pem"
    no_ca = "rediss://external:6380/0?ssl_cert_reqs=required"
    assert "ssl_ca_certs" not in redis_parse(no_ca)
    assert "ssl_ca_certs" not in kombu_parse(no_ca)["ssl"]
