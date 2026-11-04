"""CLI failures reach exit codes; support archives retain useful, redacted evidence."""

import io
import json
import os
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
from unittest.mock import Mock
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "src/common/cli") not in sys.path:
    sys.path.append(str(ROOT / "src/common/cli"))

import CLI as cli_module  # noqa: E402
import logger  # noqa: E402


@pytest.fixture
def cli():
    instance = object.__new__(cli_module.CLI)
    instance._CLI__logger = Mock()
    instance._CLI__db = None
    instance._CLI__db_error = None
    instance._CLI__variables = {"SERVER_NAME": "site.example"}
    instance._CLI__terminal_width = 80
    instance._CLI__redis = None
    instance._CLI__api_token = ""
    instance.apis = [Mock(endpoint="http://instance.invalid")]
    instance.apis[0].request.return_value = (True, "", 200, {"data": {"found": False}})
    instance.send_to_apis = Mock(return_value=(True, {"instance": {"data": []}}))
    return instance


@pytest.mark.parametrize("command", ["ban", "unban", "bans", "plugin_list", "plugin"])
@pytest.mark.parametrize("success", [True, False])
def test_real_subcommand_result_reaches_process_status(cli, tmp_path, monkeypatch, command, success):
    arguments = [command]
    expected = "SUCCESS" if success else "ERROR"
    if command in ("ban", "unban"):
        arguments += ["192.0.2.10"]
        cli.send_to_apis.return_value = success, {}
    elif command == "bans":
        cli.send_to_apis.return_value = success, {"instance": {"data": []}}
        expected = "No bans found" if success else "Failed to retrieve ban information"
    elif command == "plugin_list":
        if success:
            cli._CLI__db = Mock()
            cli._CLI__db.get_plugins.return_value = [{"id": "fixture", "type": "core", "bwcli": {"run": "run.py"}}]
        expected = "run" if success else "scheduler"
    else:
        arguments += ["fixture", "run"]
        cli._CLI__db = Mock(database_uri="sqlite:///fixture")
        cli._CLI__db.get_plugins.return_value = [{"id": "fixture", "type": "core", "bwcli": {"run": "run.py"}}]
        monkeypatch.setattr(cli_module, "sep", str(tmp_path))
        script = tmp_path / "usr/share/bunkerweb/core/fixture/bwcli/run.py"
        script.parent.mkdir(parents=True)
        script.write_text(f"raise SystemExit({0 if success else 7})\n")
        expected = "executed successfully" if success else "exit code 7"
    log = Mock()
    monkeypatch.setattr(cli_module, "CLI", lambda **kwargs: cli)
    monkeypatch.setattr(logger, "getLogger", lambda name: log)
    monkeypatch.setattr(sys, "argv", ["bwcli", *arguments])
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setattr(os, "_exit", sys.exit)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(ROOT / "src/common/cli/main.py"), run_name="__main__")
    assert exc.value.code == (0 if success else 1)
    assert expected in (log.info if success else log.error).call_args.args[0]


@pytest.mark.parametrize(
    "command,failure",
    [
        (command, failure)
        for command in ("ban", "unban", "bans")
        for failure in ("no-instance", "exception", "invalid-ip")
        if (command, failure) != ("bans", "invalid-ip")
    ],
)
def test_ban_commands_fail_with_actionable_reason(cli, command, failure):
    if failure == "no-instance":
        cli.apis = []
    elif failure == "exception":
        cli.send_to_apis.side_effect = RuntimeError("fixture API offline")
    arguments = () if command == "bans" else (("invalid",) if failure == "invalid-ip" else ("192.0.2.10",))
    if command == "ban":
        arguments += (0, "manual")
    ok, message = getattr(cli, command)(*arguments)
    assert ok is False
    expected = {"no-instance": "no BunkerWeb instance", "exception": "fixture API offline", "invalid-ip": "not a valid IP"}[failure]
    assert expected in message and "ERROR" in message


@pytest.mark.parametrize(
    "reply,expected",
    [
        ((False, "offline", 0, None), "offline"),
        ((True, "", 503, {}), "status 503"),
        ((True, "", 200, None), "malformed lease lookup reply"),
        ((True, "", 200, {"data": {"found": "yes"}}), "malformed lease lookup reply"),
        ((True, "", 200, {"data": {"found": True, "row": {}}}), "malformed lease row"),
    ],
)
def test_incomplete_lease_lookup_still_unbans_explicit_entry(cli, reply, expected):
    cli.apis[0].request.return_value = reply
    ok, message = cli.unban("192.0.2.10", "site.example")
    assert not ok and "explicit unban succeeded" in message and expected in message
    cli.send_to_apis.assert_called_once_with("POST", "/unban", data={"ip": "192.0.2.10", "ban_scope": "service", "service": "site.example"})


