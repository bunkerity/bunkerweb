"""The PRO license path must bill the shared classifier's number, not a raw count.

`service_number` used to be `len(SERVER_NAME.split())` — every non-draft service,
whatever it does — while the UI recounted its own way. Both now go through
`src/common/utils/service_classification.py`, so a valid redirect-only service
stops consuming a quota slot everywhere at once.
"""

import ast
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import service_classification  # type: ignore

ROOT = Path(__file__).resolve().parents[3]
JOB_PATH = ROOT / "src" / "common" / "core" / "pro" / "jobs" / "download-pro-plugins.py"


def _load_definitions():
    """Definitions only — the module body downloads plugins and exits.

    `service_classification` is deliberately NOT stubbed: the point of the test is
    that the job asks the real shared classifier.
    """
    tree = ast.parse(JOB_PATH.read_text(encoding="utf-8"), filename=str(JOB_PATH))
    tree.body = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign))]

    names = ("requests", "requests.exceptions", "Database", "logger", "common_utils", "model")
    stubs = {name: ModuleType(name) for name in names}
    stubs["requests"].get = Mock()
    stubs["requests"].exceptions = stubs["requests.exceptions"]
    stubs["requests.exceptions"].ConnectionError = ConnectionError
    stubs["Database"].Database = Mock()
    stubs["logger"].getLogger = Mock(return_value=Mock())
    for attr in ("bytes_hash", "get_os_info", "get_integration", "get_version", "create_plugin_tar_gz", "safe_zip_extractall"):
        setattr(stubs["common_utils"], attr, Mock())
    stubs["model"].Plugins = Mock()

    module = ModuleType("bw_download_pro_plugins_quota")
    module.__dict__["__file__"] = str(JOB_PATH)
    with patch.dict(sys.modules, stubs):
        exec(compile(tree, str(JOB_PATH), "exec"), module.__dict__)  # noqa: S102
    return module


PRO = _load_definitions()

SNAPSHOT = {
    "SERVER_NAME": "app.example.com old.example.com mixed.example.com",
    "app.example.com_USE_REVERSE_PROXY": "yes",
    "old.example.com_SERVICE_MODE": "redirect_only",
    "old.example.com_REDIRECT_TO": "https://app.example.com",
    "old.example.com_SERVE_FILES": "no",
    "mixed.example.com_SERVICE_MODE": "redirect_only",
    "mixed.example.com_REDIRECT_TO": "https://app.example.com",
    "mixed.example.com_USE_REVERSE_PROXY": "yes",
}


def test_the_licence_count_is_unchanged_while_the_exemption_is_gated():
    """Lot B is a pure refactor: every non-draft service is still billed.

    `service_classification.EXEMPTION_ENABLED` is False until Lot C supplies the
    custom-config / attachment evidence this job cannot pass, so the number on the
    wire must be exactly what `len(SERVER_NAME.split())` produced before.
    """
    db = Mock()
    db.get_non_default_settings.return_value = SNAPSHOT
    assert PRO._billable_service_number(db) == len(SNAPSHOT["SERVER_NAME"].split()) == 3
    assert db.get_non_default_settings.call_args.kwargs == {"global_only": False, "methods": False, "with_drafts": False}


def test_a_valid_redirect_only_service_stops_being_billed_once_lot_c_opens_the_gate():
    db = Mock()
    db.get_non_default_settings.return_value = SNAPSHOT
    original = service_classification.EXEMPTION_ENABLED
    service_classification.EXEMPTION_ENABLED = True
    try:
        # 3 services: one standard, one exempt redirect, one declaration that does
        # not hold up (billed, fail closed).
        assert PRO._billable_service_number(db) == 2
    finally:
        service_classification.EXEMPTION_ENABLED = original


def test_drafts_are_excluded_at_the_source():
    db = Mock()
    db.get_non_default_settings.return_value = {"SERVER_NAME": "a.example.com"}
    assert PRO._billable_service_number(db) == 1
    # with_drafts=False is what keeps a draft out of the count.
    assert db.get_non_default_settings.call_args.kwargs["with_drafts"] is False


def test_a_database_failure_falls_back_to_the_historical_count():
    """The PRO check must not go down because the quota count could not be computed."""
    db = Mock()
    db.get_non_default_settings.side_effect = RuntimeError("database is gone")
    with patch.dict("os.environ", {"SERVER_NAME": "a.example.com b.example.com"}):
        assert PRO._billable_service_number(db) == 2


def test_the_fallback_is_used_when_the_snapshot_is_unusable():
    db = Mock()
    db.get_non_default_settings.return_value = None  # not a mapping
    with patch.dict("os.environ", {"SERVER_NAME": "a.example.com b.example.com c.example.com"}):
        assert PRO._billable_service_number(db) == 3


def test_the_wire_field_stays_a_plain_string_service_number():
    """The license contract is unchanged: no new field, no shape change.

    Sending the algorithm/allowlist version is an open PO decision on the license
    contract, so the request body must still carry exactly `service_number`.
    """
    source = JOB_PATH.read_text(encoding="utf-8")
    assert '"service_number": str(_billable_service_number(db)),' in source
    assert "algorithm_version" not in source.split("data = {")[1].split("}")[0]
