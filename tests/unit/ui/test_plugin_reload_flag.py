"""The ``ui_plugins`` reload flag must be cleared BEFORE the plugins are read (dev 6a701d6ca).

``reload_plugins`` used to clear the flag after the extraction loop, and ``main.py`` cleared it a second
time after ``safe_reload_plugins``. A plugin update committed while the loop ran raised the flag, and the
trailing clear erased it: the page kept the stale copy until the next change. The flag is now cleared first,
raised again when the clear or the extraction fails, and the caller skips the worker restart on an error.

dev's "incomplete chunks" guard is not ported: 1.7 stores each plugin archive whole, so a row never comes
back with a checksum and an empty ``data``.
"""

import importlib.util
import sys
from io import BytesIO
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, Mock, patch

import pytest

from common_utils import bytes_hash  # type: ignore

ROOT = Path(__file__).resolve().parents[3]
_UI_APP = ROOT / "src" / "ui" / "app"
_MAIN = ROOT / "src" / "ui" / "main.py"


def _load(module_name: str, path: Path, stubs: dict) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {**stubs, module_name: module}):
        spec.loader.exec_module(module)
    return module


class _Api:
    """The slice of ``ApiClient`` ``reload_plugins`` talks to, with the flag the API keeps."""

    def __init__(self, plugins):
        self.plugins = plugins
        self.flag = True
        self.during_get = None  # called while get_plugins runs
        self.get_error = None
        self.clear_error = None
        self.raise_error = None

    def get_plugins(self, **kwargs):
        if self.get_error:
            raise self.get_error
        if self.during_get:
            self.during_get()
        return self.plugins

    def checked_changes(self, changes, plugins_changes=None, value=False):
        assert changes == ["ui_plugins"]
        error = self.raise_error if value else self.clear_error
        if error:
            raise error
        self.flag = value
        return {"status": "ok"}


@pytest.fixture
def ui(tmp_path):
    ui_data = _load("app.models._ui_data_flag_test", _UI_APP / "models" / "ui_data.py", {})
    stubs = {name: MagicMock() for name in ("app.api_client", "app.perf", "app.models.config", "app.models.instance", "app.plugin_api")}
    stubs["app.models.ui_data"] = ui_data
    module = _load("app._dependencies_flag_test", _UI_APP / "dependencies.py", stubs)
    module.EXTERNAL_PLUGINS_PATH = tmp_path / "plugins"
    module.PRO_PLUGINS_PATH = tmp_path / "pro"
    module.EXTERNAL_PLUGINS_PATH.mkdir()
    module.API_CLIENT = _Api([])
    return module


def _row(plugin_id="demo", data=b"not a tarball", method="ui"):
    return {
        "id": plugin_id,
        "name": plugin_id.title(),
        "type": "external",
        "method": method,
        "data": data,
        "checksum": bytes_hash(BytesIO(data).getvalue(), algorithm="sha256"),
    }


def test_an_update_committed_while_the_plugins_are_read_keeps_the_flag_raised(ui):
    api = ui.API_CLIENT
    api.during_get = lambda: setattr(api, "flag", True)  # the update lands while get_plugins runs

    ui.reload_plugins()

    assert api.flag is True


def test_a_clean_reload_leaves_the_flag_cleared_and_returns_no_error(ui):
    ui.API_CLIENT.plugins = []

    assert not ui.reload_plugins()
    assert ui.API_CLIENT.flag is False


def test_the_flag_is_cleared_before_the_plugins_are_read(ui):
    api = ui.API_CLIENT
    seen = []
    api.during_get = lambda: seen.append(api.flag)

    ui.reload_plugins()

    assert seen == [False]


def test_an_extraction_failure_returns_an_error_and_leaves_the_flag_raised(ui):
    api = ui.API_CLIENT
    api.plugins = [_row()]  # an archive that cannot be extracted

    error = ui.reload_plugins()

    assert error
    assert api.flag is True


def test_a_failing_get_plugins_returns_an_error_and_leaves_the_flag_raised(ui):
    api = ui.API_CLIENT
    api.get_error = RuntimeError("API down")

    error = ui.reload_plugins()

    assert error
    assert api.flag is True


def test_a_failed_clear_returns_an_error_and_tries_to_raise_the_flag_again(ui):
    api = ui.API_CLIENT
    api.clear_error = RuntimeError("clear refused")
    api.raise_error = RuntimeError("raise refused")
    api.checked_changes = Mock(wraps=api.checked_changes)

    error = ui.reload_plugins()

    assert error
    assert api.flag is True
    assert [call.kwargs.get("value") for call in api.checked_changes.call_args_list] == [False, True]


def test_safe_reload_plugins_hands_back_the_reload_result(ui, tmp_path):
    ui.DATA = ui.UIData(tmp_path / "ui_data.json")
    ui.DATA.update({"FORCE_RELOAD_PLUGIN": False, "IS_RELOADING_PLUGINS": False})
    ui.reload_plugins = Mock(side_effect=["", "boom"])

    assert ui.safe_reload_plugins() == ""
    assert ui.safe_reload_plugins() == "boom"


def test_safe_reload_plugins_returns_none_while_another_worker_holds_the_latch(ui, tmp_path):
    ui.DATA = ui.UIData(tmp_path / "ui_data.json")
    ui.DATA.file_path.write_text('{"IS_RELOADING_PLUGINS": true}')
    ui.reload_plugins = Mock()

    assert ui.safe_reload_plugins() is None
    ui.reload_plugins.assert_not_called()


# ------------------------------------------------------------------------------ the main.py reload block


def _reload_block(result):
    """Run the real ``before_request`` hook with ``safe_reload_plugins`` returning ``result``; return the restart mock."""
    from test_before_request_env import _Data, _app, _metadata

    application = _app(_metadata(reload_ui_plugins=True), _Data(RELOADING=False), [])
    hook = application.before_request_funcs[None][0]
    namespace = hook.__globals__
    namespace["safe_reload_plugins"] = Mock(return_value=result)
    restart = namespace["schedule_restart_workers"] = Mock()
    application.test_client().get("/templates", environ_base={"REMOTE_ADDR": "127.0.0.1"}, headers={"User-Agent": "pytest"})
    return restart, namespace["safe_reload_plugins"]


def test_main_restarts_the_workers_after_a_clean_reload():
    restart, reload_plugins = _reload_block("")

    reload_plugins.assert_called_once()
    restart.assert_called_once()


def test_main_skips_the_worker_restart_on_an_error_string():
    restart, reload_plugins = _reload_block("some plugins could not be extracted")

    reload_plugins.assert_called_once()
    restart.assert_not_called()


def test_main_skips_the_worker_restart_when_another_worker_holds_the_latch():
    restart, reload_plugins = _reload_block(None)

    reload_plugins.assert_called_once()
    restart.assert_not_called()


def test_main_no_longer_clears_the_flag_after_the_reload():
    # The trailing clear in main.py is what erased an update committed during the extraction.
    source = _MAIN.read_text(encoding="utf-8")
    block = source[source.index("# Plugin reload trigger") :]
    block = block[: block.index("LATEST_VERSION_LAST_CHECK")]

    assert "checked_changes" not in block
