"""Command parser dispatch and exit status with every external boundary replaced."""

import os
import json
import runpy
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/common/cli"))

import CLI as cli_module  # noqa: E402
import logger  # noqa: E402


@pytest.mark.parametrize(
    "arguments,method,expected_args,expected_kwargs",
    [
        (["ban", "192.0.2.1", "-exp", "0", "-reason", "test", "-service", "example.com"], "ban", ("192.0.2.1", 0, "test", "example.com"), {}),
        (["unban", "192.0.2.1", "-service", "example.com", "-confirm"], "unban", ("192.0.2.1", "example.com", True), {}),
        (["bans"], "bans", (), {}),
        (["plugin_list"], "plugin_list", (), {}),
        (["plugin", "backup", "save", "-d", "--custom", "arg"], "custom", ("backup", "save"), {"debug": True, "extra_args": ["--custom", "arg"]}),
        (["support", "-o", "out.zip", "--no-anonymize"], "support", ("out.zip", False), {}),
    ],
)
def test_main_dispatches_arguments_and_exits_success(monkeypatch, arguments, method, expected_args, expected_kwargs):
    instance = Mock()
    getattr(instance, method).return_value = True, "done"
    constructor = Mock(return_value=instance)
    log = Mock()
    monkeypatch.setattr(cli_module, "CLI", constructor)
    monkeypatch.setattr(cli_module, "support_refusal", lambda: None)
    monkeypatch.setattr(logger, "getLogger", lambda _: log)
    monkeypatch.setattr(sys, "argv", ["bwcli", *arguments])
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setattr(os, "_exit", sys.exit)
    with pytest.raises(SystemExit) as raised:
        runpy.run_path(str(ROOT / "src/common/cli/main.py"), run_name="__main__")
    assert raised.value.code == 0
    getattr(instance, method).assert_called_once_with(*expected_args, **expected_kwargs)
    constructor.assert_called_once_with(tolerant_db=method == "support")
    assert "success" in log.info.call_args.args[0]
    if method == "custom":
        log.setLevel.assert_called_once_with("DEBUG")


@pytest.mark.parametrize("case", ["failed", "exception", "unknown", "refused"])
def test_main_reports_failure_without_process_termination(monkeypatch, case):
    instance = Mock()
    instance.bans.return_value = False, "unavailable"
    if case == "exception":
        instance.bans.side_effect = RuntimeError("broken backend")
    constructor = Mock(return_value=instance)
    log = Mock()
    monkeypatch.setattr(cli_module, "CLI", constructor)
    monkeypatch.setattr(cli_module, "support_refusal", lambda: "scheduler required")
    monkeypatch.setattr(logger, "getLogger", lambda _: log)
    arguments = ["support"] if case == "refused" else ([] if case == "unknown" else ["bans"])
    monkeypatch.setattr(sys, "argv", ["bwcli", *arguments])
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setattr(os, "_exit", sys.exit)
    with pytest.raises(SystemExit) as raised:
        runpy.run_path(str(ROOT / "src/common/cli/main.py"), run_name="__main__")
    assert raised.value.code == 1
    assert log.error.called
    if case == "refused":
        constructor.assert_not_called()
        assert log.error.call_args.args == ("scheduler required",)
    elif case == "exception":
        assert "broken backend" in log.error.call_args.args[0]
    else:
        assert "fail" in log.error.call_args.args[0]


@pytest.mark.parametrize("case", ["bans", "empty", "api_failure", "api_exception", "no_instances", "redis_failure", "init_exception"])
def test_main_bans_json_output(monkeypatch, capsys, case):
    instance = object.__new__(cli_module.CLI)
    instance.apis = [] if case == "no_instances" else [Mock()]
    instance._CLI__terminal_width = 80
    instance._CLI__redis = None
    log = Mock()
    log.info.side_effect = lambda message: print(f"[CLI] {message}")
    log.error.side_effect = lambda message: print(f"[CLI] {message}", file=sys.stderr)
    instance._CLI__logger = log
    ban = {
        "ip": "192.0.2.1",
        "country": "unknown",
        "date": 0,
        "exp": 0,
        "permanent": True,
        "reason": "manual",
        "service": "bwcli",
        "ban_scope": "global",
        "kind": "ban",
    }
    expected = {"instance": [] if case == "empty" else [ban]}
    instance.send_to_apis = Mock(return_value=(True, {"instance": {"data": expected["instance"]}}))
    if case == "api_failure":
        instance.send_to_apis.return_value = False, None
    elif case == "api_exception":
        instance.send_to_apis.side_effect = RuntimeError("backend unavailable")
    elif case == "redis_failure":
        instance._CLI__redis = Mock()
        instance._CLI__redis.scan_iter.side_effect = RuntimeError("redis unavailable")
    constructor = Mock(return_value=instance)
    if case == "init_exception":
        constructor.side_effect = RuntimeError("initialization failed")
    monkeypatch.setattr(cli_module, "CLI", constructor)
    monkeypatch.setattr(logger, "getLogger", lambda _: log)
    monkeypatch.setattr(sys, "argv", ["bwcli", "bans", "--json"])
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setattr(os, "_exit", sys.exit)
    with pytest.raises(SystemExit) as raised:
        runpy.run_path(str(ROOT / "src/common/cli/main.py"), run_name="__main__")
    captured = capsys.readouterr()
    if case in ("bans", "empty"):
        assert json.loads(captured.out) == expected
        assert raised.value.code == 0
        assert captured.err == ""
    else:
        assert raised.value.code != 0
        assert captured.out == ""
        assert captured.err
    assert "\x1b" not in captured.out + captured.err
    assert "CLI command status" not in captured.out + captured.err
