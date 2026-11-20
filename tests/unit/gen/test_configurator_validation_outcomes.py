"""Configuration validation contracts, including operator-visible rejection reasons."""

from copy import deepcopy
import json
import logging
from pathlib import Path

import pytest

from Configurator import Configurator


def setting(context="global", **changes):
    return dict(context=context, default="off", help="Help", id="mode", label="Mode", regex="^(on|off)$", type="text") | changes


@pytest.fixture
def configure(tmp_path, caplog, monkeypatch):
    monkeypatch.delenv("IGNORE_REGEX_CHECK", raising=False)
    caplog.set_level(logging.DEBUG, logger="validation-outcomes")
    settings = {
        "SERVER_NAME": json.loads((Path(__file__).resolve().parents[3] / "src/common/settings.json").read_text())["SERVER_NAME"],
        "MULTISITE": setting(default="no", regex="^(yes|no)$"),
        "GLOBAL_MODE": setting(),
        "SITE_MODE": setting("multisite"),
        "ITEM": setting("multisite", multiple="items"),
        "USE_TEMPLATE": setting("multisite", default="", regex=".*"),
    }
    plugin = dict(id="fixture", name="Fixture", description="Description", version="1.0.0", stream="no", settings={"PLUGIN_MODE": setting("multisite")})
    counter = 0

    def build(variables=None, *, manifest=None, plugin_type="core", schema=None):
        nonlocal counter
        root = tmp_path / str(counter)
        counter += 1
        root.mkdir()
        path = root / "settings.json"
        path.write_text(json.dumps(settings if schema is None else schema))
        roots = {kind: root / kind for kind in ("core", "external", "pro")}
        manifests = [("core", plugin)] if plugin_type != "core" else []
        manifests.append((plugin_type, plugin if manifest is None else manifest))
        for kind, data in manifests:
            directory = roots[kind] / "fixture"
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "plugin.json").write_text(json.dumps(data))
        return Configurator(str(path), str(roots["core"]), str(roots["external"]), str(roots["pro"]), variables or {}, logging.getLogger("validation-outcomes"))

    build.plugin = plugin
    return build


@pytest.mark.parametrize(
    "variables,key,expected,error",
    [
        ({"GLOBAL_MODE": "on"}, "GLOBAL_MODE", "on", None),
        ({"GLOBAL_MODE": "invalid"}, "GLOBAL_MODE", "off", "doesn't match regex"),
        ({"SITE_MODE": "on"}, "SITE_MODE", "on", None),
        ({"SITE_MODE": "invalid"}, "SITE_MODE", "off", "doesn't match regex"),
        ({"ITEM_12": "on"}, "ITEM_12", "on", None),
        ({"ITEM_bad": "on"}, "ITEM_bad", None, "doesn't exist"),
        ({"GLOBAL_MODE_1": "on"}, "GLOBAL_MODE_1", None, "doesn't exist"),
        ({"PLUGIN_MODE": "on"}, "PLUGIN_MODE", "on", None),
        ({"PLUGIN_MODE": "invalid"}, "PLUGIN_MODE", "off", "doesn't match regex"),
        ({"UNKNOWN_TOKEN": "sensitive"}, "UNKNOWN_TOKEN", None, "doesn't exist"),
        ({"SERVER_NAME": ""}, "SERVER_NAME", "", None),
        ({"MULTISITE": "yes", "SERVER_NAME": ""}, "SERVER_NAME", "", None),
        ({"MULTISITE": "yes", "SERVER_NAME": "site.example", "site.example_SITE_MODE": "on"}, "site.example_SITE_MODE", "on", None),
        ({"MULTISITE": "yes", "SERVER_NAME": "site.example", "other.example_SITE_MODE": "on"}, "other.example_SITE_MODE", None, "doesn't exist"),
        ({"MULTISITE": "yes", "SERVER_NAME": "site.example", "site.example_GLOBAL_MODE": "on"}, "site.example_GLOBAL_MODE", None, "isn't multisite"),
        ({"MULTISITE": "yes", "SERVER_NAME": "site.example", "site.example_SERVER_NAME": " "}, "site.example_SERVER_NAME", "site.example", "can't be empty"),
        ({"MULTISITE": "yes", "SERVER_NAME": "site.example", "site.example_ITEM_2": "on"}, "site.example_ITEM_2", "on", None),
        ({"MULTISITE": "yes", "SERVER_NAME": "site.example", "site.example_ITEM_2": "invalid"}, "site.example_ITEM_2", None, "doesn't match regex"),
        ({"MULTISITE": "yes", "SERVER_NAME": "site.example", "site.example_SITE_MODE": "invalid"}, "site.example_SITE_MODE", "off", "doesn't match regex"),
    ],
)
def test_settings_acceptance_and_rejection_logs(configure, caplog, variables, key, expected, error):
    configurator = configure(variables)
    config = configurator.get_config()
    assert config.get(key) == expected
    messages = [record.message for record in caplog.records if f"Ignoring variable {key} :" in record.message]
    if error:
        assert len(messages) == 1 and error in messages[0]
        assert key not in configurator.explicit_keys
        if key == "UNKNOWN_TOKEN":
            assert "sensitive" not in messages[0] and "<redacted, length=9>" in messages[0]
    else:
        assert messages == []
        assert key in configurator.explicit_keys


