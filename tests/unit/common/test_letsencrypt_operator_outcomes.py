"""ACME cache diagnostics and repairs stay local and preserve recoverable material."""

import os
from pathlib import Path
import runpy
from unittest.mock import Mock

import pytest

import letsencrypt_consistency as le

SERVER = "https://acme-v02.api.letsencrypt.org/directory"


def account(root, name, *, complete=True):
    target = root / "accounts/acme-v02.api.letsencrypt.org/directory" / name
    target.mkdir(parents=True)
    for filename in ("regr.json", "private_key.json", "meta.json") if complete else ("regr.json",):
        (target / filename).write_text("{}")
    return target


def renewal(root, name="site.example", account_id="missing", server=SERVER):
    target = root / "renewal" / f"{name}.conf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"# keep comment\naccount = {account_id}\nserver = {server}\n")
    return target


@pytest.mark.parametrize("state", ["no-renewal", "no-reference", "missing-directory", "missing-account", "healthy"])
def test_consistency_reports_missing_account_without_changing_files(tmp_path, state):
    if state != "no-renewal":
        renewal(tmp_path, account_id="None" if state == "no-reference" else "missing")
    if state in ("missing-account", "healthy"):
        account(tmp_path, "missing" if state == "healthy" else "other")
    before = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    ok, message = le.letsencrypt_cache_consistent(tmp_path)
    assert ok is (state in ("no-renewal", "no-reference", "healthy"))
    if state == "missing-directory":
        assert message == "renewal/ references 1 account(s) but accounts/ dir is missing"
    elif state == "missing-account":
        assert "missing account(s) ['missing']" in message and "on-disk accounts: ['other']" in message
    else:
        assert message == ""
    assert before == {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}


def test_consistency_limits_account_samples_in_operator_message(tmp_path):
    for index in range(11):
        renewal(tmp_path, name=f"site-{index}.example", account_id=f"missing-{index:02}")
        account(tmp_path, f"present-{index:02}")
    ok, message = le.letsencrypt_cache_consistent(tmp_path)
    assert not ok
    assert "missing-09" in message and "missing-10" not in message
    assert "present-09" in message and "present-10" not in message
    assert message.count("...") == 2


@pytest.mark.parametrize("server,expected", [("", "names no server"), (SERVER, "no usable replacement")])
def test_orphan_without_safe_replacement_is_left_untouched(tmp_path, server, expected):
    conf = renewal(tmp_path, server=server)
    before = conf.read_bytes()
    log = Mock()
    assert le.detect_orphan_renewals(tmp_path) == [{"cert_name": "site.example", "account": "missing", "server": server}]
    assert le.repoint_orphan_renewals(tmp_path, log) == []
    assert conf.read_bytes() == before
    assert expected in (log.warning if not server else log.error).call_args.args[0]


def test_repoint_chooses_newest_complete_account_and_logs_actual_change(tmp_path):
    conf = renewal(tmp_path)
    conf.chmod(0o640)
    old = account(tmp_path, "old")
    newest = account(tmp_path, "new")
    incomplete = account(tmp_path, "incomplete", complete=False)
    for target, stamp in ((old, 10), (newest, 20), (incomplete, 30)):
        os.utime(target, (stamp, stamp))
    assert le.usable_accounts_for_server(tmp_path, SERVER) == [newest, old]
    log = Mock()
    assert le.repoint_orphan_renewals(tmp_path, log) == ["site.example"]
    assert conf.read_text() == f"# keep comment\naccount = new\nserver = {SERVER}\n"
    assert conf.stat().st_mode & 0o777 == 0o640
    assert "from missing ACME account missing to new" in log.warning.call_args.args[0]
    assert le.letsencrypt_cache_consistent(tmp_path) == (True, "")


def test_unreadable_renewal_is_skipped_and_broken_lineage_reports_it(tmp_path, monkeypatch):
    conf = renewal(tmp_path)
    original = Path.read_text

    def read(path, *args, **kwargs):
        if path == conf:
            raise OSError("fixture unreadable")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    assert le.letsencrypt_cache_consistent(tmp_path) == (True, "")
    assert le.detect_orphan_renewals(tmp_path) == []
    broken = le.detect_broken_lineages(tmp_path)
    assert len(broken) == 1 and "read" in broken[0]["reason"]
    assert conf.exists()


def test_quarantined_account_logs_destination_and_keeps_private_key(tmp_path, monkeypatch):
    target = account(tmp_path, "refused")
    quarantine = tmp_path / "quarantine"
    monkeypatch.setattr(le, "QUARANTINE_ROOT", quarantine)
    log = Mock()
    assert le.quarantine_account(target, log)
    assert not target.exists()
    saved = list(quarantine.glob("*-account-refused/private_key.json"))
    assert len(saved) == 1 and saved[0].read_text() == "{}"
    assert "Moved the refused ACME account refused" in log.info.call_args.args[0]


def test_module_self_check_exercises_certbot_layout_and_repair_contracts(capsys):
    # The shipped diagnostic includes assertions for symlink layouts, traversal and partial repairs.
    runpy.run_path(str(Path(le.__file__)), run_name="__main__")
    assert capsys.readouterr().out == "letsencrypt_consistency self-check passed\n"
