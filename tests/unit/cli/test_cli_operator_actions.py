"""CLI output, plugin execution and topology checks with fake Redis/API backends."""

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/common/cli"))

import CLI as cli_module  # noqa: E402


@pytest.fixture
def cli():
    instance = object.__new__(cli_module.CLI)
    instance._CLI__db = Mock(database_uri="sqlite:///fixture")
    instance._CLI__logger = Mock()
    instance._CLI__terminal_width = 80
    instance._CLI__variables = {"SERVER_NAME": "example.com"}
    instance._CLI__redis = None
    instance.apis = [Mock(endpoint="http://instance/")]
    instance.send_to_apis = Mock(return_value=(True, {}))
    return instance


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (None, "permanent"),
        (-1, "permanent"),
        (0, "less than a second"),
        (1, "1 second"),
        (62, "1 minute and 2 seconds"),
        (90061, "1 day 1 hour 1 minute and 1 second"),
    ],
)
def test_remaining_time_is_human_readable(seconds, expected):
    assert cli_module.format_remaining_time(seconds) == expected


@pytest.mark.parametrize(
    "service,scope,expected_service", [("example.com", "service", "example.com"), ("missing", "global", "bwcli"), ("bwcli", "global", "bwcli")]
)
def test_ban_validates_service_before_sending(cli, service, scope, expected_service):
    cli._CLI__db.get_config.return_value = {"SERVER_NAME": "example.com other.example"}
    ok, message = cli.ban("192.0.2.1", 60, "manual", service)
    assert ok and "has been banned" in message
    cli.send_to_apis.assert_called_once_with(
        "POST", "/ban", data={"ip": "192.0.2.1", "exp": 60, "reason": "manual", "service": expected_service, "ban_scope": scope}
    )


def test_ban_without_db_uses_resolved_service_config(cli, monkeypatch):
    monkeypatch.delenv("SERVER_NAME", raising=False)
    cli._CLI__db = None
    assert cli.ban("192.0.2.1", 0, "manual", "example.com")[0]
    assert cli.send_to_apis.call_args.kwargs["data"]["ban_scope"] == "service"


def test_bans_renders_scopes_dates_permanent_flags_and_leases(cli):
    cli.send_to_apis.return_value = True, {
        "instance": {
            "data": [
                {"ip": "192.0.2.1", "date": 1, "reason": "global one", "exp": 60},
                {"ip": "192.0.2.2", "date": 2, "reason": "global two", "exp": 0, "permanent": True},
                {"ip": "192.0.2.3", "date": 3, "reason": "service one", "exp": 90, "service": "_", "ban_scope": "service", "kind": "crowdsec_lease"},
                {"ip": "192.0.2.4", "date": 0, "reason": "service two", "exp": 0, "service": "example.com", "ban_scope": "service"},
            ]
        },
        "empty": {"data": []},
    }
    ok, message = cli.bans()
    assert ok
    for text in (
        "Global Bans",
        "Service-Specific Bans",
        "global one",
        "global two",
        "service one",
        "service two",
        "default server",
        "permanent",
        "CrowdSec lease",
        "No bans found",
    ):
        assert text in message
    assert message.index("192.0.2.1") < message.index("192.0.2.2")


def test_bans_keeps_instance_results_when_redis_fails(cli):
    cli.send_to_apis.return_value = True, {"instance": {"data": []}}
    cli._CLI__redis = Mock()
    cli._CLI__redis.scan_iter.side_effect = RuntimeError("offline")
    ok, message = cli.bans()
    assert ok and "No bans found" in message
    cli._CLI__logger.error.assert_called_once_with("Failed to get bans from redis: offline")


def test_redis_ban_pipeline_decodes_raw_reason_and_permanent_ttl(cli):
    redis = Mock()
    redis.scan_iter.return_value = [b"bans_ip_192.0.2.1", b"bans_ip_192.0.2.2", b"bans_ip_192.0.2.3"]
    pipeline = redis.pipeline.return_value
    pipeline.execute.return_value = [b"legacy reason", 10, json.dumps({"permanent": True, "reason": "manual"}), -1, None, -2]
    cli._CLI__redis = redis
    bans = cli._CLI__collect_redis_bans("bans_ip_*", "global")
    assert [(ban["ip"], ban["reason"], ban["exp"]) for ban in bans] == [("192.0.2.1", "legacy reason", 10), ("192.0.2.2", "manual", 0)]
    redis.pipeline.assert_called_once_with(transaction=False)
    redis.scan_iter.assert_called_once_with("bans_ip_*", count=1000)
    assert pipeline.get.call_count == 3 and pipeline.ttl.call_count == 3


def test_plugin_list_renders_commands_and_empty_plugins(cli):
    cli._CLI__db.get_plugins.return_value = [
        {"id": "backup", "type": "core", "bwcli": {"save": "save.py"}},
        {"id": "empty", "type": "external", "bwcli": {}},
        {"id": "hidden"},
    ]
    ok, message = cli.plugin_list()
    assert ok and "save" in message and "No commands available" in message
    assert "hidden" not in message
    cli._CLI__db.get_plugins.return_value = []
    assert "No plugins available" in cli.plugin_list()[1]
    cli._CLI__db = None
    assert cli.plugin_list()[0] is False


