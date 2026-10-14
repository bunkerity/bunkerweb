"""certbot-renew.py exits 3 when it rotated a certificate and still failed.

`certbot renew` covers every lineage in one run. A run that rotated lineage A and failed lineage B
used to exit 2: the run was recorded failed and nothing was published, so A's new certificate sat in
the database while every instance kept serving the old one until an unrelated reload. Exit 3 means
"changed material, run failed" (the same value as dev's `d7bf3b350`): the worker publishes it and
records the run failed. The gates stay 1.7's -- a failed cache restore is a plain 2 and never
publishes, and a direct delivery that went through must not make the worker deliver twice.

The whole script is run as shipped, with certbot, the instances and the database stubbed and real
lineage files on disk.
"""

import sys
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "src" / "common" / "core" / "letsencrypt" / "jobs" / "certbot-renew.py"
UP = {"status": "up"}


def _write(data, name, content):
    target = data / "live" / name / "fullchain.pem"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)


def run_renew(
    tmp_path,
    monkeypatch,
    *,
    before,
    certbot=None,
    returncode=0,
    finished=True,
    restore_ok=True,
    consistent=True,
    cached=True,
    instances=(UP,),
    pushed=True,
    reload_sent=True,
):
    """Run the script once. Returns ``(exit code, ApiCaller double, Job double)``."""
    data = tmp_path / "data"
    for name, content in before.items():
        _write(data, name, content)

    monkeypatch.setenv("AUTO_LETS_ENCRYPT", "yes")
    monkeypatch.setenv("MULTISITE", "no")
    monkeypatch.delenv("DISABLE_CONFIGURATION_TESTING", raising=False)

    class _Process:
        def __init__(self, *_args, **_kwargs):
            if certbot:
                certbot(data)
            self.returncode = returncode

    monkeypatch.setattr("subprocess.Popen", _Process)

    caller = Mock()
    caller.send_files.return_value = pushed
    caller.send_to_apis.return_value = (reload_sent, {})
    job = Mock(restore_ok=restore_ok)
    job.cache_dir.return_value = (cached, "" if cached else "disk full")
    job.db.get_instances.return_value = list(instances)
    job.db.import_legacy_certbot_certificates.return_value = {}

    utils = ModuleType("letsencrypt_utils")
    utils.__dict__.update(
        CERTBOT_BIN="certbot",
        DEPS_PATH=tmp_path / "deps",
        LETSENCRYPT_CACHE_PATH=tmp_path / "cache" / "letsencrypt",
        LETSENCRYPT_DATA_PATH=data,
        LETSENCRYPT_LOGS_DIR=str(tmp_path / "logs"),
        LETSENCRYPT_WORK_DIR=str(tmp_path / "work"),
        ZEROSSL_BOT_SCRIPT="zerossl-bot",
        account_id_for_cert=lambda *_a: "",
        build_certbot_env=lambda *_a: {},
        certbot_log_backup_flags=lambda *_a: [],
        failed_renewal_cert=lambda *_a: "",
        is_stale_account_line=lambda *_a: False,
        is_zerossl_used_in_env=lambda: False,
        le_cache_write_lock=nullcontext,
        letsencrypt_cache_consistent=lambda *_a: (consistent, "" if consistent else "orphaned renewal conf"),
        prepare_logs_dir=lambda *_a: None,
        purge_stale_account=lambda *_a: False,
        purge_stale_account_by_uri=lambda *_a: False,
        resolve_certbot_entrypoint=lambda *_a, **_k: ["certbot"],
        stale_account_uri=lambda *_a: "",
        stream_certbot=lambda *_a: finished,
        sanitize_and_persist=lambda *_a: [],
    )
    stubs = {
        "letsencrypt_utils": utils,
        "certbot_concurrency": Mock(ensure_accounts_for_orphans=Mock()),
        "API": Mock(),
        "ApiCaller": Mock(ApiCaller=Mock(return_value=caller)),
        "logger": Mock(getLogger=Mock(return_value=Mock())),
        "jobs": Mock(Job=Mock(return_value=job), cache_publication_lock=lambda *_a, **_k: nullcontext()),
    }
    for name, module in stubs.items():
        monkeypatch.setitem(sys.modules, name, module)

    with pytest.raises(SystemExit) as exit_info:
        exec(compile(SCRIPT.read_text(), str(SCRIPT), "exec"), {"__file__": str(SCRIPT), "__name__": "__main__"})  # noqa: S102
    return exit_info.value.code, caller, job


def rotate(*names):
    def _rotate(data):
        for name in names:
            _write(data, name, f"{name}-renewed")

    return _rotate


BEFORE = {"a.example": "a-old", "b.example": "b-old"}


