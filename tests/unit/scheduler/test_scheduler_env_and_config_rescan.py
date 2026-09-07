"""Row 24 (dev ``abb60b1ea``) — the portable half that survived the Celery split.

``build_cmd_env`` forwarded ``CUSTOM_LOG_LEVEL`` unconditionally and never forwarded
   ``SCHEDULER_LOG_TO_FILE``. An EMPTY ``CUSTOM_LOG_LEVEL`` is not "unset" to the child: it is an
   override that hides ``LOG_LEVEL`` and drops the config saver back to INFO, so a scheduler raised
   to DEBUG lost exactly the lines it was raised for. ``SCHEDULER_LOG_TO_FILE`` is what
   ``logger.py:50`` derives ``LOG_FILE_PATH`` from, so a child with no explicit path fell back to
   stderr -- journald on Linux, while the scheduler's own log file keeps the one-line summary.

The other half of dev's commit -- ``custom_configs_save_failed``, which reads
``save_custom_configs``'s overloaded return string to tell a REFUSED write from an advisory one --
was applied and then withdrawn in wave 13: on 1.7 that string did not reach the scheduler.
``PUT /configs/bulk`` turned any non-empty message into HTTP 500, ``base_api_client`` discarded the
body of a 5xx, and ``SchedulerApiClient.save_custom_configs`` returned the bare ``API returned
500`` -- so the predicate would have classified a LANDED write carrying an advisory
``Service <x> not found`` line as a refusal and wedged the rescan. See ``report-DEV-2b4.md``
§Row 24.

Wave 14 (DEV-3) fixed the transport instead of re-adding the predicate: the classification now
happens in the route, which is the last place that still HAS the string
(``tests/unit/api/test_configs_bulk_save_classification.py``). An advisory is a 200 carrying the
message; a refusal is a 4xx carrying the reason. ``save_custom_configs`` below therefore returns
``""`` exactly when the write landed -- which is what dev's predicate computed, moved to the producer.

That disposed of the *predicate*, not of the guard it fed, which lane DEV-3b ports here. Dev's row
24 also makes ``check_configs_changes`` skip ``generate_custom_configs`` when the write was refused,
and on 1.7 ``generate_custom_configs`` unlinks every file under ``/etc/bunkerweb/configs/*/*``
(``main.py:334-342``) before rewriting from the database -- so a refused write did not merely fail to
apply the operator's edit, it DELETED the only copy of it and put the stale database one back.
``main.py`` now returns ``None`` on a refusal instead -- ``None`` and not the ``changes`` flag,
because the SIGHUP rescan caller reads a truthy return as "set ``CONFIGS_NEED_GENERATION``" and
reaches the very same unlink at the end of the pass; returning ``changes`` left the guard a no-op on
the one runtime path a manual edit travels.

The condition is the refusal MESSAGE and never ``API_CLIENT.readonly``: ``base_api_client.py``
caches ``readonly=True`` when the API is merely unreachable, so dev's own
``and not SCHEDULER.db.readonly`` would disarm the guard in exactly the case it exists for. It is
anchored at the start of the string, because a commit failure behind an advisory returns
``Service <name> not found ...\n<reason>`` with an operator-chosen ``<name>``. A genuinely read-only
database is exempt: nothing can ever be stored there, so the folder has to keep being materialized
from the database -- and only the boot-time call is affected, the rescan caller being already gated
on ``not API_CLIENT.readonly``.

``src/scheduler/main.py`` mkdir()s at import, so it is loaded through the same sandboxed importer
``test_healthcheck_loading.py`` uses.
"""

import ast
import importlib.util
import sys
import textwrap
from pathlib import Path
from shutil import rmtree
from types import SimpleNamespace
from unittest.mock import Mock, patch

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


