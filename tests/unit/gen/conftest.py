"""Path setup for config-generation tests.

Adds ``src/common/gen`` so ``Configurator`` imports. ``common_utils`` (its only
non-stdlib dependency) is already on the path via the root conftest. We deliberately
do NOT rely on ``import utils`` here — ``src/common/gen/utils.py`` and
``src/api/app/utils.py`` would both be top-level ``utils`` in a combined run, so the
``has_permissions`` test loads that module by file path instead.
"""

import sys
from pathlib import Path

_GEN = str(Path(__file__).resolve().parents[3] / "src" / "common" / "gen")
if _GEN not in sys.path:
    sys.path.insert(0, _GEN)

# This directory too, so `import _listen_helpers` resolves here whatever else is being collected.
# APPENDED, never inserted. Other suites import bare module names that also exist here --
# `tests/unit/ui` does `from conftest import english` -- and a test directory at the FRONT of
# sys.path is exactly how those resolve to the wrong file. `_listen_helpers` is a unique name, so
# the tail of the path is enough for it and the front is left to whoever is being collected.
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.append(_HERE)


# --- real end-to-end render harness ------------------------------------------------
# Some behaviours (listen ports, default_server ownership, the port union) live in the SEAM
# between Configurator and Templator: a template only ever sees one server block, while the rules
# are about the set of blocks. Rendering the real tree is the only way to assert them.

import logging  # noqa: E402
import tempfile  # noqa: E402

import pytest  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONFS = _REPO_ROOT / "src" / "common" / "confs"
_CORE = _REPO_ROOT / "src" / "common" / "core"
_SETTINGS = _REPO_ROOT / "src" / "common" / "settings.json"


@pytest.fixture(scope="module")
def render_tree():
    """``render_tree(**variables)`` -> the rendered tree as ``{relative path: text}``, memoised.

    ``Templator.__init__`` builds its Jinja bytecode cache as ``Path(sep, "var", "cache", …)`` and
    ``sep`` is that module's ONLY use of ``os.path.sep``, so rebinding it is the whole redirect --
    no write to ``/var/cache``, no root needed. It is restored on teardown.
    """
    import Templator as T  # type: ignore  (src/common/gen is on the path, see above)
    from Configurator import Configurator  # type: ignore

    with tempfile.TemporaryDirectory() as root:
        sandbox = Path(root)
        original_sep = T.sep
        T.sep = str(sandbox)
        logger = logging.getLogger("render-tree")
        plugins = sandbox / "plugins"
        plugins.mkdir()
        pro_plugins = sandbox / "pro-plugins"
        pro_plugins.mkdir()
        cache = {}

        def _render(**variables):
            key = tuple(sorted(variables.items()))
            if key not in cache:
                config = Configurator(str(_SETTINGS), str(_CORE), str(plugins), str(pro_plugins), dict(variables), logger).get_config(None)
                output = sandbox / f"out{len(cache)}"
                output.mkdir()
                T.Templator(str(_CONFS), str(_CORE), str(plugins), str(pro_plugins), str(output), "/etc/nginx", config, config.copy(), config.copy()).render()
                cache[key] = {str(path.relative_to(output)): path.read_text() for path in sorted(output.rglob("*.conf"))}
            return cache[key]

        try:
            yield _render
        finally:
            T.sep = original_sep


# The plain helpers live in _listen_helpers.py, NOT here: `from conftest import ...` binds to
# whichever conftest module got imported first in a combined run (tests/unit/ui/conftest.py wins
# alphabetically), which is a collection error waiting to happen. conftest keeps the fixtures,
# which pytest resolves by name rather than by import.
