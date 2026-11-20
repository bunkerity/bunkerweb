"""Invalid import specs must return the plugin import error and restore search paths.

Absent specs and loaders must produce a useful diagnostic without executing actions.
"""

import sys
from importlib.machinery import ModuleSpec
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize("missing", ["spec", "loader"])
def test_invalid_action_spec_returns_import_error(h, tmp_path, monkeypatch, missing):
    module = h.routes.plugins
    root = tmp_path / "plugins"
    ui = root / "demo" / "ui"
    ui.mkdir(parents=True)
    action = ui / "actions.py"
    action.write_text("raise AssertionError('invalid spec must never execute actions')\n")
    for attr in ("PRO_PLUGINS_PATH", "EXTERNAL_PLUGINS_PATH", "CORE_PLUGINS_PATH"):
        monkeypatch.setattr(module, attr, root)
    monkeypatch.setattr(module, "sys_path", list(sys.path))
    monkeypatch.delitem(sys.modules, "bw_ui_actions_demo", raising=False)
    spec = None if missing == "spec" else ModuleSpec("bw_ui_actions_demo", loader=None)
    monkeypatch.setattr(module, "spec_from_file_location", lambda *args: spec)
    log = Mock()
    monkeypatch.setattr(module, "LOGGER", log)
    before = list(module.sys_path)

    with h.app.test_request_context("/", json={}):
        result = module.run_action("demo", "pre_render")

    assert result == {"status": "ko", "code": 500, "message": "An error occurred while importing the plugin, see logs for more details"}
    assert module.sys_path == before
    assert "bw_ui_actions_demo" not in sys.modules
    assert f"Could not load actions from {action}" in str(log.error.call_args_list)
