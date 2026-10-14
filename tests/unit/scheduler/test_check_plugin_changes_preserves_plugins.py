"""``check_plugin_changes`` (scheduler) must never delete a plugin it did not look at.

The scan sends ``update_external_plugins`` only the plugins that are NEW or CHANGED on disk -- an
unchanged one, and one whose database row is not ``manual`` (installed by the download job), are
skipped before the list is built. Called with ``delete_missing=True`` that partial list read, to the
database, as "everything else was uninstalled": one edited hand-mounted plugin deleted every URL
installed plugin and every unchanged hand-mounted one, with their saved settings (dev #3303).

The shipped function is nested inside ``if __name__ == "__main__"`` of ``src/scheduler/main.py``, so
it is cut out of the source by AST and run against a real ``Database`` through a client double that
forwards exactly what the scheduler sent.
"""

import ast
import json
from base64 import b64decode, b64encode
from contextlib import suppress
from pathlib import Path
from typing import Literal

import pytest

from common_utils import bytes_hash, create_plugin_tar_gz, dict_to_frozenset  # type: ignore
from fixtures.seed import make_external_plugin

MAIN = Path(__file__).resolve().parents[3] / "src" / "scheduler" / "main.py"


def _nested_function(name):
    tree = ast.parse(MAIN.read_text(encoding="utf-8"), filename=str(MAIN))
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))


class _Logger:
    def __getattr__(self, level):
        return lambda *args, **kwargs: None


class _ApiClient:
    """What ``scheduler/api_client.py`` + the API router do, minus HTTP: base64 in, bytes to the DB."""

    def __init__(self, db):
        self.db = db
        self.calls = []

    def get_plugins(self, _type="external"):
        return self.db.get_plugins(_type=_type)

    def update_external_plugins(self, plugins, _type="external", **kwargs):
        self.calls.append((_type, kwargs, [p["id"] for p in plugins]))
        for plugin in plugins:
            if isinstance(plugin.get("data"), str):
                plugin["data"] = b64decode(plugin["data"])
        return self.db.update_external_plugins(plugins, _type=_type, **kwargs)


@pytest.fixture
def scan(db, tmp_path, monkeypatch):
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    monkeypatch.setattr(type(db), "_uep_resolve_plugin_dir", lambda self, plugin_id, _type: plugins_dir / plugin_id)
    client = _ApiClient(db)
    namespace = {
        "API_CLIENT": client,
        "LOGGER": _Logger(),
        "EXTERNAL_PLUGINS_PATH": plugins_dir,
        "PRO_PLUGINS_PATH": tmp_path / "pro",
        "Literal": Literal,
        "suppress": suppress,
        "json_load": json.load,
        "b64encode": b64encode,
        "bytes_hash": bytes_hash,
        "create_plugin_tar_gz": create_plugin_tar_gz,
        "dict_to_frozenset": dict_to_frozenset,
        "generate_external_plugins": lambda *args, **kwargs: None,
    }
    exec(compile(_nested_function("check_plugin_changes"), str(MAIN), "exec"), namespace)  # noqa: S102

    def _disk(plugin_id, *, version="1.0", method="manual", in_db=True, stale_db=False):
        """A plugin directory, and (``in_db``) the row the database holds for it."""
        plugin = make_external_plugin(plugin_id, version=version, method=method)
        folder = plugins_dir / plugin_id
        folder.mkdir()
        manifest = {key: plugin[key] for key in ("id", "name", "description", "version", "stream", "settings")} | {"jobs": []}
        (folder / "plugin.json").write_text(json.dumps(manifest))
        checksum = bytes_hash(create_plugin_tar_gz(folder, arc_root=plugin_id), algorithm="sha256")
        if in_db:
            row = make_external_plugin(plugin_id, version=version, method=method, checksum="stale" if stale_db else checksum)
            assert db.update_external_plugins([row], _type="external", delete_missing=False) == ""
        return folder

    scan_fn = namespace["check_plugin_changes"]
    scan_fn.client = client
    scan_fn.disk = _disk
    return scan_fn


def _ids(db):
    return sorted(p["id"] for p in db.get_plugins(_type="external"))


def test_one_changed_manual_plugin_deletes_nothing_else(db, scan):
    scan.disk("url_plugin", method="scheduler")  # installed by the download job: skipped by the scan
    scan.disk("quiet_manual")  # hand-mounted, unchanged: skipped by the scan
    scan.disk("edited_manual", stale_db=True)  # hand-mounted and edited: the only one the scan sends

    scan("external")

    assert [c[2] for c in scan.client.calls] == [["edited_manual"]]
    assert _ids(db) == ["edited_manual", "quiet_manual", "url_plugin"]


def test_a_new_manual_plugin_deletes_nothing_else(db, scan):
    scan.disk("url_plugin", method="scheduler")
    scan.disk("quiet_manual")
    scan.disk("brand_new", in_db=False)

    scan("external")

    assert _ids(db) == ["brand_new", "quiet_manual", "url_plugin"]


def test_a_plugin_removed_from_disk_is_still_removed(db, scan):
    """The delete_missing the scan exists for: a hand-mounted plugin whose directory is gone."""
    scan.disk("edited_manual", stale_db=True)
    scan.disk("quiet_manual")
    gone = make_external_plugin("gone_manual", method="manual")
    assert db.update_external_plugins([gone], _type="external", delete_missing=False) == ""

    scan("external")

    assert _ids(db) == ["edited_manual", "quiet_manual"]


def test_a_url_plugin_whose_directory_is_gone_is_left_to_the_download_job(db, scan):
    """Not on disk and not manual: the scan does not own it (the job re-installs or prunes it)."""
    scan.disk("edited_manual", stale_db=True)
    url_row = make_external_plugin("url_plugin", method="scheduler")
    assert db.update_external_plugins([url_row], _type="external", delete_missing=False) == ""

    scan("external")

    assert _ids(db) == ["edited_manual", "url_plugin"]


class TestSchedulerClient:
    """The wire half: the ids the scan names must be in the PUT body, and an old caller's body must not change."""

    @staticmethod
    def _client():
        from unittest.mock import Mock

        from api_client import SchedulerApiClient  # type: ignore  (src/scheduler on sys.path)

        client = SchedulerApiClient("http://api.invalid", "token")
        client._put = Mock(return_value={})
        return client

    def test_the_ids_are_sent(self):
        client = self._client()
        assert client.update_external_plugins([], _type="external", delete_missing=True, preserve_ids={"b", "a"}) == ""
        client._put.assert_called_once_with("/plugins/external", json={"plugins": [], "_type": "external", "delete_missing": True, "preserve_ids": ["a", "b"]})

    def test_a_caller_that_names_none_sends_the_old_body(self):
        client = self._client()
        client.update_external_plugins([], _type="pro", delete_missing=False)
        client._put.assert_called_once_with("/plugins/external", json={"plugins": [], "_type": "pro", "delete_missing": False})
