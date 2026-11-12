"""Host discovery and logging decisions use isolated files and never contact syslog."""

import hashlib
import io
import logging
import re
from pathlib import Path
import runpy
from unittest.mock import Mock

import pytest

import common_utils as utils
import certificate_validation

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def host_files(tmp_path, monkeypatch):
    def path(*parts):
        original = Path(*parts)
        return tmp_path / original.relative_to("/") if original.is_absolute() else original

    monkeypatch.setattr(utils, "Path", path)
    return path


@pytest.mark.parametrize("contents", [None, "NAME=Debian\n", "NAME=Alpine\n"])
def test_docker_secrets_are_alpine_only(host_files, capsys, monkeypatch, contents):
    if contents is not None:
        release = host_files("/etc/os-release")
        release.parent.mkdir()
        release.write_text(contents)
    secrets = host_files("/run/secrets")
    secrets.mkdir(parents=True)
    (secrets / "api_token").write_text(" token-value\n")
    (secrets / "directory").mkdir()
    (secrets / "unreadable").write_text("hidden")
    read = Path.read_text

    def read_text(path, *args, **kwargs):
        if path.name == "unreadable":
            raise OSError("fixture permission denied")
        return read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    result = utils.handle_docker_secrets()
    if contents == "NAME=Alpine\n":
        assert result == {"API_TOKEN": "token-value"}
        assert "Failed to read Docker secret unreadable: fixture permission denied" in capsys.readouterr().out
    else:
        assert result == {} and capsys.readouterr().out == ""


def test_unreadable_os_release_ignores_secrets(host_files, monkeypatch):
    release = host_files("/etc/os-release")
    release.parent.mkdir()
    release.touch()
    monkeypatch.setattr(Path, "read_text", Mock(side_effect=OSError("fixture unreadable")))
    assert utils.handle_docker_secrets() == {}


@pytest.mark.parametrize(
    "variables,marker,release,expected",
    [
        ({"KUBERNETES_MODE": "YES", "SWARM_MODE": "yes"}, None, None, "Kubernetes"),
        ({"SWARM_MODE": "yes", "AUTOCONF_MODE": "yes"}, None, None, "Swarm"),
        ({"AUTOCONF_MODE": "YES"}, None, None, "Autoconf"),
        ({}, "linux\n", "NAME=Alpine", "Linux"),
        ({}, None, "NAME=Alpine", "Docker"),
        ({}, None, "NAME=Debian", "Linux"),
        ({}, None, None, "Linux"),
    ],
)
def test_integration_precedence(host_files, monkeypatch, variables, marker, release, expected):
    for name in ("KUBERNETES_MODE", "SWARM_MODE", "AUTOCONF_MODE"):
        monkeypatch.delenv(name, raising=False)
    for name, value in variables.items():
        monkeypatch.setenv(name, value)
    for target, value in (("/usr/share/bunkerweb/INTEGRATION", marker), ("/etc/os-release", release)):
        if value is not None:
            path = host_files(target)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value)
    assert utils.get_integration() == expected


def test_integration_read_error_is_unknown(host_files, monkeypatch):
    for name in ("KUBERNETES_MODE", "SWARM_MODE", "AUTOCONF_MODE"):
        monkeypatch.delenv(name, raising=False)
    marker = host_files("/usr/share/bunkerweb/INTEGRATION")
    marker.parent.mkdir(parents=True)
    marker.touch()
    monkeypatch.setattr(Path, "read_text", Mock(side_effect=OSError("fixture unreadable")))
    assert utils.get_integration() == "Unknown"


def test_os_metadata_and_version_are_read_from_installed_files(host_files, monkeypatch):
    release = host_files("/etc/os-release")
    release.parent.mkdir()
    release.write_text('NAME="Fixture Linux"\nVERSION="42"\nVERSION_ID="42"\nVERSION_CODENAME="fixture"\nID=fixture\nIGNORED=yes\nmalformed\n')
    monkeypatch.setattr(utils, "machine", lambda: "fixture-arch")
    assert utils.get_os_info() == dict(name="Fixture Linux", version="42", version_id="42", version_codename="fixture", id="fixture", arch="fixture-arch")
    version = host_files("/usr/share/bunkerweb/VERSION")
    version.parent.mkdir(parents=True)
    version.write_text("1.6.18~rc3\n")
    assert utils.get_version() == "1.6.18~rc3"


