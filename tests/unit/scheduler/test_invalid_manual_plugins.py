"""A malformed hand-mounted plugin is kept and reported, never deleted and never fatal.

``check_plugin_changes`` ran ``json_load(plugin.json)`` and ``plugin_data["id"]`` unguarded in a
thread-pool task whose ``future.result()`` re-raises in the main thread; the ``except:`` that wraps the
scheduler's whole ``__main__`` block logs and calls ``stop(1)``, so one typo in one ``plugin.json``
took the scheduler down on every restart. ``generate_external_plugins`` then deleted any directory the
database had no row for, which is exactly what a rejected plugin is.

Two hand-mounted plugins whose settings share an ``id`` were a second way in: the database answers
``1062 Duplicate entry`` on ``bw_settings.name`` and the directory disappeared with no clear message.

The scheduler's functions are cut out of ``src/scheduler/main.py`` by AST (the module starts the
scheduler on import) and run against a real ``Database`` and a real ``Configurator``.
"""

import ast
import json
import logging
import sys
from base64 import b64decode, b64encode
from contextlib import suppress
from io import BytesIO
from pathlib import Path
from shutil import rmtree
from stat import S_IRGRP, S_IRUSR, S_IWUSR, S_IXGRP, S_IXUSR
from tarfile import open as tar_open
from traceback import format_exc
from typing import Literal, Union

import pytest

from common_utils import bytes_hash, create_plugin_tar_gz, dict_to_frozenset, plugin_tar_exclude  # type: ignore
from fixtures.seed import make_external_plugin
from manual_plugins import read_manual_plugin  # type: ignore

ROOT = Path(__file__).resolve().parents[3]
MAIN = ROOT / "src" / "scheduler" / "main.py"
if str(ROOT / "src" / "common" / "gen") not in sys.path:
    sys.path.append(str(ROOT / "src" / "common" / "gen"))

from Configurator import Configurator  # type: ignore  # noqa: E402


def _function(name):
    tree = ast.parse(MAIN.read_text(encoding="utf-8"), filename=str(MAIN))
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))


class _Logger:
    def __init__(self):
        self.lines = []

    def __getattr__(self, level):
        return lambda message, *args, **kwargs: self.lines.append((level, str(message)))

    def text(self, *levels):
        return "\n".join(message for level, message in self.lines if not levels or level in levels)


@pytest.fixture(scope="module")
def validator():
    return Configurator(str(ROOT / "src" / "common" / "settings.json"), str(ROOT / "src" / "common" / "core"), [], [], {}, logging.getLogger("p2a"))


class _ApiClient:
    """What ``scheduler/api_client.py`` + the API router do, minus HTTP: base64 in, bytes to the DB."""

    readonly = False

    def __init__(self, db, stored=None):
        self.db = db
        self.stored = stored
        self.calls = []

    def get_plugins(self, _type="external", with_data=False, only_enabled=False):
        if self.stored is not None:  # a canned answer for generate_external_plugins
            return self.stored
        return self.db.get_plugins(_type=_type)

    def update_external_plugins(self, plugins, _type="external", **kwargs):
        self.calls.append((_type, kwargs, [p["id"] for p in plugins]))
        for plugin in plugins:
            if isinstance(plugin.get("data"), str):
                plugin["data"] = b64decode(plugin["data"])
        return self.db.update_external_plugins(plugins, _type=_type, **kwargs)


def _manifest(plugin_id, *, settings=None, **extra):
    base = make_external_plugin(plugin_id)
    manifest = {key: base[key] for key in ("id", "name", "description", "version", "stream", "settings")}
    if settings is not None:
        manifest["settings"] = settings
    return manifest | extra


def _setting(setting_id, **extra):
    return {"id": setting_id, "context": "global", "default": "x", "help": "h", "label": "L", "regex": "^.*$", "type": "text"} | extra


