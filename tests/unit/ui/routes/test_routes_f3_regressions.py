"""Regression checks for plugin isolation, form redirects, and folder-backed cache downloads."""

import json
import sys
from urllib.parse import parse_qs, urlsplit

import pytest


@pytest.mark.parametrize(
    "path, field, page",
    [
        ("/jobs/run", "jobs", "/jobs"),
        ("/pro/key", "PRO_LICENSE_KEY", "/pro"),
        ("/plugins/delete", "plugins", "/plugins"),
        ("/plugins/refresh", "csrf_token", "/plugins"),
        ("/instances/reload", "instances", "/instances"),
    ],
)
def test_missing_form_fields_return_the_validation_redirect(h, path, field, page):
    client = h.client()

    response = client.post(path, data={"unrelated": "value"})

    assert response.status_code == 302
    assert parse_qs(urlsplit(response.headers["Location"]).query)["next"] == [page]
    assert h.flashes(client) == [(f"Missing {field} in form", "error")]
    h.db.checked_changes.assert_not_called()
    h.db.delete_plugin.assert_not_called()
    h.config.check_variables.assert_not_called()
    h.instances.get_instances.assert_not_called()
    assert h.data["RELOADING"] is False


def test_job_messages_only_include_plugins_scheduled_to_run(h):
    h.db.checked_changes.return_value = ""
    client = h.client()

    response = client.post("/jobs/run", data={"jobs": json.dumps([{"plugin": "p", "name": "n"}, {"name": "orphan"}])})

    h.db.checked_changes.assert_called_once_with(["config"], ["p"], True)
    assert response.status_code == 302
    assert parse_qs(urlsplit(response.headers["Location"]).query)["message"] == ["Run selected job's plugins: p/n"]
    assert h.flashes(client) == [("Job's plugins will be run in the background by the scheduler.", "message")]


@pytest.fixture
def action_loader(h, tmp_path, monkeypatch):
    module = h.routes.plugins
    root = tmp_path / "plugins"
    root.mkdir()
    for attr in ("PRO_PLUGINS_PATH", "EXTERNAL_PLUGINS_PATH", "CORE_PLUGINS_PATH"):
        monkeypatch.setattr(module, attr, root)
    monkeypatch.setattr(module, "TMP_DIR", tmp_path / "tmp")
    monkeypatch.delitem(sys.modules, "actions", raising=False)
    # Restore interpreter paths even when the broken loader pops one too many.
    monkeypatch.setattr(module, "sys_path", list(sys.path))

    def install(name, source):
        ui = root / name / "ui"
        ui.mkdir(parents=True)
        (ui / "actions.py").write_text(source)

    return module, install


@pytest.mark.parametrize("method", ["pre_render", "shared_action"])
def test_actions_cannot_inherit_another_plugins_method_or_change_sys_path(h, action_loader, method):
    module, install = action_loader
    install("first", f"def {method}(**kwargs):\n    return {{'owner': 'first'}}\n")
    install("second", "def unrelated(**kwargs):\n    return {}\n")
    before = list(module.sys_path)

    with h.app.test_request_context("/", json={}):
        assert module.run_action("first", method)["data"] == {"owner": "first"}
        result = module.run_action("second", method)

    assert result["message"] == (
        "The plugin does not have a pre_render method" if method == "pre_render" else "The plugin does not have a method, see logs for more details"
    )
    assert module.sys_path == before


@pytest.mark.parametrize("service", ["global", "example.com"])
def test_folder_cache_download_uses_the_stored_name(h, service):
    stored_name = "folder:/var/cache/bunkerweb/letsencrypt/etc.tgz"
    payload = b"folder archive"

    def lookup(job_name, file_name, **kwargs):
        return payload if file_name == stored_name else None

    h.db.get_job_cache_file.side_effect = lookup

    response = h.client().get(f"/cache/{service}/letsencrypt/certbot/folder:_var_cache_bunkerweb_letsencrypt_etc.tgz?download=true")

    assert response.status_code == 200
    assert response.get_data() == payload
    assert "attachment" in response.headers["Content-Disposition"]
    h.db.get_job_cache_file.assert_called_once_with("certbot", stored_name, service_id=None if service == "global" else service, plugin_id="letsencrypt")


def test_actions_support_dataclasses_with_postponed_annotations(h, action_loader, monkeypatch):
    module, install = action_loader
    monkeypatch.delitem(sys.modules, "bw_ui_actions_dataclass_plugin", raising=False)
    install(
        "dataclass_plugin",
        "from __future__ import annotations\n"
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class Result:\n"
        "    owner: str\n"
        "def pre_render(**kwargs):\n"
        "    return {'owner': Result('dataclass_plugin').owner}\n",
    )
    try:
        with h.app.test_request_context("/", json={}):
            result = module.run_action("dataclass_plugin", "pre_render")
        assert result == {"status": "ok", "code": 200, "data": {"owner": "dataclass_plugin"}}
    finally:
        sys.modules.pop("bw_ui_actions_dataclass_plugin", None)


def test_actions_with_shared_top_level_names_keep_separate_modules(h, action_loader, monkeypatch):
    module, install = action_loader
    for plugin in ("first", "second"):
        monkeypatch.delitem(sys.modules, f"bw_ui_actions_{plugin}", raising=False)
        install(plugin, f"OWNER = '{plugin}'\ndef pre_render(**kwargs):\n    return {{'owner': OWNER}}\n")
    try:
        with h.app.test_request_context("/", json={}):
            assert module.run_action("first", "pre_render")["data"] == {"owner": "first"}
            assert module.run_action("second", "pre_render")["data"] == {"owner": "second"}
        first = sys.modules["bw_ui_actions_first"]
        second = sys.modules["bw_ui_actions_second"]
        assert first is not second
        assert first.pre_render() == {"owner": "first"}
        assert second.pre_render() == {"owner": "second"}
    finally:
        sys.modules.pop("bw_ui_actions_first", None)
        sys.modules.pop("bw_ui_actions_second", None)


def test_actions_reload_current_file_on_each_call(h, action_loader, monkeypatch):
    module, install = action_loader
    monkeypatch.delitem(sys.modules, "bw_ui_actions_reload_plugin", raising=False)
    install("reload_plugin", "def pre_render(**kwargs):\n    return {'version': 'old'}\n")
    try:
        with h.app.test_request_context("/", json={}):
            assert module.run_action("reload_plugin", "pre_render")["data"] == {"version": "old"}
            action_file = module.get_plugin_path("reload_plugin") / "ui" / "actions.py"
            action_file.write_text("def pre_render(**kwargs):\n    return {'version': 'current file'}\n")
            assert module.run_action("reload_plugin", "pre_render")["data"] == {"version": "current file"}
    finally:
        sys.modules.pop("bw_ui_actions_reload_plugin", None)


def test_actions_remove_module_after_import_failure(h, action_loader, monkeypatch):
    module, install = action_loader
    errors = []
    monkeypatch.setattr(module.LOGGER, "error", errors.append)
    name = "bw_ui_actions_broken_plugin"
    monkeypatch.delitem(sys.modules, name, raising=False)
    install("broken_plugin", "import sys\nassert __name__ in sys.modules\nraise RuntimeError('broken import')\n")
    try:
        with h.app.test_request_context("/", json={}):
            result = module.run_action("broken_plugin", "pre_render")
        assert result["code"] == 500
        assert name not in sys.modules
        assert errors == ["An error occurred while importing the plugin: broken import"]
    finally:
        sys.modules.pop(name, None)
