"""Hermetic checks of credential files, process environments and cache publication guards."""

from base64 import b64encode
from contextlib import contextmanager, nullcontext
import io
import json
import logging
import os
from pathlib import Path
from subprocess import TimeoutExpired
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import letsencrypt_utils as utils


@pytest.fixture
def env(monkeypatch):
    values = {}
    monkeypatch.setattr(os, "environ", values)
    monkeypatch.setattr(utils, "environ", values)
    return values


def test_certbot_environment_removes_db_settings_but_restores_internal_api(env):
    env.update(API_TOKEN="internal-token", API_HTTP_PORT="5000", DATABASE_URI="sqlite:///unit.sqlite")
    original = {"PATH": "/test/bin", "PYTHONPATH": "first::second", "DNS_SECRET": "secret", "API_TOKEN": "stale", "DATABASE_URI": "stale"}
    job = SimpleNamespace(
        db=SimpleNamespace(get_config=lambda: {"DNS_SECRET": "secret", "API_TOKEN": "internal-token", "DATABASE_URI": "sqlite:///unit.sqlite"})
    )
    result = utils.build_certbot_env(job, "deps", original)
    assert result == {
        "PATH": "/test/bin",
        "PYTHONPATH": "first:second:deps",
        "API_TOKEN": "internal-token",
        "API_HTTP_PORT": "5000",
        "DATABASE_URI": "sqlite:///unit.sqlite",
    }
    assert original["DNS_SECRET"] == "secret"
    assert utils.build_certbot_env(job, "deps", result)["PYTHONPATH"] == "first:second:deps"


@pytest.mark.parametrize("value, expected", [(" 7 ", "7"), ("-1", "0"), ("invalid", "50"), ("0", "0")])
def test_log_backup_limits_are_validated(env, value, expected):
    env["LETS_ENCRYPT_MAX_LOG_BACKUPS"] = value
    assert utils.certbot_log_backup_flags() == ["--max-log-backups", expected]


def test_base64_json_and_individual_credential_values_are_decoded(env):
    env["LETS_ENCRYPT_DNS_CREDENTIAL_ITEM"] = b64encode(json.dumps({"DNS_CLOUDFLARE_API_TOKEN": "json-secret"}).encode()).decode()
    provider = utils.extract_provider("svc", "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM", "cloudflare", logger=Mock())
    assert b"json-secret" in provider.get_formatted_credentials()
    env["LETS_ENCRYPT_DNS_CREDENTIAL_ITEM"] = "dns_cloudflare_api_token " + b64encode(b"separate-secret").decode()
    provider = utils.extract_provider("svc", "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM", "cloudflare", logger=Mock())
    assert b"separate-secret" in provider.get_formatted_credentials()


def test_invalid_credentials_log_validation_without_secret(env):
    env["LETS_ENCRYPT_DNS_CREDENTIAL_ITEM"] = "dns_cloudflare_email private-email-marker"
    log = Mock()
    assert utils.extract_provider("svc", "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM", "cloudflare", logger=log) is None
    message = log.error.call_args.args[0]
    assert "validating credentials" in message
    assert "private-email-marker" not in message


def test_bad_base64_falls_back_to_literal_and_empty_credentials_skip(env):
    env["LETS_ENCRYPT_DNS_CREDENTIAL_ITEM"] = "dns_cloudflare_api_token ////"
    log = Mock()
    provider = utils.extract_provider("svc", "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM", "cloudflare", logger=log)
    assert b"////" in provider.get_formatted_credentials()
    assert log.debug.called
    env.clear()
    assert utils.extract_provider("svc", "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM", "cloudflare", logger=log) is None
    assert "no DNS credentials" in log.warning.call_args.args[0]


def test_credentials_write_is_private_idempotent_and_refuses_symlink(tmp_path):
    provider = utils.PROVIDERS["route53"](aws_access_key_id="test-key", aws_secret_access_key="test-secret")
    path = Path(utils.write_provider_credentials_file(provider, tmp_path))
    assert path.read_bytes() == provider.get_formatted_credentials()
    assert path.stat().st_mode & 0o777 == 0o600
    assert Path(utils.write_provider_credentials_file(provider, tmp_path)) == path
    target = tmp_path / "untouched"
    target.write_text("keep")
    path.unlink()
    path.symlink_to(target)
    with pytest.raises(OSError):
        utils.write_provider_credentials_file(provider, tmp_path)
    assert target.read_text() == "keep"