def _mount(plugins_dir, name, content):
    """A directory under the plugins path; ``content`` is a manifest dict or the raw bytes/text of plugin.json."""
    folder = plugins_dir / name
    folder.mkdir()
    text = content if isinstance(content, (str, bytes)) else json.dumps(content)
    (folder / "plugin.json").write_bytes(text if isinstance(text, bytes) else text.encode())
    return folder


@pytest.fixture
def env(db, tmp_path, monkeypatch, validator):
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    monkeypatch.setattr(type(db), "_uep_resolve_plugin_dir", lambda self, plugin_id, _type: plugins_dir / plugin_id)
    logger = _Logger()
    client = _ApiClient(db)
    namespace = {
        "API_CLIENT": client,
        "LOGGER": logger,
        "EXTERNAL_PLUGINS_PATH": plugins_dir,
        "PRO_PLUGINS_PATH": tmp_path / "pro",
        "Literal": Literal,
        "Union": Union,
        "Path": Path,
        "suppress": suppress,
        "b64encode": b64encode,
        "json_load": json.load,
        "bytes_hash": bytes_hash,
        "create_plugin_tar_gz": create_plugin_tar_gz,
        "dict_to_frozenset": dict_to_frozenset,
        "plugin_tar_exclude": plugin_tar_exclude,
        "rmtree": rmtree,
        "tar_open": tar_open,
        "BytesIO": BytesIO,
        "format_exc": format_exc,
        "S_IRUSR": S_IRUSR,
        "S_IWUSR": S_IWUSR,
        "S_IXUSR": S_IXUSR,
        "S_IRGRP": S_IRGRP,
        "S_IXGRP": S_IXGRP,
        "read_manual_plugin": read_manual_plugin,
        "get_plugin_validator": lambda: validator,
        "generate_external_plugins": lambda *args, **kwargs: None,
    }
    for name in ("check_plugin_changes", "generate_external_plugins"):
        scope = dict(namespace)
        exec(compile(_function(name), str(MAIN), "exec"), scope)  # noqa: S102
        namespace[f"real_{name}"] = scope[name]

    class Env:
        pass

    result = Env()
    result.db, result.dir, result.client, result.logger = db, plugins_dir, client, logger
    result.scan = namespace["real_check_plugin_changes"]
    result.namespace = namespace
    return result


def _clear_message(error):
    """The refusal is the scheduler's own sentence, not the database's complaint about a violated constraint."""
    assert not any(marker in error for marker in ("IntegrityError", "UNIQUE", "1062", "Duplicate entry")), error


def _ids(db):
    return sorted(p["id"] for p in db.get_plugins(_type="external"))


def _register(db, plugins_dir, manifest, *, method="manual"):
    """A plugin the database already holds, with its directory on disk (checksum in step)."""
    folder = _mount(plugins_dir, manifest["id"], manifest)
    checksum = bytes_hash(create_plugin_tar_gz(folder, arc_root=folder.name), algorithm="sha256")
    row = make_external_plugin(manifest["id"], method=method, checksum=checksum)
    row["settings"] = manifest["settings"]
    assert db.update_external_plugins([row], _type="external", delete_missing=False) == ""
    return folder


# --- a malformed manifest is kept and reported ------------------------------------------------------


@pytest.mark.parametrize(
    "content",
    [
        pytest.param('{"id": "broken", "name": ', id="truncated-json"),
        pytest.param(b"\xff\xfe\x00 not utf-8", id="not-utf-8"),
        pytest.param("[1, 2]", id="not-an-object"),
        pytest.param('{"name": "no id"}', id="no-id"),
        pytest.param({"id": "broken", "name": "n", "description": "d", "version": "one", "stream": "no", "settings": {}}, id="bad-version"),
        pytest.param({"id": "broken", "name": "n", "description": "d", "version": "1.0", "stream": "no", "settings": {"A": "not an object"}}, id="bad-setting"),
        pytest.param("[" * 100000, id="nested-too-deep"),
    ],
)
def test_a_malformed_manifest_does_not_crash_the_scan(env, content):
    good = _mount(env.dir, "good", _manifest("good"))
    broken = _mount(env.dir, "broken", content)
    before = (broken / "plugin.json").read_bytes()

    env.scan("external")  # used to raise out of the task and, through future.result(), stop the scheduler

    assert _ids(env.db) == ["good"]
    assert (broken / "plugin.json").read_bytes() == before
    assert good.is_dir()
    assert "broken" in env.logger.text("error")