class TestUnchangedBehaviour:
    def test_nothing_renewed_exits_zero_and_publishes_nothing(self, tmp_path, monkeypatch):
        code, caller, _ = run_renew(tmp_path, monkeypatch, before=BEFORE)
        assert code == 0
        caller.send_files.assert_not_called()

    def test_every_lineage_renewed_and_delivered_exits_zero(self, tmp_path, monkeypatch):
        code, caller, _ = run_renew(tmp_path, monkeypatch, before=BEFORE, certbot=rotate("a.example", "b.example"))
        assert code == 0
        caller.send_files.assert_called_once()
        caller.send_to_apis.assert_called_once()

    def test_every_lineage_renewed_but_not_deliverable_exits_one(self, tmp_path, monkeypatch):
        code, _, _ = run_renew(tmp_path, monkeypatch, before=BEFORE, certbot=rotate("a.example", "b.example"), instances=())
        assert code == 1

    def test_a_failure_that_changed_nothing_is_still_a_plain_failure(self, tmp_path, monkeypatch):
        code, caller, _ = run_renew(tmp_path, monkeypatch, before=BEFORE, returncode=1)
        assert code == 2
        caller.send_files.assert_not_called()


class TestPartialRenewal:
    def test_one_lineage_rotated_and_one_failed_exits_three_when_it_cannot_be_delivered(self, tmp_path, monkeypatch):
        code, _, job = run_renew(tmp_path, monkeypatch, before=BEFORE, certbot=rotate("a.example"), returncode=1, instances=())
        assert code == 3
        job.cache_dir.assert_called_once()

    def test_delivered_directly_it_stays_a_failure_without_asking_for_a_second_delivery(self, tmp_path, monkeypatch):
        code, caller, _ = run_renew(tmp_path, monkeypatch, before=BEFORE, certbot=rotate("a.example"), returncode=1)
        assert code == 2, "the other lineage's failure must stay visible, and 3 would make the worker deliver again"
        caller.send_files.assert_called_once()
        caller.send_to_apis.assert_called_once()

    def test_a_push_that_failed_leaves_the_worker_to_deliver(self, tmp_path, monkeypatch):
        code, _, _ = run_renew(tmp_path, monkeypatch, before=BEFORE, certbot=rotate("a.example"), returncode=1, pushed=False)
        assert code == 3

    def test_a_reload_that_was_refused_leaves_the_worker_to_deliver(self, tmp_path, monkeypatch):
        code, _, _ = run_renew(tmp_path, monkeypatch, before=BEFORE, certbot=rotate("a.example"), returncode=1, reload_sent=False)
        assert code == 3

    def test_a_timeout_with_a_rotated_lineage_exits_three(self, tmp_path, monkeypatch):
        code, _, _ = run_renew(tmp_path, monkeypatch, before=BEFORE, certbot=rotate("a.example"), returncode=None, finished=False, instances=())
        assert code == 3

    def test_a_new_lineage_counts_as_rotated(self, tmp_path, monkeypatch):
        code, _, _ = run_renew(tmp_path, monkeypatch, before=BEFORE, certbot=rotate("c.example"), returncode=1, instances=())
        assert code == 3

    def test_a_lineage_that_vanished_does_not(self, tmp_path, monkeypatch):
        def drop(data):
            (data / "live" / "b.example" / "fullchain.pem").unlink()

        code, caller, _ = run_renew(tmp_path, monkeypatch, before=BEFORE, certbot=drop, returncode=1)
        assert code == 2
        caller.send_files.assert_not_called()

    def test_a_lineage_that_became_unreadable_does_not(self, tmp_path, monkeypatch):
        def break_it(data):
            target = data / "live" / "a.example" / "fullchain.pem"
            target.unlink()
            target.mkdir()

        code, caller, _ = run_renew(tmp_path, monkeypatch, before=BEFORE, certbot=break_it, returncode=1)
        assert code == 2
        caller.send_files.assert_not_called()


class TestGatesStay1_7s:
    def test_a_failed_cache_restore_never_publishes(self, tmp_path, monkeypatch):
        code, caller, job = run_renew(tmp_path, monkeypatch, before=BEFORE, certbot=rotate("a.example"), returncode=1, restore_ok=False)
        assert code == 2
        job.cache_dir.assert_not_called()
        caller.send_files.assert_not_called()

    def test_an_inconsistent_tree_with_a_rotated_lineage_leaves_publication_to_the_worker(self, tmp_path, monkeypatch):
        code, caller, job = run_renew(tmp_path, monkeypatch, before=BEFORE, certbot=rotate("a.example"), returncode=1, consistent=False)
        assert code == 3
        job.cache_dir.assert_not_called()
        caller.send_files.assert_not_called()

    def test_an_inconsistent_tree_after_a_clean_run_is_still_a_one(self, tmp_path, monkeypatch):
        code, _, _ = run_renew(tmp_path, monkeypatch, before=BEFORE, consistent=False)
        assert code == 1

    def test_a_cache_write_failure_keeps_the_codes_it_had(self, tmp_path, monkeypatch):
        code, caller, _ = run_renew(tmp_path, monkeypatch, before=BEFORE, certbot=rotate("a.example"), returncode=1, cached=False)
        assert code == 3
        clean, _, _ = run_renew(tmp_path / "again", monkeypatch, before=BEFORE, certbot=rotate("a.example"), cached=False)
        assert clean == 1
        caller.send_files.assert_not_called()