@pytest.mark.parametrize(
    "v2,v1,expected",
    [
        ("150000 100000", None, 2),
        ("max 100000", ("50000", "100000"), 1),
        ("invalid", ("200001", "100000"), 3),
        ("0 100000", ("-1", "100000"), None),
        (None, None, None),
    ],
)
def test_cgroup_limits_round_up_and_fall_back(host_files, v2, v1, expected):
    files = {"/sys/fs/cgroup/cpu.max": v2}
    if v1:
        files.update({"/sys/fs/cgroup/cpu/cpu.cfs_quota_us": v1[0], "/sys/fs/cgroup/cpu/cpu.cfs_period_us": v1[1]})
    for target, content in files.items():
        if content is not None:
            path = host_files(target)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    assert utils._cgroup_cpu_limit() == expected


@pytest.mark.parametrize("cpus,affinity,cgroup,expected", [(8, {0, 1, 2}, 2, 2), (None, set(), None, 1), (8, OSError("unavailable"), None, 8)])
def test_effective_cpu_count_obeys_smallest_available_limit(monkeypatch, cpus, affinity, cgroup, expected):
    monkeypatch.setattr(utils, "cpu_count", lambda: cpus)
    monkeypatch.setattr(utils, "sched_getaffinity", Mock(side_effect=affinity) if isinstance(affinity, Exception) else lambda pid: affinity)
    monkeypatch.setattr(utils, "_cgroup_cpu_limit", lambda: cgroup)
    assert utils.effective_cpu_count() == expected


@pytest.mark.parametrize("workers,threads,expected", [("invalid", "invalid", 32), ("4", "40", 96), ("-1", "0", 32)])
def test_shared_pool_size_has_floor_and_handles_invalid_configuration(monkeypatch, workers, threads, expected):
    monkeypatch.setenv("MAX_WORKERS", workers)
    monkeypatch.setenv("MAX_THREADS", threads)
    assert utils.shared_redis_pool_size() == expected


def test_hashes_match_standard_library_and_rewind_stream(tmp_path):
    payload = b"content" * 600
    target = tmp_path / "payload"
    target.write_bytes(payload)
    stream = io.BytesIO(payload)
    expected = hashlib.sha256(payload).hexdigest()
    assert utils.file_hash(str(target), algorithm="sha256") == expected
    assert utils.bytes_hash(payload, algorithm="sha256") == expected
    assert utils.bytes_hash(stream, algorithm="sha256") == expected and stream.tell() == 0
    assert utils.bytes_hash("content", algorithm="sha256") == hashlib.sha256(b"content").hexdigest()
    assert utils.dict_to_frozenset({"a": {"b": [3, 1]}, "c": 2}) == frozenset({("a", frozenset({("b", (1, 3))})), ("c", 2)})


def test_release_pagination_and_stable_line_selection():
    older = {"tag_name": "v1.6.18"}
    newer = {"tag_name": "v1.7.1"}
    response = Mock()
    response.json.side_effect = [[older] * 100, [newer]]
    get = Mock(return_value=response)
    releases = utils.fetch_bunkerweb_releases(get)
    assert releases == [older] * 100 + [newer]
    assert get.call_count == 2 and "page=2" in get.call_args.args[0]
    assert get.call_args.kwargs["timeout"] == 3
    candidates = [
        None,
        {},
        {"tag_name": "dev"},
        {"tag_name": "1.6.19~rc1"},
        {"tag_name": "1.6.20", "draft": True},
        {"tag_name": "1.6.21", "prerelease": True},
        *releases,
    ]
    assert utils.pick_latest_line_release(candidates, "v1.6.17~rc3") == older
    assert utils.pick_latest_line_release(candidates, "dev") == newer
    assert utils.pick_latest_line_release(candidates, "1.8.0~rc1") == newer
    assert utils.is_newer_version_available("v1.6.18~rc3", "1.6.18")
    assert not utils.is_newer_version_available("dev", "1.6.18")


def test_release_fetch_stops_on_error_object_and_propagates_transport_failure():
    response = Mock()
    response.json.return_value = {"message": "fixture limit"}
    assert utils.fetch_bunkerweb_releases(Mock(return_value=response)) == []
    response.raise_for_status.side_effect = RuntimeError("fixture HTTP failure")
    with pytest.raises(RuntimeError, match="fixture HTTP failure"):
        utils.fetch_bunkerweb_releases(Mock(return_value=response))


@pytest.mark.parametrize(
    "certificate,names,uncovered",
    [
        (
            {"sans": ["*.example.com"], "subject_cn": "ignored.test"},
            ["site.example.com", "example.com", "nested.site.example.com", "other.test"],
            ["example.com", "nested.site.example.com", "other.test"],
        ),
        ({"sans": ["SITE.EXAMPLE.COM."]}, ["site.example.com", "other.example.com"], ["other.example.com"]),
        ({"subject_cn": "legacy.example.com"}, ["legacy.example.com", "other.example.com"], ["other.example.com"]),
        ({}, ["site.example.com"], ["site.example.com"]),
    ],
)
def test_certificate_name_warnings_obey_san_priority_and_wildcard_depth(certificate, names, uncovered):
    before = names.copy()
    result = certificate_validation.uncovered_server_names(certificate, names)
    assert result == uncovered
    assert names == before and result is not names