def test_a_scan_with_only_a_malformed_manifest_does_not_crash(env):
    broken = _mount(env.dir, "broken", "{ nope")

    env.scan("external")

    assert broken.is_dir()
    assert _ids(env.db) == []
    assert "broken" in env.logger.text("error")


def test_a_registered_plugin_whose_manifest_broke_stays_registered(env):
    """A sibling changed too, so the scan sends ``delete_missing=True`` and the broken one is not in its list."""
    _register(env.db, env.dir, _manifest("kept"))
    folder = env.dir / "kept"
    (folder / "plugin.json").write_text("{ typo")
    _mount(env.dir, "fresh", _manifest("fresh"))

    env.scan("external")

    assert _ids(env.db) == ["fresh", "kept"]
    assert folder.joinpath("plugin.json").read_text() == "{ typo"
    assert "kept" in env.logger.text("error")


def test_a_valid_plugin_is_still_registered(env):
    _mount(env.dir, "fine", _manifest("fine"))

    env.scan("external")

    assert _ids(env.db) == ["fine"]
    assert env.logger.text("error") == ""


# --- duplicate setting ids ---------------------------------------------------------------------------


def test_two_plugins_sharing_a_setting_id_register_one_and_name_the_other(env):
    _mount(env.dir, "alpha", _manifest("alpha", settings={"ALPHA_ONE": _setting("shared-id")}))
    beta = _mount(env.dir, "beta", _manifest("beta", settings={"BETA_ONE": _setting("shared-id")}))

    env.scan("external")  # used to be "API returned 500 ... 1062 Duplicate entry" and a missing directory

    assert _ids(env.db) == ["alpha"]
    assert beta.is_dir()
    error = env.logger.text("error")
    assert "beta" in error and "shared-id" in error and "alpha" in error
    _clear_message(error)


def test_a_plugin_repeating_a_setting_id_is_refused_with_both_keys(env):
    twice = _mount(env.dir, "twice", _manifest("twice", settings={"TWICE_A": _setting("same"), "TWICE_B": _setting("same")}))

    env.scan("external")

    assert _ids(env.db) == []
    assert twice.is_dir()
    error = env.logger.text("error")
    assert "TWICE_A" in error and "TWICE_B" in error and "same" in error
    _clear_message(error)


def test_a_setting_key_or_id_owned_by_core_is_refused(env):
    by_key = _mount(env.dir, "bykey", _manifest("bykey", settings={"USE_ANTIBOT": _setting("bykey-own-id")}))
    by_id = _mount(env.dir, "byid", _manifest("byid", settings={"BYID_OWN": _setting("use-antibot")}))

    env.scan("external")

    assert _ids(env.db) == []
    assert by_key.is_dir() and by_id.is_dir()
    error = env.logger.text("error")
    assert "USE_ANTIBOT" in error and "use-antibot" in error
    _clear_message(error)


def test_a_new_plugin_cannot_take_an_id_a_registered_plugin_holds(env):
    _register(env.db, env.dir, _manifest("holder", settings={"HOLDER_ONE": _setting("held-id")}))
    thief = _mount(env.dir, "thief", _manifest("thief", settings={"THIEF_ONE": _setting("held-id")}))

    env.scan("external")

    assert _ids(env.db) == ["holder"]
    assert thief.is_dir()
    assert "holder" in env.logger.text("error")
    _clear_message(env.logger.text("error"))


