"""Load the real ``src/api/app/utils.py`` for tests that stub the API package.

The router tests build a fake ``bw_services.utils`` / ``bw_global_settings.utils`` module rather
than importing the API package (there is no live ``TestClient`` under ``tests/unit/api``). Every
symbol a router imports from it has to exist, and for a PURE helper the honest stub is the real
function: stubbing ``reportable_config`` with a ``Mock`` would let the reduction the endpoints now
depend on drift from what production runs without a single test noticing.
"""

import importlib.util
import sys
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def load_api_utils() -> ModuleType:
    """Import ``src/api/app/utils.py`` in isolation and return the module."""
    names = {
        "app": ModuleType("app"),
        "app.models": ModuleType("app.models"),
        "app.models.api_database": ModuleType("app.models.api_database"),
    }
    names["app"].__path__ = []
    names["app.models"].__path__ = []
    names["app.models.api_database"].APIDatabase = Mock
    with patch.dict(sys.modules, names):
        spec = importlib.util.spec_from_file_location("bw_api_app_utils", ROOT / "src" / "api" / "app" / "utils.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module
