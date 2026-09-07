"""Row 24 (dev ``abb60b1ea``) — the portable half that survived the Celery split.

``build_cmd_env`` forwarded ``CUSTOM_LOG_LEVEL`` unconditionally and never forwarded
   ``SCHEDULER_LOG_TO_FILE``. An EMPTY ``CUSTOM_LOG_LEVEL`` is not "unset" to the child: it is an
   override that hides ``LOG_LEVEL`` and drops the config saver back to INFO, so a scheduler raised
   to DEBUG lost exactly the lines it was raised for. ``SCHEDULER_LOG_TO_FILE`` is what
   ``logger.py:50`` derives ``LOG_FILE_PATH`` from, so a child with no explicit path fell back to
   stderr -- journald on Linux, while the scheduler's own log file keeps the one-line summary.

The other half of dev's commit that looked portable -- ``custom_configs_save_failed``, which reads
``save_custom_configs``'s overloaded return string to tell a REFUSED write from an advisory one --
was applied and then withdrawn: on 1.7 that string never reaches the scheduler. ``PUT /configs/bulk``
turns any non-empty message into HTTP 500 (``src/api/app/routers/configs.py:172-175``),
``base_api_client`` maps 500 to ``ApiUnavailableError("API returned 500")`` and
``SchedulerApiClient.save_custom_configs`` returns that, so the predicate would classify a LANDED
write with an advisory ``Service <x> not found`` line as a refusal and wedge the rescan. See
``report-DEV-2b4.md`` §Row 24.

``src/scheduler/main.py`` mkdir()s at import, so it is loaded through the same sandboxed importer
``test_healthcheck_loading.py`` uses.
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_MAIN_PATH = Path(__file__).resolve().parents[3] / "src" / "scheduler" / "main.py"
_REAL_MKDIR = Path.mkdir


def _sandboxed_mkdir(sandbox):
    def _mkdir(self, *args, **kwargs):
        target = self if self.is_relative_to(sandbox) else (sandbox.joinpath(*self.parts[1:]) if self.is_absolute() else self)
        if target.is_absolute() and not target.is_relative_to(sandbox):
            raise PermissionError(13, "Permission denied", str(target))
        return _REAL_MKDIR(target, *args, **kwargs)

    return _mkdir


@pytest.fixture(scope="module")
def scheduler_main(tmp_path_factory):
    sandbox = tmp_path_factory.mktemp("row24-import-sandbox")
    spec = importlib.util.spec_from_file_location("bw_scheduler_main_row24", _MAIN_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["bw_scheduler_main_row24"] = module
    with patch.object(Path, "mkdir", _sandboxed_mkdir(sandbox)):
        spec.loader.exec_module(module)
    yield module
    sys.modules.pop("bw_scheduler_main_row24", None)


class TestBuildCmdEnv:
    def test_an_empty_custom_log_level_is_not_forwarded(self, scheduler_main, monkeypatch):
        """Forwarding `""` is not neutral: the child reads it as an override back to INFO."""
        monkeypatch.setenv("LOG_LEVEL", "debug")
        monkeypatch.delenv("CUSTOM_LOG_LEVEL", raising=False)

        assert "CUSTOM_LOG_LEVEL" not in scheduler_main.build_cmd_env()

    def test_a_set_custom_log_level_is_still_forwarded(self, scheduler_main, monkeypatch):
        monkeypatch.setenv("CUSTOM_LOG_LEVEL", "warning")

        assert scheduler_main.build_cmd_env()["CUSTOM_LOG_LEVEL"] == "warning"

    def test_scheduler_log_to_file_travels_with_the_rest(self, scheduler_main, monkeypatch):
        """`logger.py:50` derives LOG_FILE_PATH from it; without it the child logs to stderr."""
        monkeypatch.setenv("SCHEDULER_LOG_TO_FILE", "yes")

        assert scheduler_main.build_cmd_env()["SCHEDULER_LOG_TO_FILE"] == "yes"

    def test_an_unset_scheduler_log_to_file_stays_unset(self, scheduler_main, monkeypatch):
        monkeypatch.delenv("SCHEDULER_LOG_TO_FILE", raising=False)

        assert "SCHEDULER_LOG_TO_FILE" not in scheduler_main.build_cmd_env()
