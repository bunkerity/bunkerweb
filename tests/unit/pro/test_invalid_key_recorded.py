"""A refused PRO key is recorded, so later runs stop probing `/pro/status` (M34).

The 403 branch of `download-pro-plugins.py` exited 0 before `db.set_metadata`, so nothing was stored for a
key that never worked and every run (boot, reload, manual) live-probed the API again, while `/pro` kept
saying "not yet verified". The whole job runs here with its imports stubbed and one canned API answer.
"""

import ast
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


# the envelope bunkernet_pro answers a request without a usable bearer with (403 on /pro/status)
ENVELOPE = {"result": "ko", "data": {"status": "invalid", "expire_date": "", "max_services": 0, "overlapped": False}}


def _job():
    """The job's pure helpers, cut out of its source: the module body runs the whole job on import."""
    tree = ast.parse(JOB_PATH.read_text(encoding="utf-8"))
    keep = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "is_pro_api_verdict"]
    module = ModuleType("bw_download_pro_plugins_helpers")
    exec(compile(ast.Module(keep, []), str(JOB_PATH), "exec"), module.__dict__)  # noqa: S102
    return module


def _answer(status, content_type="application/json", body=ENVELOPE):
    def _json():
        if body is None:
            raise ValueError("no JSON body")
        return body

    return SimpleNamespace(status_code=status, headers={"Content-Type": content_type}, json=_json)


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


def _assert_attempt_without_verdict(db):
    """Same shape as the 429 branch: the key and the day are remembered, `pro_status`/`is_pro` are left alone."""
    written = db.set_metadata.call_args.args[0]
    assert written["pro_license"] == KEY
    assert written["last_pro_check"] is not None
    assert "pro_status" not in written
    assert "is_pro" not in written


def test_an_html_403_is_not_a_verdict(monkeypatch):
    # the edge WAF page in front of the API (BunkerWeb's own error.html) says nothing about the key
    code, db, _ = _run(monkeypatch, _metadata(), _answer(403, "text/html; charset=utf-8", body=None))

    assert code == 0
    _assert_attempt_without_verdict(db)


def test_an_edge_403_is_not_probed_again_today(monkeypatch):
    _, db, _ = _run(monkeypatch, _metadata(), _answer(403, "text/html; charset=utf-8", body=None))
    recorded = db.set_metadata.call_args.args[0]

    _, _, get = _run(monkeypatch, _metadata(pro_license=KEY, last_pro_check=recorded["last_pro_check"]))

    get.assert_not_called()


def test_a_json_403_without_the_envelope_is_not_a_verdict(monkeypatch):
    code, db, _ = _run(monkeypatch, _metadata(), _answer(403, body={"error": "x"}))

    assert code == 0
    _assert_attempt_without_verdict(db)


def test_a_json_content_type_with_an_unparsable_body_is_not_a_verdict(monkeypatch):
    code, db, _ = _run(monkeypatch, _metadata(), _answer(403, body=None))

    assert code == 0
    _assert_attempt_without_verdict(db)


def test_a_json_envelope_with_a_charset_is_a_verdict(monkeypatch):
    code, db, _ = _run(monkeypatch, _metadata(), _answer(403, "application/json; charset=utf-8"))

    assert code == 0
    written = db.set_metadata.call_args.args[0]
    assert written["pro_status"] == "invalid"
    assert written["is_pro"] is False


def test_a_legacy_action_body_is_a_verdict(monkeypatch):
    code, db, _ = _run(monkeypatch, _metadata(), _answer(403, body={"action": "nothing"}))

    assert code == 0
    assert db.set_metadata.call_args.args[0]["pro_status"] == "invalid"


def test_an_edge_403_on_a_key_that_was_pro_records_nothing(monkeypatch):
    _, db, _ = _run(monkeypatch, _metadata(is_pro=True, pro_license=KEY, pro_status="active"), _answer(403, "text/html", body=None))

    db.set_metadata.assert_not_called()


@pytest.mark.parametrize(
    ("status", "content_type", "body", "expected"),
    [
        (403, "application/json", ENVELOPE, True),
        (403, "Application/JSON; charset=utf-8", ENVELOPE, True),
        (403, "application/json", {"action": "clean"}, True),
        (403, "application/json", {"error": "x"}, False),
        (403, "application/json", {"result": "ok"}, False),
        (403, "application/json", ["result", "ko"], False),
        (403, "application/json", None, False),
        (403, "text/html; charset=utf-8", ENVELOPE, False),
        (403, "", ENVELOPE, False),
        (200, "application/json", ENVELOPE, False),
    ],
)
def test_is_pro_api_verdict(status, content_type, body, expected):
    assert _job().is_pro_api_verdict(_answer(status, content_type, body)) is expected


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
