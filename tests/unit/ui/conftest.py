"""Fixtures for UIDatabase tests.

Unlike the API mixins, the UI mixins use absolute ``app.models...`` imports (e.g.
``from app.models.models import UiUsers``), so we must import the real ``UIDatabase``
via the ``app`` package with ``src/ui`` on the path. Only the UI imports ``app`` (the
API tests recompose without it), so ``import app`` resolves uniquely to ``src/ui/app``
and there's no collision in a combined run.
"""

import sys
from functools import lru_cache
from pathlib import Path

import pytest
from jinja2.defaults import DEFAULT_NAMESPACE

_UI_ROOT = str(Path(__file__).resolve().parents[3] / "src" / "ui")
if _UI_ROOT not in sys.path:
    sys.path.insert(0, _UI_ROOT)

import plugin_extensions  # type: ignore  # noqa: E402 — on sys.path via the root conftest

from app.models.ui_database import UIDatabase  # noqa: E402
from app.utils import get_activation_map  # noqa: E402

from fixtures.db_factory import resolve_uri  # noqa: E402
from fixtures.engines import reset_schema  # noqa: E402

# `is_plugin_active`'s manifest tier reads plugin.json files through
# `plugin_extensions.iter_plugin_activations()`, which (by design — see plugin_extensions.py)
# scans the hardcoded, non-overridable container path `/usr/share/bunkerweb/core`. That path
# only exists inside a built image (the Dockerfiles `COPY src/common/core core` there); a bare
# checkout has nothing there. Point the scan at the real manifests in this repo for every UI
# test, and clear `get_activation_map`'s cache so each test re-reads them under the patched path.
_REAL_CORE_PLUGINS_PATH = str(Path(__file__).resolve().parents[3] / "src" / "common" / "core")


@pytest.fixture(autouse=True)
def _real_plugin_activation_manifests(monkeypatch):
    monkeypatch.setattr(plugin_extensions, "CORE_PLUGINS_PATH", _REAL_CORE_PLUGINS_PATH)
    get_activation_map.cache_clear()
    yield
    get_activation_map.cache_clear()


@pytest.fixture
def ui_db(db_engine, tmp_path, quiet_logger, _clean_env):
    uri = resolve_uri(db_engine, tmp_path)
    reset_schema(uri)
    database = UIDatabase(quiet_logger, sqlalchemy_string=uri, log=False)
    try:
        yield database
    finally:
        database.close()


# --------------------------------------------------------------------------------------
# Server-side translation in the standalone Jinja harnesses
# --------------------------------------------------------------------------------------
# Templates converted to native i18n (see test_i18n_migration.CONVERTED) call `_()`, which
# Flask-Babel installs as a Jinja global. The harnesses in this directory build a bare
# `Environment` to render one template without booting the app, so they need it too — otherwise
# the render dies with `'_' is undefined`.
#
# Installing it into Jinja's own default namespace (below) covers every one of them, including the
# envs built inline inside a single assertion. The alternative — patching each harness — was tried
# first and does not hold: converting one shared macro broke 27 tests across 4 files, and the next
# conversion would break a different set.
#
# It reads the *real* compiled English catalog rather than faking one, so a harness sees the same
# string production would render, `%(name)s` placeholders and all.
_TRANSLATIONS = Path(__file__).resolve().parents[3] / "src" / "ui" / "translations"


@lru_cache(maxsize=1)
def _english_catalog():
    from babel.messages.pofile import read_po

    with (_TRANSLATIONS / "en" / "LC_MESSAGES" / "messages.po").open("rb") as handle:
        catalog = read_po(handle, locale="en")
    return {message.id: message.string for message in catalog if message.id and not message.pluralizable}


def babel_globals():
    """`{"_": ..., "gettext": ..., "ngettext": ...}` for a harness's `env.globals.update(...)`.

    Mirrors `flask_babel.Domain.gettext`: `%`-formats only when variables are passed, which is
    the rule that decides whether a literal `%` in a message is escaped.
    """

    def gettext(key, **variables):
        text = _english_catalog().get(key, key)
        return text % variables if variables else text

    def ngettext(singular, plural, num, **variables):
        variables.setdefault("num", num)
        text = _english_catalog().get(singular if num == 1 else plural, singular)
        return text % variables

    return {"_": gettext, "gettext": gettext, "ngettext": ngettext}


def english(key, **variables):
    """What a converted template *renders* for `key`: the English catalog string, HTML-escaped,
    or the key itself when the catalog has none — which is also what gettext does at runtime.

    Tests that used to assert `data-i18n="<key>"` in the markup assert this instead: the
    translation now happens before the HTML leaves the server, so the key is no longer there.

    Escaped because that is what reaches the page: Jinja autoescaping turns the apostrophe in
    "the plugin's total time" into `&#39;`, and comparing the raw catalog string against rendered
    HTML fails for every message that contains one.
    """
    from markupsafe import escape

    return str(escape(babel_globals()["_"](key, **variables)))


# Jinja copies this dict into `Environment.globals` at construction, so every environment built
# after this module is imported — and conftest is imported before any test module — carries `_`,
# exactly as the real app does.
DEFAULT_NAMESPACE.update(babel_globals())
