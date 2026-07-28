"""The generic ``config`` plugin extension: compile, namespace guard, atomic artefact.

A plugin declaring ``extensions.config`` gets to turn its own stored documents into
derived settings plus one cache artefact, once per config generation. It runs inside the
generator, so a failure here aborts the whole push — which is the point, and is what most
of these tests pin down.
"""

import json
from pathlib import Path

import pytest

from plugin_extensions import ConfigExtensionError, enforced_variable_namespace, run_config_extensions  # type: ignore

COMPILER = """
def compile_config(db, config, logger):
    return {"variables": %s, "data": %s}
"""


class FakeDB:
    """Only has to be non-None: a ``core`` plugin skips the checksum verification."""


def _plugin(root: Path, plugin_id: str, *, body: str, settings=None) -> Path:
    directory = root / plugin_id
    (directory / "config").mkdir(parents=True)
    (directory / "config" / "__init__.py").write_text("")
    (directory / "config" / "compiler.py").write_text(body)
    manifest = {
        "id": plugin_id,
        "name": plugin_id,
        "description": "test",
        "version": "1.0",
        "stream": "no",
        "settings": settings or {},
        "extensions": {"config": {"module": "config/compiler.py"}},
    }
    (directory / "plugin.json").write_text(json.dumps(manifest))
    return directory


def _run(root: Path, config=None, full_config=None, cache=None):
    config = {"SERVER_NAME": "app.example.com"} if config is None else config
    full_config = dict(config) if full_config is None else full_config
    return run_config_extensions(
        FakeDB(),
        config,
        full_config,
        _Logger(),
        paths=[(root, "core")],
        cache_root=cache if cache is not None else root / "cache",
    )


class _Logger:
    def info(self, *_args, **_kwargs):
        pass

    def warning(self, *_args, **_kwargs):
        pass

    def error(self, *_args, **_kwargs):
        pass


def test_variables_are_merged_and_the_artefact_is_written_canonically(tmp_path):
    _plugin(tmp_path, "demoa", body=COMPILER % ('{"DEMOA_FLAG": "yes"}', '{"b": 1, "a": [2, 1]}'), settings={"DEMOA_FLAG": {"default": "no"}})
    cache = tmp_path / "cache"

    config, full_config = _run(tmp_path, cache=cache)

    assert config["DEMOA_FLAG"] == "yes" and full_config["DEMOA_FLAG"] == "yes"
    # One fixed path per plugin — the plugin never chooses where its artefact lands.
    artefact = cache / "demoa" / "config.json"
    assert artefact.read_text() == '{"a":[2,1],"b":1}'


def test_a_server_prefixed_variable_is_accepted(tmp_path):
    _plugin(
        tmp_path,
        "demob",
        body=COMPILER % ('{"app.example.com_DEMOB_FLAG": "yes"}', "None"),
        settings={"DEMOB_FLAG": {"default": "no"}},
    )
    config, _ = _run(tmp_path)
    assert config["app.example.com_DEMOB_FLAG"] == "yes"


def test_a_variable_outside_the_plugin_namespace_is_refused(tmp_path):
    _plugin(tmp_path, "democ", body=COMPILER % ('{"USE_ANTIBOT": "captcha"}', "None"))
    with pytest.raises(ConfigExtensionError, match="outside its DEMOC_ namespace"):
        _run(tmp_path)


def test_a_plugin_cannot_rewrite_a_setting_it_does_not_declare(tmp_path):
    """The namespace alone is not enough — a plugin id can prefix a foreign setting."""
    _plugin(tmp_path, "use", body=COMPILER % ('{"USE_ANTIBOT": "captcha"}', "None"))
    with pytest.raises(ConfigExtensionError, match="would overwrite USE_ANTIBOT"):
        _run(tmp_path, config={"SERVER_NAME": "app.example.com", "USE_ANTIBOT": "no"})


def test_a_non_string_variable_is_refused(tmp_path):
    _plugin(tmp_path, "demod", body=COMPILER % ('{"DEMOD_FLAG": True}', "None"), settings={"DEMOD_FLAG": {"default": "no"}})
    with pytest.raises(ConfigExtensionError, match="non-string variable"):
        _run(tmp_path)


def test_a_raising_compiler_aborts_and_writes_nothing(tmp_path):
    _plugin(tmp_path, "demoe", body="def compile_config(db, config, logger):\n    raise RuntimeError('boom')\n")
    cache = tmp_path / "cache"

    with pytest.raises(ConfigExtensionError, match="boom"):
        _run(tmp_path, cache=cache)
    assert not (cache / "demoe").exists()


def test_a_module_without_compile_config_is_refused(tmp_path):
    _plugin(tmp_path, "demof", body="value = 1\n")
    with pytest.raises(ConfigExtensionError, match="compile_config"):
        _run(tmp_path)


def test_one_failing_plugin_leaves_no_artefact_for_the_others(tmp_path):
    """Two-phase: every compiler runs before anything is written.

    Otherwise a healthy plugin's newer artefact would sit on disk waiting for some
    unrelated later push to ship it, while its matching NGINX config was never rendered.
    """
    _plugin(tmp_path, "aaagood", body=COMPILER % ('{"AAAGOOD_FLAG": "yes"}', '{"ok": true}'), settings={"AAAGOOD_FLAG": {"default": "no"}})
    _plugin(tmp_path, "zzzbad", body="def compile_config(db, config, logger):\n    raise RuntimeError('boom')\n")
    cache = tmp_path / "cache"

    with pytest.raises(ConfigExtensionError):
        _run(tmp_path, cache=cache)
    assert not (cache / "aaagood").exists()


def test_the_bootstrap_render_without_a_database_is_a_no_op(tmp_path):
    _plugin(tmp_path, "demozz", body=COMPILER % ('{"DEMOG_FLAG": "yes"}', '{"x": 1}'), settings={"DEMOG_FLAG": {"default": "no"}})
    cache = tmp_path / "cache"
    config = {"SERVER_NAME": "app.example.com"}

    # ``gen/main.py --variables`` renders the loading placeholder before any database
    # exists; no plugin has a stored document to compile yet.
    result, _ = run_config_extensions(None, config, dict(config), _Logger(), paths=[(tmp_path, "core")], cache_root=cache)
    assert "DEMOG_FLAG" not in result and not cache.exists()


def test_the_namespace_is_derived_from_the_plugin_id():
    assert enforced_variable_namespace("web-cache") == "WEB_CACHE"
    assert enforced_variable_namespace("workflows") == "WORKFLOWS"