@pytest.mark.parametrize(
    "plugin,command,expected", [("missing", "save", "not found"), ("backup", "missing", "Available commands"), ("empty", "save", "No CLI commands")]
)
def test_unknown_plugin_commands_report_available_choices(cli, plugin, command, expected):
    cli._CLI__db.get_plugins.return_value = [{"id": "backup", "type": "core", "bwcli": {"save": "save.py"}}, {"id": "empty", "type": "external", "bwcli": {}}]
    ok, message = cli.custom(plugin, command)
    assert not ok and expected in message


@pytest.mark.parametrize(
    "body,expected_ok,expected_message",
    [
        ("pass", True, "executed successfully"),
        ("raise SystemExit(0)", True, "executed successfully"),
        ("raise SystemExit(7)", False, "exit code 7"),
        ("raise RuntimeError('failed fixture')", False, "failed fixture"),
    ],
)
def test_python_plugin_restores_environment_argv_and_import_path(cli, tmp_path, monkeypatch, body, expected_ok, expected_message):
    plugin = tmp_path / "plugin"
    command = plugin / "bwcli" / "fixture.py"
    command.parent.mkdir(parents=True)
    output = tmp_path / "observed.json"
    command.write_text(
        "import json, os, sys\n"
        f"with open({str(output)!r}, 'w') as f:\n"
        " json.dump({'argv': sys.argv, 'level': os.environ['LOG_LEVEL'], 'db': os.environ['DATABASE_URI'], 'extra': os.environ['CLI_EXTRA_ARGS']}, f)\n"
        + body
        + "\n"
    )
    monkeypatch.setenv("C3_KEEP", "original")
    before_env, before_args, before_path = os.environ.copy(), sys.argv.copy(), sys.path.copy()
    ok, message = cli._CLI__exec_plugin_module(command, plugin, "fixture", "run", True, ["--flag", "value"])
    assert ok is expected_ok and expected_message in message
    assert json.loads(output.read_text()) == {"argv": [str(command), "--flag", "value"], "level": "DEBUG", "db": "sqlite:///fixture", "extra": "--flag value"}
    assert os.environ == before_env and sys.argv == before_args and sys.path == before_path


@pytest.mark.parametrize("status", [0, 4])
def test_external_plugin_uses_explicit_argv_and_environment(cli, tmp_path, monkeypatch, status):
    process = Mock(return_value=SimpleNamespace(returncode=status))
    monkeypatch.setattr(cli_module, "run", process)
    path = tmp_path / "command.sh"
    ok, message = cli._CLI__exec_external_command(path, "fixture", "run", True, ["--flag"])
    assert ok is (status == 0)
    assert "executed successfully" in message if status == 0 else "exit code 4" in message
    assert process.call_args.args == ([str(path), "--flag"],)
    assert process.call_args.kwargs["env"]["LOG_LEVEL"] == "DEBUG"
    assert process.call_args.kwargs["env"]["DATABASE_URI"] == "sqlite:///fixture"


@pytest.mark.parametrize(
    "installed,all_in_one,service,install_type,expected",
    [
        (False, False, None, None, "scheduler runs"),
        (True, True, "no", None, "scheduler is disabled"),
        (True, True, "yes", "full", None),
        (True, False, None, "worker", "installed as worker"),
        (True, False, None, "manager", None),
    ],
)
def test_support_refusal_uses_install_topology(tmp_path, monkeypatch, installed, all_in_one, service, install_type, expected):
    scheduler = tmp_path / "scheduler"
    aio = tmp_path / "aio"
    marker = tmp_path / "INSTALL_TYPE"
    if installed:
        scheduler.mkdir()
    if all_in_one:
        aio.mkdir()
    if install_type:
        marker.write_text(install_type)
    monkeypatch.setattr(cli_module, "SCHEDULER_PATH", scheduler)
    monkeypatch.setattr(cli_module, "ALL_IN_ONE_PATH", aio)
    monkeypatch.setattr(cli_module, "INSTALL_TYPE_PATH", marker)
    monkeypatch.setattr(cli_module, "get_integration", lambda: "Linux")
    monkeypatch.setattr(cli_module, "getenv", lambda name, default=None: service if name == "SERVICE_SCHEDULER" else default)
    monkeypatch.setattr(cli_module, "systemctl_state", Mock(side_effect=AssertionError("unexpected systemctl")))
    result = cli_module.support_refusal()
    assert result is None if expected is None else expected in result


def test_legacy_worker_refusal_checks_both_systemctl_states(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_module, "SCHEDULER_PATH", tmp_path)
    monkeypatch.setattr(cli_module, "ALL_IN_ONE_PATH", tmp_path / "aio")
    monkeypatch.setattr(cli_module, "INSTALL_TYPE_PATH", tmp_path / "missing")
    monkeypatch.setattr(cli_module, "get_integration", lambda: "Linux")
    state = Mock(side_effect=["disabled", "inactive"])
    monkeypatch.setattr(cli_module, "systemctl_state", state)
    assert "worker host" in cli_module.support_refusal()
    assert [call.args for call in state.call_args_list] == [("is-enabled",), ("is-active",)]