def test_an_edited_plugin_may_keep_its_own_setting_ids(env):
    """The registered row of the plugin being updated is not a conflict with itself."""
    folder = _register(env.db, env.dir, _manifest("editme", settings={"EDITME_ONE": _setting("mine")}))
    manifest = _manifest("editme", settings={"EDITME_ONE": _setting("mine", help="changed")}, version="1.1")
    folder.joinpath("plugin.json").write_text(json.dumps(manifest))

    env.scan("external")

    assert env.logger.text("error") == ""
    assert [p["version"] for p in env.db.get_plugins(_type="external") if p["id"] == "editme"] == ["1.1"]


# --- generate_external_plugins -----------------------------------------------------------------------


def _stored(manifest, dir_for_tar, *, method="manual", name=None):
    """What ``API_CLIENT.get_plugins(with_data=True)`` returns for a plugin the database holds."""
    source = dir_for_tar / (name or manifest["id"])
    source.mkdir(parents=True)
    source.joinpath("plugin.json").write_text(json.dumps(manifest))
    content = create_plugin_tar_gz(source, arc_root=source.name)
    return manifest | {
        "type": "external",
        "method": method,
        "name": manifest["name"],
        "data": content.getvalue(),
        "checksum": bytes_hash(content, algorithm="sha256"),
        "enabled": True,
    }


def _generate(env, stored, tmp_path):
    env.client.stored = stored
    env.namespace["real_generate_external_plugins"](env.dir)


def test_an_unregistered_malformed_directory_survives_generation(env, tmp_path):
    broken = _mount(env.dir, "broken", "{ nope")
    no_manifest = env.dir / "stray"
    no_manifest.mkdir()
    (no_manifest / "readme.txt").write_text("x")

    _generate(env, [], tmp_path)

    assert broken.joinpath("plugin.json").read_text() == "{ nope"
    assert not no_manifest.exists()  # no plugin.json: nothing to preserve, removed as before
    assert "broken" in env.logger.text("warning", "error")


def test_an_unregistered_invalid_manifest_survives_generation(env, tmp_path):
    invalid = _mount(env.dir, "invalid", {"id": "invalid", "name": "n"})

    _generate(env, [], tmp_path)

    assert invalid.is_dir()


def test_an_unregistered_valid_directory_is_still_removed(env, tmp_path):
    """Unchanged: a valid directory the database does not know is removed (design question D10, not this lane)."""
    valid = _mount(env.dir, "valid", _manifest("valid"))

    _generate(env, [], tmp_path)

    assert not valid.exists()


def test_a_broken_edit_of_a_stored_manual_plugin_is_not_overwritten_by_the_stored_copy(env, tmp_path):
    stored = _stored(_manifest("mine"), tmp_path / "src")
    broken = _mount(env.dir, "mine", "{ half-edited")

    _generate(env, [stored], tmp_path)

    assert broken.joinpath("plugin.json").read_text() == "{ half-edited"


def test_a_stored_manual_plugin_whose_directory_is_named_otherwise_is_not_overwritten(env, tmp_path):
    """The archive root is the directory name, not the plugin id: extracting it would overwrite the broken edit."""
    stored = _stored(_manifest("mine"), tmp_path / "src", name="other-name")
    broken = _mount(env.dir, "other-name", "{ half-edited")

    _generate(env, [stored], tmp_path)

    assert broken.joinpath("plugin.json").read_text() == "{ half-edited"


def test_a_stored_installed_plugin_is_still_restored_over_a_broken_directory(env, tmp_path):
    """Only manual plugins are the user's: one the download job installed is the database's to restore."""
    stored = _stored(_manifest("fetched"), tmp_path / "src", method="scheduler")
    _mount(env.dir, "fetched", "{ junk")

    _generate(env, [stored], tmp_path)

    assert json.loads(env.dir.joinpath("fetched", "plugin.json").read_text())["id"] == "fetched"


def test_a_stored_manual_plugin_with_changed_valid_directory_is_still_restored(env, tmp_path):
    stored = _stored(_manifest("mine"), tmp_path / "src")
    _mount(env.dir, "mine", _manifest("mine", version="9.9"))

    _generate(env, [stored], tmp_path)

    assert json.loads(env.dir.joinpath("mine", "plugin.json").read_text())["version"] == "1.0"
