"""`safe_reload_plugins` must re-extract on every plugin change, not only the first since boot.

`IS_RELOADING_PLUGINS` lives in the file-backed `ui_data.json` every gunicorn worker shares. It used
to be cleared only on worker import (`main.py`), so after one reload a later `reload_ui_plugins`
flag was consumed without re-extracting: a plugin deleted after an update stayed materialised in
`/etc/bunkerweb/plugins/`.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, Mock, patch

import pytest

_UI_APP = Path(__file__).resolve().parents[3] / "src" / "ui" / "app"


def _load(module_name: str, path: Path, stubs: dict) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {**stubs, module_name: module}):
        spec.loader.exec_module(module)
    return module


@pytest.fixture
def dependencies(tmp_path):
    ui_data = _load("app.models._ui_data_latch_test", _UI_APP / "models" / "ui_data.py", {})
    stubs = {name: MagicMock() for name in ("common_utils", "app.api_client", "app.perf", "app.models.config", "app.models.instance", "app.plugin_api")}
    stubs["app.models.ui_data"] = ui_data
    module = _load("app._dependencies_latch_test", _UI_APP / "dependencies.py", stubs)
    module.DATA = ui_data.UIData(tmp_path / "ui_data.json")
    module.DATA.update({"FORCE_RELOAD_PLUGIN": False, "IS_RELOADING_PLUGINS": False})
    module.reload_plugins = Mock()
    return module


def test_second_plugin_change_reloads_again(dependencies):
    dependencies.safe_reload_plugins()
    dependencies.safe_reload_plugins()

    assert dependencies.reload_plugins.call_count == 2
    assert dependencies.DATA["IS_RELOADING_PLUGINS"] is False


def test_failed_reload_does_not_leave_the_latch_set(dependencies):
    dependencies.reload_plugins.side_effect = [RuntimeError("API down"), None]

    with pytest.raises(RuntimeError):
        dependencies.safe_reload_plugins()
    dependencies.safe_reload_plugins()

    assert dependencies.reload_plugins.call_count == 2


def test_reload_in_flight_in_another_worker_is_not_duplicated(dependencies):
    # Another worker holds the latch: it is written to the shared file, not to this worker's memory.
    dependencies.DATA.file_path.write_text('{"IS_RELOADING_PLUGINS": true}')

    dependencies.safe_reload_plugins()

    dependencies.reload_plugins.assert_not_called()