class TestSaveCustomConfigsReportsOnlyRefusals:
    """``err`` is the scheduler's "did the write land" signal: it decides whether
    ``check_configs_changes`` regenerates ``/etc/bunkerweb/configs`` over an edit that is still
    only on disk. An advisory must not look like a refusal, and must not be lost either."""

    @staticmethod
    def _client(put):
        from api_client import SchedulerApiClient  # type: ignore  (src/scheduler on sys.path)

        client = SchedulerApiClient.__new__(SchedulerApiClient)
        client._put = put
        client._logger = Mock()
        return client

    def test_a_landed_write_with_an_advisory_reports_no_error_and_is_logged(self):
        advisory = "Service app1.example.com not found, please check your config"
        client = self._client(lambda *_args, **_kwargs: {"status": "success", "message": advisory})

        assert client.save_custom_configs([], "manual") == ""
        assert advisory in client._logger.warning.call_args[0][0]

    def test_a_clean_write_logs_nothing(self):
        client = self._client(lambda *_args, **_kwargs: {"status": "success"})

        assert client.save_custom_configs([], "manual") == ""
        client._logger.warning.assert_not_called()

    def test_a_refusal_is_still_returned_verbatim(self):
        from base_api_client import ApiClientError  # type: ignore

        def _refuse(*_args, **_kwargs):
            raise ApiClientError("The database is read-only, the changes will not be saved", status_code=400)

        client = self._client(_refuse)

        assert client.save_custom_configs([], "manual") == "The database is read-only, the changes will not be saved"


# --------------------------------------------------------------------------------------------
# The other half of row 24 -- the regeneration guard (lane DEV-3b)
# --------------------------------------------------------------------------------------------


def _check_configs_changes_source() -> str:
    """``check_configs_changes`` is nested inside ``if __name__ == "__main__":``, so importing the
    module never defines it. Lift the REAL function body out of the file rather than restating it:
    a copy living in the test would keep passing while the shipped guard rotted."""
    source = _MAIN_PATH.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef) and node.name == "check_configs_changes":
            start, end = node.lineno - 1, node.end_lineno
            return textwrap.dedent("".join(lines[start:end]))
    raise AssertionError("check_configs_changes is no longer defined in src/scheduler/main.py")


class _Api:
    """Only the two methods the rescan calls. ``save_result`` is returned, or raised when it is an
    exception -- the scheduler treats both as a refusal."""

    def __init__(self, save_result):
        self._save_result = save_result
        self.db_configs: list = []
        self.saved = None

    def get_custom_configs(self) -> list:
        return list(self.db_configs)

    def save_custom_configs(self, configs, method):
        self.saved = (configs, method)
        if isinstance(self._save_result, BaseException):
            raise self._save_result
        return self._save_result


@pytest.fixture
def rescan(scheduler_main, tmp_path):
    """Run the real ``check_configs_changes`` over a throwaway configs tree.

    ``generate_custom_configs`` is the real one too, only re-pointed at ``tmp_path``: what it does
    to a file that exists only on disk IS the behaviour under test, so stubbing it out would leave
    the test asserting nothing about the data loss it guards."""
    configs_path = tmp_path.joinpath("configs")
    edit = configs_path.joinpath("server-http", "operator.conf")

    def _run(save_result, *, generate: bool = True):
        # Re-seeded per call: a run that regenerates DELETES the edit, and the next call would then
        # scan an empty tree, compute `changes = False` and assert nothing.
        rmtree(configs_path, ignore_errors=True)
        edit.parent.mkdir(parents=True)
        edit.write_text("# edited on disk only\n", encoding="utf-8")
        api = _Api(save_result)
        generated = []

        def _generate(configs=None, *, original_path=configs_path):
            generated.append(configs)
            return scheduler_main.generate_custom_configs(configs, original_path=original_path)

        namespace = dict(vars(scheduler_main))
        namespace.update({"API_CLIENT": api, "LOGGER": Mock(), "CUSTOM_CONFIGS_PATH": configs_path, "generate_custom_configs": _generate})
        exec(compile(_check_configs_changes_source(), str(_MAIN_PATH), "exec"), namespace)  # noqa: S102
        changes = namespace["check_configs_changes"](generate=generate)
        return SimpleNamespace(changes=changes, api=api, generated=generated, edit=edit, logger=namespace["LOGGER"])

    return _run


