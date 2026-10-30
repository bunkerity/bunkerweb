"""Account scoping, registration boundaries and publication of isolated certbot trees."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
from threading import Lock
from unittest.mock import Mock

import pytest

import certbot_concurrency as concurrency

PRODUCTION = concurrency.LETSENCRYPT_PRODUCTION_DIRECTORY
STAGING = concurrency.LETSENCRYPT_STAGING_DIRECTORY
ZEROSSL = concurrency.ZEROSSL_DIRECTORY


def account(root, server, name, email="", modified=100):
    path = root / concurrency._server_url_to_subpath(server) / name
    path.mkdir(parents=True, exist_ok=True)
    (path / "regr.json").write_text("{}")
    (path / "meta.json").write_text(json.dumps({"email": email}))
    (path / "private_key.json").write_text("{}")
    os.utime(path, (modified, modified))
    return path


def test_account_selection_is_ca_scoped_and_prefers_email_then_newest(tmp_path):
    accounts = tmp_path / "accounts"
    account(accounts, PRODUCTION, "old", "OPS@example.com", 10)
    account(accounts, PRODUCTION, "new", "ops@example.com", 20)
    account(accounts, PRODUCTION, "anonymous", modified=30)
    account(accounts, STAGING, "stage", "ops@example.com", 40)
    account(accounts, ZEROSSL, "zero", "ops@example.com", 50)
    assert concurrency.select_account_id(accounts, False, "ops@example.com", PRODUCTION) == "new"
    assert concurrency.select_account_id(accounts, False, "", PRODUCTION) == "anonymous"
    assert concurrency.select_account_id(accounts, False, "other@example.com", PRODUCTION) == "anonymous"
    assert concurrency.select_account_id(accounts, False, "ops@example.com", ZEROSSL) == "zero"
    assert concurrency.select_account_id(accounts, True, "ops@example.com", STAGING) == "stage"
    assert concurrency._account_exists(accounts, False, "OPS@example.com", PRODUCTION)
    assert not concurrency._account_exists(accounts, False, "missing@example.com", PRODUCTION)
    assert concurrency._account_exists(accounts, False, "", PRODUCTION)
    assert concurrency.select_account_id(accounts, False, "", "https://missing.example/directory") is None
    assert not concurrency._account_exists(accounts, False, "", "https://missing.example/directory")


def test_legacy_selection_filters_staging_and_ignores_invalid_metadata(tmp_path):
    accounts = tmp_path / "accounts"
    first = account(accounts, PRODUCTION, "prod", modified=10)
    (first / "meta.json").write_text("invalid json")
    second = account(accounts, STAGING, "stage", modified=20)
    (second / "meta.json").write_text("[]")
    (accounts / "ordinary-file").write_text("ignore")
    (accounts / "empty-account").mkdir()
    assert concurrency.select_account_id(accounts, False, "") == "prod"
    assert concurrency.select_account_id(accounts, True, "") == "stage"
    assert concurrency._account_exists(accounts, False, "")
    assert not concurrency._account_exists(accounts, True, "ops@example.com")
    assert set(concurrency._find_directory_dirs(accounts)) == {first.parent, second.parent}
    assert concurrency._scoped_account_root(accounts, "") is None


def test_missing_or_empty_account_tree_is_not_an_account(tmp_path):
    for accounts in (tmp_path / "absent", tmp_path):
        assert concurrency.select_account_id(accounts, False, "") is None
        assert not concurrency._account_exists(accounts, False, "")


@pytest.mark.parametrize("server", [PRODUCTION, ZEROSSL])
def test_server_scoped_discovery_tolerates_broken_and_missing_meta(tmp_path, server):
    accounts = tmp_path / "accounts"
    invalid = account(accounts, server, "invalid", modified=10)
    (invalid / "meta.json").write_text("{")
    missing = account(accounts, server, "missing", modified=20)
    (missing / "meta.json").unlink()
    (invalid.parent / "not-account").mkdir()
    (invalid.parent / "not-dir").write_text("x")
    assert concurrency.select_account_id(accounts, False, "", server) == "missing"
    assert {path.name for path, email in concurrency._collect_account_candidates(invalid.parent) if email == ""} == {"invalid", "missing"}


@pytest.mark.parametrize("zerossl", [False, True])
def test_registration_command_preserves_email_staging_debug_and_environment(tmp_path, monkeypatch, zerossl):
    process = Mock(return_value=CompletedProcess([], 0, stdout="registered"))
    monkeypatch.setattr(concurrency, "run", process)
    env = {"LETS_ENCRYPT_MAX_LOG_BACKUPS": "7", "PATH": "/test/bin"}
    register = concurrency.ensure_zerossl_accounts if zerossl else concurrency.ensure_accounts
    register({(True, "ops@example.com"), (False, "")}, env, "fake-register", "DEBUG", tmp_path, "work", "logs", Mock())
    assert process.call_count == 2
    anonymous, named = [call.args[0] for call in process.call_args_list]
    assert anonymous[:4] == ["fake-register", "register", "-n", "--agree-tos"]
    assert "--register-unsafely-without-email" in anonymous
    assert "--staging" not in anonymous
    assert named[named.index("--email") + 1] == "ops@example.com"
    assert "--staging" in named
    assert "-v" in named
    assert named[named.index("--config-dir") + 1] == str(tmp_path)
    assert named[named.index("--max-log-backups") + 1] == "7"
    assert process.call_args.kwargs["env"] is env
    assert process.call_args.kwargs["timeout"] == 300
    assert process.call_args.kwargs["check"] is False


@pytest.mark.parametrize("zerossl", [False, True])
def test_registration_skips_existing_account(tmp_path, monkeypatch, zerossl):
    server = ZEROSSL if zerossl else PRODUCTION
    account(tmp_path / "accounts", server, "present", "ops@example.com")
    process = Mock(side_effect=AssertionError("existing account must not register"))
    monkeypatch.setattr(concurrency, "run", process)
    register = concurrency.ensure_zerossl_accounts if zerossl else concurrency.ensure_accounts
    register({(False, "ops@example.com")}, {}, "fake-register", "INFO", tmp_path, "work", "logs", Mock())
    process.assert_not_called()


@pytest.mark.parametrize("zerossl", [False, True])
@pytest.mark.parametrize(
    "result, expected",
    [
        (TimeoutExpired("fake-register", 300), "timed out"),
        (CompletedProcess([], 1, stdout="Existing account found"), "already exists"),
        (CompletedProcess([], 1, stdout="registration refused"), "registration refused"),
    ],
)
def test_registration_failures_are_reported_without_aborting(tmp_path, monkeypatch, zerossl, result, expected):
    process = Mock(side_effect=result) if isinstance(result, Exception) else Mock(return_value=result)
    monkeypatch.setattr(concurrency, "run", process)
    log = Mock()
    register = concurrency.ensure_zerossl_accounts if zerossl else concurrency.ensure_accounts
    register({(False, "")}, {}, "fake-register", "INFO", tmp_path, "work", "logs", log)
    messages = [call.args[0] for call in log.error.call_args_list + log.info.call_args_list]
    assert any(expected in message for message in messages)


def test_orphan_recovery_registers_only_missing_supported_endpoints(tmp_path, monkeypatch):
    monkeypatch.setattr(concurrency, "environ", {"svc_EMAIL_LETS_ENCRYPT": " service@example.com "})
    monkeypatch.setattr(concurrency, "detect_orphan_renewals", lambda path: [{"server": server} for server in (PRODUCTION, PRODUCTION, STAGING, ZEROSSL, "")])
    monkeypatch.setattr(concurrency, "usable_accounts_for_server", lambda path, server: ["usable"] if server == STAGING else [])
    register = Mock()
    monkeypatch.setattr(concurrency, "ensure_accounts", register)
    log = Mock()
    concurrency.ensure_accounts_for_orphans(tmp_path, {"PATH": "fake"}, "certbot", "INFO", "work", "logs", log)
    assert register.call_args.args[0] == {(False, "service@example.com")}
    assert any(ZEROSSL in call.args[0] and "re-issue" in call.args[0] for call in log.error.call_args_list)
    assert any("Still no loadable" in call.args[0] for call in log.error.call_args_list)


@pytest.mark.parametrize("servers", [[], [ZEROSSL], [STAGING]])
def test_orphan_recovery_skips_unneeded_registration(tmp_path, monkeypatch, servers):
    monkeypatch.setattr(concurrency, "detect_orphan_renewals", lambda path: [{"server": server} for server in servers])
    monkeypatch.setattr(concurrency, "usable_accounts_for_server", lambda path, server: ["usable"] if server == STAGING else [])
    register = Mock()
    monkeypatch.setattr(concurrency, "ensure_accounts", register)
    concurrency.ensure_accounts_for_orphans(tmp_path, {}, "certbot", "INFO", "work", "logs", Mock())
    register.assert_not_called()


def test_recovery_email_uses_global_then_service_then_empty(monkeypatch):
    env = {"EMAIL_LETS_ENCRYPT": " global@example.com ", "svc_EMAIL_LETS_ENCRYPT": "service@example.com"}
    monkeypatch.setattr(concurrency, "environ", env)
    assert concurrency._configured_letsencrypt_email() == "global@example.com"
    env["EMAIL_LETS_ENCRYPT"] = " "
    assert concurrency._configured_letsencrypt_email() == "service@example.com"
    env["svc_EMAIL_LETS_ENCRYPT"] = " "
    assert concurrency._configured_letsencrypt_email() == ""


@pytest.mark.parametrize("success", [True, False])
def test_isolated_run_only_publishes_success_but_always_merges_logs(tmp_path, success):
    data, cache, work, logs = (tmp_path / name for name in ("data", "cache", "work", "logs"))
    account(data / "accounts", PRODUCTION, "existing")
    paths, scratch = concurrency.prepare_certbot_paths("app.example.com", True, cache, data, str(work), str(logs))
    assert (paths.config_dir / "accounts" / concurrency._server_url_to_subpath(PRODUCTION) / "existing/regr.json").read_text() == "{}"
    renewal = paths.config_dir / "renewal/app.example.com.conf"
    renewal.parent.mkdir()
    renewal.write_text(f"archive_dir = {paths.config_dir}/archive/app.example.com\nwork_dir = {paths.work_dir}\nlogs_dir = {paths.logs_dir}\n")
    archive = paths.config_dir / "archive/app.example.com"
    archive.mkdir(parents=True)
    (archive / "fullchain1.pem").write_bytes(b"issued")
    live = paths.config_dir / "live/app.example.com"
    live.mkdir(parents=True)
    (live / "fullchain.pem").symlink_to("../../archive/app.example.com/fullchain1.pem")
    (paths.work_dir / "checkpoint").write_text("checkpoint")
    logs.mkdir()
    (logs / "letsencrypt.log").write_text("previous")
    (paths.logs_dir / "letsencrypt.log").write_text("current")
    (paths.logs_dir / "new.log").write_text("new")
    (paths.logs_dir / "alias.log").symlink_to("new.log")
    entered = []

    @contextmanager
    def merge_lock():
        entered.append(True)
        yield

    concurrency.finalize_certbot_run(paths, scratch, success, merge_lock(), data, str(work), str(logs), Mock())
    assert entered == [True]
    assert (logs / "letsencrypt.log").read_text() == "previous\ncurrent"
    assert (logs / "alias.log").is_symlink()
    assert (logs / "alias.log").read_text() == "new"
    assert not scratch.exists()
    if success:
        assert (data / "live/app.example.com/fullchain.pem").is_symlink()
        assert (data / "live/app.example.com/fullchain.pem").read_bytes() == b"issued"
        assert (data / "renewal/app.example.com.conf").read_text() == f"archive_dir = {data}/archive/app.example.com\nwork_dir = {work}\nlogs_dir = {logs}\n"
        assert (work / "checkpoint").read_text() == "checkpoint"
    else:
        assert not (data / "live").exists()
        assert not work.exists()


def test_serial_run_uses_canonical_paths_and_never_removes_them(tmp_path):
    paths, scratch = concurrency.prepare_certbot_paths("svc", False, tmp_path / "cache", tmp_path / "data", "work", "logs")
    assert paths == concurrency.CertbotPaths(tmp_path / "data", Path("work"), Path("logs"))
    assert scratch is None
    concurrency.finalize_certbot_run(paths, scratch, False, Lock(), tmp_path / "data", "work", "logs", Mock())
    assert tmp_path.exists()


def test_merge_replaces_files_and_broken_symlinks(tmp_path):
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    (src / "file").write_text("new")
    (dest / "file").symlink_to("missing")
    (src / "link").symlink_to("file")
    (dest / "link").write_text("old")
    concurrency._merge_dir(src, dest)
    assert (dest / "file").read_text() == "new"
    assert (dest / "link").is_symlink()
    assert (dest / "link").read_text() == "new"


def test_merge_errors_log_and_preserve_existing_file(tmp_path, monkeypatch):
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    (src / "file").write_text("new")
    monkeypatch.setattr(concurrency, "copy2", Mock(side_effect=OSError("disk full")))
    log = Mock()
    concurrency._merge_dir(src, dest, log)
    concurrency._merge_logs(src, dest, log)
    assert log.warning.call_count == 2
    assert not (dest / "file").exists()
    blocker = tmp_path / "not-directory"
    blocker.write_text("keep")
    concurrency._merge_dir(src, blocker, log)
    concurrency._merge_logs(src, blocker, log)
    assert blocker.read_text() == "keep"
    assert log.warning.call_count == 4


def test_cleanup_failure_is_reported_after_log_merge(tmp_path, monkeypatch):
    paths, scratch = concurrency.prepare_certbot_paths("svc", True, tmp_path / "cache", tmp_path / "data", "work", "logs")
    monkeypatch.setattr(concurrency, "rmtree", Mock(side_effect=OSError("busy")))
    log = Mock()
    concurrency.finalize_certbot_run(paths, scratch, False, Lock(), tmp_path / "data", str(tmp_path / "work"), str(tmp_path / "logs"), log)
    assert "busy" in log.warning.call_args.args[0]
    assert scratch.is_dir()


@pytest.mark.parametrize("operation", ["read_text", "write_text"])
def test_renewal_rewrite_io_failure_is_logged_and_other_configs_continue(tmp_path, monkeypatch, operation):
    paths, _ = concurrency.prepare_certbot_paths("svc", True, tmp_path / "cache", tmp_path / "data", "work", "logs")
    renewal = paths.config_dir / "renewal"
    renewal.mkdir()
    failing, good = renewal / "failing.conf", renewal / "good.conf"
    for conf in (failing, good):
        conf.write_text(f"archive_dir = {paths.config_dir}/archive\n")
    original = getattr(Path, operation)

    def access(path, *args, **kwargs):
        if path == failing:
            raise OSError("read-only")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, operation, access)
    log = Mock()
    concurrency._rewrite_renewal_paths(paths, tmp_path / "data", "work", "logs", log)
    assert (tmp_path / "data").as_posix() in good.read_text()
    assert "read-only" in log.debug.call_args.args[0]


def test_nested_log_merge_failure_does_not_discard_other_logs(tmp_path):
    src, dest = tmp_path / "src", tmp_path / "dest"
    (src / "blocked").mkdir(parents=True)
    dest.mkdir()
    (src / "blocked/file.log").write_text("blocked")
    (src / "good.log").write_text("keep")
    (dest / "blocked").write_text("existing file")
    log = Mock()
    concurrency._merge_logs(src, dest, log)
    assert (dest / "blocked").read_text() == "existing file"
    assert (dest / "good.log").read_text() == "keep"
    assert "log subdirectory" in log.warning.call_args.args[0]
