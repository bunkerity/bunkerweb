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

import json  # noqa: E402
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


@pytest.fixture
def render_db_tree(db):
    """``render_db_tree(globals_, services)`` -> the tree the SCHEDULER renders, not the entrypoint.

    There are two generation paths and they hand Templator different shapes:

    * ``bw`` renders from the environment -- ``gen/main.py:117`` builds the config with
      ``Configurator.get_config``, which materialises an inherited copy of every multisite setting
      under every service name (ports excepted, ``Configurator.py:363-376``).
    * the scheduler renders from the database -- ``scheduler/main.py:427-441`` calls ``gen/main.py``
      with no ``--variables``, so line 128 takes ``db.get_non_default_settings()`` as ``config`` and
      ``db.get_config(methods=True)`` as ``full_config`` / ``default_config``.

    Every port declared through the UI, the API or autoconf reaches the render this second way, so a
    rule that only holds on the first one holds for almost nobody.

    **The two dicts come from a REAL ``Database``**, not from a hand-written imitation of one. The
    previous version of this fixture built them from the caller's variables and materialised nothing
    at all, so it rendered a shape the scheduler never produces: it was green against a
    ``config_read.py`` that leaked an inherited ``<service>_HTTP_PORT_1`` into the NON-default view
    and therefore made every service look like it had declared the whole global list. Seeding
    ``settings.json`` plus every core ``plugin.json`` and going through ``save_config`` costs about
    a second per test and removes the only thing that made this harness able to agree with a broken
    database layer.

    Consequence worth knowing: this fixture consumes ``db``, so the tests using it are parametrised
    over ``--db-engines`` like the DB suite. On the default (``sqlite``) that is one run; a
    ``--db-engines=sqlite,postgresql,mariadb`` invocation renders the tree once per engine.
    """
    import Templator as T  # type: ignore
    from fixtures.seed import make_core_plugin  # type: ignore

    plugin_manifests = [make_core_plugin("general", settings=json.loads(_SETTINGS.read_text()))]
    for manifest in sorted(_CORE.glob("*/plugin.json")):
        data = json.loads(manifest.read_text())
        data.setdefault("settings", {})
        data.setdefault("jobs", [])
        # `bwcli` is a plugin.json key init_tables does not consume; passing it through would be
        # the only difference between this seed and what the scheduler's own init does.
        data.pop("bwcli", None)
        plugin_manifests.append(data)
    ok, err = db.init_tables(plugin_manifests)
    assert ok, f"init_tables failed: {err}"

    with tempfile.TemporaryDirectory() as root:
        sandbox = Path(root)
        original_sep = T.sep
        T.sep = str(sandbox)
        plugins = sandbox / "plugins"
        plugins.mkdir()
        pro_plugins = sandbox / "pro-plugins"
        pro_plugins.mkdir()
        rendered = []

        def _render(globals_: dict, services: dict):
            declared = {f"{service}_{key}": value for service, settings in services.items() for key, value in settings.items()}
            # `<service>_SERVER_NAME` is what makes save_config create the bw_services row, exactly
            # as the API and the UI send it.
            declared.update({f"{service}_SERVER_NAME": service for service in services})
            saved = db.save_config(
                {"MULTISITE": "yes", "SERVER_NAME": " ".join(services)} | globals_ | declared,
                "scheduler",
                changed=True,
            )
            assert not isinstance(saved, str), f"save_config refused the seed: {saved}"

            config = db.get_non_default_settings()
            full = db.get_config(methods=True)
            default_config = {setting: data["default"] for setting, data in full.items()}
            full_config = {setting: data["value"] for setting, data in full.items()}

            output = sandbox / f"out{len(rendered)}"
            output.mkdir()
            rendered.append(output)
            T.Templator(str(_CONFS), str(_CORE), str(plugins), str(pro_plugins), str(output), "/etc/nginx", config, default_config, full_config).render()
            return {str(path.relative_to(output)): path.read_text() for path in sorted(output.rglob("*")) if path.is_file()}

        try:
            yield _render
        finally:
            T.sep = original_sep


# The plain helpers live in _listen_helpers.py, NOT here: `from conftest import ...` binds to
# whichever conftest module got imported first in a combined run (tests/unit/ui/conftest.py wins
# alphabetically), which is a collection error waiting to happen. conftest keeps the fixtures,
# which pytest resolves by name rather than by import.
