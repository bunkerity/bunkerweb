"""The operator's forced Pro update must survive a failed download.

`force_pro_update` is set when someone asks for an update now. The job used to clear it the moment
it read it, before attempting anything, so a download that then failed — no network, refused
licence, API down — consumed the request and nothing retried it. The force was silently dropped.

Same class as the push-configs bug: releasing the marker for work that was not performed.
"""

import ast
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]
JOB_PATH = ROOT / "src" / "common" / "core" / "pro" / "jobs" / "download-pro-plugins.py"


def _load_definitions():
    """Definitions only — the module body downloads plugins and exits."""
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

    module = ModuleType("bw_download_pro_plugins")
    module.__dict__["__file__"] = str(JOB_PATH)
    with patch.dict(sys.modules, stubs):
        exec(compile(tree, str(JOB_PATH), "exec"), module.__dict__)  # noqa: S102
    return module


PRO = _load_definitions()


def test_a_completed_forced_update_releases_the_request():
    assert PRO.may_clear_forced_update(force_update=True, force_consumed=True) is True


@pytest.mark.parametrize("consumed", (False, True))
def test_nothing_is_released_when_no_force_was_requested(consumed):
    # Ordinary scheduled runs must never touch the flag; an operator may have set it mid-run.
    assert PRO.may_clear_forced_update(force_update=False, force_consumed=consumed) is False


def test_a_forced_update_that_never_downloaded_keeps_the_request():
    """The regression. 429, access denied and network failure all land here.

    Those paths log that they keep the current PRO plugins state — so they have to keep the
    request that asked for the change too, otherwise it is lost with nothing to re-raise it.
    """
    assert PRO.may_clear_forced_update(force_update=True, force_consumed=False) is False


def test_the_flag_is_not_cleared_before_the_download():
    """Guards the placement, which is the whole bug — the predicate alone cannot.

    A clear anywhere in the first half of the module would re-introduce it, so pin that every
    `force_pro_update` write sits after the download call it depends on.
    """
    source = JOB_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(JOB_PATH))

    download_lines = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and any(isinstance(a, ast.Constant) and "pro/download" in str(a.value) for a in getattr(node, "args", []))
        or (isinstance(node, ast.JoinedStr) and "pro/download" in ast.dump(node))
    ]
    assert download_lines, "the download call moved; update this test"
    first_download = min(download_lines)

    writes = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Constant) and node.value == "force_pro_update"]
    reads_and_writes = [ln for ln in writes if ln > 0]
    assert reads_and_writes, "force_pro_update disappeared from the job"

    cleared_early = [ln for ln in reads_and_writes if ln < first_download and "set_metadata" in source.splitlines()[ln - 1]]
    assert not cleared_early, f"force_pro_update is cleared before the download at line(s) {cleared_early}"


def test_both_success_paths_mark_the_request_consumed_after_their_write_not_before():
    """The two exits differed, and only one of them was safe.

    "All Pro plugins are up to date" used to set `force_consumed` before writing `last_pro_check`,
    so a run whose own bookkeeping failed still cleared the operator's explicit update request. The
    install path always ordered it the other way. The asymmetry is not neutral: leaving the flag set
    costs one repeated forced check on a daily job, while clearing it wrongly drops the request with
    nothing to retry it.
    """
    source = JOB_PATH.read_text(encoding="utf-8")

    # The "up to date" branch, bounded by its own exit so the install path's ordering cannot stand
    # in for it.
    branch_start = source.index('LOGGER.info("All Pro plugins are up to date")')
    branch_end = source.index("sys_exit(0)", branch_start)
    branch = source[branch_start:branch_end]

    assert 'db.set_metadata({"last_pro_check": current_date})' in branch
    assert "force_consumed = True" in branch, "the branch stopped marking the forced update consumed at all"
    consumed_at = branch.index("force_consumed = True")
    write_at = branch.index("db.set_metadata")
    assert consumed_at > write_at, "the up-to-date branch marks the request consumed before the write that can fail"


