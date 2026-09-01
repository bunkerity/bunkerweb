from configparser import ConfigParser
from importlib.util import module_from_spec, spec_from_file_location
from logging import getLogger
from pathlib import Path
from re import findall
from sys import modules
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
UNITS_DIR = ROOT / "src" / "all-in-one" / "supervisor.d"
LOGSTREAM = ROOT / "src" / "all-in-one" / "logstream.sh"

docker = ModuleType("docker")
docker.DockerClient = type("DockerClient", (), {})
docker_models = ModuleType("docker.models")
docker_containers = ModuleType("docker.models.containers")
docker_containers.Container = type("Container", (), {})
docker_errors = ModuleType("docker.errors")
docker_errors.NotFound = type("NotFound", (Exception,), {})
with patch.dict(
    modules,
    {"docker": docker, "docker.models": docker_models, "docker.models.containers": docker_containers, "docker.errors": docker_errors},
):
    spec = spec_from_file_location("test_harness_docker", ROOT / "tests" / "utils" / "docker.py")
    docker_utils = module_from_spec(spec)
    spec.loader.exec_module(docker_utils)


class FakeContainer:
    def __init__(self, logs: str, labels: dict):
        self._logs = logs.encode("utf-8")
        self.labels = labels

    def logs(self, **_kwargs):
        return self._logs


def get_logs(monkeypatch, logs: str, labels: dict, component: str):
    container = FakeContainer(logs, labels)
    monkeypatch.setattr(docker_utils, "get_container", lambda _logger, _type: container)
    return docker_utils.get_logs(getLogger(__name__), component, None)


def shipped_aio_log_tags():
    commands = []
    for unit in sorted(UNITS_DIR.glob("*.ini")):
        parser = ConfigParser(inline_comment_prefixes=(";",), strict=False, interpolation=None)
        parser.read(unit)
        commands.append(parser.get(f"program:{unit.stem}", "command"))
    commands.extend(line for line in LOGSTREAM.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("#"))
    return set(findall(r"\[[A-Z]+(?:\.[A-Z]+)*\]", "\n".join(commands)))


def test_aio_scheduler_logs_ignore_worker_errors_without_hiding_scheduler_errors(monkeypatch):
    worker_error = "2026-08-26T17:05:23Z [WORKER] [UPDATE-CHECK] [❌] rate limited"
    scheduler_info = "2026-08-26T17:05:24Z [SCHEDULER] configuration applied"
    labels = {"bunkerweb.type": "all-in-one"}

    scoped = get_logs(monkeypatch, f"{worker_error}\n{scheduler_info}\n", labels, "scheduler")
    assert scoped == [scheduler_info]
    assert all("❌" not in line for line in scoped)

    scheduler_error = "2026-08-26T17:05:25Z [SCHEDULER] [❌] reload failed"
    scoped = get_logs(monkeypatch, f"{worker_error}\n{scheduler_error}\n", labels, "scheduler")
    assert scoped == [scheduler_error]
    assert any("❌" in line for line in scoped)


def test_aio_scheduler_scope_uses_the_leading_component_tag(monkeypatch):
    worker_line = "2026-08-26T17:05:23Z [WORKER] restarting after [SCHEDULER] request"
    scheduler_line = "2026-08-26T17:05:24Z [SCHEDULER] configuration applied"

    assert get_logs(monkeypatch, f"{worker_line}\n{scheduler_line}", {"bunkerweb.type": "all-in-one"}, "scheduler") == [scheduler_line]


def test_aio_bunkerweb_logs_keep_nginx_and_modsecurity_streams(monkeypatch):
    lines = [
        "2026-08-26T17:05:23Z [WORKER] [❌] unrelated worker error",
        "2026-08-26T17:05:24Z [BUNKERWEB] entrypoint ready",
        "2026-08-26T17:05:25Z [NGINX.ACCESS] request served",
        "2026-08-26T17:05:26Z [NGINX.ERROR] nginx diagnostic",
        "2026-08-26T17:05:27Z [MODSEC] [❌] rule loading failed",
    ]

    scoped = get_logs(monkeypatch, "\n".join(lines), {"bunkerweb.type": "all-in-one"}, "bunkerweb")
    assert scoped == lines[1:]
    assert any("❌" in line for line in scoped)


def test_non_aio_logs_are_unchanged(monkeypatch):
    lines = [
        "2026-08-26T17:05:23Z scheduler line without an AIO prefix",
        "2026-08-26T17:05:24Z [WORKER] [❌] line from a dedicated container",
    ]

    assert get_logs(monkeypatch, "\n".join(lines), {"bunkerweb.type": "scheduler"}, "scheduler") == lines


def test_unmapped_aio_component_logs_are_unchanged(monkeypatch):
    lines = [
        "2026-08-26T17:05:23Z [WORKER] database job",
        "2026-08-26T17:05:24Z untagged database diagnostic",
    ]

    assert get_logs(monkeypatch, "\n".join(lines), {"bunkerweb.type": "all-in-one"}, "database") == lines


def test_known_aio_log_tags_match_the_shipped_producers():
    assert set(docker_utils.AIO_RECOGNIZED_LOG_TAGS) == shipped_aio_log_tags()


def test_aio_scopes_keep_untagged_failures(monkeypatch):
    worker_error = "2026-08-26T17:05:23Z [WORKER] [❌] unrelated worker error"
    fatal = "2026-08-26T17:05:24Z INFO exited: scheduler (entered FATAL state)"
    entrypoint_error = "2026-08-26T17:05:25Z [2026-08-26 17:05:25] - ENTRYPOINT - ❌ - Failed to create Redis data directory"
    labels = {"bunkerweb.type": "all-in-one"}

    for component in ("scheduler", "bunkerweb"):
        assert get_logs(monkeypatch, "\n".join((worker_error, fatal, entrypoint_error)), labels, component) == [fatal, entrypoint_error]
