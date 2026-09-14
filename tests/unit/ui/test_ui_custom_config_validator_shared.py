"""`app/routes/configs.py` and `app/routes/utils.py` must consume the shared validator, not a
private copy of it -- the UI half of the check `tests/unit/api/test_custom_config_validator_shared.py`
does for the API. Before this lane, `CONFIG_NAME_RX` (`configs.py`) and `CUSTOM_CONF_RX`
(`routes/utils.py`) were each their own literal regex, and `routes/utils.py`'s own comment says
the two `CUSTOM_CONF_RX` copies (this one and `src/common/gen/save_config.py`'s) had already
drifted once. A future revert to a local copy must fail loudly here.

Both route modules import `app.dependencies` at module scope, which builds a real `Config()` that
reads the image-only `/usr/share/bunkerweb/settings.json` -- a bare import fails at collection
time outside a built image. `configs.py` also pulls `app.routes.utils`, which pulls
`qrcode.main`, not a test dependency. Load each module from its file against stubs, the pattern
`test_save_scope.py`'s `_import_services_module` documents.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import custom_configs_validation as shared  # type: ignore  (src/common/utils on sys.path via root conftest)

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIGS_ROUTE = REPO_ROOT / "src" / "ui" / "app" / "routes" / "configs.py"
UTILS_ROUTE = REPO_ROOT / "src" / "ui" / "app" / "routes" / "utils.py"


def _stub_dependencies() -> ModuleType:
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DATA = Mock()
    return dependencies


def _stub_qrcode() -> tuple:
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main
    return qrcode, qrcode_main


def _import_route_module(source: Path, module_name: str) -> ModuleType:
    """Load one `app/routes/*.py` file under a throwaway name, real `app.dependencies` and
    `qrcode.main` swapped for stubs for the duration of the exec only."""
    dependencies = _stub_dependencies()
    qrcode, qrcode_main = _stub_qrcode()
    spec = importlib.util.spec_from_file_location(module_name, source)
    module = importlib.util.module_from_spec(spec)
    stubs = {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


_configs = _import_route_module(CONFIGS_ROUTE, "app.routes._configs_validator_shared")
_utils = _import_route_module(UTILS_ROUTE, "app.routes._utils_validator_shared")


def test_config_name_rx_is_the_shared_object():
    """`CONFIG_NAME_RX = NAME_RX` in `configs.py` is a direct re-export -- unlike a fresh
    `re.compile()` call, this `is` check is not vulnerable to CPython's pattern-cache coincidence
    (see `test_custom_config_validator_shared.py` in `tests/unit/api/` for that caveat); it is
    checked anyway, alongside the `.pattern` equality, so this file does not have to be trusted to
    know which guarantee is load-bearing."""
    assert _configs.CONFIG_NAME_RX is shared.NAME_RX
    assert _configs.CONFIG_NAME_RX.pattern == shared.NAME_RX.pattern


def test_custom_conf_rx_matches_the_shared_builder():
    """`CUSTOM_CONF_RX` is built by a call to `build_env_style_key_rx(...)`, not re-exported by
    reference, so unlike `CONFIG_NAME_RX` above, object identity is not a promise the code makes
    -- only that the pattern text is the one the shared builder produces (`report-CC-A.md`'s
    "already drifted once" finding was about the *pattern text*, not object identity)."""
    assert _utils.CUSTOM_CONF_RX.pattern == shared.build_env_style_key_rx(with_service_prefix=False).pattern
