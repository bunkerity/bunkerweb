"""FIX-QA5-I18N-3 item 2: a built-in template's step titles/subtitles must resolve through the
`templates` plugin's i18n catalog, not always show the raw English JSON.

Before this session, `template_edit.js` read `step.title`/`step.subtitle` straight off the API
response, which was always the literal text of `src/common/core/templates/templates/<id>.json` --
so even a locale that already ships a full translation (`de.json` has all 5 built-ins' steps) never
saw it. The fix resolves each step server-side, in `routes/templates.py::_convert_template_details`,
through `app.i18n.plugin_text("templates", f"templates.{id}.steps.{index}.title", <raw text>)` --
the same mechanism a setting's label/help already uses.

Two things need proving, so two tests: the catalog mechanism itself actually resolves a real
non-English translation for a real built-in template (using `de.json`, which already ships full
step content -- no fixture, no fake catalog), and `_convert_template_details` actually calls
`plugin_text` with the right `(plugin_id, key_path, fallback)` shape for every step, not just for
the first one or the title-only half.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src" / "ui"))

from app.i18n import init_i18n, plugin_text  # noqa: E402


# --------------------------------------------------------------------------------------
# The catalog mechanism: a real built-in template, a real locale file, no fixtures
# --------------------------------------------------------------------------------------
@pytest.fixture
def babel_app():
    from flask import Flask

    app = Flask("bw_ui_i18n_test", root_path=str(REPO / "src" / "ui"))
    app.config["SECRET_KEY"] = "test"
    init_i18n(app)
    return app


def test_a_built_in_templates_step_title_resolves_to_the_shipped_german_translation(babel_app):
    from flask_babel import force_locale

    with babel_app.test_request_context("/"), force_locale("de"):
        title = plugin_text("templates", "templates.low.steps.0.title", "Web service - Front service")
        subtitle = plugin_text("templates", "templates.low.steps.0.subtitle", "Configure your web service facing your clients")

    step = json.loads((REPO / "src" / "common" / "core" / "templates" / "locales" / "de.json").read_text())["templates"]["templates"]["low"]["steps"]["0"]
    assert title == step["title"] == "Webdienst - Front-Dienst"
    assert subtitle == step["subtitle"] != "Configure your web service facing your clients"


def test_a_second_locale_also_resolves_a_real_shipped_translation(babel_app):
    """Every locale under `locales/` now ships full step content for the built-ins (the
    translation lanes ran after this item's report was last written) -- French checked as a
    second, independent data point next to German above."""
    from flask_babel import force_locale

    with babel_app.test_request_context("/"), force_locale("fr"):
        title = plugin_text("templates", "templates.low.steps.0.title", "Web service - Front service")

    assert title == "Service web - Service frontal"


def test_an_unknown_step_key_falls_back_to_the_raw_english_without_raising():
    """No locale ships a step index this high -- the fallback must survive a catalog miss
    (unknown key, or no app/request context at all, as here) without raising or returning `None`."""
    title = plugin_text("templates", "templates.low.steps.999.title", "Web service - Front service")

    assert title == "Web service - Front service"


def test_a_template_with_no_owning_plugin_id_is_never_looked_up():
    """A user-created template has `plugin_id is None` -- `plugin_text` must return the raw value
    unchanged rather than attempting (and mis-resolving against) a lookup with no plugin."""
    assert plugin_text(None, "templates..steps.0.title", "My own step") == "My own step"


# --------------------------------------------------------------------------------------
# The wiring: `_convert_template_details` actually calls `plugin_text`, for every step
# --------------------------------------------------------------------------------------
def _import_templates_module() -> ModuleType:
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DATA = Mock()
    dependencies.CORE_PLUGINS_PATH = REPO / "src" / "common" / "core"
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main
    module_name = "app.routes._templates_test_step_titles_i18n"
    spec = importlib.util.spec_from_file_location(module_name, REPO / "src" / "ui" / "app" / "routes" / "templates.py")
    module = importlib.util.module_from_spec(spec)
    stubs = {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


MODULE = _import_templates_module()


def test_convert_template_details_calls_plugin_text_for_every_step_title_and_subtitle(monkeypatch):
    calls = []

    def recording_plugin_text(plugin_id, key_path, fallback):
        calls.append((plugin_id, key_path, fallback))
        return fallback  # no real catalog lookup here -- this test is about the call shape

    monkeypatch.setattr(MODULE, "plugin_text", recording_plugin_text)

    details = {
        "id": "low",
        "plugin_id": "templates",
        "name": "Basic security level",
        "settings": {},
        "steps": [
            {"title": "Web service - Front service", "subtitle": "Configure your web service facing your clients", "settings": [], "configs": []},
            {"title": "Web service - Upstream server", "subtitle": "Configure the upstream server to be protected by BunkerWeb", "settings": [], "configs": []},
        ],
        "configs": [],
    }

    converted = MODULE._convert_template_details(details)

    assert calls == [
        ("templates", "templates.low.steps.0.title", "Web service - Front service"),
        ("templates", "templates.low.steps.0.subtitle", "Configure your web service facing your clients"),
        ("templates", "templates.low.steps.1.title", "Web service - Upstream server"),
        ("templates", "templates.low.steps.1.subtitle", "Configure the upstream server to be protected by BunkerWeb"),
    ]
    # The stub returns the fallback unchanged, so the converted payload is untouched --
    # the byte-identical-when-untranslated half of the same contract every other translated()
    # call site in this wave carries.
    assert converted["steps"][0]["title"] == "Web service - Front service"
    assert converted["steps"][1]["subtitle"] == "Configure the upstream server to be protected by BunkerWeb"


def test_convert_template_details_passes_none_plugin_id_for_a_user_created_template(monkeypatch):
    """A template with no `plugin_id` in its DB row (a plain UI-created one) must still call
    `plugin_text` -- which itself no-ops on a `None` plugin id (pinned above) -- rather than
    skipping the call and losing the byte-identical-fallback guarantee."""
    calls = []
    monkeypatch.setattr(MODULE, "plugin_text", lambda plugin_id, key_path, fallback: calls.append((plugin_id, key_path, fallback)) or fallback)

    details = {"id": "my-template", "plugin_id": None, "steps": [{"title": "My step", "subtitle": "", "settings": [], "configs": []}]}
    MODULE._convert_template_details(details)

    assert calls == [(None, "templates.my-template.steps.0.title", "My step"), (None, "templates.my-template.steps.0.subtitle", "")]