@pytest.mark.parametrize("plugin_type", ["external", "pro"])
@pytest.mark.parametrize("value,expected", [("on", "on"), ("invalid", "off")])
def test_packaged_plugin_settings_obey_same_regex(configure, caplog, plugin_type, value, expected):
    configurator = configure({"PLUGIN_MODE": value}, plugin_type=plugin_type)
    assert configurator.get_config()["PLUGIN_MODE"] == expected
    plugin = configurator.get_plugins(plugin_type)[0]
    assert plugin["data"] and len(plugin["checksum"]) == 64
    assert plugin["method"] == "manual" and plugin["type"] == plugin_type
    assert ("Ignoring variable PLUGIN_MODE" in caplog.text) is (value == "invalid")


@pytest.mark.parametrize(
    "path,value,error",
    [
        (("id",), "bad/id", "Invalid id"),
        (("name",), "x" * 129, "Invalid name"),
        (("description",), "x" * 257, "Invalid description"),
        (("version",), "latest", "Invalid version"),
        (("stream",), "maybe", "Invalid stream"),
        (("settings", "PLUGIN_MODE", "context"), "service", "Invalid context"),
        (("settings", "PLUGIN_MODE", "default"), "x" * 4097, "Invalid default"),
        (("settings", "PLUGIN_MODE", "help"), "x" * 513, "Invalid help"),
        (("settings", "PLUGIN_MODE", "label"), "x" * 257, "Invalid label"),
        (("settings", "PLUGIN_MODE", "regex"), "x" * 1025, "Invalid regex"),
        (("settings", "PLUGIN_MODE", "type"), "invalid", "Invalid type"),
        (("settings", "PLUGIN_MODE", "multiple"), "bad/value", "Invalid multiple"),
        (("settings", "bad-name"), setting(), "Invalid setting name"),
        (("settings", "PLUGIN_MODE", "select"), ["x" * 257], "Invalid select value"),
    ],
)
def test_invalid_manifest_never_contributes_settings(configure, caplog, path, value, error):
    plugin = deepcopy(configure.plugin)
    target = plugin
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    configurator = configure(manifest=plugin)
    assert configurator.get_plugins("core") == []
    assert "Ignoring core plugin" in caplog.text and error in caplog.text


@pytest.mark.parametrize("missing", ["id", "settings", "stream"])
def test_missing_manifest_fields_report_plugin_rejection(configure, caplog, missing):
    plugin = deepcopy(configure.plugin)
    plugin.pop(missing)
    assert configure(manifest=plugin).get_plugins("core") == []
    assert "Missing mandatory keys" in caplog.text


@pytest.mark.parametrize("missing", ["context", "regex", "id"])
def test_missing_setting_fields_report_rejection(configure, caplog, missing):
    plugin = deepcopy(configure.plugin)
    plugin["settings"]["PLUGIN_MODE"].pop(missing)
    assert configure(manifest=plugin).get_plugins("core") == []
    assert "missing keys for setting PLUGIN_MODE" in caplog.text


@pytest.mark.parametrize(
    "changes,error",
    [
        ({"name": "bad/name"}, "Invalid name for job"),
        ({"file": "bad file.py"}, "Invalid file for job"),
        ({"every": "year"}, "Invalid every"),
        ({"reload": "yes"}, "Invalid reload"),
        ({"async": 1}, "Invalid async"),
        ({"missing": True}, "missing keys for job"),
        ({}, None),
    ],
)
def test_job_manifest_errors_are_reported(configure, caplog, changes, error):
    plugin = deepcopy(configure.plugin)
    job = dict(name="download", file="jobs/download.py", every="hour", reload=True)
    if changes.get("missing"):
        job.pop("file")
    else:
        job.update(changes)
    plugin["jobs"] = [job]
    loaded = configure(manifest=plugin).get_plugins("core")
    assert bool(loaded) is (error is None)
    assert error in caplog.text if error else "Ignoring core plugin" not in caplog.text


