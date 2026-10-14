"""``PUT /plugins/external`` carries ``preserve_ids`` from the scheduler to the database (dev #3303).

The scheduler's scan of hand-mounted plugins lists only what changed on disk, so it names the ids it
did not list: without the field on the wire the database reads the partial list as "the rest was
uninstalled". Three hops: the request model, the router, the scheduler's client.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

import schemas  # type: ignore  (src/api/app on sys.path)

ROOT = Path(__file__).resolve().parents[3]


class TestRequestModel:
    def test_absent_means_nothing_is_preserved(self):
        assert schemas.UpdateExternalPluginsRequest(plugins=[]).preserve_ids == []

    def test_the_ids_round_trip(self):
        assert schemas.UpdateExternalPluginsRequest(plugins=[], preserve_ids=["a", "b"]).preserve_ids == ["a", "b"]

    @pytest.mark.parametrize("bad", ["a", 3, [1], [["a"]], {"a": 1}])
    def test_only_a_list_of_strings_is_accepted(self, bad):
        with pytest.raises(ValidationError):
            schemas.UpdateExternalPluginsRequest(plugins=[], preserve_ids=bad)


class TestRouter:
    @pytest.fixture
    def router(self):
        import importlib.util
        from types import ModuleType
        from unittest.mock import patch

        class _Router:
            def __init__(self, **_kwargs):
                pass

            def _passthrough(self, *_args, **_kwargs):
                return lambda function: function

            get = put = post = patch = delete = _passthrough

        names = {
            "fastapi": ModuleType("fastapi"),
            "fastapi.responses": ModuleType("fastapi.responses"),
            "bw_plugins": ModuleType("bw_plugins"),
            "bw_plugins.routers": ModuleType("bw_plugins.routers"),
            "bw_plugins.auth": ModuleType("bw_plugins.auth"),
            "bw_plugins.auth.guard": ModuleType("bw_plugins.auth.guard"),
            "bw_plugins.schemas": ModuleType("bw_plugins.schemas"),
            "bw_plugins.utils": ModuleType("bw_plugins.utils"),
            "common_utils": ModuleType("common_utils"),
        }
        names["fastapi"].APIRouter = _Router
        names["fastapi"].Depends = lambda dependency: dependency
        names["fastapi"].File = lambda *a, **k: None
        names["fastapi"].Form = lambda *a, **k: None
        names["fastapi"].UploadFile = object
        names["fastapi.responses"].JSONResponse = lambda *, status_code, content: SimpleNamespace(status_code=status_code, content=content)
        for package in ("bw_plugins", "bw_plugins.routers", "bw_plugins.auth"):
            names[package].__path__ = []
        names["bw_plugins.auth.guard"].guard = object()
        names["bw_plugins.schemas"].PluginEnabledRequest = object
        names["bw_plugins.schemas"].UpdateExternalPluginsRequest = object
        names["bw_plugins.utils"].get_db = Mock()
        for name in ("bytes_hash", "create_plugin_tar_gz", "plugin_icon_content_type", "read_plugin_icon", "read_local_plugin_icon"):
            setattr(names["common_utils"], name, Mock())
        with patch.dict(sys.modules, names):
            spec = importlib.util.spec_from_file_location("bw_plugins.routers.plugins", ROOT / "src" / "api" / "app" / "routers" / "plugins.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        db = Mock()
        db.update_external_plugins.return_value = ""
        module.get_db = lambda: db
        module.db = db
        return module

    def test_the_ids_reach_the_database_as_a_set(self, router):
        payload = SimpleNamespace(plugins=[], plugin_type="external", delete_missing=True, preserve_ids=["quiet", "url"])
        assert router.update_external_plugins(payload).status_code == 200
        router.db.update_external_plugins.assert_called_once_with([], _type="external", delete_missing=True, preserve_ids={"quiet", "url"})

    def test_an_empty_field_preserves_nothing(self, router):
        payload = SimpleNamespace(plugins=[], plugin_type="pro", delete_missing=False, preserve_ids=[])
        router.update_external_plugins(payload)
        router.db.update_external_plugins.assert_called_once_with([], _type="pro", delete_missing=False, preserve_ids=set())