def test_route53_multisite_selects_first_distinct_credentials_and_ignores_passthrough(env, tmp_path):
    env.update(MULTISITE="yes", SERVER_NAME="one.example.com alias.example.com two.example.com skipped.example.com http.example.com off.example.com")
    for name, key in (("one.example.com", "first"), ("alias.example.com", "first"), ("two.example.com", "second"), ("skipped.example.com", "skip")):
        env.update(
            {
                f"{name}_AUTO_LETS_ENCRYPT": "yes",
                f"{name}_LETS_ENCRYPT_CHALLENGE": "dns",
                f"{name}_LETS_ENCRYPT_DNS_PROVIDER": "route53",
                f"{name}_LETS_ENCRYPT_DNS_CREDENTIAL_ITEM": f"aws_access_key_id {key}-key",
                f"{name}_LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_1": f"aws_secret_access_key {key}-secret",
            }
        )
    env["skipped.example.com_LETS_ENCRYPT_PASSTHROUGH"] = "yes"
    env["http.example.com_AUTO_LETS_ENCRYPT"] = "yes"
    cmd_env = {}
    log = Mock()
    paths = utils.setup_route53_aws_config(cmd_env, tmp_path, log)
    assert len(paths) == 2
    assert cmd_env == {"AWS_CONFIG_FILE": paths[0]}
    assert b"first-key" in Path(paths[0]).read_bytes()
    assert b"second-key" in Path(paths[1]).read_bytes()
    assert "2 distinct route53" in log.warning.call_args.args[0]
    assert len(list(tmp_path.iterdir())) == 2


@pytest.mark.parametrize("failure", [ValueError("invalid credentials"), OSError("disk full")])
def test_route53_failures_do_not_abort_other_renewals(env, tmp_path, monkeypatch, failure):
    env.update(AUTO_LETS_ENCRYPT="yes", LETS_ENCRYPT_CHALLENGE="dns", LETS_ENCRYPT_DNS_PROVIDER="route53")
    if isinstance(failure, OSError):
        monkeypatch.setattr(utils, "extract_provider", Mock(return_value=object()))
        monkeypatch.setattr(utils, "write_provider_credentials_file", Mock(side_effect=failure))
    else:
        monkeypatch.setattr(utils, "extract_provider", Mock(side_effect=failure))
    log = Mock()
    cmd_env = {"keep": "value"}
    assert utils.setup_route53_aws_config(cmd_env, tmp_path, log) == []
    assert cmd_env == {"keep": "value"}
    assert str(failure) in log.warning.call_args.args[0]


@pytest.mark.parametrize(
    "settings, expected",
    [
        ({}, False),
        ({"AUTO_LETS_ENCRYPT": "yes", "LETS_ENCRYPT_SERVER": "ZeroSSL"}, True),
        ({"MULTISITE": "yes", "SERVER_NAME": "off on", "LETS_ENCRYPT_SERVER": "zerossl", "on_AUTO_LETS_ENCRYPT": "yes"}, True),
        ({"MULTISITE": "yes", "SERVER_NAME": "off on", "off_LETS_ENCRYPT_SERVER": "zerossl", "on_AUTO_LETS_ENCRYPT": "yes"}, False),
    ],
)
def test_zerossl_detection_requires_active_service(settings, expected):
    assert utils.is_zerossl_used_in_env(settings) is expected


def test_zerossl_entrypoint_requires_executable_wrapper(tmp_path):
    wrapper = tmp_path / "zerossl-bot.sh"
    log = Mock()
    assert utils.resolve_certbot_entrypoint("zerossl", "certbot", wrapper, log) == []
    assert utils.resolve_certbot_entrypoint("zerossl", "certbot", wrapper, log, fallback_to_certbot=True) == ["certbot"]
    wrapper.write_text("#!/bin/sh\n")
    wrapper.chmod(0o600)
    assert utils.resolve_certbot_entrypoint("zerossl", "certbot", wrapper, log) == []
    wrapper.chmod(0o700)
    env = {}
    assert utils.resolve_certbot_entrypoint("zerossl", "certbot", wrapper, log, env) == [str(wrapper)]
    assert env == {"CERTBOT_BIN": "certbot"}
    assert utils.resolve_certbot_entrypoint("letsencrypt", "certbot", wrapper, log) == ["certbot"]