class TestARefusedWriteDoesNotRegenerateOverTheEdit:
    """``generate_custom_configs`` unlinks every file under ``configs/*/*`` before rewriting from the
    database. Regenerating after a REFUSED write therefore deletes the operator's edit and restores
    the stale database copy -- unrecoverably, since the refusal means the edit was never stored."""

    REFUSAL = "Refusing to save custom configs: the manual payload is empty while 3 manual custom config(s) exist. Nothing was changed."

    def test_a_refusal_keeps_the_on_disk_edit(self, rescan):
        run = rescan(self.REFUSAL)

        assert run.api.saved is not None, "the write was never attempted, so this proves nothing"
        assert run.generated == [], "a refused write must not regenerate from the database"
        assert run.edit.read_text(encoding="utf-8") == "# edited on disk only\n"

    def test_a_refusal_does_not_ask_its_caller_to_regenerate_either(self, rescan):
        """Skipping the in-function regeneration is only half of it. The SIGHUP rescan calls this
        with ``generate=False`` and reads a TRUTHY return as "set ``CONFIGS_NEED_GENERATION``",
        which reaches the same unlink through ``generate_custom_configs`` at the end of the pass --
        so returning ``changes`` here left the guard a no-op on the one runtime path a manual edit
        travels. Dev returns ``None``; so do we."""
        assert rescan(self.REFUSAL).changes is None
        assert not rescan(self.REFUSAL, generate=False).changes, "the caller reads this as 'regenerate and reload'"

    def test_an_exception_whose_str_is_empty_is_still_a_refusal(self, rescan):
        """Some driver errors stringify to ``""``. Reading that as "nothing was refused" is exactly
        the way the guard would be disarmed on the failure it exists for."""
        run = rescan(RuntimeError(""))

        assert run.generated == []
        assert run.edit.exists()

    def test_a_landed_write_regenerates_as_before(self, rescan):
        """The empty return is the API client's "it landed" signal (an advisory is a 200 that is
        logged, not returned). Nothing is held back, and the delete is real -- proving it here is
        what makes the refusal case above meaningful.

        The file disappearing is this fixture's empty database talking, not production: after a
        write that landed the row exists and the regeneration writes the same content back. What is
        asserted here is that the unlink RAN, which is the whole hazard the refusal case guards."""
        run = rescan("")

        assert run.generated == [[]]
        assert not run.edit.exists()

    def test_a_read_only_database_regenerates_as_before(self, rescan):
        """Nothing can ever be stored on a read-only database, so the folder has to keep being
        materialized from it. Keyed on the message and never on ``API_CLIENT.readonly``, which reads
        True for an API that is merely unreachable -- dev's own condition, and it would disarm the
        guard in exactly the case it exists for."""
        run = rescan("The database is read-only, the changes will not be saved")

        assert run.generated == [[]]
        assert not run.edit.exists()

    def test_a_service_named_read_only_does_not_buy_the_exemption(self, rescan):
        """The exemption is anchored, not a substring test. A commit failure behind an advisory
        returns ``Service <name> not found ...\n<reason>`` and ``<name>`` is operator-chosen, so an
        unanchored ``"read-only" in refused`` is disarmed by naming a service ``read-only.x``."""
        run = rescan("Service read-only.example.com not found, please check your config\nOperationalError")

        assert run.generated == []
        assert run.edit.exists()

    def test_a_landed_write_still_tells_the_caller_there_was_a_change(self, rescan):
        """The guard must not cost the rescan its actual signal: a write that LANDED still returns
        the truthy flag both callers act on, with or without the in-function regeneration."""
        assert rescan("").changes is True
        assert rescan("", generate=False).changes is True
        assert rescan("", generate=False).generated == [], "generate=False never regenerates"

    def test_the_refusal_is_still_logged(self, rescan):
        run = rescan(self.REFUSAL)

        assert self.REFUSAL in run.logger.error.call_args[0][0]