@pytest.mark.parametrize(
    "changes,error,normalized",
    [
        ({"type": "multivalue", "separator": ""}, "Empty separator", None),
        ({"type": "multiselect", "separator": "x" * 11}, "Invalid separator", None),
        ({"type": "file", "accept": 12}, "Invalid accept", None),
        ({"type": "file", "accept": "x" * 513}, "Invalid accept", None),
        ({"type": "multivalue"}, None, {"separator": " "}),
        ({"type": "file"}, None, {"accept": ""}),
        ({"type": "text", "separator": ",", "accept": ".pem"}, None, {}),
    ],
)
def test_setting_metadata_normalization_and_limits(configure, caplog, changes, error, normalized):
    plugin = deepcopy(configure.plugin)
    plugin["settings"]["PLUGIN_MODE"].update(changes)
    loaded = configure(manifest=plugin).get_plugins("core")
    if error:
        assert loaded == [] and error in caplog.text
    else:
        actual = loaded[0]["settings"]["PLUGIN_MODE"]
        assert {key: actual[key] for key in ("separator", "accept") if key in actual} == normalized
        assert "Ignoring core plugin" not in caplog.text


@pytest.mark.parametrize("name", ["bad/name", "site.example bad/name"])
def test_invalid_server_name_is_fatal(configure, caplog, name):
    configurator = configure({"MULTISITE": "yes", "SERVER_NAME": name})
    with pytest.raises(SystemExit) as exc:
        configurator.get_config()
    assert exc.value.code == 1
    assert "Invalid SERVER_NAME" in caplog.text


def test_alias_rejection_keeps_service_and_reports_reason(configure, caplog):
    configurator = configure({"MULTISITE": "yes", "SERVER_NAME": "site.example", "site.example_SERVER_NAME": "bad/name"})
    config = configurator.get_config()
    assert config["site.example_SERVER_NAME"] == "site.example"
    assert "Ignoring site.example_SERVER_NAME because regex is not valid" in caplog.text
    assert "Ignoring variable site.example_SERVER_NAME" in caplog.text


def test_valid_aliases_inherit_only_multisite_defaults(configure, caplog):
    config = configure(
        {"MULTISITE": "yes", "SERVER_NAME": "site.example", "site.example_SERVER_NAME": "site.example alias.example", "SITE_MODE": "on"}
    ).get_config()
    assert config["site.example_SERVER_NAME"] == "site.example alias.example"
    assert config["site.example_SITE_MODE"] == "on"
    assert "site.example_GLOBAL_MODE" not in config
    assert "Ignoring" not in caplog.text


@pytest.mark.parametrize("multisite", ["yes", "no"])
def test_malformed_schema_regex_warns_without_dropping_value(configure, caplog, multisite):
    plugin = deepcopy(configure.plugin)
    plugin["settings"]["PLUGIN_MODE"]["regex"] = "["
    config = configure({"MULTISITE": multisite, "PLUGIN_MODE": "on"}, manifest=plugin).get_config()
    assert config["PLUGIN_MODE"] == "on"
    assert "Invalid regex for PLUGIN_MODE : [, ignoring regex check" in caplog.text


@pytest.mark.parametrize(
    "first_run,urls,warns", [(True, "https://plugins.invalid/plugin.tgz", False), (False, "https://plugins.invalid/plugin.tgz", True), (True, "", True)]
)
def test_first_run_defers_unknown_plugin_variables_only_until_download(configure, caplog, first_run, urls, warns):
    config = configure({"FUTURE_SETTING": "on", "EXTERNAL_PLUGIN_URLS": urls}).get_config(first_run=first_run)
    assert "FUTURE_SETTING" not in config
    assert ("Ignoring variable FUTURE_SETTING" in caplog.text) is warns


@pytest.mark.parametrize("schema,error", [({}, "No settings found"), (None, "No core plugins found")])
def test_missing_required_defaults_abort_generation(configure, caplog, schema, error):
    configurator = configure(schema=schema, manifest={} if schema is None else None)
    with pytest.raises(SystemExit) as exc:
        configurator.get_config()
    assert exc.value.code == 1 and error in caplog.text