def test_a_forced_update_reinstalls_an_identical_scheduler_plugin(tmp_path, monkeypatch):
    source = tmp_path / "source"
    installed = tmp_path / "installed"
    source.mkdir()
    installed.joinpath("demo").mkdir(parents=True)
    source.joinpath("plugin.json").write_text('{"id": "demo", "version": "1.0"}', encoding="utf-8")
    source.joinpath("payload.txt").write_text("fresh", encoding="utf-8")
    installed.joinpath("demo", "payload.txt").write_text("stale", encoding="utf-8")

    db = Mock()
    db.get_plugins.return_value = [{"id": "demo", "version": "1.0", "checksum": "same", "method": "scheduler"}]
    monkeypatch.setattr(PRO, "PRO_PLUGINS_DIR", installed)
    monkeypatch.setattr(PRO, "cleaned_up_plugins", False)
    monkeypatch.setattr(PRO, "_plugin_checksum_matches_database", lambda *_args: True)

    assert PRO.install_plugin(source, db, preview=False, force=True) is True
    assert installed.joinpath("demo", "payload.txt").read_text(encoding="utf-8") == "fresh"


@pytest.mark.parametrize("forced", (False, True), ids=("plain", "forced"))
def test_a_missing_preview_archive_is_a_no_change_not_a_job_error(tmp_path, monkeypatch, forced):
    logger = Mock()
    db = Mock()
    db.get_metadata.return_value = {
        "force_pro_update": forced,
        "last_pro_check": None,
        "is_pro": False,
        "pro_license": "",
        "pro_overlapped": False,
        "pro_services": 0,
        "pro_status": "invalid",
        "non_draft_services": 0,
    }
    db.set_metadata.return_value = ""
    response = Mock(status_code=404, headers={})

    real_path = Path

    def redirected_path(*parts):
        path = real_path(*parts)
        if path == real_path("/var/tmp/bunkerweb/pro/plugins"):
            return tmp_path / "tmp"
        if path == real_path("/etc/bunkerweb/pro/plugins"):
            return tmp_path / "plugins"
        return path

    stubs = {name: ModuleType(name) for name in ("requests", "requests.exceptions", "Database", "logger", "common_utils", "pathlib")}
    stubs["requests"].get = Mock(return_value=response)
    stubs["requests"].exceptions = stubs["requests.exceptions"]
    stubs["requests.exceptions"].ConnectionError = ConnectionError
    stubs["Database"].Database = Mock(return_value=db)
    stubs["logger"].getLogger = Mock(return_value=logger)
    stubs["pathlib"].Path = redirected_path
    stubs["common_utils"].bytes_hash = Mock()
    stubs["common_utils"].get_os_info = Mock(return_value="linux")
    stubs["common_utils"].get_integration = Mock(return_value="docker")
    stubs["common_utils"].get_version = Mock(return_value="1.7-dev")
    stubs["common_utils"].create_plugin_tar_gz = Mock()
    stubs["common_utils"].safe_zip_extractall = Mock()
    monkeypatch.delenv("PRO_LICENSE_KEY", raising=False)

    namespace = {"__file__": str(JOB_PATH)}
    with patch.dict(sys.modules, stubs), pytest.raises(SystemExit) as stopped:
        exec(compile(JOB_PATH.read_text(encoding="utf-8"), str(JOB_PATH), "exec"), namespace)  # noqa: S102

    assert stopped.value.code == 0
    logger.error.assert_not_called()
    if forced:
        # The 404 is a definitive "nothing to install": the operator's forced-update request
        # must be released, or the flag stays set forever on preview-less versions.
        db.set_metadata.assert_any_call({"force_pro_update": False})
    else:
        for call in db.set_metadata.call_args_list:
            assert call != (({"force_pro_update": False},),), "an unforced run must not touch the flag"
    assert any("Couldn't find Pro plugins for BunkerWeb version 1.7-dev" in call.args[0] for call in logger.warning.call_args_list)
