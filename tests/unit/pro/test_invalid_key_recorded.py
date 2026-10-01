"""A refused PRO key is recorded, so later runs stop probing `/pro/status` (M34).

The 403 branch of `download-pro-plugins.py` exited 0 before `db.set_metadata`, so nothing was stored for a
key that never worked and every run (boot, reload, manual) live-probed the API again, while `/pro` kept
saying "not yet verified". The whole job runs here with its imports stubbed and one canned API answer.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]
JOB_PATH = ROOT / "src" / "common" / "core" / "pro" / "jobs" / "download-pro-plugins.py"
KEY = "not-a-real-key-0000"
NOW = datetime.now(timezone.utc)


def _metadata(**over):
    return {"is_pro": False, "pro_license": "", "pro_status": "invalid", "last_pro_check": None, "non_draft_services": 0, "force_pro_update": False} | over


def _run(monkeypatch, db_metadata, response=None, key=KEY):
    """Run the job once; return (exit code, db mock, requests.get mock)."""
    db = Mock()
    db.get_metadata.return_value = db_metadata
    db.set_metadata.return_value = ""
    get = Mock(return_value=response)

    names = ("requests", "requests.exceptions", "Database", "logger", "common_utils", "service_classification", "model")
    stubs = {name: ModuleType(name) for name in names}
    stubs["requests"].get = get
    stubs["requests"].exceptions = stubs["requests.exceptions"]
    stubs["requests.exceptions"].ConnectionError = ConnectionError
    stubs["Database"].Database = Mock(return_value=db)
    stubs["logger"].getLogger = Mock(return_value=Mock())
    for attr in ("bytes_hash", "create_plugin_tar_gz", "safe_zip_extractall"):
        setattr(stubs["common_utils"], attr, Mock())
    stubs["common_utils"].get_os_info = Mock(return_value="linux")
    stubs["common_utils"].get_integration = Mock(return_value="docker")
    stubs["common_utils"].get_version = Mock(return_value="1.7.0")
    stubs["service_classification"].count_snapshot = Mock(
        return_value=SimpleNamespace(billable=1, algorithm_version=1, allowlist_version=1, exempt_redirect=0, invalid=0, draft=0)
    )
    stubs["model"].Plugins = Mock()
    monkeypatch.setenv("PRO_LICENSE_KEY", key)
    monkeypatch.setenv("DATABASE_URI", "sqlite:///:memory:")

    module = ModuleType("bw_download_pro_plugins_run")
    module.__dict__["__file__"] = str(JOB_PATH)
    with patch.dict(sys.modules, stubs), patch("pathlib.Path.mkdir"), patch("pathlib.Path.glob", return_value=[]), patch("time.sleep"):
        with pytest.raises(SystemExit) as exit_info:
            exec(compile(JOB_PATH.read_text(encoding="utf-8"), str(JOB_PATH), "exec"), module.__dict__)  # noqa: S102
    return exit_info.value.code, db, get


def _answer(status, content_type="application/json"):
    return SimpleNamespace(status_code=status, headers={"Content-Type": content_type}, json=lambda: {"status": "ko"})


def test_a_refused_key_is_recorded(monkeypatch):
    code, db, _ = _run(monkeypatch, _metadata(), _answer(403))

    assert code == 0
    written = db.set_metadata.call_args.args[0]
    assert written["pro_license"] == KEY
    assert written["pro_status"] == "invalid"
    assert written["is_pro"] is False
    assert written["last_pro_check"] is not None


def test_a_refused_key_is_not_probed_again_today(monkeypatch):
    code, db, get = _run(monkeypatch, _metadata(pro_license=KEY, last_pro_check=NOW))

    assert code == 0
    get.assert_not_called()
    db.set_metadata.assert_not_called()


def test_a_changed_key_is_probed(monkeypatch):
    _, _, get = _run(monkeypatch, _metadata(pro_license="another-key", last_pro_check=NOW), _answer(403))

    get.assert_called_once()


def test_a_refusal_recorded_yesterday_is_probed_again(monkeypatch):
    _, _, get = _run(monkeypatch, _metadata(pro_license=KEY, last_pro_check=NOW - timedelta(days=1)), _answer(403))

    get.assert_called_once()


def test_a_forced_update_is_not_short_circuited_by_the_skip(monkeypatch):
    # the skip must not swallow a forced run: it goes on to the download path (force never probes /pro/status)
    _, db, _ = _run(monkeypatch, _metadata(pro_license=KEY, last_pro_check=NOW, force_pro_update=True), _answer(403))

    assert db.get_metadata.called


def test_an_html_403_is_a_verdict_too(monkeypatch):
    # the real PRO API answers a bad key with the edge's HTML 403 page, never JSON
    code, db, _ = _run(monkeypatch, _metadata(), _answer(403, "text/html; charset=utf-8"))

    assert code == 0
    written = db.set_metadata.call_args.args[0]
    assert written["pro_license"] == KEY
    assert written["pro_status"] == "invalid"
    assert written["last_pro_check"] is not None


def test_a_rate_limit_records_the_attempt_without_a_verdict(monkeypatch):
    code, db, _ = _run(monkeypatch, _metadata(), _answer(429, "text/html; charset=utf-8"))

    assert code == 0
    written = db.set_metadata.call_args.args[0]
    assert written["pro_license"] == KEY
    assert written["last_pro_check"] is not None
    assert "pro_status" not in written
    assert "is_pro" not in written


def test_a_rate_limited_key_is_not_probed_again_today(monkeypatch):
    _, _, get = _run(monkeypatch, _metadata(pro_license=KEY, pro_status="expired", last_pro_check=NOW))

    get.assert_not_called()


def test_a_rate_limit_on_a_key_that_was_pro_records_nothing(monkeypatch):
    _, db, _ = _run(monkeypatch, _metadata(is_pro=True, pro_license=KEY, pro_status="active"), _answer(429))

    db.set_metadata.assert_not_called()


@pytest.mark.parametrize("answer", [_answer(500)])
def test_a_non_verdict_answer_is_not_recorded(monkeypatch, answer):
    _, db, _ = _run(monkeypatch, _metadata(), answer)

    db.set_metadata.assert_not_called()


def test_a_connection_failure_is_not_recorded(monkeypatch):
    code, db, _ = _run(monkeypatch, _metadata(), None)

    assert code == 2
    db.set_metadata.assert_not_called()


def test_a_403_on_a_key_that_was_pro_keeps_the_state(monkeypatch):
    # an active licence answered 403 without "clean" is an access problem, not a verdict: nothing is overwritten
    _, db, _ = _run(monkeypatch, _metadata(is_pro=True, pro_license=KEY, pro_status="active"), _answer(403))

    db.set_metadata.assert_not_called()
