"""LE orphan discovery stays in memory, caches checksums and escapes notifications."""

from unittest.mock import Mock

import pytest
from flask import session

from _core_ui_helpers import tar_bytes


@pytest.fixture
def hooks(load_plugin, ui_env):
    return load_plugin("letsencrypt", "hooks.py")


def cache_row(hooks, checksum="one"):
    return {
        "file_name": hooks._LE_CACHE_TGZ_FILENAME,
        "checksum": checksum,
        "data": tar_bytes(
            {
                "./renewal/orphan.test.conf": "# comment\naccount = absent\nserver = https://acme.example/directory\n",
                "./renewal/healthy.test.conf": "account = present\nserver = https://acme.example/directory\n",
                "./renewal/no-account.conf": "account = None\n",
                "./accounts/acme.example/directory/present/regr.json": "{}",
                "./irrelevant": "ignored",
            }
        ),
    }


def test_orphan_cache_walk_and_checksum_fast_path(hooks, ui_env):
    row = cache_row(hooks)
    ui_env.db.get_jobs_cache_files.return_value = [row]
    expected = [{"cert_name": "orphan.test", "account": "absent", "server": "https://acme.example/directory"}]
    assert hooks._detect_orphans_from_db_cache() == expected
    assert ui_env.db.get_jobs_cache_files.call_count == 2
    ui_env.db.get_jobs_cache_files.reset_mock()
    assert hooks._detect_orphans_from_db_cache() == expected
    ui_env.db.get_jobs_cache_files.assert_called_once_with(with_data=False, job_name="certbot-renew")


def test_orphan_result_cache_eviction_keeps_newest(hooks, ui_env):
    for index in range(6):
        ui_env.db.get_jobs_cache_files.return_value = [cache_row(hooks, str(index))]
        assert len(hooks._detect_orphans_from_db_cache()) == 1
    assert list(hooks._ORPHAN_RESULT_BY_CHECKSUM) == ["2", "3", "4", "5"]


@pytest.mark.parametrize("payload", [b"", b"not a gzip tar"])
def test_empty_or_corrupt_cache_is_nonfatal(hooks, ui_env, payload):
    ui_env.db.get_jobs_cache_files.return_value = [{"file_name": hooks._LE_CACHE_TGZ_FILENAME, "data": payload}]
    assert hooks._detect_orphans_from_db_cache() == []
    assert hooks._ORPHAN_RESULT_BY_CHECKSUM == {}


def test_metadata_failure_still_checks_blob(hooks, ui_env):
    row = cache_row(hooks)
    ui_env.db.get_jobs_cache_files.side_effect = [RuntimeError("metadata unavailable"), [row]]
    assert hooks._detect_orphans_from_db_cache()[0]["cert_name"] == "orphan.test"
    ui_env.db.get_jobs_cache_files.side_effect = RuntimeError("offline")
    assert hooks._detect_orphans_from_db_cache() == []


def test_unrelated_cache_is_ignored(hooks, ui_env):
    ui_env.db.get_jobs_cache_files.return_value = [{"file_name": "other.tgz", "data": b"invalid"}]
    assert hooks._detect_orphans_from_db_cache() == []


def test_notifications_escape_values_deduplicate_and_rearm(hooks, ui_env):
    orphan = {"cert_name": "<img src=x>", "account": "<script>bad()</script>"}
    with ui_env.app.test_request_context("/"):
        hooks._flash_new_orphans([orphan])
        message, category = ui_env.utils.flash.call_args.args
        assert category == "warning"
        assert "&lt;img src=x&gt;" in message
        assert "&lt;script&gt;bad()&lt;/script&gt;" in message
        assert "<script>" not in message
        assert ui_env.utils.flash.call_args.kwargs == {"save": True}
        hooks._flash_new_orphans([orphan])
        assert ui_env.utils.flash.call_count == 1
        hooks._flash_new_orphans([])
        assert session[hooks._ORPHAN_NOTIFIED_KEY] == []
        hooks._flash_new_orphans([orphan])
        assert ui_env.utils.flash.call_count == 2


def test_notification_failure_does_not_break_request(hooks, ui_env):
    ui_env.utils.flash.side_effect = RuntimeError("storage offline")
    with ui_env.app.test_request_context("/"):
        hooks._flash_new_orphans([{"cert_name": "example.test", "account": "missing"}])
        assert session[hooks._ORPHAN_NOTIFIED_KEY] == ["example.test"]


@pytest.mark.parametrize("path", ["/check", "/setup", "/loading", "/login", "/totp", "/logout"])
def test_auth_setup_routes_skip_orphan_detection(hooks, ui_env, monkeypatch, path):
    detect = Mock(side_effect=AssertionError("must not query cache"))
    monkeypatch.setattr(hooks, "_detect_orphans_from_db_cache", detect)
    with ui_env.app.test_request_context(path):
        assert hooks.context_processor() is None
    detect.assert_not_called()


def test_context_processor_throttles_and_clears_healed_notifications(hooks, ui_env, monkeypatch):
    detect = Mock(return_value=[{"cert_name": "example.test", "account": "missing"}])
    monkeypatch.setattr(hooks, "_detect_orphans_from_db_cache", detect)
    monkeypatch.setattr(hooks, "time", lambda: 100)
    with ui_env.app.test_request_context("/home"):
        assert hooks.context_processor() == {"columns_preferences_defaults_letsencrypt": hooks.COLUMNS_PREFERENCES_DEFAULTS}
        assert session[hooks._ORPHAN_CHECK_LAST_KEY] == 100
        assert session[hooks._ORPHAN_NOTIFIED_KEY] == ["example.test"]
        hooks.context_processor()
        detect.assert_called_once_with()
        detect.return_value = []
        monkeypatch.setattr(hooks, "time", lambda: 160)
        hooks.context_processor()
        assert session[hooks._ORPHAN_NOTIFIED_KEY] == []
        assert detect.call_count == 2


def test_context_processor_suppresses_cache_errors(hooks, ui_env, monkeypatch):
    monkeypatch.setattr(hooks, "time", lambda: 100)
    monkeypatch.setattr(hooks, "_detect_orphans_from_db_cache", Mock(side_effect=RuntimeError("offline")))
    with ui_env.app.test_request_context("/home"):
        assert "columns_preferences_defaults_letsencrypt" in hooks.context_processor()
