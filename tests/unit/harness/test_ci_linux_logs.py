"""UB5-5/7: Linux log reads select the service and keep complete in-scope records."""

import importlib.util
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def linux_logs(monkeypatch, tmp_path):
    alias = "ci_linux_utils"
    for name in ("docker", "k8s"):
        module = ModuleType(f"{alias}.{name}")
        module.get_logs = lambda *_: []
        module.run_command = lambda *_: (0, "")
        monkeypatch.setitem(sys.modules, module.__name__, module)
    spec = importlib.util.spec_from_file_location(alias, ROOT / "tests/utils/__init__.py", submodule_search_locations=[str(ROOT / "tests/utils")])
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, alias, module)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ERROR_LOG_FILE", tmp_path / "error.log")
    (tmp_path / "error.log").write_text("wrong stream\n")
    return module, tmp_path


def test_linux_logs_exclude_prior_action(linux_logs):
    module, directory = linux_logs
    (directory / "error.log").write_text("2026/11/06 10:00:00 old request\n2026/11/06 10:01:01 current request\n")
    logs = module.get_logs(logging.getLogger(__name__), "Linux", datetime(2026, 11, 6, 10, 1, tzinfo=timezone.utc))
    assert logs == ["2026/11/06 10:01:01 current request\n"]


def test_linux_upgrade_reads_scheduler_file(linux_logs):
    module, directory = linux_logs
    (directory / "error.log").write_text("nginx ready\n")
    (directory / "scheduler.log").write_text("❌ migration failed\n")
    logs = module.get_logs(logging.getLogger(__name__), "Linux", log_from="scheduler")
    assert logs == ["❌ migration failed\n"]


@pytest.mark.parametrize("service", ["scheduler", "ui", "api"])
@pytest.mark.parametrize("boundary", [datetime(2026, 11, 6, 10, 1, tzinfo=timezone.utc), "2026-11-06T10:01:00+00:00"])
def test_service_file_filters_timezone_aware_records(linux_logs, service, boundary):
    module, directory = linux_logs
    (directory / "error.log").write_text("wrong stream\n")
    old = f"[2026-11-06 11:00:59 +0100] [{service.upper()}] [123] [❌] - old\n"
    current = f"[2026-11-06 11:01:00 +0100] [{service.upper()}] [123] [❌] - current\n"
    (directory / f"{service}.log").write_text(old + current)
    assert module.get_logs(logging.getLogger(__name__), "Linux", boundary, log_from=service) == [current]


@pytest.mark.parametrize(
    "service,old,current",
    [
        ("bunkerweb", "2026/11/06 10:00:59 old record\n", "2026/11/06 10:01:00 new record\n"),
        ("scheduler", "[2026-11-06 10:00:59 +0000] [SCHEDULER] old record\n", "[2026-11-06 10:01:00 +0000] [SCHEDULER] new record\n"),
    ],
)
def test_multiline_record_crossing_boundary_keeps_its_header_time(linux_logs, service, old, current):
    module, directory = linux_logs
    filename = "error.log" if service == "bunkerweb" else f"{service}.log"
    (directory / filename).write_text(old + "Traceback from older action\n  old frame\n" + current + "Traceback from current action\n  current frame\n")
    assert module.get_logs(logging.getLogger(__name__), "Linux", "2026-11-06T10:01:00+00:00", log_from=service) == [
        current,
        "Traceback from current action\n",
        "  current frame\n",
    ]


def test_unparsable_continuation_stays_with_current_record(linux_logs):
    module, directory = linux_logs
    lines = ["2026/11/06 10:01:00 current record\n", "unparsable continuation\n"]
    (directory / "error.log").write_text("".join(lines))
    assert module.get_logs(logging.getLogger(__name__), "Linux", "2026-11-06T10:01:00+00:00") == lines


def test_bounded_read_rejects_orphan_line_without_timestamp(linux_logs):
    module, directory = linux_logs
    (directory / "error.log").write_text("orphan without a timestamp\n")
    with pytest.raises(ValueError, match="timestamp"):
        module.get_logs(logging.getLogger(__name__), "Linux", "2026-11-06T10:01:00+00:00")


def test_bounded_read_rejects_malformed_timestamp(linux_logs):
    module, directory = linux_logs
    (directory / "error.log").write_text("2026/11/06 10:01:00 current record\n2026/99/06 10:01:01 malformed record\n")
    with pytest.raises(ValueError, match="timestamp"):
        module.get_logs(logging.getLogger(__name__), "Linux", "2026-11-06T10:01:00+00:00")


def test_unbounded_read_preserves_unparsable_lines(linux_logs):
    module, directory = linux_logs
    lines = ["orphan line\n", "nginx: [emerg] invalid configuration\n"]
    (directory / "error.log").write_text("".join(lines))
    assert module.get_logs(logging.getLogger(__name__), "Linux") == lines


def test_unknown_linux_stream_is_rejected(linux_logs):
    module, directory = linux_logs
    (directory / "error.log").write_text("must not return nginx logs for another service\n")
    with pytest.raises(ValueError, match="Linux log"):
        module.get_logs(logging.getLogger(__name__), "Linux", log_from="database")


def test_second_precision_log_keeps_first_action_second(linux_logs):
    module, directory = linux_logs
    current = "2026/11/06 10:01:00 current request\n"
    (directory / "error.log").write_text("2026/11/06 10:00:59 previous request\n" + current)
    boundary = datetime(2026, 11, 6, 10, 1, 0, 900000, tzinfo=timezone.utc)
    assert module.get_logs(logging.getLogger(__name__), "Linux", boundary) == [current]


@pytest.mark.parametrize("integration,service", [("Docker", "ui"), ("Kubernetes", "ui"), ("Kubernetes", "api")])
def test_new_linux_sources_do_not_select_unsupported_container_stream(linux_logs, integration, service):
    module, _ = linux_logs
    with pytest.raises(ValueError, match="log source"):
        module.get_logs(logging.getLogger(__name__), integration, log_from=service)
