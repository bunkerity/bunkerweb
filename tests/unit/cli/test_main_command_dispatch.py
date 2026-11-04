"""Command parser dispatch and exit status with every external boundary replaced."""

import os
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
