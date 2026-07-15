"""Plugin API router mounting stays guarded and collision-safe."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]


class _AppType:
    pass


def _load_module():
    modules = {
        "fastapi": ModuleType("fastapi"),
        "bw_plugin_loader": ModuleType("bw_plugin_loader"),
        "bw_plugin_loader.routers": ModuleType("bw_plugin_loader.routers"),
        "bw_plugin_loader.auth": ModuleType("bw_plugin_loader.auth"),
        "bw_plugin_loader.auth.guard": ModuleType("bw_plugin_loader.auth.guard"),
        "bw_plugin_loader.rate_limit": ModuleType("bw_plugin_loader.rate_limit"),
        "bw_plugin_loader.utils": ModuleType("bw_plugin_loader.utils"),
    }
    modules["fastapi"].Depends = lambda dependency: ("depends", dependency)
    modules["fastapi"].FastAPI = _AppType
    modules["bw_plugin_loader"].__path__ = []
    modules["bw_plugin_loader.routers"].__path__ = []
    modules["bw_plugin_loader.auth"].__path__ = []
    modules["bw_plugin_loader.auth.guard"].guard = "guard"
    modules["bw_plugin_loader.rate_limit"].limiter_dep_dynamic = lambda: "rate-limit"
    modules["bw_plugin_loader.utils"].LOGGER = Mock()
    modules["bw_plugin_loader.utils"].get_db = lambda log=False: "db"
    with patch.dict(sys.modules, modules):
        path = ROOT / "src" / "api" / "app" / "routers" / "plugin_loader.py"
        spec = importlib.util.spec_from_file_location("bw_plugin_loader.routers.plugin_loader", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


LOADER = _load_module()


class _App:
    def __init__(self):
        self.routes = [SimpleNamespace(path="/instances/health")]
        self.mounted = []

    def include_router(self, router, **kwargs):
        self.mounted.append((router, kwargs))


def _extension(plugin_id, module="router"):
    return SimpleNamespace(
        plugin_id=plugin_id,
        plugin_type="core",
        directory=Path("/tmp") / plugin_id,
        api={"module": module} if module else {},
    )


def test_discovers_only_valid_non_colliding_router(monkeypatch):
    extensions = [
        _extension("untrusted"),
        _extension("instances"),
        _extension("missing"),
        _extension("broken"),
        _extension("good"),
    ]
    plugin_extensions = ModuleType("plugin_extensions")
    plugin_extensions.iter_extension_plugins = lambda logger: extensions
    plugin_extensions.extension_allowed = lambda ext, db, logger: (ext.plugin_id != "untrusted")
    plugin_extensions.effective_api_prefix = lambda ext: f"/{ext.plugin_id}"

    def import_router(plugin_id, _directory, _module):
        if plugin_id == "broken":
            raise ImportError("broken")
        return SimpleNamespace(router=None if plugin_id == "missing" else f"{plugin_id}-router")

    plugin_extensions.import_plugin_submodule = import_router
    monkeypatch.setitem(sys.modules, "plugin_extensions", plugin_extensions)
    app = _App()

    LOADER.discover_plugin_routers(app)

    assert app.mounted == [
        (
            "good-router",
            {"prefix": "/good", "dependencies": [("depends", "guard"), "rate-limit"]},
        )
    ]


def test_existing_prefixes_are_top_level_only():
    app = SimpleNamespace(
        routes=[
            SimpleNamespace(path="/instances/health"),
            SimpleNamespace(path="/docs"),
            SimpleNamespace(path=""),
        ]
    )
    assert LOADER._existing_top_prefixes(app) == {"/instances", "/docs"}