@pytest.mark.parametrize("timeout", [False, True])
def test_stream_drains_buffered_lines_and_kills_on_timeout(timeout):
    stderr = io.StringIO(" first line \nsecond line\n")
    wait = Mock(side_effect=[TimeoutExpired("certbot", 0.01), 0] if timeout else [0])
    process = SimpleNamespace(stderr=stderr, wait=wait, kill=Mock())
    log, on_line = Mock(), Mock()
    assert utils.stream_certbot(process, log, 0.01, on_line) is (not timeout)
    assert [call.args[0] for call in on_line.call_args_list] == ["first line", "second line"]
    assert [call.args[0] for call in log.info.call_args_list] == ["first line", "second line"]
    assert stderr.closed
    assert process.kill.call_count == int(timeout)
    assert wait.call_count == (2 if timeout else 1)


def test_stream_without_stderr_waits_successfully():
    process = SimpleNamespace(stderr=None, wait=Mock(), kill=Mock())
    assert utils.stream_certbot(process, Mock(), 0.01)
    process.wait.assert_called_once_with(timeout=0.01)
    process.kill.assert_not_called()


def test_job_log_handler_is_idempotent_and_writes_records(env, tmp_path):
    env["LETS_ENCRYPT_MAX_LOG_BACKUPS"] = "invalid"
    log = logging.Logger("unit-letsencrypt", logging.INFO)
    try:
        utils.attach_job_log_file(log, "job.log", tmp_path)
        utils.attach_job_log_file(log, "job.log", tmp_path)
        assert len(log.handlers) == 1
        assert log.handlers[0].backupCount == 50
        log.warning("operator can see skipped generation")
        assert "operator can see skipped generation" in (tmp_path / "job.log").read_text()
        assert tmp_path.stat().st_mode & 0o7777 == 0o2770
    finally:
        for handler in log.handlers:
            handler.close()


def test_log_preparation_removes_unwritable_files_and_sets_modes(tmp_path, monkeypatch):
    writable, blocked = tmp_path / "certbot.log", tmp_path / "old.log.1"
    writable.write_text("keep")
    blocked.write_text("remove")
    mask = Mock()
    monkeypatch.setattr(utils, "umask", mask)
    monkeypatch.setattr(utils, "access", lambda path, mode: path != blocked)
    utils.prepare_logs_dir(tmp_path, Mock())
    mask.assert_called_once_with(0o007)
    assert writable.read_text() == "keep"
    assert writable.stat().st_mode & 0o777 == 0o660
    assert not blocked.exists()


