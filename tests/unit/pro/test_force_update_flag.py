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