@pytest.mark.parametrize("confirm", [False, True])
@pytest.mark.parametrize("outcome", ["success", "changed", "partial", "exception"])
def test_crowdsec_lease_unban_reports_preview_and_partial_failures(cli, monkeypatch, confirm, outcome):
    cli.apis[0].request.return_value = (True, "", 200, {"data": {"found": True, "row": {"reason_data": {}}}})
    cli._CLI__db = Mock()
    current = {
        "decisions": [
            {"key": "decision-1", "scope": "Ip", "value": "192.0.2.10", "type": "ban", "origin": "list", "scenario": "fixture", "connection_id": "connection-1"}
        ],
        "unavailable": ["offline"],
        "warnings": {"list_origin": True, "range": True},
        "management_missing": ["readonly"],
    }
    monkeypatch.setattr(cli_module, "CrowdSecClient", Mock())
    monkeypatch.setattr(cli_module, "preview", lambda *args: current)
    result = dict(
        status=outcome,
        deleted=[1],
        already_absent=[],
        failed=[{"key": "decision-1", "error": "denied"}],
        lease_failed=[{"instance": "node-1", "error": "offline"}],
        down=["node-2"],
        unavailable=["connection-2"],
    )
    execute = Mock(return_value=result)
    if outcome == "exception":
        execute.side_effect = cli_module.CrowdSecError("fixture LAPI offline")
    monkeypatch.setattr(cli_module, "execute", execute)
    ok, message = cli.unban("192.0.2.10", confirm=confirm)
    assert ok is (confirm and outcome == "success")
    if not confirm:
        execute.assert_not_called()
        for text in ("-confirm", "community blocklist", "range", "management credentials", "offline", "decision"):
            assert text in message
    elif outcome == "success":
        assert "deleted: 1, already absent: 0" in message
    elif outcome == "changed":
        assert "changed since the preview" in message
    elif outcome == "exception":
        assert "fixture LAPI offline" in message
    else:
        for text in ("Partial CrowdSec result", "decision-1", "denied", "node-1", "node-2", "connection-2"):
            assert text in message


def test_lease_unban_without_scheduler_refuses_crowdsec_change(cli):
    cli.apis[0].request.return_value = (True, "", 200, {"data": {"found": True, "row": {"reason_data": {}}}})
    ok, message = cli.unban("192.0.2.10", confirm=True)
    assert not ok and "scheduler host (database access)" in message


@pytest.mark.multiengine
def test_support_bundle_uses_real_database_and_masks_credentials(cli, db, tmp_path, monkeypatch):
    from fixtures.seed import make_core_plugin, make_general_settings

    plugin = make_core_plugin(
        "fixture",
        settings={
            "FIXTURE_PASSWORD": {
                "id": "fixture-password",
                "context": "global",
                "default": "",
                "help": "h",
                "label": "Password",
                "regex": ".*",
                "type": "password",
            }
        },
        jobs=[{"name": "fixture-job", "file": "download.py", "every": "hour", "reload": False}],
    )
    assert db.init_tables([make_general_settings(), plugin])[0]
    assert not isinstance(db.save_config({"SERVER_NAME": "site.example", "FIXTURE_PASSWORD": "test-credential"}, "scheduler"), str)
    assert db.upsert_job_cache("", "payload", b"cache-content", job_name="fixture-job") == ""
    cli._CLI__db = db
    cli.apis = []
    monkeypatch.setattr(cli_module, "sep", str(tmp_path))
    monkeypatch.setattr(cli_module, "LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr(cli_module, "get_integration", lambda: "Linux")
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs/scheduler.log").write_text("request site.example password=test-credential\n")
    nginx = tmp_path / "etc/nginx"
    nginx.mkdir(parents=True)
    (nginx / "default.conf").write_text("proxy_set_header Authorization 'Bearer test-credential';\nserver_name site.example;\n")
    output = tmp_path / "support.zip"
    ok, message = cli.support(str(output))
    assert ok and "Support bundle written to" in message
    with ZipFile(output) as archive:
        files = {name: archive.read(name).decode() for name in archive.namelist()}
    assert "test-credential" not in "".join(files.values())
    config = json.loads(files["config.json"])
    assert config["FIXTURE_PASSWORD"]["value"] == "[REDACTED]"
    jobs = json.loads(files["jobs.json"])
    assert jobs["cache_files"][0]["bytes"] == len(b"cache-content")
    assert jobs["jobs"]["fixture-job"]["last_run"] is None
    assert "cache" not in jobs["jobs"]["fixture-job"]
    assert "[REDACTED]" in files["nginx/etc-nginx-conf.txt"]
    assert "site.example" not in files["nginx/etc-nginx-conf.txt"]


@pytest.mark.parametrize("output_kind", ["file", "stdout", "tty", "unwritable"])
def test_support_without_database_still_returns_evidence(cli, tmp_path, monkeypatch, output_kind):
    monkeypatch.setattr(cli_module, "sep", str(tmp_path))
    monkeypatch.setattr(cli_module, "LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr(cli_module, "get_integration", lambda: "Kubernetes")
    cli._CLI__db_error = "schema unavailable"
    cli.apis[0].request.return_value = False, "instance offline", 0, {}
    stream = SimpleNamespace(isatty=lambda: output_kind == "tty", buffer=io.BytesIO())
    monkeypatch.setattr(cli_module, "sys_stdout", stream)
    output = "-" if output_kind in ("stdout", "tty") else str(tmp_path if output_kind == "unwritable" else tmp_path / "bundle.zip")
    ok, message = cli.support(output)
    if output_kind in ("tty", "unwritable"):
        assert not ok and ("Refusing to write" if output_kind == "tty" else "Failed to write") in message
        return
    assert ok
    data = stream.buffer.getvalue() if output_kind == "stdout" else Path(output).read_bytes()
    with ZipFile(io.BytesIO(data)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        instances = json.loads(archive.read("instances.json"))
    assert instances[0]["health"]["reachable"] is False
    assert any(item["item"] == "database" and item["reason"] == "schema unavailable" for item in manifest["unavailable"])
    assert any(item["item"] == "logs" and "kubectl logs" in item["reason"] for item in manifest["unavailable"])


@pytest.mark.parametrize("plugin_type", ["core", "external", "pro"])
def test_missing_plugin_file_reports_resolved_location(cli, tmp_path, monkeypatch, plugin_type):
    cli._CLI__db = Mock()
    cli._CLI__db.get_plugins.return_value = [{"id": "fixture", "type": plugin_type, "bwcli": {"run": "missing.py"}}]
    monkeypatch.setattr(cli_module, "sep", str(tmp_path))
    ok, message = cli.custom("fixture", "run")
    assert not ok and "File" in message and "bwcli/missing.py not found" in message