@pytest.fixture
def load_logging(monkeypatch):
    for name in ("CUSTOM_LOG_LEVEL", "LOG_LEVEL", "LOG_TYPES", "LOG_FILE_PATH", "SCHEDULER_LOG_TO_FILE", "LOG_SYSLOG_ADDRESS", "DATABASE_LOG_LEVEL"):
        monkeypatch.delenv(name, raising=False)
    configured = Mock()
    monkeypatch.setattr(logging, "basicConfig", configured)
    monkeypatch.setattr(logging, "setLoggerClass", lambda *args: None)
    monkeypatch.setattr(logging, "addLevelName", lambda *args: None)
    syslog = Mock()
    monkeypatch.setattr("logging.handlers.SysLogHandler", syslog)
    loaded = []

    def load(**variables):
        for name, value in variables.items():
            monkeypatch.setenv(name, value)
        namespace = runpy.run_path(str(ROOT / "src/common/utils/logger.py"))
        loaded.append(namespace)
        return namespace, configured, syslog

    yield load
    for namespace in loaded:
        for entry in namespace["log_types"].values():
            entry["handler"].close()


@pytest.mark.parametrize("message", ["visible log entry", "\x1b[32mvisible log entry\x1b[0m"])
def test_file_logging_emits_message_and_uses_custom_level(load_logging, tmp_path, message):
    target = tmp_path / "scheduler.log"
    namespace, configured, _ = load_logging(
        LOG_TYPES="file stderr", LOG_FILE_PATH=str(target), LOG_LEVEL="WARNING", CUSTOM_LOG_LEVEL="DEBUG", DATABASE_LOG_LEVEL="ERROR"
    )
    assert set(namespace["log_types"]) == {"file", "stderr"}
    assert configured.call_args.kwargs["level"] == logging.DEBUG
    assert configured.call_args.kwargs["force"] is True
    handler = namespace["log_types"]["file"]["handler"]
    record = logging.LogRecord("fixture", logging.INFO, __file__, 1, message, (), None)
    record.levelname = "INFO"
    handler.emit(record)
    handler.flush()
    output = target.read_text()
    assert re.fullmatch(
        rf"\[[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}} [0-9]{{2}}:[0-9]{{2}}:[0-9]{{2}} [+-][0-9]{{4}}\] \[fixture\] \[{record.process}\] \[INFO\] - visible log entry\n",
        output,
    )
    assert "\x1b" not in output
    assert logging.getLogger("sqlalchemy").level == logging.ERROR
    assert namespace["BWLogger"]("sqlalchemy.engine").level == logging.NOTSET
    assert namespace["BWLogger"]("fixture").level == logging.INFO
    assert namespace["setup_logger"]("utility-explicit", "ERROR").level == logging.ERROR
    assert namespace["setup_logger"]("utility-fallback", "invalid").level == logging.DEBUG
    assert namespace["setup_logger"]("utility-integer", logging.WARNING).level == logging.WARNING


@pytest.mark.parametrize("bad_path", ["relative.log", "traversal", ""])
def test_invalid_file_destination_warns_and_falls_back(load_logging, caplog, tmp_path, bad_path):
    if bad_path == "traversal":
        (tmp_path / "logs").mkdir()
        bad_path = str(tmp_path / "logs/../outside.log")
    namespace, configured, _ = load_logging(LOG_TYPES="file", LOG_FILE_PATH=bad_path)
    assert set(namespace["log_types"]) == {"stderr"}
    assert "invalid. Logs will not be written to file" in caplog.text
    assert "No valid log types configured. Defaulting to stderr" in caplog.text
    assert len(configured.call_args.kwargs["handlers"]) == 1


@pytest.mark.parametrize("address", ["udp://logs.example:1514", "tcp://logs.example:1514", "/dev/log"])
def test_syslog_handler_failure_warns_and_keeps_stderr(load_logging, caplog, address):
    # Constructor alone is replaced: parsing and the fallback configuration remain real.
    import logging.handlers

    logging.handlers.SysLogHandler.side_effect = OSError("fixture syslog offline")
    namespace, _, handler = load_logging(LOG_TYPES="syslog", LOG_SYSLOG_ADDRESS=address)
    assert handler.call_count == 1
    assert set(namespace["log_types"]) == {"stderr"}
    assert "fixture syslog offline" in caplog.text