def test_unusable_log_directory_logs_failure(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("keep")
    log = Mock(handlers=[])
    assert utils.ensure_logs_dir(blocker / "logs", log) is None
    assert "Failed to create" in log.error.call_args.args[0]
    utils.attach_job_log_file(log, "job.log", blocker / "logs")
    assert blocker.read_text() == "keep"


@pytest.mark.parametrize(
    "before, after, restore_ok, repaired, repointed, persists",
    [
        ({"checksum": "same"}, {"checksum": "same"}, True, ["broken"], [], True),
        ({"checksum": "same"}, {"checksum": "same"}, True, [], ["repointed"], True),
        ({"checksum": "old"}, {"checksum": "new"}, True, ["broken"], [], False),
        (None, {"checksum": "created-by-ui"}, True, ["broken"], [], False),
        (RuntimeError("db unavailable"), {"checksum": "new"}, True, ["broken"], [], True),
        (None, None, True, [], [], False),
        (None, None, False, ["broken"], [], False),
    ],
)
def test_sanitize_persistence_obeys_restore_and_optimistic_concurrency(tmp_path, monkeypatch, before, after, restore_ok, repaired, repointed, persists):
    job = SimpleNamespace(
        job_name="certbot-renew",
        restore_ok=restore_ok,
        db=SimpleNamespace(get_job_cache_file=Mock(side_effect=[before, after])),
        cache_dir=Mock(return_value=(True, "")),
    )
    monkeypatch.setattr(utils, "repoint_orphan_renewals", Mock(return_value=repointed))
    monkeypatch.setattr(utils, "sanitize_le_cache", Mock(return_value=repaired))
    lock_held = []

    @contextmanager
    def lock():
        lock_held.append(True)
        yield
        lock_held.pop()

    def persist(path):
        assert lock_held == [True]
        return True, ""

    job.cache_dir.side_effect = persist
    monkeypatch.setattr(utils, "le_cache_write_lock", lock)
    log = Mock()
    assert utils.sanitize_and_persist(job, tmp_path, log) == repaired
    assert job.cache_dir.call_count == int(persists)
    assert lock_held == []
    job.db.get_job_cache_file.assert_any_call("certbot-renew", f"folder:{tmp_path}.tgz", with_info=True, with_data=False)
    if before != after and not persists and restore_ok:
        assert "changed since restore" in log.warning.call_args.args[0]


@pytest.mark.parametrize("failure", [(False, "db refused"), OSError("write failed")])
def test_sanitize_cache_write_errors_preserve_repair_result(tmp_path, monkeypatch, failure):
    job = SimpleNamespace(job_name="certbot-renew", restore_ok=True, db=SimpleNamespace(get_job_cache_file=Mock(return_value=None)), cache_dir=Mock())
    if isinstance(failure, Exception):
        job.cache_dir.side_effect = failure
    else:
        job.cache_dir.return_value = failure
    monkeypatch.setattr(utils, "repoint_orphan_renewals", lambda path, log: [])
    monkeypatch.setattr(utils, "sanitize_le_cache", lambda path, log: ["broken"])
    monkeypatch.setattr(utils, "le_cache_write_lock", nullcontext)
    log = Mock()
    assert utils.sanitize_and_persist(job, tmp_path, log) == ["broken"]
    assert (str(failure) if isinstance(failure, Exception) else failure[1]) in log.error.call_args.args[0]


def test_stale_uri_purges_only_matching_account(tmp_path, monkeypatch):
    accounts = tmp_path / "accounts/ca/directory"
    for name, body in (("broken", "{"), ("keep", '{"uri":"https://ca/acme/acct/1"}'), ("retire", '{"uri":"https://ca/acme/acct/2"}')):
        path = accounts / name
        path.mkdir(parents=True)
        (path / "regr.json").write_text(body)
    retired = []

    def quarantine(path, log):
        retired.append(path.name)
        (path / "regr.json").unlink()
        path.rmdir()

    monkeypatch.setattr(utils, "quarantine_account", quarantine)
    monkeypatch.setattr(utils, "detect_orphan_renewals", lambda path: [{"account": "retire", "cert_name": "app.example.com"}])
    log = Mock()
    assert utils.purge_stale_account_by_uri(tmp_path, "https://ca/acme/acct/2", log)
    assert retired == ["retire"]
    assert (accounts / "keep/regr.json").is_file()
    assert any("app.example.com" in call.args[0] for call in log.warning.call_args_list)
    assert not utils.purge_stale_account_by_uri(tmp_path, "https://ca/acme/acct/absent", log)
    assert "no local account" in log.error.call_args.args[0]
    assert not utils.purge_stale_account(tmp_path, "", log)
    assert not utils.purge_stale_account_by_uri(tmp_path / "absent", "uri", log)


def test_stale_account_quarantine_failure_is_logged(tmp_path, monkeypatch):
    path = tmp_path / "accounts/ca/directory/stale"
    path.mkdir(parents=True)
    (path / "regr.json").write_text("{}")
    monkeypatch.setattr(utils, "quarantine_account", Mock(side_effect=OSError("read-only")))
    log = Mock()
    assert not utils.purge_stale_account(tmp_path, "stale", log)
    assert "read-only" in log.error.call_args.args[0]
    assert (path / "regr.json").is_file()


def test_invalid_base64_json_is_reported_as_missing_credentials(env):
    env["LETS_ENCRYPT_DNS_CREDENTIAL_ITEM"] = b64encode(b"not json").decode()
    log = Mock()
    assert utils.extract_provider("svc", "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM", "cloudflare", logger=log) is None
    assert log.debug.called
    assert "no DNS credentials" in log.warning.call_args.args[0]


def test_log_handler_open_failure_does_not_abort_job(env, tmp_path, monkeypatch):
    monkeypatch.setattr(utils, "RotatingFileHandler", Mock(side_effect=OSError("disk full")))
    log = logging.Logger("unit-letsencrypt-open-failure")
    error = Mock()
    monkeypatch.setattr(log, "error", error)
    utils.attach_job_log_file(log, "job.log", tmp_path)
    assert log.handlers == []
    assert "disk full" in error.call_args.args[0]


def test_log_permission_failures_are_best_effort(tmp_path, monkeypatch):
    log_file = tmp_path / "certbot.log"
    log_file.write_text("keep")
    monkeypatch.setattr(utils, "umask", Mock(side_effect=OSError("umask refused")))
    monkeypatch.setattr(Path, "chmod", Mock(side_effect=OSError("chmod refused")))
    log = Mock()
    utils.prepare_logs_dir(tmp_path, log)
    assert log_file.read_text() == "keep"
    messages = [call.args[0] for call in log.debug.call_args_list]
    assert any("umask" in message for message in messages)
    assert any("chmod refused" in message for message in messages)
